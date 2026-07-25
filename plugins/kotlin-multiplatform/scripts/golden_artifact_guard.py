#!/usr/bin/env python3
"""Validate an exact allowlist of PNG screenshot goldens inside a ZIP archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import struct
import tempfile
import unicodedata
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, NoReturn


SCHEMA = "kmp.golden_artifact_guard.v1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ZIP_EOCD_SIGNATURE = b"PK\x05\x06"
ZIP_CENTRAL_SIGNATURE = b"PK\x01\x02"
ZIP_LOCAL_SIGNATURE = b"PK\x03\x04"
ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
ALLOWED_ZIP_EXTRA_FIELDS = {0x5455, 0x7875}
PRIVACY_METADATA_CHUNKS = {b"eXIf", b"iTXt", b"tEXt", b"zTXt"}
KNOWN_CRITICAL_CHUNKS = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}
ALLOWED_ANCILLARY_CHUNKS = {
    b"cHRM",
    b"gAMA",
    b"pHYs",
    b"sRGB",
}
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class GuardProblem(Exception):
    def __init__(self, code: str, message: str, path: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


class GuardArgumentError(Exception):
    pass


def fail(code: str, message: str, path: str | None = None) -> NoReturn:
    raise GuardProblem(code, message, path)


def open_pinned_regular(path: Path, label: str) -> tuple[BinaryIO, os.stat_result]:
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise ValueError(f"{label}_unreadable") from exc
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        raise ValueError(f"{label}_must_be_regular_file")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"{label}_unreadable") from exc

    try:
        after = os.fstat(descriptor)
        if not stat.S_ISREG(after.st_mode):
            raise ValueError(f"{label}_must_be_regular_file")
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError(f"{label}_changed_during_open")
        return os.fdopen(descriptor, "rb"), after
    except Exception:
        os.close(descriptor)
        raise


def snapshot_archive(path: Path, max_archive_bytes: int) -> tuple[BinaryIO, str, int]:
    source, metadata = open_pinned_regular(path, "archive")
    # ZipExtFile requires seekable() on Python 3.10; use a real pinned snapshot.
    snapshot = tempfile.TemporaryFile(mode="w+b")
    digest = hashlib.sha256()
    size = 0
    try:
        with source:
            if metadata.st_size > max_archive_bytes:
                fail("archive_size_limit", "archive exceeds the configured byte limit")
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_archive_bytes:
                    fail(
                        "archive_size_limit",
                        "archive exceeds the configured byte limit",
                    )
                digest.update(chunk)
                snapshot.write(chunk)
        snapshot.seek(0)
        return snapshot, digest.hexdigest(), size
    except Exception:
        snapshot.close()
        raise


def read_exact_at(snapshot: BinaryIO, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0:
        fail("invalid_zip_structure", "ZIP contains an invalid byte range")
    snapshot.seek(offset)
    payload = snapshot.read(size)
    if len(payload) != size:
        fail("invalid_zip_structure", "ZIP record exceeds the archive bounds")
    return payload


def validate_zip_extra_fields(extra: bytes) -> None:
    offset = 0
    while offset < len(extra):
        if len(extra) - offset < 4:
            fail("malformed_zip_extra_field", "ZIP extra field header is truncated")
        field_id, field_size = struct.unpack_from("<HH", extra, offset)
        offset += 4
        end = offset + field_size
        if end > len(extra):
            fail("malformed_zip_extra_field", "ZIP extra field payload is truncated")
        data = extra[offset:end]

        if field_id not in ALLOWED_ZIP_EXTRA_FIELDS:
            fail(
                "unsupported_zip_extra_field",
                "ZIP extra field is outside the portable metadata allowlist",
            )
        if field_id == 0x5455:
            valid = (
                1 <= len(data) <= 13
                and data[0] & ~0x07 == 0
                and (len(data) - 1) % 4 == 0
            )
        else:
            valid = len(data) >= 4 and data[0] == 1
            if valid:
                uid_size = data[1]
                gid_size_offset = 2 + uid_size
                valid = (
                    1 <= uid_size <= 8
                    and gid_size_offset < len(data)
                    and 1 <= data[gid_size_offset] <= 8
                    and gid_size_offset + 1 + data[gid_size_offset] == len(data)
                )
        if not valid:
            fail(
                "malformed_zip_extra_field",
                "ZIP portable metadata extra field has an invalid payload",
            )
        offset = end


def find_eocd(snapshot: BinaryIO, archive_size: int) -> tuple[int, tuple[Any, ...]]:
    tail_size = min(archive_size, 22 + 65_535)
    tail_offset = archive_size - tail_size
    tail = read_exact_at(snapshot, tail_offset, tail_size)
    for index in range(len(tail) - 22, -1, -1):
        if tail[index : index + 4] != ZIP_EOCD_SIGNATURE:
            continue
        fields = struct.unpack_from("<4s4H2IH", tail, index)
        comment_size = fields[7]
        absolute_offset = tail_offset + index
        if absolute_offset + 22 + comment_size == archive_size:
            return absolute_offset, fields
    raise ValueError("archive_not_valid_zip")


def preflight_zip(
    snapshot: BinaryIO,
    archive_size: int,
    max_files: int,
) -> tuple[int, int]:
    eocd_offset, fields = find_eocd(snapshot, archive_size)
    (
        _,
        disk_number,
        central_disk,
        entries_on_disk,
        declared_entries,
        central_size,
        central_offset,
        _,
    ) = fields
    if disk_number != 0 or central_disk != 0 or entries_on_disk != declared_entries:
        fail("multi_disk_archive", "multi-disk ZIP archives are not accepted")
    if (
        declared_entries == 0xFFFF
        or entries_on_disk == 0xFFFF
        or central_size == 0xFFFFFFFF
        or central_offset == 0xFFFFFFFF
    ):
        fail("zip64_archive", "ZIP64 archives are outside the bounded contract")
    if declared_entries > max_files:
        fail("archive_file_limit", "archive exceeds the configured file limit")
    if central_offset + central_size != eocd_offset:
        fail(
            "ambiguous_zip_layout",
            "ZIP central directory is prefixed, shifted, or otherwise ambiguous",
        )

    position = central_offset
    central_end = central_offset + central_size
    counted_entries = 0
    while position < central_end:
        fixed = read_exact_at(snapshot, position, 46)
        values = struct.unpack("<4s6H3I5H2I", fixed)
        if values[0] != ZIP_CENTRAL_SIGNATURE:
            fail(
                "invalid_central_directory",
                "ZIP central directory contains an unexpected record",
            )
        compressed_size = values[8]
        expanded_size = values[9]
        name_size = values[10]
        extra_size = values[11]
        comment_size = values[12]
        disk_start = values[13]
        local_offset = values[16]
        if (
            compressed_size == 0xFFFFFFFF
            or expanded_size == 0xFFFFFFFF
            or disk_start == 0xFFFF
            or local_offset == 0xFFFFFFFF
        ):
            fail("zip64_archive", "ZIP64 members are outside the bounded contract")
        if disk_start != 0:
            fail("multi_disk_archive", "multi-disk ZIP members are not accepted")

        record_size = 46 + name_size + extra_size + comment_size
        if position + record_size > central_end:
            fail(
                "invalid_central_directory",
                "ZIP central directory record exceeds its declared bounds",
            )
        extra = read_exact_at(snapshot, position + 46 + name_size, extra_size)
        validate_zip_extra_fields(extra)
        counted_entries += 1
        if counted_entries > max_files:
            fail("archive_file_limit", "archive exceeds the configured file limit")
        position += record_size

    if position != central_end or counted_entries != declared_entries:
        fail(
            "central_directory_count_mismatch",
            "ZIP central directory count does not match its end record",
        )
    snapshot.seek(0)
    return counted_entries, central_offset


def inspect_local_record(snapshot: BinaryIO, info: zipfile.ZipInfo) -> tuple[int, int]:
    saved_offset = snapshot.tell()
    try:
        fixed = read_exact_at(snapshot, info.header_offset, 30)
        values = struct.unpack("<4s5H3I2H", fixed)
        if values[0] != ZIP_LOCAL_SIGNATURE:
            fail("invalid_local_header", "ZIP member local header is invalid")
        local_flags = values[2]
        local_compression = values[3]
        local_crc = values[6]
        local_compressed_size = values[7]
        local_expanded_size = values[8]
        name_size = values[9]
        extra_size = values[10]
        if local_flags != info.flag_bits or local_compression != info.compress_type:
            fail(
                "local_central_header_mismatch",
                "ZIP local flags or compression method differ from the central record",
            )
        if local_compressed_size == 0xFFFFFFFF or local_expanded_size == 0xFFFFFFFF:
            fail(
                "zip64_archive", "ZIP64 local records are outside the bounded contract"
            )
        if local_flags & 0x08:
            if local_crc not in {0, info.CRC}:
                fail(
                    "local_central_header_mismatch",
                    "ZIP deferred local CRC conflicts with the central record",
                )
            if local_compressed_size not in {0, info.compress_size}:
                fail(
                    "local_central_header_mismatch",
                    "ZIP deferred compressed size conflicts with the central record",
                )
            if local_expanded_size not in {0, info.file_size}:
                fail(
                    "local_central_header_mismatch",
                    "ZIP deferred expanded size conflicts with the central record",
                )
        elif (
            local_crc != info.CRC
            or local_compressed_size != info.compress_size
            or local_expanded_size != info.file_size
        ):
            fail(
                "local_central_header_mismatch",
                "ZIP local CRC or sizes differ from the central record",
            )

        local_name = read_exact_at(snapshot, info.header_offset + 30, name_size)
        encoding = "utf-8" if info.flag_bits & 0x800 else "cp437"
        try:
            expected_name = info.orig_filename.encode(encoding)
        except UnicodeError as exc:
            raise GuardProblem(
                "ambiguous_member_name",
                "ZIP member name cannot be represented by its declared encoding",
            ) from exc
        if local_name != expected_name:
            fail(
                "local_central_header_mismatch",
                "ZIP local member name differs from the central record",
            )

        extra = read_exact_at(snapshot, info.header_offset + 30 + name_size, extra_size)
        validate_zip_extra_fields(extra)
        data_offset = info.header_offset + 30 + name_size + extra_size
        record_end = data_offset + info.compress_size
        if info.flag_bits & 0x08:
            descriptor = read_exact_at(snapshot, record_end, 16)
            signature, crc, compressed_size, expanded_size = struct.unpack(
                "<4sIII", descriptor
            )
            if signature != b"PK\x07\x08":
                fail(
                    "missing_data_descriptor",
                    "ZIP deferred-size member lacks a signed data descriptor",
                )
            if (
                crc != info.CRC
                or compressed_size != info.compress_size
                or expanded_size != info.file_size
            ):
                fail(
                    "data_descriptor_mismatch",
                    "ZIP data descriptor differs from the central record",
                )
            record_end += 16
        return data_offset, record_end
    finally:
        snapshot.seek(saved_offset)


def normalized_member_path(value: str, *, label: str) -> str:
    if not value:
        fail("empty_path", f"{label} path must not be empty")
    if "\x00" in value:
        fail("nul_path", f"{label} path contains a NUL byte")
    if CONTROL_CHARACTERS.search(value):
        fail("control_character_path", f"{label} path contains a control character")
    if "\\" in value:
        fail("backslash_path", f"{label} path must use POSIX separators", value)
    if value.startswith("/") or value.startswith("//"):
        fail("absolute_path", f"{label} path must be relative", value)
    if ":" in value:
        fail("alternate_root_path", f"{label} path contains an ambiguous colon", value)
    if value.endswith("/") or "//" in value:
        fail(
            "directory_or_ambiguous_path",
            f"{label} path is not a regular file path",
            value,
        )
    if any(part in {"", ".", ".."} for part in value.split("/")):
        fail("escaping_path", f"{label} path escapes or aliases its root", value)
    if unicodedata.normalize("NFC", value) != value:
        fail("non_normalized_path", f"{label} path must use NFC normalization", value)

    candidate = PurePosixPath(value)
    if candidate.is_absolute():
        fail("escaping_path", f"{label} path escapes or aliases its root", value)
    if candidate.suffix != ".png":
        fail("non_png_path", f"{label} path must end in lowercase .png", value)
    return candidate.as_posix()


def collision_key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def load_allowlist(path: Path, max_files: int) -> tuple[list[str], str]:
    source, metadata = open_pinned_regular(path, "allowlist")
    try:
        with source:
            if metadata.st_size > 1024 * 1024:
                raise ValueError("allowlist_too_large")
            payload = source.read(1024 * 1024 + 1)
        if len(payload) > 1024 * 1024:
            raise ValueError("allowlist_too_large")
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("allowlist_must_be_utf8") from exc

    paths: list[str] = []
    exact: set[str] = set()
    folded: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if len(paths) >= max_files:
            fail("allowlist_file_limit", "allowlist exceeds the configured file limit")
        normalized = normalized_member_path(line, label="allowlist")
        if normalized in exact:
            fail(
                "duplicate_allowlist_path",
                "allowlist contains a duplicate path",
                normalized,
            )
        folded_key = collision_key(normalized)
        if folded_key in folded:
            fail(
                "colliding_allowlist_path",
                "allowlist contains case-folding or normalization collisions",
                normalized,
            )
        exact.add(normalized)
        folded[folded_key] = normalized
        paths.append(normalized)

    if not paths:
        fail("empty_allowlist", "allowlist must contain at least one PNG path")
    canonical = "".join(f"{item}\n" for item in sorted(paths)).encode("utf-8")
    return paths, hashlib.sha256(canonical).hexdigest()


def classify_member(info: zipfile.ZipInfo, raw_name: str) -> None:
    if info.is_dir() or raw_name.endswith("/"):
        fail("directory_member", "archive directories are not accepted", raw_name)
    if info.flag_bits & 0x1:
        fail("encrypted_member", "encrypted archive members are not accepted", raw_name)
    if info.flag_bits & ~0x080E:
        fail(
            "unsupported_zip_flags",
            "archive member uses unsupported general-purpose ZIP flags",
            raw_name,
        )
    if info.compress_type not in ALLOWED_COMPRESSION:
        fail(
            "unsupported_compression",
            "only stored and deflated archive members are accepted",
            raw_name,
        )
    if info.compress_type == zipfile.ZIP_STORED and info.flag_bits & 0x6:
        fail(
            "unsupported_zip_flags",
            "stored archive member uses deflate-only option flags",
            raw_name,
        )

    if info.create_system == 3:
        mode = (info.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)
        if file_type not in {0, stat.S_IFREG}:
            code = "symlink_member" if file_type == stat.S_IFLNK else "special_member"
            fail(code, "archive member is not a regular file", raw_name)
    elif info.create_system == 0:
        dos_attributes = info.external_attr & 0xFF
        if dos_attributes & 0x5E:
            fail(
                "non_regular_dos_member",
                "archive member has non-regular DOS attributes",
                raw_name,
            )
    else:
        fail(
            "unsupported_creator_system",
            "archive member creator system is outside the portable contract",
            raw_name,
        )


def read_member_payload(
    snapshot: BinaryIO,
    info: zipfile.ZipInfo,
    data_offset: int,
) -> bytes:
    compressed = read_exact_at(snapshot, data_offset, info.compress_size)
    if info.compress_type == zipfile.ZIP_STORED:
        if info.compress_size != info.file_size:
            fail(
                "stored_size_mismatch",
                "stored ZIP member compressed and expanded sizes differ",
                info.filename,
            )
        payload = compressed
    else:
        output = bytearray()
        decompressor = zlib.decompressobj(-15)
        pending = compressed
        try:
            while pending:
                remaining = info.file_size + 1 - len(output)
                if remaining <= 0:
                    fail(
                        "member_expands_past_declared_size",
                        "ZIP member expands beyond its declared size",
                        info.filename,
                    )
                chunk = decompressor.decompress(
                    pending,
                    min(64 * 1024, remaining),
                )
                output.extend(chunk)
                if len(output) > info.file_size:
                    fail(
                        "member_expands_past_declared_size",
                        "ZIP member expands beyond its declared size",
                        info.filename,
                    )
                pending = decompressor.unconsumed_tail
                if decompressor.unused_data:
                    fail(
                        "trailing_deflate_data",
                        "ZIP member contains data after its DEFLATE stream",
                        info.filename,
                    )
            while True:
                remaining = info.file_size + 1 - len(output)
                if remaining <= 0:
                    break
                chunk = decompressor.decompress(
                    b"",
                    min(64 * 1024, remaining),
                )
                if not chunk:
                    break
                output.extend(chunk)
        except zlib.error as exc:
            raise GuardProblem(
                "invalid_deflate_stream",
                "ZIP member is not a valid raw DEFLATE stream",
                info.filename,
            ) from exc

        if len(output) > info.file_size:
            fail(
                "member_expands_past_declared_size",
                "ZIP member expands beyond its declared size",
                info.filename,
            )
        if not decompressor.eof:
            fail(
                "incomplete_deflate_stream",
                "ZIP member DEFLATE stream is incomplete",
                info.filename,
            )
        if decompressor.unused_data:
            fail(
                "trailing_deflate_data",
                "ZIP member contains trailing DEFLATE data",
                info.filename,
            )
        payload = bytes(output)

    if len(payload) != info.file_size:
        fail(
            "declared_size_mismatch",
            "archive member size does not match metadata",
            info.filename,
        )
    if zlib.crc32(payload) & 0xFFFFFFFF != info.CRC:
        fail(
            "member_crc_mismatch",
            "archive member CRC does not match the central record",
            info.filename,
        )
    return payload


def parse_ihdr(
    data: bytes, path: str, max_pixels: int
) -> tuple[int, int, int, int, int]:
    if len(data) != 13:
        fail("invalid_ihdr", "IHDR must contain exactly 13 bytes", path)
    width, height, bit_depth, color_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", data)
    )
    if width == 0 or height == 0:
        fail("invalid_dimensions", "PNG dimensions must be nonzero", path)
    if width * height > max_pixels:
        fail("pixel_limit", "PNG dimensions exceed the configured pixel limit", path)

    if color_type not in {2, 6} or bit_depth != 8:
        fail(
            "unsupported_png_format",
            "goldens must use 8-bit truecolor or truecolor-with-alpha PNG",
            path,
        )
    if compression != 0 or filtering != 0 or interlace not in {0, 1}:
        fail("invalid_ihdr_method", "PNG IHDR uses an unsupported method value", path)
    return width, height, bit_depth, color_type, interlace


def validate_ancillary_chunk(
    chunk_type: bytes,
    data: bytes,
    path: str,
    *,
    seen_ancillary: set[bytes],
    seen_plte: bool,
    seen_idat: bool,
) -> None:
    if chunk_type in seen_ancillary:
        fail(
            "duplicate_ancillary_chunk",
            "PNG contains a duplicate portable ancillary chunk",
            path,
        )
    if seen_idat:
        fail(
            "ancillary_chunk_after_idat",
            "portable ancillary chunks must precede IDAT",
            path,
        )
    if chunk_type in {b"cHRM", b"gAMA", b"sRGB"} and seen_plte:
        fail(
            "invalid_ancillary_order",
            "color-space ancillary chunks must precede PLTE",
            path,
        )

    valid = False
    if chunk_type == b"cHRM":
        valid = len(data) == 32
    elif chunk_type == b"gAMA":
        valid = len(data) == 4 and struct.unpack(">I", data)[0] != 0
    elif chunk_type == b"pHYs":
        valid = len(data) == 9 and data[8] in {0, 1}
    elif chunk_type == b"sRGB":
        valid = len(data) == 1 and data[0] <= 3
    if not valid:
        fail(
            "invalid_ancillary_chunk",
            "PNG portable ancillary chunk has an invalid payload",
            path,
        )
    seen_ancillary.add(chunk_type)


def pass_dimensions(width: int, height: int, interlace: int) -> list[tuple[int, int]]:
    if interlace == 0:
        return [(width, height)]

    passes = (
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    )
    dimensions: list[tuple[int, int]] = []
    for x_start, y_start, x_step, y_step in passes:
        pass_width = 0 if width <= x_start else (width - x_start + x_step - 1) // x_step
        pass_height = (
            0 if height <= y_start else (height - y_start + y_step - 1) // y_step
        )
        if pass_width and pass_height:
            dimensions.append((pass_width, pass_height))
    return dimensions


def scanline_groups(
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    interlace: int,
) -> list[tuple[int, int]]:
    samples_per_pixel = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    bits_per_pixel = samples_per_pixel * bit_depth
    groups: list[tuple[int, int]] = []
    for pass_width, pass_height in pass_dimensions(width, height, interlace):
        row_bytes = (pass_width * bits_per_pixel + 7) // 8
        groups.append((row_bytes, pass_height))
    return groups


def validate_idat_stream(
    compressed: bytes,
    path: str,
    *,
    width: int,
    height: int,
    bit_depth: int,
    color_type: int,
    interlace: int,
    max_decoded_bytes: int,
    remaining_total_decoded_bytes: int,
) -> int:
    groups = scanline_groups(width, height, bit_depth, color_type, interlace)
    expected_rows = sum(row_count for _, row_count in groups)
    expected_size = sum((row_bytes + 1) * row_count for row_bytes, row_count in groups)
    if expected_size > max_decoded_bytes:
        fail(
            "decoded_png_size_limit",
            "PNG scanlines exceed the configured decoded byte limit",
            path,
        )
    if expected_size > remaining_total_decoded_bytes:
        fail(
            "total_decoded_png_size_limit",
            "PNG scanlines exceed the remaining aggregate decoded byte limit",
            path,
        )

    decoded_size = 0
    row_index = 0
    row_remaining = 0
    group_index = 0
    group_rows_remaining = groups[0][1]

    def consume(output: bytes) -> None:
        nonlocal decoded_size, group_index, group_rows_remaining, row_index
        nonlocal row_remaining
        decoded_size += len(output)
        if decoded_size > expected_size:
            fail(
                "invalid_idat_size",
                "PNG IDAT expands beyond its expected scanlines",
                path,
            )

        offset = 0
        while offset < len(output):
            if row_remaining == 0:
                while group_rows_remaining == 0 and group_index + 1 < len(groups):
                    group_index += 1
                    group_rows_remaining = groups[group_index][1]
                if row_index >= expected_rows:
                    fail(
                        "invalid_idat_size",
                        "PNG IDAT contains undeclared scanline bytes",
                        path,
                    )
                filter_type = output[offset]
                if filter_type > 4:
                    fail(
                        "invalid_png_filter",
                        "PNG scanline uses an invalid filter",
                        path,
                    )
                row_remaining = groups[group_index][0]
                group_rows_remaining -= 1
                row_index += 1
                offset += 1
                continue
            consumed = min(row_remaining, len(output) - offset)
            row_remaining -= consumed
            offset += consumed

    decompressor = zlib.decompressobj()
    pending = compressed
    try:
        while pending:
            output = decompressor.decompress(pending, 64 * 1024)
            consume(output)
            pending = decompressor.unconsumed_tail
            if decompressor.unused_data:
                fail(
                    "trailing_idat_stream",
                    "PNG IDAT contains data after the zlib stream",
                    path,
                )
        while True:
            output = decompressor.decompress(b"", 64 * 1024)
            if not output:
                break
            consume(output)
    except zlib.error as exc:
        raise GuardProblem(
            "invalid_idat_stream",
            "PNG IDAT is not a valid bounded zlib stream",
            path,
        ) from exc

    if not decompressor.eof:
        fail("incomplete_idat_stream", "PNG IDAT zlib stream is incomplete", path)
    if decompressor.unused_data:
        fail("trailing_idat_stream", "PNG IDAT contains trailing compressed data", path)
    if (
        decoded_size != expected_size
        or row_index != expected_rows
        or row_remaining != 0
    ):
        fail(
            "invalid_idat_size", "PNG IDAT does not match its declared scanlines", path
        )
    return expected_size


def validate_png(
    payload: bytes,
    path: str,
    max_pixels: int,
    max_decoded_bytes: int,
    remaining_total_pixels: int,
    remaining_total_decoded_bytes: int,
) -> tuple[int, int, int]:
    if not payload.startswith(PNG_SIGNATURE):
        fail(
            "invalid_png_signature", "member does not begin with a PNG signature", path
        )

    offset = len(PNG_SIGNATURE)
    chunk_index = 0
    width = 0
    height = 0
    bit_depth: int | None = None
    color_type: int | None = None
    interlace: int | None = None
    seen_ihdr = False
    seen_plte = False
    seen_idat = False
    idat_ended = False
    seen_iend = False
    seen_ancillary: set[bytes] = set()
    compressed_idat = bytearray()

    while offset < len(payload):
        if len(payload) - offset < 12:
            fail("truncated_png_chunk", "PNG contains a truncated chunk", path)
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        if any(not (65 <= byte <= 90 or 97 <= byte <= 122) for byte in chunk_type):
            fail(
                "invalid_chunk_type", "PNG chunk type must contain ASCII letters", path
            )
        if 97 <= chunk_type[2] <= 122:
            fail(
                "invalid_chunk_type", "PNG chunk type has an invalid reserved bit", path
            )
        end = offset + 12 + length
        if end > len(payload):
            fail(
                "truncated_png_chunk", "PNG chunk length exceeds available bytes", path
            )

        chunk_data = payload[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + length : end])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            fail("invalid_png_crc", "PNG chunk CRC does not match", path)

        if chunk_index == 0 and chunk_type != b"IHDR":
            fail("ihdr_not_first", "IHDR must be the first PNG chunk", path)
        if chunk_type in PRIVACY_METADATA_CHUNKS:
            fail(
                "privacy_metadata_chunk",
                "PNG contains textual or EXIF metadata that is outside the golden contract",
                path,
            )
        if 65 <= chunk_type[0] <= 90 and chunk_type not in KNOWN_CRITICAL_CHUNKS:
            fail(
                "unknown_critical_chunk", "PNG contains an unknown critical chunk", path
            )
        if 97 <= chunk_type[0] <= 122 and chunk_type not in ALLOWED_ANCILLARY_CHUNKS:
            fail(
                "unknown_ancillary_chunk",
                "PNG contains an ancillary chunk outside the portable allowlist",
                path,
            )
        if chunk_type in ALLOWED_ANCILLARY_CHUNKS:
            validate_ancillary_chunk(
                chunk_type,
                chunk_data,
                path,
                seen_ancillary=seen_ancillary,
                seen_plte=seen_plte,
                seen_idat=seen_idat,
            )

        if chunk_type == b"IHDR":
            if seen_ihdr:
                fail("duplicate_ihdr", "PNG contains more than one IHDR chunk", path)
            width, height, bit_depth, color_type, interlace = parse_ihdr(
                chunk_data, path, max_pixels
            )
            seen_ihdr = True
        elif not seen_ihdr:
            fail("chunk_before_ihdr", "PNG contains data before IHDR", path)
        elif chunk_type == b"PLTE":
            if seen_plte or seen_idat or length == 0 or length % 3 != 0 or length > 768:
                fail("invalid_plte", "PNG contains an invalid PLTE chunk", path)
            if color_type in {0, 4}:
                fail("plte_forbidden", "PNG color type must not contain PLTE", path)
            if color_type == 3 and bit_depth is not None and length // 3 > 2**bit_depth:
                fail("invalid_plte", "indexed-color PLTE has too many entries", path)
            seen_plte = True
        elif chunk_type == b"IDAT":
            if seen_iend or idat_ended:
                fail("noncontiguous_idat", "PNG IDAT chunks must be contiguous", path)
            if color_type == 3 and not seen_plte:
                fail(
                    "missing_plte", "indexed-color PNG requires PLTE before IDAT", path
                )
            seen_idat = True
            compressed_idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            if length != 0 or seen_iend or not seen_idat:
                fail("invalid_iend", "PNG contains an invalid IEND chunk", path)
            seen_iend = True
            if end != len(payload):
                fail("trailing_png_data", "PNG contains bytes after IEND", path)
        elif seen_idat:
            idat_ended = True

        offset = end
        chunk_index += 1
        if seen_iend:
            break

    if not seen_ihdr or not seen_idat or not seen_iend:
        fail("incomplete_png", "PNG must contain IHDR, IDAT, and IEND", path)
    assert bit_depth is not None
    assert color_type is not None
    assert interlace is not None
    if width * height > remaining_total_pixels:
        fail(
            "total_pixel_limit",
            "PNG dimensions exceed the remaining aggregate pixel limit",
            path,
        )
    decoded_bytes = validate_idat_stream(
        bytes(compressed_idat),
        path,
        width=width,
        height=height,
        bit_depth=bit_depth,
        color_type=color_type,
        interlace=interlace,
        max_decoded_bytes=max_decoded_bytes,
        remaining_total_decoded_bytes=remaining_total_decoded_bytes,
    )
    return width, height, decoded_bytes


def inspect_archive(
    archive_path: Path,
    allowlist: list[str],
    allowlist_sha256: str,
    *,
    expected_archive_sha256: str | None,
    max_archive_bytes: int,
    max_entry_bytes: int,
    max_total_bytes: int,
    max_compression_ratio: float,
    max_pixels: int,
    max_decoded_bytes: int,
    max_total_pixels: int,
    max_total_decoded_bytes: int,
    max_files: int,
) -> dict[str, Any]:
    snapshot, archive_sha256, archive_size = snapshot_archive(
        archive_path, max_archive_bytes
    )
    if expected_archive_sha256 and archive_sha256 != expected_archive_sha256:
        snapshot.close()
        fail(
            "archive_digest_mismatch",
            "archive SHA-256 does not match the expected digest",
        )

    try:
        declared_entries, central_offset = preflight_zip(
            snapshot, archive_size, max_files
        )
    except Exception:
        snapshot.close()
        raise

    expected = set(allowlist)
    seen_exact: set[str] = set()
    seen_folded: dict[str, str] = {}
    members: list[dict[str, Any]] = []
    declared_total = 0
    compressed_total = 0
    decoded_total = 0
    pixel_total = 0
    local_data_offsets: dict[int, int] = {}
    local_ranges: list[tuple[int, int]] = []

    try:
        archive = zipfile.ZipFile(snapshot, "r")
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        snapshot.close()
        raise ValueError("archive_not_valid_zip") from exc

    with snapshot, archive:
        infos = archive.infolist()
        if len(infos) != declared_entries:
            fail(
                "central_directory_count_mismatch",
                "ZIP parser count does not match the bounded preflight",
            )
        if len(infos) != len(expected):
            fail(
                "member_count_mismatch",
                "archive member count does not equal the exact allowlist count",
            )

        for info in infos:
            data_offset, record_end = inspect_local_record(snapshot, info)
            if info.header_offset < 0 or record_end > central_offset:
                fail(
                    "overlapping_zip_records",
                    "ZIP local record overlaps the central directory",
                )
            local_data_offsets[id(info)] = data_offset
            local_ranges.append((info.header_offset, record_end))
            raw_name = getattr(info, "orig_filename", info.filename)
            if raw_name != info.filename:
                fail(
                    "ambiguous_member_name",
                    "archive member name was normalized by ZIP parsing",
                )
            member_path = normalized_member_path(raw_name, label="archive member")
            classify_member(info, member_path)

            if member_path in seen_exact:
                fail(
                    "duplicate_member",
                    "archive contains a duplicate member",
                    member_path,
                )
            folded_key = collision_key(member_path)
            if folded_key in seen_folded:
                fail(
                    "colliding_member",
                    "archive contains case-folding or normalization collisions",
                    member_path,
                )
            seen_exact.add(member_path)
            seen_folded[folded_key] = member_path

            if info.file_size > max_entry_bytes:
                fail(
                    "entry_size_limit",
                    "archive member exceeds the configured byte limit",
                    member_path,
                )
            declared_total += info.file_size
            compressed_total += info.compress_size
            if declared_total > max_total_bytes:
                fail(
                    "total_size_limit",
                    "archive exceeds the configured expanded byte limit",
                )
            if info.file_size > 0:
                ratio = info.file_size / max(info.compress_size, 1)
                if ratio > max_compression_ratio:
                    fail(
                        "compression_ratio_limit",
                        "archive member exceeds the configured expansion ratio",
                        member_path,
                    )

        previous_end = 0
        for record_start, record_end in sorted(local_ranges):
            if record_start != previous_end:
                fail(
                    "ambiguous_zip_layout",
                    "ZIP local member records overlap or contain undeclared gaps",
                )
            previous_end = record_end
        if previous_end != central_offset:
            fail(
                "ambiguous_zip_layout",
                "ZIP contains undeclared bytes before the central directory",
            )

        missing = sorted(expected - seen_exact)
        unexpected = sorted(seen_exact - expected)
        if missing or unexpected:
            problem_path = unexpected[0] if unexpected else missing[0]
            fail(
                "allowlist_mismatch",
                "archive member set does not equal the exact allowlist",
                problem_path,
            )

        actual_total = 0
        for info in sorted(infos, key=lambda item: item.filename):
            member_path = info.filename
            payload = read_member_payload(
                snapshot,
                info,
                local_data_offsets[id(info)],
            )
            actual_total += len(payload)
            if actual_total > max_total_bytes:
                fail(
                    "total_size_limit",
                    "archive exceeds the configured expanded byte limit",
                )

            width, height, decoded_bytes = validate_png(
                payload,
                member_path,
                max_pixels,
                max_decoded_bytes,
                max_total_pixels - pixel_total,
                max_total_decoded_bytes - decoded_total,
            )
            pixel_total += width * height
            decoded_total += decoded_bytes
            members.append(
                {
                    "path": member_path,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                    "compressed_bytes": info.compress_size,
                    "width": width,
                    "height": height,
                    "decoded_bytes": decoded_bytes,
                }
            )

    return {
        "schema": SCHEMA,
        "status": "accepted",
        "archive": {
            "sha256": archive_sha256,
            "size_bytes": archive_size,
            "member_count": len(members),
            "compressed_member_bytes": compressed_total,
            "expanded_member_bytes": sum(item["size_bytes"] for item in members),
            "decoded_png_bytes": decoded_total,
            "pixels": pixel_total,
        },
        "allowlist": {
            "sha256": allowlist_sha256,
            "member_count": len(allowlist),
        },
        "limits": {
            "max_archive_bytes": max_archive_bytes,
            "max_entry_bytes": max_entry_bytes,
            "max_total_bytes": max_total_bytes,
            "max_compression_ratio": max_compression_ratio,
            "max_pixels": max_pixels,
            "max_decoded_bytes": max_decoded_bytes,
            "max_total_pixels": max_total_pixels,
            "max_total_decoded_bytes": max_total_decoded_bytes,
            "max_files": max_files,
        },
        "members": members,
        "errors": [],
    }


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("value must be finite and positive")
    return parsed


class ReceiptArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise GuardArgumentError(message)


def parse_args() -> argparse.Namespace:
    parser = ReceiptArgumentParser(
        description=(
            "Validate a ZIP archive against an exact newline-delimited PNG allowlist "
            "without extracting it."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--allowlist", required=True, type=Path)
    parser.add_argument("--expected-archive-sha256")
    parser.add_argument("--max-files", type=positive_int, default=128)
    parser.add_argument(
        "--max-archive-bytes", type=positive_int, default=64 * 1024 * 1024
    )
    parser.add_argument(
        "--max-entry-bytes", type=positive_int, default=16 * 1024 * 1024
    )
    parser.add_argument(
        "--max-total-bytes", type=positive_int, default=64 * 1024 * 1024
    )
    parser.add_argument("--max-compression-ratio", type=positive_float, default=200.0)
    parser.add_argument("--max-pixels", type=positive_int, default=100_000_000)
    parser.add_argument(
        "--max-decoded-bytes", type=positive_int, default=128 * 1024 * 1024
    )
    parser.add_argument(
        "--max-total-decoded-bytes",
        type=positive_int,
        default=256 * 1024 * 1024,
    )
    parser.add_argument("--max-total-pixels", type=positive_int, default=100_000_000)
    return parser.parse_args()


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    try:
        args = parse_args()
    except GuardArgumentError:
        emit(
            {
                "schema": SCHEMA,
                "status": "input-error",
                "errors": [
                    {
                        "code": "invalid_arguments",
                        "message": "command arguments could not be validated",
                    }
                ],
            }
        )
        return 1

    expected_digest = args.expected_archive_sha256
    if expected_digest is not None:
        expected_digest = expected_digest.lower()
        if not SHA256_PATTERN.fullmatch(expected_digest):
            emit(
                {
                    "schema": SCHEMA,
                    "status": "input-error",
                    "errors": [
                        {
                            "code": "invalid_expected_archive_sha256",
                            "message": "expected archive SHA-256 must contain 64 hexadecimal characters",
                        }
                    ],
                }
            )
            return 1

    try:
        allowlist, allowlist_sha256 = load_allowlist(args.allowlist, args.max_files)
        payload = inspect_archive(
            args.archive,
            allowlist,
            allowlist_sha256,
            expected_archive_sha256=expected_digest,
            max_archive_bytes=args.max_archive_bytes,
            max_entry_bytes=args.max_entry_bytes,
            max_total_bytes=args.max_total_bytes,
            max_compression_ratio=args.max_compression_ratio,
            max_pixels=args.max_pixels,
            max_decoded_bytes=args.max_decoded_bytes,
            max_total_pixels=args.max_total_pixels,
            max_total_decoded_bytes=args.max_total_decoded_bytes,
            max_files=args.max_files,
        )
    except GuardProblem as exc:
        error: dict[str, str] = {"code": exc.code, "message": exc.message}
        if exc.path is not None:
            error["path"] = exc.path
        emit({"schema": SCHEMA, "status": "rejected", "errors": [error]})
        return 2
    except ValueError as exc:
        emit(
            {
                "schema": SCHEMA,
                "status": "input-error",
                "errors": [
                    {"code": str(exc), "message": "input could not be validated"}
                ],
            }
        )
        return 1
    except OSError:
        emit(
            {
                "schema": SCHEMA,
                "status": "input-error",
                "errors": [{"code": "io_error", "message": "input could not be read"}],
            }
        )
        return 1

    emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
