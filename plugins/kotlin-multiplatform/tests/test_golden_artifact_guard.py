from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
import zlib
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "golden_artifact_guard.py"
SKILL = ROOT / "skills" / "kmp-testing-quality" / "SKILL.md"
REFERENCE = ROOT / "references" / "screenshot-golden-ci.md"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

GUARD_SPEC = importlib.util.spec_from_file_location("golden_artifact_guard", GUARD)
assert GUARD_SPEC is not None
assert GUARD_SPEC.loader is not None
GUARD_MODULE = importlib.util.module_from_spec(GUARD_SPEC)
GUARD_SPEC.loader.exec_module(GUARD_MODULE)


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type)
    checksum = zlib.crc32(data, checksum) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)
    )


def rgba_png(
    width: int = 2,
    height: int = 2,
    *,
    filter_type: int = 0,
    before_idat: tuple[bytes, ...] = (),
    idat: bytes | None = None,
) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    scanlines = b"".join(
        bytes([filter_type]) + bytes([row % 251]) * (width * 4) for row in range(height)
    )
    compressed = zlib.compress(scanlines) if idat is None else idat
    return (
        PNG_SIGNATURE
        + png_chunk(b"IHDR", ihdr)
        + b"".join(before_idat)
        + png_chunk(b"IDAT", compressed)
        + png_chunk(b"IEND", b"")
    )


def indexed_png() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 1, 1, 1, 3, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"PLTE", b"\x00\x00\x00")
        + png_chunk(b"IDAT", zlib.compress(b"\x00\x80"))
        + png_chunk(b"IEND", b"")
    )


def write_archive(
    path: Path,
    entries: list[tuple[str, bytes, int]],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
    extras: dict[str, bytes] | None = None,
    creator_systems: dict[str, int] | None = None,
    external_attributes: dict[str, int] | None = None,
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            for name, payload, mode in entries:
                info = zipfile.ZipInfo(name)
                info.create_system = (creator_systems or {}).get(name, 3)
                info.external_attr = (external_attributes or {}).get(name, mode << 16)
                info.compress_type = compression
                info.extra = (extras or {}).get(name, b"")
                archive.writestr(info, payload)


def write_raw_single_member_archive(
    path: Path,
    *,
    method: int = zipfile.ZIP_DEFLATED,
    hidden_suffix: bytes = b"",
    central_flags: int = 0,
    local_flags: int | None = None,
    local_method: int | None = None,
    include_descriptor: bool = False,
    archive_comment: bytes = b"",
    member_comment: bytes = b"",
) -> None:
    name = b"goldens/a.png"
    declared_payload = rgba_png(1, 1)
    actual_payload = declared_payload + hidden_suffix
    if method == zipfile.ZIP_DEFLATED:
        compressor = zlib.compressobj(level=9, wbits=-15)
        compressed = compressor.compress(actual_payload) + compressor.flush()
    else:
        compressed = actual_payload

    crc = zlib.crc32(declared_payload) & 0xFFFFFFFF
    effective_local_flags = central_flags if local_flags is None else local_flags
    effective_local_method = method if local_method is None else local_method
    deferred = bool(effective_local_flags & 0x08)
    local = struct.pack(
        "<4s5H3I2H",
        b"PK\x03\x04",
        20,
        effective_local_flags,
        effective_local_method,
        0,
        0,
        0 if deferred else crc,
        0 if deferred else len(compressed),
        0 if deferred else len(declared_payload),
        len(name),
        0,
    )
    local += name + compressed
    if include_descriptor:
        local += struct.pack(
            "<4sIII",
            b"PK\x07\x08",
            crc,
            len(compressed),
            len(declared_payload),
        )

    central = struct.pack(
        "<4s6H3I5H2I",
        b"PK\x01\x02",
        (3 << 8) | 20,
        20,
        central_flags,
        method,
        0,
        0,
        crc,
        len(compressed),
        len(declared_payload),
        len(name),
        0,
        len(member_comment),
        0,
        0,
        REGULAR_MODE << 16,
        0,
    )
    central += name + member_comment
    eocd = struct.pack(
        "<4s4H2IH",
        b"PK\x05\x06",
        0,
        0,
        1,
        1,
        len(central),
        len(local),
        len(archive_comment),
    )
    path.write_bytes(local + central + eocd + archive_comment)


def invoke_guard(
    archive_path: Path,
    allowlist_path: Path,
    extra_args: tuple[str, ...] = (),
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    result = subprocess.run(
        [
            sys.executable,
            str(GUARD),
            "--archive",
            str(archive_path),
            "--allowlist",
            str(allowlist_path),
            *extra_args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result, json.loads(result.stdout)


def run_guard(
    directory: Path,
    *,
    entries: list[tuple[str, bytes, int]],
    allowlist: str,
    extra_args: tuple[str, ...] = (),
    extras: dict[str, bytes] | None = None,
    creator_systems: dict[str, int] | None = None,
    external_attributes: dict[str, int] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object], Path]:
    archive_path = directory / "goldens.zip"
    allowlist_path = directory / "goldens.allowlist"
    write_archive(
        archive_path,
        entries,
        extras=extras,
        creator_systems=creator_systems,
        external_attributes=external_attributes,
    )
    allowlist_path.write_text(allowlist, encoding="utf-8")
    result, receipt = invoke_guard(archive_path, allowlist_path, extra_args)
    return result, receipt, archive_path


REGULAR_MODE = stat.S_IFREG | 0o600


class GoldenArtifactGuardTest(unittest.TestCase):
    def test_accepts_exact_allowlist_and_emits_deterministic_receipt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            entries = [
                (
                    "goldens/z.png",
                    rgba_png(
                        3,
                        2,
                        before_idat=(
                            png_chunk(b"sRGB", b"\x00"),
                            png_chunk(b"pHYs", struct.pack(">IIB", 72, 72, 1)),
                        ),
                    ),
                    REGULAR_MODE,
                ),
                ("goldens/a.png", rgba_png(1, 1), REGULAR_MODE),
            ]
            archive_path = directory / "goldens.zip"
            timestamp_extra = struct.pack("<HHBI", 0x5455, 5, 1, 1)
            write_archive(
                archive_path,
                entries,
                extras={"goldens/a.png": timestamp_extra},
            )
            expected_digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            (directory / "goldens.allowlist").write_text(
                "goldens/z.png\ngoldens/a.png\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(GUARD),
                    "--archive",
                    str(archive_path),
                    "--allowlist",
                    str(directory / "goldens.allowlist"),
                    "--expected-archive-sha256",
                    expected_digest,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            receipt = json.loads(result.stdout)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("accepted", receipt["status"])
            self.assertEqual(expected_digest, receipt["archive"]["sha256"])
            self.assertEqual(2, receipt["archive"]["member_count"])
            self.assertEqual(
                ["goldens/a.png", "goldens/z.png"],
                [member["path"] for member in receipt["members"]],
            )
            self.assertEqual([], receipt["errors"])
            self.assertNotIn(temp_dir, result.stdout)

    def test_rejects_digest_and_exact_member_set_mismatches(self):
        cases = (
            (
                "digest",
                [("goldens/a.png", rgba_png(), REGULAR_MODE)],
                "goldens/a.png\n",
                ("--expected-archive-sha256", "0" * 64),
                "archive_digest_mismatch",
            ),
            (
                "member-set",
                [
                    ("goldens/a.png", rgba_png(), REGULAR_MODE),
                    ("goldens/c.png", rgba_png(), REGULAR_MODE),
                ],
                "goldens/a.png\ngoldens/b.png\n",
                (),
                "allowlist_mismatch",
            ),
        )
        for label, entries, allowlist, extra_args, code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                result, receipt, _ = run_guard(
                    Path(temp_dir),
                    entries=entries,
                    allowlist=allowlist,
                    extra_args=extra_args,
                )
                self.assertEqual(2, result.returncode)
                self.assertEqual("rejected", receipt["status"])
                self.assertEqual(code, receipt["errors"][0]["code"])

    def test_rejects_ambiguous_archive_paths_and_collisions(self):
        cases = (
            ("dot", "./goldens/a.png", "escaping_path"),
            ("parent", "goldens/../a.png", "escaping_path"),
            ("backslash", "goldens\\a.png", "backslash_path"),
            ("absolute", "/goldens/a.png", "absolute_path"),
            ("trailing-dot", "goldens./a.png", "win32_trailing_alias"),
            ("trailing-space", "goldens /a.png", "win32_trailing_alias"),
            ("reserved-directory", "CON/a.png", "win32_reserved_name"),
            ("reserved-file", "goldens/NUL.png", "win32_reserved_name"),
            (
                "reserved-superscript",
                "goldens/COM\u00b9.png",
                "win32_reserved_name",
            ),
            (
                "reserved-space-before-extension",
                "goldens/NUL .png",
                "win32_reserved_name",
            ),
            (
                "reserved-numbered-space-before-extension",
                "goldens/COM1 .png",
                "win32_reserved_name",
            ),
            (
                "reserved-superscript-space-before-extension",
                "goldens/LPT\u00b9 .png",
                "win32_reserved_name",
            ),
            (
                "reserved-directory-space-before-extension",
                "CON .dir/a.png",
                "win32_reserved_name",
            ),
            (
                "reserved-console-space-before-extension",
                "goldens/CONIN$ .png",
                "win32_reserved_name",
            ),
        )
        for label, member, code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                result, receipt, _ = run_guard(
                    Path(temp_dir),
                    entries=[(member, rgba_png(), REGULAR_MODE)],
                    allowlist="goldens/a.png\n",
                )
                self.assertEqual(2, result.returncode)
                self.assertEqual(code, receipt["errors"][0]["code"])

        with tempfile.TemporaryDirectory() as temp_dir:
            result, receipt, _ = run_guard(
                Path(temp_dir),
                entries=[
                    ("Goldens/A.png", rgba_png(), REGULAR_MODE),
                    ("goldens/a.png", rgba_png(), REGULAR_MODE),
                ],
                allowlist="goldens/a.png\ngoldens/b.png\n",
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual("colliding_member", receipt["errors"][0]["code"])

    def test_rejects_win32_invalid_component_characters(self):
        for character in '<>"|?*':
            with (
                self.subTest(character=character),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                result, receipt, _ = run_guard(
                    Path(temp_dir),
                    entries=[
                        (
                            f"goldens/a{character}.png",
                            rgba_png(),
                            REGULAR_MODE,
                        )
                    ],
                    allowlist="goldens/a.png\n",
                )
                self.assertEqual(2, result.returncode)
                self.assertEqual(
                    "win32_invalid_character",
                    receipt["errors"][0]["code"],
                )

    def test_rejects_win32_unsafe_allowlist_paths(self):
        cases = (
            ("trailing-dot", "goldens./a.png", "win32_trailing_alias"),
            ("trailing-space", "goldens /a.png", "win32_trailing_alias"),
            ("reserved", "goldens/PRN.png", "win32_reserved_name"),
            (
                "reserved-space-before-extension",
                "goldens/CONOUT$ .png",
                "win32_reserved_name",
            ),
            (
                "reserved-superscript-space-before-extension",
                "goldens/COM\u00b2 .png",
                "win32_reserved_name",
            ),
            ("invalid-character", "goldens/a?.png", "win32_invalid_character"),
        )
        for label, allowlist_path, code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                result, receipt, _ = run_guard(
                    Path(temp_dir),
                    entries=[("goldens/a.png", rgba_png(), REGULAR_MODE)],
                    allowlist=f"{allowlist_path}\n",
                )
                self.assertEqual(2, result.returncode)
                self.assertEqual(code, receipt["errors"][0]["code"])

    def test_win32_collision_key_is_defensive_and_safe_controls_pass(self):
        canonical_key = GUARD_MODULE.collision_key("goldens/a.png")
        self.assertEqual(
            canonical_key,
            GUARD_MODULE.collision_key("goldens./a.png"),
        )
        self.assertEqual(
            canonical_key,
            GUARD_MODULE.collision_key("goldens /a.png"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result, receipt, _ = run_guard(
                Path(temp_dir),
                entries=[
                    (".goldens/a.png", rgba_png(), REGULAR_MODE),
                    ("goldens/COM10.png", rgba_png(), REGULAR_MODE),
                ],
                allowlist=".goldens/a.png\ngoldens/COM10.png\n",
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("accepted", receipt["status"])

    def test_rejects_duplicate_and_non_regular_members(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result, receipt, _ = run_guard(
                Path(temp_dir),
                entries=[
                    ("goldens/a.png", rgba_png(), REGULAR_MODE),
                    ("goldens/a.png", rgba_png(), REGULAR_MODE),
                ],
                allowlist="goldens/a.png\ngoldens/b.png\n",
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual("duplicate_member", receipt["errors"][0]["code"])

        with tempfile.TemporaryDirectory() as temp_dir:
            result, receipt, _ = run_guard(
                Path(temp_dir),
                entries=[
                    (
                        "goldens/a.png",
                        b"elsewhere.png",
                        stat.S_IFLNK | 0o777,
                    )
                ],
                allowlist="goldens/a.png\n",
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual("symlink_member", receipt["errors"][0]["code"])

        with tempfile.TemporaryDirectory() as temp_dir:
            result, receipt, _ = run_guard(
                Path(temp_dir),
                entries=[("goldens/a.png", rgba_png(), REGULAR_MODE)],
                allowlist="goldens/a.png\n",
                creator_systems={"goldens/a.png": 0},
                external_attributes={"goldens/a.png": 0x10},
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual(
                "non_regular_dos_member",
                receipt["errors"][0]["code"],
            )

    def test_validates_raw_member_stream_and_local_header_contract(self):
        cases = (
            (
                "deflate-hidden-suffix",
                {
                    "method": zipfile.ZIP_DEFLATED,
                    "hidden_suffix": b"SECRET" * 1000,
                },
                "member_expands_past_declared_size",
            ),
            (
                "stored-hidden-suffix",
                {
                    "method": zipfile.ZIP_STORED,
                    "hidden_suffix": b"SECRET",
                },
                "stored_size_mismatch",
            ),
            (
                "local-method-mismatch",
                {
                    "method": zipfile.ZIP_DEFLATED,
                    "local_method": zipfile.ZIP_STORED,
                },
                "local_central_header_mismatch",
            ),
            (
                "local-encryption-flag-mismatch",
                {
                    "method": zipfile.ZIP_DEFLATED,
                    "local_flags": 0x1,
                },
                "local_central_header_mismatch",
            ),
            (
                "missing-data-descriptor",
                {
                    "method": zipfile.ZIP_DEFLATED,
                    "central_flags": 0x8,
                },
                "missing_data_descriptor",
            ),
        )
        for label, arguments, code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                directory = Path(temp_dir)
                archive_path = directory / "candidate.zip"
                allowlist_path = directory / "allowlist.txt"
                write_raw_single_member_archive(archive_path, **arguments)
                allowlist_path.write_text("goldens/a.png\n", encoding="utf-8")
                result, receipt = invoke_guard(archive_path, allowlist_path)
                self.assertEqual(2, result.returncode)
                self.assertEqual(code, receipt["errors"][0]["code"])

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            archive_path = directory / "candidate.zip"
            allowlist_path = directory / "allowlist.txt"
            write_raw_single_member_archive(
                archive_path,
                central_flags=0x8,
                include_descriptor=True,
            )
            allowlist_path.write_text("goldens/a.png\n", encoding="utf-8")
            result, receipt = invoke_guard(archive_path, allowlist_path)
            self.assertEqual(0, result.returncode)
            self.assertEqual("accepted", receipt["status"])

    def test_rejects_archive_and_member_comments(self):
        cases = (
            ("archive", {"archive_comment": b"opaque producer metadata"}),
            ("member", {"member_comment": b"opaque member metadata"}),
        )
        for label, arguments in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                directory = Path(temp_dir)
                archive_path = directory / "candidate.zip"
                allowlist_path = directory / "allowlist.txt"
                write_raw_single_member_archive(archive_path, **arguments)
                allowlist_path.write_text("goldens/a.png\n", encoding="utf-8")

                result, receipt = invoke_guard(archive_path, allowlist_path)

                self.assertEqual(2, result.returncode)
                self.assertEqual(
                    "unsupported_zip_comment",
                    receipt["errors"][0]["code"],
                )

    def test_preflights_all_local_records_before_reading_member_payloads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            archive_path = directory / "candidate.zip"
            write_archive(
                archive_path,
                [
                    ("goldens/a.png", rgba_png(), REGULAR_MODE),
                    ("goldens/b.png", rgba_png(), REGULAR_MODE),
                ],
            )
            with zipfile.ZipFile(archive_path, "r") as archive:
                second_header_offset = archive.infolist()[1].header_offset
            payload = bytearray(archive_path.read_bytes())
            struct.pack_into(
                "<H",
                payload,
                second_header_offset + 8,
                zipfile.ZIP_STORED,
            )
            archive_path.write_bytes(payload)

            with mock.patch.object(
                GUARD_MODULE, "read_member_payload"
            ) as read_member_payload:
                with self.assertRaises(GUARD_MODULE.GuardProblem) as raised:
                    GUARD_MODULE.inspect_archive(
                        archive_path,
                        ["goldens/a.png", "goldens/b.png"],
                        hashlib.sha256(
                            b"goldens/a.png\ngoldens/b.png\n"
                        ).hexdigest(),
                        expected_archive_sha256=None,
                        max_archive_bytes=1024 * 1024,
                        max_entry_bytes=1024 * 1024,
                        max_total_bytes=1024 * 1024,
                        max_compression_ratio=200.0,
                        max_pixels=1_000_000,
                        max_decoded_bytes=4 * 1024 * 1024,
                        max_total_pixels=1_000_000,
                        max_total_decoded_bytes=4 * 1024 * 1024,
                        max_files=8,
                    )

            self.assertEqual("local_central_header_mismatch", raised.exception.code)
            read_member_payload.assert_not_called()

    def test_rejects_malformed_or_nonportable_png_payloads(self):
        valid = bytearray(rgba_png())
        idat_marker = valid.index(b"IDAT")
        valid[idat_marker + 4] ^= 0x01
        cases = (
            ("signature", b"not-a-png", "invalid_png_signature"),
            ("crc", bytes(valid), "invalid_png_crc"),
            (
                "privacy",
                rgba_png(before_idat=(png_chunk(b"tEXt", b"author\x00private"),)),
                "privacy_metadata_chunk",
            ),
            (
                "unknown-ancillary",
                rgba_png(before_idat=(png_chunk(b"vpAg", b"opaque"),)),
                "unknown_ancillary_chunk",
            ),
            (
                "unsupported-profile",
                rgba_png(before_idat=(png_chunk(b"iCCP", b"x\x00\x00data"),)),
                "unknown_ancillary_chunk",
            ),
            (
                "malformed-gamma",
                rgba_png(before_idat=(png_chunk(b"gAMA", b"x"),)),
                "invalid_ancillary_chunk",
            ),
            (
                "invalid-srgb-intent",
                rgba_png(before_idat=(png_chunk(b"sRGB", b"\x04"),)),
                "invalid_ancillary_chunk",
            ),
            (
                "duplicate-srgb",
                rgba_png(
                    before_idat=(
                        png_chunk(b"sRGB", b"\x00"),
                        png_chunk(b"sRGB", b"\x00"),
                    )
                ),
                "duplicate_ancillary_chunk",
            ),
            ("invalid-zlib", rgba_png(idat=b"not-zlib"), "invalid_idat_stream"),
            ("invalid-filter", rgba_png(filter_type=5), "invalid_png_filter"),
            ("indexed-color", indexed_png(), "unsupported_png_format"),
            ("trailing", rgba_png() + b"x", "trailing_png_data"),
        )
        for label, payload, code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                result, receipt, _ = run_guard(
                    Path(temp_dir),
                    entries=[("goldens/a.png", payload, REGULAR_MODE)],
                    allowlist="goldens/a.png\n",
                )
                self.assertEqual(2, result.returncode)
                self.assertEqual(code, receipt["errors"][0]["code"])

    def test_enforces_archive_entry_expansion_and_decoded_limits(self):
        large_metadata = png_chunk(b"iCCP", b"x" * 100_000)
        cases = (
            (
                "entry",
                rgba_png(),
                ("--max-entry-bytes", "32"),
                "entry_size_limit",
            ),
            (
                "ratio",
                rgba_png(before_idat=(large_metadata,)),
                ("--max-compression-ratio", "2"),
                "compression_ratio_limit",
            ),
            (
                "decoded",
                rgba_png(10, 10),
                ("--max-decoded-bytes", "100"),
                "decoded_png_size_limit",
            ),
        )
        for label, payload, extra_args, code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                result, receipt, _ = run_guard(
                    Path(temp_dir),
                    entries=[("goldens/a.png", payload, REGULAR_MODE)],
                    allowlist="goldens/a.png\n",
                    extra_args=extra_args,
                )
                self.assertEqual(2, result.returncode)
                self.assertEqual(code, receipt["errors"][0]["code"])

        with tempfile.TemporaryDirectory() as temp_dir:
            result, receipt, _ = run_guard(
                Path(temp_dir),
                entries=[
                    ("goldens/a.png", rgba_png(10, 10), REGULAR_MODE),
                    ("goldens/b.png", rgba_png(10, 10), REGULAR_MODE),
                ],
                allowlist="goldens/a.png\ngoldens/b.png\n",
                extra_args=("--max-total-decoded-bytes", "500"),
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual(
                "total_decoded_png_size_limit",
                receipt["errors"][0]["code"],
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            result, receipt, _ = run_guard(
                Path(temp_dir),
                entries=[
                    ("goldens/a.png", rgba_png(10, 10), REGULAR_MODE),
                    ("goldens/b.png", rgba_png(10, 10), REGULAR_MODE),
                ],
                allowlist="goldens/a.png\ngoldens/b.png\n",
                extra_args=("--max-total-pixels", "150"),
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual("total_pixel_limit", receipt["errors"][0]["code"])

    def test_rejects_path_alias_extra_fields_and_preflights_member_count(self):
        raw_name = b"goldens/a.png"
        unicode_path_payload = (
            b"\x01"
            + struct.pack("<I", zlib.crc32(raw_name) & 0xFFFFFFFF)
            + b"../outside.png"
        )
        unicode_path_extra = (
            struct.pack("<HH", 0x7075, len(unicode_path_payload)) + unicode_path_payload
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            result, receipt, _ = run_guard(
                Path(temp_dir),
                entries=[("goldens/a.png", rgba_png(), REGULAR_MODE)],
                allowlist="goldens/a.png\n",
                extras={"goldens/a.png": unicode_path_extra},
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual(
                "unsupported_zip_extra_field",
                receipt["errors"][0]["code"],
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            result, receipt, _ = run_guard(
                Path(temp_dir),
                entries=[
                    ("goldens/a.png", b"", REGULAR_MODE),
                    ("goldens/b.png", b"", REGULAR_MODE),
                    ("goldens/c.png", b"", REGULAR_MODE),
                ],
                allowlist="goldens/a.png\n",
                extra_args=("--max-files", "2"),
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual("archive_file_limit", receipt["errors"][0]["code"])

    def test_rejects_nonfinite_ratio_limits_at_argument_boundary(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp_dir:
                directory = Path(temp_dir)
                result = subprocess.run(
                    [
                        sys.executable,
                        str(GUARD),
                        "--archive",
                        str(directory / "unused.zip"),
                        "--allowlist",
                        str(directory / "unused.allowlist"),
                        f"--max-compression-ratio={value}",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                receipt = json.loads(result.stdout)
                self.assertEqual(1, result.returncode)
                self.assertEqual("", result.stderr)
                self.assertEqual("input-error", receipt["status"])
                self.assertEqual("invalid_arguments", receipt["errors"][0]["code"])

        result = subprocess.run(
            [sys.executable, str(GUARD)],
            check=False,
            capture_output=True,
            text=True,
        )
        receipt = json.loads(result.stdout)
        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stderr)
        self.assertEqual("input-error", receipt["status"])
        self.assertEqual("invalid_arguments", receipt["errors"][0]["code"])

    def test_pins_archive_identity_and_validates_one_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            archive_path = directory / "candidate.zip"
            replacement_path = directory / "replacement.zip"
            write_archive(
                archive_path,
                [("goldens/a.png", rgba_png(1, 1), REGULAR_MODE)],
            )
            write_archive(
                replacement_path,
                [("goldens/b.png", rgba_png(2, 2), REGULAR_MODE)],
            )
            original_digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()

            snapshot, digest, _ = GUARD_MODULE.snapshot_archive(
                archive_path, 1024 * 1024
            )
            os.replace(replacement_path, archive_path)
            with snapshot, zipfile.ZipFile(snapshot, "r") as archive:
                self.assertEqual(["goldens/a.png"], archive.namelist())
            self.assertEqual(original_digest, digest)

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            archive_path = directory / "candidate.zip"
            replacement_path = directory / "replacement.zip"
            write_archive(
                archive_path,
                [("goldens/a.png", rgba_png(), REGULAR_MODE)],
            )
            write_archive(
                replacement_path,
                [("goldens/b.png", rgba_png(), REGULAR_MODE)],
            )
            real_open = os.open
            swapped = False

            def swapping_open(path: Path, flags: int) -> int:
                nonlocal swapped
                if not swapped and Path(path) == archive_path:
                    os.replace(replacement_path, archive_path)
                    swapped = True
                return real_open(path, flags)

            with mock.patch.object(GUARD_MODULE.os, "open", side_effect=swapping_open):
                with self.assertRaisesRegex(ValueError, "archive_changed_during_open"):
                    GUARD_MODULE.snapshot_archive(archive_path, 1024 * 1024)

    def test_guidance_routes_through_guard_and_preserves_state_boundaries(self):
        skill = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        reference = " ".join(REFERENCE.read_text(encoding="utf-8").split()).lower()

        for phrase in (
            "$plugin_root",
            "golden_artifact_guard.py",
            "does not download, extract, or authorize",
            "`accepted` receipt",
        ):
            self.assertIn(phrase, skill)
        for phrase in (
            "generator routing and review-object state",
            "open review object",
            "branch-only generator",
            "immutable job or run identifier",
            "mutable latest-by-ref lookup",
            "diagnostic and non-deliverable",
            "do not create, close, retarget, or mutate",
            "do not blindly retry",
            "does not extract files",
            "or authorize a visual change",
            "8-bit truecolor or truecolor-with-alpha",
            "golden_artifact_guard.py",
            "downstream consumer extraction or import staging directory",
            "remove only the partial directory created for that attempt",
        ):
            self.assertIn(phrase, reference)

    def test_changed_capability_files_are_public_safe_ascii(self):
        for path in (GUARD, SKILL, REFERENCE):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii())
            self.assertNotIn("/Users/", text)
            self.assertNotIn("\\Users\\", text)


if __name__ == "__main__":
    unittest.main()
