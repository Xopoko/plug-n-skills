#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCHEMA_PLAN = "scientific_research.plan.v1"
SCHEMA_RECORD = "scientific_research.record.v1"
SCHEMA_QUERY_LOG = "scientific_research.query_log.v1"
SCHEMA_SOURCE_STATUS = "scientific_research.source_status.v1"
SCHEMA_SCREENING = "scientific_research.screening_summary.v1"
SCHEMA_QUALITY = "scientific_research.quality_gate.v1"
USER_AGENT = "PlugNSkillsScientificResearch/0.2 (+https://github.com/Xopoko/plug-n-skills)"
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
MAX_SUMMARY_CHARS = 4000

DEFAULT_SOURCES = ["openalex", "arxiv", "crossref", "europepmc", "semantic-scholar"]
ALLOWED_SOURCES = {
    "openalex",
    "arxiv",
    "crossref",
    "europepmc",
    "semantic-scholar",
    "ncbi",
    "core",
    "opencitations",
    "dblp",
    "doaj",
}
CONFIDENCE = {"low", "medium", "high"}
SCREENING_DECISIONS = {"include", "exclude", "maybe", "duplicate"}
SOURCE_POLICIES = {
    "openalex": {
        "fallbacks": ["crossref", "semantic-scholar", "europepmc"],
        "cooldown_seconds": 900,
        "max_per_page": 100,
    },
    "arxiv": {
        "fallbacks": ["openalex", "semantic-scholar", "crossref"],
        "cooldown_seconds": 60,
        "min_interval_seconds": 3.0,
    },
    "crossref": {"fallbacks": ["openalex", "europepmc"], "cooldown_seconds": 300},
    "europepmc": {"fallbacks": ["ncbi", "crossref"], "cooldown_seconds": 300},
    "semantic-scholar": {"fallbacks": ["openalex", "crossref"], "cooldown_seconds": 300},
    "ncbi": {
        "fallbacks": ["europepmc", "crossref"],
        "cooldown_seconds": 300,
        "min_interval_seconds": 0.4,
    },
    "core": {"fallbacks": ["openalex", "crossref"], "cooldown_seconds": 300, "min_interval_seconds": 1.0},
    "dblp": {"fallbacks": ["crossref", "semantic-scholar", "openalex"], "cooldown_seconds": 300, "min_interval_seconds": 1.0},
    "doaj": {"fallbacks": ["europepmc", "crossref"], "cooldown_seconds": 300, "min_interval_seconds": 1.0},
    "opencitations": {"fallbacks": ["crossref", "openalex"], "cooldown_seconds": 300, "min_interval_seconds": 1.0},
}
RECORD_FIELDS = [
    "schema",
    "key",
    "source",
    "source_id",
    "title",
    "creators",
    "year",
    "container",
    "doi",
    "pmid",
    "pmcid",
    "arxiv_id",
    "landing_url",
    "open_copy_url",
    "summary",
    "query",
    "dedupe_keys",
    "raw_metadata",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"unreadable_json:{path}:{exc}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid_json:{path}:line_{exc.lineno}:{exc.msg}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"unreadable_jsonl:{path}:{exc}")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            # Fail loudly: silently skipping a provenance line would hide data loss.
            raise SystemExit(f"invalid_jsonl:{path}:line_{line_no}:{exc.msg}")
        if isinstance(value, dict):
            rows.append(value)
    return rows


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return clean_text(" ".join(clean_text(item) for item in value))
    return " ".join(str(value).split())


def first_text(*values: Any) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def normalize_doi(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    return text.strip()


def normalize_title(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalize_url(value: Any) -> str:
    return clean_text(value).strip().rstrip("/")


def slugify(value: str, limit: int = 96) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "item")[:limit].strip("-") or "item"


def stable_hash(value: str) -> str:
    digest = 0xCBF29CE484222325
    for byte in value.encode("utf-8", errors="replace"):
        digest ^= byte
        digest = (digest * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{digest:016x}"


def quote_component(value: Any) -> str:
    safe = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
    encoded = bytearray()
    for byte in str(value).encode("utf-8", errors="replace"):
        if byte in safe:
            encoded.append(byte)
        else:
            encoded.extend(f"%{byte:02X}".encode("ascii"))
    return encoded.decode("ascii")


def urlencode(params: dict[str, Any]) -> str:
    return "&".join(f"{quote_component(key)}={quote_component(value)}" for key, value in params.items())


class ScholarlyHttpError(RuntimeError):
    def __init__(self, url: str, status_code: int, headers: dict[str, str], body: str) -> None:
        self.url = url
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.retry_after_seconds = retry_after_seconds(headers)
        body_excerpt = clean_text(body)[:240]
        pieces = [f"HTTP {status_code}"]
        if self.retry_after_seconds:
            pieces.append(f"retry_after_seconds={self.retry_after_seconds}")
        if body_excerpt:
            pieces.append(f"body={body_excerpt}")
        super().__init__(" ".join(pieces))


def parse_http_date(value: str) -> dt.datetime | None:
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return None


def retry_after_seconds(headers: dict[str, str]) -> int:
    normalized = {key.lower(): value for key, value in headers.items()}
    retry_after = clean_text(normalized.get("retry-after", ""))
    if retry_after.isdigit():
        return max(0, int(retry_after))
    parsed_date = parse_http_date(retry_after)
    if parsed_date:
        delta = parsed_date - dt.datetime.now(dt.timezone.utc)
        return max(0, int(delta.total_seconds()))
    openalex_reset = clean_text(normalized.get("x-ratelimit-reset", ""))
    if openalex_reset.isdigit():
        return max(0, int(openalex_reset))
    return 0


def utc_from_now(seconds: int) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=max(0, seconds))).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(value: Any) -> dt.datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def classify_fetch_error(source: str, exc: BaseException) -> tuple[str, int, int]:
    text = str(exc)
    code = exc.status_code if isinstance(exc, ScholarlyHttpError) else 0
    if not code:
        code_match = re.search(r"HTTP\s+(\d+)", text, flags=re.IGNORECASE)
        code = int(code_match.group(1)) if code_match else 0
    retry_after = exc.retry_after_seconds if isinstance(exc, ScholarlyHttpError) else 0
    lowered = text.lower()
    if code == 400 or "requires_doi_query" in lowered:
        # Malformed query, not a capacity problem: no cooldown, fix the query.
        return "query_error", code, 0
    if source == "openalex" and code in {403, 429}:
        return "cooldown", code, retry_after
    if source == "openalex" and code == 409:
        return "auth_required", code, retry_after
    if code in {401, 403}:
        return "auth_required", code, retry_after
    if code in {408, 425, 429, 500, 502, 503, 504}:
        return "cooldown", code, retry_after
    if "rate limit" in lowered or "too many requests" in lowered or "cooldown" in lowered:
        return "cooldown", code, retry_after
    if "auth" in lowered or "api key" in lowered or "api_key" in lowered or "key_required" in lowered or "forbidden" in lowered:
        return "auth_required", code, retry_after
    return "error", code, retry_after


def cooldown_seconds(source: str, retry_after: int = 0) -> int:
    if retry_after > 0:
        return retry_after
    return int(SOURCE_POLICIES.get(source, {}).get("cooldown_seconds", 300))


def source_status_path(out_dir: Path) -> Path:
    return out_dir / "03_runs" / "source-status.json"


def load_source_status(out_dir: Path) -> dict[str, Any]:
    path = source_status_path(out_dir)
    if path.exists():
        try:
            data = read_json(path)
            if isinstance(data.get("sources"), dict):
                return data
        except Exception:
            pass
    return {
        "schema": SCHEMA_SOURCE_STATUS,
        "generated_at_utc": utc_now(),
        "sources": {},
        "notes": "Source availability is local to this corpus directory and is safe to delete.",
    }


def source_status_entry(status: dict[str, Any], source: str) -> dict[str, Any]:
    sources = status.setdefault("sources", {})
    if not isinstance(sources, dict):
        status["sources"] = {}
        sources = status["sources"]
    entry = sources.setdefault(source, {})
    if not isinstance(entry, dict):
        entry = {}
        sources[source] = entry
    return entry


def update_source_success(status: dict[str, Any], source: str, endpoint: str, count: int) -> None:
    entry = source_status_entry(status, source)
    entry.update({
        "status": "ok",
        "last_ok_at_utc": utc_now(),
        "last_endpoint": endpoint,
        "last_records_returned": count,
        "cooldown_until_utc": "",
        "last_error": "",
        "last_http_status": 0,
        "fallbacks": SOURCE_POLICIES.get(source, {}).get("fallbacks", []),
    })
    status["generated_at_utc"] = utc_now()


def update_source_failure(
    status: dict[str, Any],
    source: str,
    state: str,
    error: str,
    endpoint: str,
    http_status: int = 0,
    retry_after: int = 0,
) -> None:
    entry = source_status_entry(status, source)
    cooldown_until = ""
    if state == "cooldown":
        cooldown_until = utc_from_now(cooldown_seconds(source, retry_after))
    entry.update({
        "status": state,
        "last_error_at_utc": utc_now(),
        "last_error": clean_text(error)[:500],
        "last_endpoint": endpoint,
        "last_http_status": http_status,
        "retry_after_seconds": retry_after,
        "cooldown_until_utc": cooldown_until,
        "fallbacks": SOURCE_POLICIES.get(source, {}).get("fallbacks", []),
    })
    status["generated_at_utc"] = utc_now()


def is_source_cooling_down(status: dict[str, Any], source: str) -> tuple[bool, str]:
    entry = status.get("sources", {}).get(source, {}) if isinstance(status.get("sources"), dict) else {}
    cooldown_until = parse_utc(entry.get("cooldown_until_utc", "")) if isinstance(entry, dict) else None
    if cooldown_until and cooldown_until > dt.datetime.now(dt.timezone.utc):
        return True, cooldown_until.strftime("%Y-%m-%dT%H:%M:%SZ")
    return False, ""


def write_source_status(out_dir: Path, status: dict[str, Any]) -> None:
    write_json(source_status_path(out_dir), status)


def dedupe_keys(record: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    if record.get("doi"):
        keys.add("doi:" + normalize_doi(record["doi"]))
    if record.get("pmid"):
        keys.add("pmid:" + clean_text(record["pmid"]).lower())
    if record.get("pmcid"):
        keys.add("pmcid:" + clean_text(record["pmcid"]).lower())
    if record.get("arxiv_id"):
        keys.add("arxiv:" + clean_text(record["arxiv_id"]).lower())
    title = normalize_title(record.get("title", ""))
    if title:
        keys.add("title:" + title)
    open_copy = normalize_url(record.get("open_copy_url", ""))
    if open_copy:
        keys.add("open-copy-url:" + open_copy)
    if record.get("content_sha256"):
        keys.add("content-sha256:" + clean_text(record["content_sha256"]).lower())
    if not keys:
        keys.add("fallback:" + stable_hash(json.dumps(record, sort_keys=True, default=str)))
    return keys


def primary_key(record: dict[str, Any]) -> str:
    if record.get("doi"):
        return "doi-" + slugify(normalize_doi(record["doi"]))
    if record.get("pmcid"):
        return "pmcid-" + slugify(record["pmcid"])
    if record.get("pmid"):
        return "pmid-" + slugify(record["pmid"])
    if record.get("arxiv_id"):
        return "arxiv-" + slugify(record["arxiv_id"])
    if record.get("title"):
        return "title-" + slugify(record["title"])
    return "record-" + stable_hash(json.dumps(record, sort_keys=True, default=str))[:12]


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "schema": SCHEMA_RECORD,
        "key": clean_text(record.get("key", "")),
        "source": clean_text(record.get("source", "")),
        "source_id": clean_text(record.get("source_id", "")),
        "title": first_text(record.get("title"), record.get("display_name"), record.get("name")),
        "creators": clean_text(record.get("creators", "")),
        "year": clean_text(record.get("year", "")),
        "container": clean_text(record.get("container", "")),
        "doi": normalize_doi(record.get("doi", "")),
        "pmid": clean_text(first_text(record.get("pmid"), record.get("PMID"))),
        "pmcid": clean_text(first_text(record.get("pmcid"), record.get("PMCID"))),
        "arxiv_id": clean_text(record.get("arxiv_id", "")),
        "landing_url": normalize_url(first_text(record.get("landing_url"), record.get("url"), record.get("URL"))),
        "open_copy_url": normalize_url(first_text(record.get("open_copy_url"), record.get("pdf_url"), record.get("url_for_pdf"))),
        "summary": clean_text(first_text(record.get("summary"), record.get("abstract"), record.get("abstract_text"), record.get("description")))[:MAX_SUMMARY_CHARS],
        "query": clean_text(record.get("query", "")),
        "raw_metadata": record.get("raw_metadata", record),
    }
    keys = sorted(dedupe_keys(normalized))
    normalized["dedupe_keys"] = keys
    normalized["key"] = normalized["key"] or primary_key(normalized)
    return normalized


def dedupe_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for record in records:
        normalized = normalize_record(record)
        keys = set(normalized["dedupe_keys"])
        if keys & seen:
            duplicate_count += 1
            continue
        seen.update(keys)
        accepted.append(normalized)
    return accepted, duplicate_count


def http_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 30.0) -> dict[str, Any]:
    return json.loads(http_text(url, headers={"Accept": "application/json", **(headers or {})}, timeout=timeout))


def http_text(url: str, *, headers: dict[str, str] | None = None, timeout: float = 30.0) -> str:
    req_headers = {"User-Agent": USER_AGENT}
    req_headers.update(headers or {})
    request = Request(url, headers=req_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise RuntimeError(f"response_too_large:>{MAX_RESPONSE_BYTES}_bytes:{url}")
            return data.decode(content_type, errors="replace")
    except HTTPError as exc:
        content_type = exc.headers.get_content_charset() or "utf-8"
        body = exc.read().decode(content_type, errors="replace")
        raise ScholarlyHttpError(url, exc.code, dict(exc.headers.items()), body) from exc
    except URLError as exc:
        reason = clean_text(getattr(exc, "reason", exc))
        raise RuntimeError(f"network_error:{reason}") from exc


def authors_from_openalex(authorships: Any) -> str:
    if not isinstance(authorships, list):
        return ""
    names = []
    for authorship in authorships[:12]:
        if isinstance(authorship, dict):
            author = authorship.get("author")
            if isinstance(author, dict) and author.get("display_name"):
                names.append(clean_text(author["display_name"]))
    return "; ".join(names)


def abstract_from_inverted_index(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, offsets in index.items():
        if isinstance(offsets, list):
            for offset in offsets:
                if isinstance(offset, int):
                    positions.append((offset, str(word)))
    return " ".join(word for _, word in sorted(positions))


def sanitize_openalex_query(query: str) -> str:
    """OpenAlex stemmed search rejects wildcard characters (? and *) with HTTP 400."""
    return re.sub(r"\s+", " ", query.replace("?", " ").replace("*", " ")).strip()


def fetch_openalex(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {
        "search": sanitize_openalex_query(query),
        "per_page": str(min(limit, int(SOURCE_POLICIES["openalex"]["max_per_page"]))),
        "select": "id,doi,title,display_name,publication_year,authorships,primary_location,open_access,abstract_inverted_index,type,cited_by_count,ids",
    }
    api_key = env_value("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key
    if contact_email:
        params["mailto"] = contact_email
    url = "https://api.openalex.org/works?" + urlencode(params)
    data = http_json(url, timeout=timeout)
    records = []
    for item in data.get("results", [])[:limit]:
        if not isinstance(item, dict):
            continue
        primary = item.get("primary_location") if isinstance(item.get("primary_location"), dict) else {}
        pdf_url = ""
        if isinstance(primary.get("pdf_url"), str):
            pdf_url = primary["pdf_url"]
        elif isinstance(item.get("open_access"), dict) and isinstance(item["open_access"].get("oa_url"), str):
            pdf_url = item["open_access"]["oa_url"]
        ids = item.get("ids") if isinstance(item.get("ids"), dict) else {}
        records.append({
            "source": "openalex",
            "source_id": first_text(item.get("id"), ids.get("openalex")),
            "title": first_text(item.get("title"), item.get("display_name")),
            "creators": authors_from_openalex(item.get("authorships")),
            "year": item.get("publication_year") or "",
            "container": "",
            "doi": first_text(item.get("doi"), ids.get("doi")),
            "landing_url": first_text(ids.get("doi"), item.get("id")),
            "open_copy_url": pdf_url,
            "summary": abstract_from_inverted_index(item.get("abstract_inverted_index")),
            "query": query,
            "raw_metadata": item,
        })
    return records, {"endpoint": url, "count": len(records), "provider_meta": data.get("meta", {})}


def fetch_arxiv(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {
        "search_query": "all:" + query,
        "start": "0",
        "max_results": str(min(limit, 100)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + urlencode(params)
    text = http_text(url, timeout=timeout)
    records = []
    for entry in re.findall(r"<entry>(.*?)</entry>", text, flags=re.DOTALL)[:limit]:
        entry_id = clean_text(xml_text(entry, "id"))
        arxiv_id = entry_id.rsplit("/", 1)[-1]
        pdf_url = ""
        landing = entry_id
        for attrs in re.findall(r"<link\s+([^>]+)/?>", entry):
            href = xml_attr(attrs, "href")
            if xml_attr(attrs, "title") == "pdf" or xml_attr(attrs, "type") == "application/pdf":
                pdf_url = href
            if xml_attr(attrs, "rel") == "alternate":
                landing = href or landing
        creators = "; ".join(clean_text(xml_text(author, "name")) for author in re.findall(r"<author>(.*?)</author>", entry, flags=re.DOTALL))
        doi = clean_text(xml_text(entry, "arxiv:doi") or xml_text(entry, "doi"))
        published = clean_text(xml_text(entry, "published"))
        records.append({
            "source": "arxiv",
            "source_id": entry_id,
            "title": xml_text(entry, "title"),
            "creators": creators,
            "year": published[:4],
            "container": "arXiv",
            "doi": doi,
            "arxiv_id": arxiv_id,
            "landing_url": landing,
            "open_copy_url": pdf_url,
            "summary": xml_text(entry, "summary"),
            "query": query,
            "raw_metadata": {"entry_id": entry_id, "published": published},
        })
    return records, {"endpoint": url, "count": len(records)}


def xml_unescape(value: str) -> str:
    value = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), value)
    value = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), value)
    return (
        value.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
    )


def xml_text(blob: str, tag: str) -> str:
    escaped = re.escape(tag)
    match = re.search(rf"<{escaped}(?:\s[^>]*)?>(.*?)</{escaped}>", blob, flags=re.DOTALL)
    return clean_text(xml_unescape(match.group(1))) if match else ""


def xml_attr(attrs: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}=[\"']([^\"']*)[\"']", attrs)
    return xml_unescape(match.group(1)) if match else ""


def fetch_crossref(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {
        "query": query,
        "rows": str(min(limit, 100)),
        "select": "DOI,title,container-title,issued,URL,type,author,abstract",
    }
    if contact_email:
        params["mailto"] = contact_email
    url = "https://api.crossref.org/works?" + urlencode(params)
    data = http_json(url, timeout=timeout)
    items = data.get("message", {}).get("items", [])
    records = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        year = ""
        parts = item.get("issued", {}).get("date-parts") if isinstance(item.get("issued"), dict) else None
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            year = str(parts[0][0])
        authors = []
        for author in item.get("author", [])[:12] if isinstance(item.get("author"), list) else []:
            if isinstance(author, dict):
                authors.append(clean_text(" ".join([str(author.get("given", "")), str(author.get("family", ""))])))
        records.append({
            "source": "crossref",
            "source_id": normalize_doi(item.get("DOI", "")),
            "title": first_text(item.get("title")),
            "creators": "; ".join(a for a in authors if a),
            "year": year,
            "container": first_text(item.get("container-title")),
            "doi": item.get("DOI", ""),
            "landing_url": item.get("URL", ""),
            "summary": item.get("abstract", ""),
            "query": query,
            "raw_metadata": item,
        })
    return records, {"endpoint": url, "count": len(records)}


def fetch_europepmc(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {
        "query": query,
        "format": "json",
        "pageSize": str(min(limit, 100)),
        "resultType": "core",
    }
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode(params)
    data = http_json(url, timeout=timeout)
    items = data.get("resultList", {}).get("result", [])
    records = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        open_copy = ""
        full_text_urls = item.get("fullTextUrlList", {}).get("fullTextUrl") if isinstance(item.get("fullTextUrlList"), dict) else []
        if isinstance(full_text_urls, list):
            for full in full_text_urls:
                if isinstance(full, dict) and full.get("availabilityCode") in {"OA", "F"}:
                    open_copy = full.get("url", "")
                    break
        records.append({
            "source": "europepmc",
            "source_id": first_text(item.get("id"), item.get("source")),
            "title": item.get("title", ""),
            "creators": item.get("authorString", ""),
            "year": item.get("pubYear", ""),
            "container": item.get("journalTitle", ""),
            "doi": item.get("doi", ""),
            "pmid": item.get("pmid", ""),
            "pmcid": item.get("pmcid", ""),
            "landing_url": first_text(item.get("doiUrl"), item.get("fullTextUrl")),
            "open_copy_url": open_copy,
            "summary": item.get("abstractText", ""),
            "query": query,
            "raw_metadata": item,
        })
    return records, {"endpoint": url, "count": len(records)}


def fetch_semantic_scholar(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = {
        "query": query,
        "limit": str(min(limit, 100)),
        "fields": "paperId,title,authors,year,venue,externalIds,url,abstract,openAccessPdf,citationCount",
    }
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urlencode(params)
    headers = {}
    api_key = env_value("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    data = http_json(url, headers=headers, timeout=timeout)
    records = []
    for item in data.get("data", [])[:limit]:
        if not isinstance(item, dict):
            continue
        ids = item.get("externalIds") if isinstance(item.get("externalIds"), dict) else {}
        pdf = item.get("openAccessPdf") if isinstance(item.get("openAccessPdf"), dict) else {}
        authors = "; ".join(clean_text(author.get("name", "")) for author in item.get("authors", [])[:12] if isinstance(author, dict))
        records.append({
            "source": "semantic-scholar",
            "source_id": item.get("paperId", ""),
            "title": item.get("title", ""),
            "creators": authors,
            "year": item.get("year", ""),
            "container": item.get("venue", ""),
            "doi": ids.get("DOI", ""),
            "pmid": ids.get("PubMed", ""),
            "pmcid": ids.get("PubMedCentral", ""),
            "arxiv_id": ids.get("ArXiv", ""),
            "landing_url": item.get("url", ""),
            "open_copy_url": pdf.get("url", ""),
            "summary": item.get("abstract", ""),
            "query": query,
            "raw_metadata": item,
        })
    return records, {"endpoint": url, "count": len(records)}


def fetch_ncbi(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """PubMed via NCBI E-utilities: esearch for ids, esummary for metadata."""
    common: dict[str, Any] = {"db": "pubmed", "retmode": "json", "tool": "plug-n-skills-scientific-research"}
    api_key = env_value("NCBI_API_KEY")
    if api_key:
        common["api_key"] = api_key
    if contact_email:
        common["email"] = contact_email
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urlencode(
        {**common, "term": query, "retmax": str(min(limit, 100)), "sort": "relevance"}
    )
    search_data = http_json(search_url, timeout=timeout)
    ids = search_data.get("esearchresult", {}).get("idlist", [])
    ids = [clean_text(item) for item in ids if clean_text(item)][:limit]
    if not ids:
        return [], {"endpoint": search_url, "count": 0}
    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?" + urlencode(
        {**common, "id": ",".join(ids)}
    )
    summary_data = http_json(summary_url, timeout=timeout)
    result = summary_data.get("result", {}) if isinstance(summary_data.get("result"), dict) else {}
    records = []
    for uid in ids:
        item = result.get(uid)
        if not isinstance(item, dict):
            continue
        doi = ""
        pmcid = ""
        for ident in item.get("articleids", []) if isinstance(item.get("articleids"), list) else []:
            if not isinstance(ident, dict):
                continue
            id_type = clean_text(ident.get("idtype", "")).lower()
            if id_type == "doi":
                doi = clean_text(ident.get("value", ""))
            elif id_type == "pmc":
                pmcid = clean_text(ident.get("value", ""))
        authors = "; ".join(
            clean_text(author.get("name", ""))
            for author in (item.get("authors") or [])[:12]
            if isinstance(author, dict)
        )
        records.append({
            "source": "ncbi",
            "source_id": uid,
            "title": item.get("title", ""),
            "creators": authors,
            "year": clean_text(item.get("pubdate", ""))[:4],
            "container": first_text(item.get("fulljournalname"), item.get("source")),
            "doi": doi,
            "pmid": uid,
            "pmcid": pmcid,
            "landing_url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
            "open_copy_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/" if pmcid else "",
            "summary": "",
            "query": query,
            "raw_metadata": item,
        })
    return records, {"endpoint": search_url, "count": len(records)}


def fetch_core(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """CORE v3 works search; requires a free CORE_API_KEY."""
    api_key = env_value("CORE_API_KEY")
    if not api_key:
        raise RuntimeError("core_api_key_required: set CORE_API_KEY (free registration at core.ac.uk)")
    url = "https://api.core.ac.uk/v3/search/works?" + urlencode({"q": query, "limit": str(min(limit, 100))})
    data = http_json(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
    records = []
    for item in data.get("results", [])[:limit]:
        if not isinstance(item, dict):
            continue
        authors = "; ".join(
            clean_text(author.get("name", ""))
            for author in (item.get("authors") or [])[:12]
            if isinstance(author, dict)
        )
        records.append({
            "source": "core",
            "source_id": clean_text(item.get("id", "")),
            "title": item.get("title", ""),
            "creators": authors,
            "year": clean_text(item.get("yearPublished", "")),
            "container": first_text(item.get("publisher")),
            "doi": item.get("doi", ""),
            "landing_url": first_text(item.get("doi") and f"https://doi.org/{normalize_doi(item.get('doi'))}", item.get("downloadUrl")),
            "open_copy_url": item.get("downloadUrl", ""),
            "summary": item.get("abstract", ""),
            "query": query,
            "raw_metadata": {k: v for k, v in item.items() if k != "fullText"},
        })
    return records, {"endpoint": url, "count": len(records)}


def fetch_dblp(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """DBLP computer-science bibliography; no key required."""
    url = "https://dblp.org/search/publ/api?" + urlencode({"q": query, "format": "json", "h": str(min(limit, 100))})
    data = http_json(url, timeout=timeout)
    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    if isinstance(hits, dict):
        hits = [hits]
    records = []
    for hit in hits[:limit] if isinstance(hits, list) else []:
        info = hit.get("info") if isinstance(hit, dict) and isinstance(hit.get("info"), dict) else {}
        if not info:
            continue
        raw_authors = info.get("authors", {})
        author_items = raw_authors.get("author", []) if isinstance(raw_authors, dict) else []
        if isinstance(author_items, dict):
            author_items = [author_items]
        authors = "; ".join(
            clean_text(author.get("text", "") if isinstance(author, dict) else author)
            for author in author_items[:12]
        )
        records.append({
            "source": "dblp",
            "source_id": clean_text(info.get("key", "")),
            "title": info.get("title", ""),
            "creators": authors,
            "year": clean_text(info.get("year", "")),
            "container": info.get("venue", ""),
            "doi": info.get("doi", ""),
            "landing_url": first_text(info.get("ee"), info.get("url")),
            "open_copy_url": info.get("ee", "") if clean_text(info.get("access", "")) == "open" else "",
            "summary": "",
            "query": query,
            "raw_metadata": info,
        })
    return records, {"endpoint": url, "count": len(records)}


def fetch_doaj(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """DOAJ open-access article search; no key required."""
    url = f"https://doaj.org/api/search/articles/{quote_component(query)}?pageSize={min(limit, 100)}"
    data = http_json(url, timeout=timeout)
    records = []
    for item in data.get("results", [])[:limit]:
        bib = item.get("bibjson") if isinstance(item, dict) and isinstance(item.get("bibjson"), dict) else {}
        if not bib:
            continue
        doi = ""
        for ident in bib.get("identifier", []) if isinstance(bib.get("identifier"), list) else []:
            if isinstance(ident, dict) and clean_text(ident.get("type", "")).lower() == "doi":
                doi = clean_text(ident.get("id", ""))
                break
        fulltext = ""
        for link in bib.get("link", []) if isinstance(bib.get("link"), list) else []:
            if isinstance(link, dict) and clean_text(link.get("type", "")).lower() == "fulltext":
                fulltext = clean_text(link.get("url", ""))
                break
        authors = "; ".join(
            clean_text(author.get("name", ""))
            for author in (bib.get("author") or [])[:12]
            if isinstance(author, dict)
        )
        journal = bib.get("journal") if isinstance(bib.get("journal"), dict) else {}
        records.append({
            "source": "doaj",
            "source_id": clean_text(item.get("id", "")),
            "title": bib.get("title", ""),
            "creators": authors,
            "year": clean_text(bib.get("year", "")),
            "container": journal.get("title", ""),
            "doi": doi,
            "landing_url": f"https://doi.org/{normalize_doi(doi)}" if doi else fulltext,
            "open_copy_url": fulltext,
            "summary": bib.get("abstract", ""),
            "query": query,
            "raw_metadata": bib,
        })
    return records, {"endpoint": url, "count": len(records)}


DOI_QUERY_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)


def strip_omid_brackets(value: Any) -> str:
    return clean_text(re.sub(r"\s*\[[^\]]*\]", "", clean_text(value)))


def fetch_opencitations(query: str, limit: int, timeout: float, contact_email: str = "") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """OpenCitations Meta metadata lookup; the query must be a DOI."""
    match = DOI_QUERY_RE.match(clean_text(query))
    if not match:
        raise RuntimeError("opencitations_requires_doi_query: pass a DOI (10.xxxx/...) as the query")
    doi = match.group(1)
    url = f"https://opencitations.net/meta/api/v1/metadata/doi:{quote_component(doi)}"
    headers = {}
    token = env_value("OPENCITATIONS_ACCESS_TOKEN")
    if token:
        headers["authorization"] = token
    raw = http_text(url, headers={"Accept": "application/json", **headers}, timeout=timeout)
    data = json.loads(raw) if raw.strip() else []
    records = []
    for item in data[:limit] if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        records.append({
            "source": "opencitations",
            "source_id": clean_text(item.get("id", "")),
            "title": item.get("title", ""),
            "creators": strip_omid_brackets(item.get("author", "")),
            "year": clean_text(item.get("pub_date", ""))[:4],
            "container": strip_omid_brackets(item.get("venue", "")),
            "doi": doi,
            "landing_url": f"https://doi.org/{doi}",
            "summary": "",
            "query": query,
            "raw_metadata": item,
        })
    return records, {"endpoint": url, "count": len(records)}


FETCHERS = {
    "openalex": fetch_openalex,
    "arxiv": fetch_arxiv,
    "crossref": fetch_crossref,
    "europepmc": fetch_europepmc,
    "semantic-scholar": fetch_semantic_scholar,
    "ncbi": fetch_ncbi,
    "core": fetch_core,
    "dblp": fetch_dblp,
    "doaj": fetch_doaj,
    "opencitations": fetch_opencitations,
}


def env_value(name: str) -> str:
    try:
        import os

        return os.environ.get(name, "")
    except Exception:
        return ""


def plan_payload(args: argparse.Namespace) -> dict[str, Any]:
    sources = args.source or DEFAULT_SOURCES
    return {
        "schema": SCHEMA_PLAN,
        "created_at_utc": utc_now(),
        "topic": args.topic,
        "questions": args.question or [args.topic],
        "sources": sources,
        "limits": {
            "per_source": args.per_source,
            "total_records": args.total_records,
            "download_limit": args.download_limit,
        },
        "contact_email": args.contact_email,
        "policy": {
            "open_copy_only": True,
            "no_paywall_bypass": True,
            "rate_limit_degrade": True,
            "record_blocked_sources": True,
        },
        "outputs": {
            "layout": [
                "01_index/records.csv",
                "01_index/records.jsonl",
                "01_index/download_status.csv",
                "01_index/query_log.jsonl",
                "02_sources/pdf",
                "02_sources/metadata",
                "03_runs",
                "04_knowledge_base/cards",
                "05_reports",
                "runtime_distillation",
            ]
        },
        "quality_gates": {
            "min_records": min(args.total_records, max(1, args.per_source)),
            "min_sources": min(2, len(sources)),
            "claims_require_evidence": True,
        },
    }


def validate_plan_payload(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if plan.get("schema") != SCHEMA_PLAN:
        errors.append("schema_must_be_scientific_research.plan.v1")
    if not isinstance(plan.get("topic"), str) or not plan["topic"].strip():
        errors.append("topic_required")
    if not isinstance(plan.get("questions"), list) or not all(isinstance(q, str) and q.strip() for q in plan.get("questions", [])):
        errors.append("questions_must_be_non_empty_strings")
    sources = plan.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources_required")
    else:
        unknown = sorted({str(source) for source in sources} - ALLOWED_SOURCES)
        if unknown:
            errors.append("unknown_sources:" + ",".join(unknown))
    limits = plan.get("limits")
    if not isinstance(limits, dict):
        errors.append("limits_required")
    else:
        for field in ["per_source", "total_records", "download_limit"]:
            if not isinstance(limits.get(field), int) or limits[field] < 0:
                errors.append(f"limits.{field}_non_negative_int_required")
        if isinstance(limits.get("per_source"), int) and limits["per_source"] <= 0:
            errors.append("limits.per_source_positive_required")
    policy = plan.get("policy")
    if not isinstance(policy, dict) or policy.get("no_paywall_bypass") is not True or policy.get("open_copy_only") is not True:
        errors.append("policy_must_require_open_copy_only_and_no_paywall_bypass")
    return errors


def command_plan(args: argparse.Namespace) -> int:
    payload = plan_payload(args)
    write_json(Path(args.out), payload)
    print(f"wrote_plan={Path(args.out).resolve()}")
    return 0


def command_validate_plan(args: argparse.Namespace) -> int:
    plan = read_json(Path(args.plan))
    errors = validate_plan_payload(plan)
    if errors:
        for error in errors:
            print(f"error={error}")
        return 1
    print("valid=1")
    return 0


def ensure_layout(out_dir: Path) -> None:
    for rel in [
        "01_index",
        "02_sources/pdf",
        "02_sources/metadata",
        "03_runs",
        "04_knowledge_base/cards",
        "05_reports",
        "runtime_distillation",
    ]:
        (out_dir / rel).mkdir(parents=True, exist_ok=True)


def command_search(args: argparse.Namespace) -> int:
    plan = read_json(Path(args.plan))
    errors = validate_plan_payload(plan)
    if errors:
        for error in errors:
            print(f"error={error}")
        return 1
    out_dir = Path(args.out_dir)
    ensure_layout(out_dir)
    source_status = load_source_status(out_dir)
    per_source = args.per_source or int(plan["limits"]["per_source"])
    contact_email = clean_text(args.contact_email or plan.get("contact_email", ""))
    queries = plan["questions"] or [plan["topic"]]
    records: list[dict[str, Any]] = []
    query_logs: list[dict[str, Any]] = []
    for source in plan["sources"]:
        fetcher = FETCHERS.get(source)
        if fetcher is None:
            status = "skipped"
            error = "source_not_implemented"
            update_source_failure(source_status, source, status, error, "")
            for query in queries:
                query_logs.append(log_row(source, query, status, 0, "", error))
            continue
        for query in queries:
            status = "ok"
            error = ""
            endpoint = ""
            source_records: list[dict[str, Any]] = []
            cooling_down, cooldown_until = is_source_cooling_down(source_status, source)
            if cooling_down:
                query_logs.append(log_row(
                    source,
                    query,
                    "cooldown",
                    0,
                    "",
                    f"local_cooldown_until_utc={cooldown_until}",
                ))
                continue
            try:
                source_records, meta = fetcher(query, per_source, args.timeout, contact_email)
                endpoint = clean_text(meta.get("endpoint", ""))
                records.extend(source_records)
                update_source_success(source_status, source, endpoint, len(source_records))
            except (RuntimeError, ScholarlyHttpError) as exc:
                status, code, retry_after = classify_fetch_error(source, exc)
                endpoint = clean_text(getattr(exc, "url", endpoint))
                error = str(exc)
                update_source_failure(source_status, source, status, error, endpoint, code, retry_after)
            except (TimeoutError, OSError, json.JSONDecodeError) as exc:
                status = "error"
                error = f"{type(exc).__name__}: {exc}"
                update_source_failure(source_status, source, status, error, endpoint)
            query_logs.append(log_row(source, query, status, len(source_records), endpoint, error))
            sleep_seconds = max(args.sleep_seconds, float(SOURCE_POLICIES.get(source, {}).get("min_interval_seconds", 0.0)))
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    # The index is provenance: merge into it, never rewrite it from one run.
    index_path = out_dir / "01_index" / "records.jsonl"
    existing = load_jsonl(index_path) if index_path.exists() else []
    # Existing records come first so prior provenance survives both dedupe
    # and the total-records cap.
    accepted, duplicates = dedupe_records(existing + records)
    total_limit = int(plan["limits"]["total_records"])
    dropped: list[dict[str, Any]] = []
    if len(accepted) > total_limit:
        dropped = accepted[total_limit:]
        accepted = accepted[:total_limit]
        append_jsonl(
            out_dir / "03_runs" / "dropped-over-limit.jsonl",
            [
                {
                    "key": item.get("key", ""),
                    "title": item.get("title", ""),
                    "source": item.get("source", ""),
                    "query": item.get("query", ""),
                    "dropped_at_utc": utc_now(),
                }
                for item in dropped
            ],
        )
    new_index_text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in accepted)
    old_index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    index_changed = new_index_text != old_index_text
    index_backup = ""
    if existing and index_changed:
        backup_path = out_dir / "03_runs" / f"records-pre-search-{utc_now().replace(':', '').replace('-', '')}.jsonl"
        backup_path.write_text(old_index_text, encoding="utf-8")
        index_backup = str(backup_path.resolve())
    if index_changed:
        write_records(out_dir, accepted)
        write_download_status(out_dir, accepted)
    append_jsonl(out_dir / "01_index" / "query_log.jsonl", query_logs)
    write_source_status(out_dir, source_status)
    summary = {
        "schema": "scientific_research.search_summary.v2",
        "generated_at_utc": utc_now(),
        "plan": str(Path(args.plan).resolve()),
        "out_dir": str(out_dir.resolve()),
        "records_existing": len(existing),
        "records_fetched": len(records),
        "records_seen": len(records),
        "records_accepted": len(accepted),
        "records_dropped_over_limit": len(dropped),
        "dropped_records_path": str((out_dir / "03_runs" / "dropped-over-limit.jsonl").resolve()) if dropped else "",
        "index_changed": index_changed,
        "index_backup_path": index_backup,
        "duplicates": duplicates,
        "sources": sorted({record["source"] for record in accepted}),
        "query_statuses": query_logs,
        "source_status_path": str(source_status_path(out_dir).resolve()),
    }
    write_json(out_dir / "03_runs" / "search-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def log_row(source: str, query: str, status: str, count: int, endpoint: str, error: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA_QUERY_LOG,
        "queried_at_utc": utc_now(),
        "source": source,
        "query": query,
        "status": status,
        "records_returned": count,
        "endpoint": endpoint,
        "error": error,
    }


def planned_source_status(source: str, saved: dict[str, Any]) -> dict[str, Any]:
    entry = saved.get("sources", {}).get(source, {}) if isinstance(saved.get("sources"), dict) else {}
    cooling_down, cooldown_until = is_source_cooling_down(saved, source)
    status = "cooldown" if cooling_down else clean_text(entry.get("status", "available")) or "available"
    payload = {
        "source": source,
        "status": status,
        "cooldown_until_utc": cooldown_until or clean_text(entry.get("cooldown_until_utc", "")),
        "fallbacks": SOURCE_POLICIES.get(source, {}).get("fallbacks", []),
        "last_error": clean_text(entry.get("last_error", "")),
        "last_http_status": entry.get("last_http_status", 0),
    }
    if source == "openalex":
        payload["api_key_configured"] = bool(env_value("OPENALEX_API_KEY"))
        payload["api_key_policy"] = "required_for_scale_or_after_free_credits"
        payload["max_per_page"] = SOURCE_POLICIES["openalex"]["max_per_page"]
    if source == "semantic-scholar":
        payload["api_key_configured"] = bool(env_value("SEMANTIC_SCHOLAR_API_KEY"))
    if source == "core":
        payload["api_key_configured"] = bool(env_value("CORE_API_KEY"))
        payload["api_key_policy"] = "required"
    if source == "ncbi":
        payload["api_key_configured"] = bool(env_value("NCBI_API_KEY"))
        payload["api_key_policy"] = "optional_raises_rate_limit"
    if source == "opencitations":
        payload["query_contract"] = "doi_only"
    if source == "arxiv":
        payload["min_interval_seconds"] = SOURCE_POLICIES["arxiv"]["min_interval_seconds"]
    return payload


def command_source_status(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir) if args.out_dir else Path(".")
    saved = load_source_status(out_dir)
    sources = args.source or DEFAULT_SOURCES
    payload = {
        "schema": SCHEMA_SOURCE_STATUS,
        "generated_at_utc": utc_now(),
        "out_dir": str(out_dir.resolve()) if args.out_dir else "",
        "sources": {source: planned_source_status(source, saved) for source in sources},
    }
    if args.out:
        write_json(Path(args.out), payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def write_records(out_dir: Path, records: list[dict[str, Any]]) -> None:
    jsonl = out_dir / "01_index" / "records.jsonl"
    jsonl.write_text("", encoding="utf-8")
    append_jsonl(jsonl, records)
    csv_path = out_dir / "01_index" / "records.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECORD_FIELDS)
        writer.writeheader()
        for record in records:
            row = {}
            for field in RECORD_FIELDS:
                value = record.get(field, "")
                row[field] = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            writer.writerow(row)


def write_download_status(out_dir: Path, records: list[dict[str, Any]]) -> None:
    fields = ["key", "status", "source_url", "local_pdf_path", "error", "checked_at"]
    with (out_dir / "01_index" / "download_status.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            url = clean_text(record.get("open_copy_url", ""))
            writer.writerow({
                "key": record["key"],
                "status": "planned-open-copy" if url else "open-copy-not-found",
                "source_url": url,
                "local_pdf_path": "",
                "error": "",
                "checked_at": utc_now(),
            })


def command_dedupe(args: argparse.Namespace) -> int:
    records = load_jsonl(Path(args.records))
    accepted, duplicates = dedupe_records(records)
    out = Path(args.out)
    out.write_text("", encoding="utf-8")
    append_jsonl(out, accepted)
    print(json.dumps({"records_in": len(records), "records_out": len(accepted), "duplicates": duplicates}, sort_keys=True))
    return 0


def command_screening_summary(args: argparse.Namespace) -> int:
    records = load_jsonl(Path(args.records))
    decisions = load_jsonl(Path(args.decisions)) if args.decisions else []
    record_keys = {clean_text(record.get("key", "")) for record in records}
    failures: list[str] = []
    decision_counts = {decision: 0 for decision in sorted(SCREENING_DECISIONS)}
    exclusion_reasons: dict[str, int] = {}
    screened_keys: set[str] = set()
    unknown_keys: set[str] = set()

    for index, row in enumerate(decisions):
        key = clean_text(row.get("record_key", row.get("key", "")))
        decision = clean_text(row.get("decision", "")).lower()
        reason = clean_text(row.get("reason", "unspecified")) or "unspecified"
        if not key:
            failures.append(f"decision-{index+1:03d}:missing_record_key")
            continue
        if key not in record_keys:
            unknown_keys.add(key)
        if decision not in SCREENING_DECISIONS:
            failures.append(f"{key}:invalid_decision")
            continue
        screened_keys.add(key)
        decision_counts[decision] += 1
        if decision == "exclude":
            exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1

    if unknown_keys:
        failures.append("unknown_record_keys:" + ",".join(sorted(unknown_keys)))
    if not decisions:
        failures.append("no_screening_decisions")

    payload = {
        "schema": SCHEMA_SCREENING,
        "generated_at_utc": utc_now(),
        "passed": not failures,
        "failures": failures,
        "identified_records": len(records),
        "screened_records": len(screened_keys),
        "unscreened_records": len(record_keys - screened_keys),
        "included_records": decision_counts["include"],
        "excluded_records": decision_counts["exclude"],
        "maybe_records": decision_counts["maybe"],
        "duplicate_records": decision_counts["duplicate"],
        "exclusion_reasons": dict(sorted(exclusion_reasons.items())),
    }
    write_json(Path(args.out), payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["passed"] else 1


def command_quality_gate(args: argparse.Namespace) -> int:
    records = load_jsonl(Path(args.records))
    claims = load_jsonl(Path(args.claims)) if args.claims else []
    record_keys = {clean_text(record.get("key", "")) for record in records}
    sources = {clean_text(record.get("source", "")) for record in records if record.get("source")}
    min_records = args.min_records
    min_sources = args.min_sources
    if args.plan:
        plan = read_json(Path(args.plan))
        gates = plan.get("quality_gates", {}) if isinstance(plan.get("quality_gates"), dict) else {}
        if isinstance(gates.get("min_records"), int):
            min_records = max(min_records, gates["min_records"])
        if isinstance(gates.get("min_sources"), int):
            min_sources = max(min_sources, gates["min_sources"])
    excluded_keys: set[str] = set()
    if args.decisions:
        for row in load_jsonl(Path(args.decisions)):
            if clean_text(row.get("decision", "")).lower() == "exclude":
                key = clean_text(row.get("record_key", row.get("key", "")))
                if key:
                    excluded_keys.add(key)
    failures: list[str] = []
    if len(records) < min_records:
        failures.append(f"record_count_below_min:{len(records)}<{min_records}")
    if len(sources) < min_sources:
        failures.append(f"source_count_below_min:{len(sources)}<{min_sources}")
    # A gate that passes with nothing to check is an illusion of rigor.
    if not claims and not args.allow_empty_claims:
        failures.append("no_claims_provided")
    unsupported_claims: list[str] = []
    for index, claim in enumerate(claims):
        claim_id = clean_text(claim.get("claim_id", f"claim-{index+1:03d}"))
        evidence_keys = claim.get("evidence_keys", [])
        source_refs = claim.get("source_refs", [])
        if not isinstance(evidence_keys, list):
            evidence_keys = []
        if not isinstance(source_refs, list):
            source_refs = []
        evidence_key_set = {clean_text(key) for key in evidence_keys if clean_text(key)}
        if not clean_text(claim.get("claim", "")):
            unsupported_claims.append(claim_id + ":missing_claim_text")
        if not evidence_key_set and not any(clean_text(ref) for ref in source_refs):
            unsupported_claims.append(claim_id + ":missing_evidence")
        missing_keys = sorted(evidence_key_set - record_keys)
        if missing_keys:
            unsupported_claims.append(claim_id + ":missing_record_keys:" + ",".join(missing_keys))
        excluded_cited = sorted(evidence_key_set & excluded_keys)
        if excluded_cited:
            unsupported_claims.append(claim_id + ":cites_excluded_record:" + ",".join(excluded_cited))
        if clean_text(claim.get("confidence", "")) not in CONFIDENCE:
            unsupported_claims.append(claim_id + ":invalid_confidence")
        if not clean_text(claim.get("limitations", "")):
            unsupported_claims.append(claim_id + ":missing_limitations")
    if unsupported_claims:
        failures.extend("unsupported_claim:" + item for item in unsupported_claims)
    payload = {
        "schema": SCHEMA_QUALITY,
        "generated_at_utc": utc_now(),
        "passed": not failures,
        "failures": failures,
        "records": len(records),
        "sources": sorted(sources),
        "claims": len(claims),
        "min_records": min_records,
        "min_sources": min_sources,
        "excluded_records_checked": len(excluded_keys),
        "unsupported_claims": unsupported_claims,
    }
    write_json(Path(args.out), payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded scholarly research helper for the Scientific Research Codex plugin.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Write a validated research plan contract.")
    plan.add_argument("--topic", required=True)
    plan.add_argument("--question", action="append", default=[])
    plan.add_argument("--source", action="append", choices=sorted(ALLOWED_SOURCES))
    plan.add_argument("--per-source", type=int, default=20)
    plan.add_argument("--total-records", type=int, default=100)
    plan.add_argument("--download-limit", type=int, default=0)
    plan.add_argument("--contact-email", default="")
    plan.add_argument("--out", required=True)
    plan.set_defaults(func=command_plan)

    validate = sub.add_parser("validate-plan", help="Validate a research plan contract.")
    validate.add_argument("plan")
    validate.set_defaults(func=command_validate_plan)

    search = sub.add_parser("search", help="Execute bounded public scholarly API searches.")
    search.add_argument("--plan", required=True)
    search.add_argument("--out-dir", required=True)
    search.add_argument("--per-source", type=int, default=0)
    search.add_argument("--timeout", type=float, default=30.0)
    search.add_argument("--sleep-seconds", type=float, default=1.0)
    search.add_argument("--contact-email", default="")
    search.set_defaults(func=command_search)

    status = sub.add_parser("source-status", help="Report source routing, credentials, and local cooldown state.")
    status.add_argument("--source", action="append", choices=sorted(ALLOWED_SOURCES))
    status.add_argument("--out-dir", default="")
    status.add_argument("--out", default="")
    status.set_defaults(func=command_source_status)

    dedupe = sub.add_parser("dedupe", help="Deduplicate a records JSONL file.")
    dedupe.add_argument("--records", required=True)
    dedupe.add_argument("--out", required=True)
    dedupe.set_defaults(func=command_dedupe)

    screening = sub.add_parser("screening-summary", help="Summarize PRISMA-style screening decisions for a corpus.")
    screening.add_argument("--records", required=True)
    screening.add_argument("--decisions", default="")
    screening.add_argument("--out", required=True)
    screening.set_defaults(func=command_screening_summary)

    quality = sub.add_parser("quality-gate", help="Validate record and claim evidence support.")
    quality.add_argument("--records", required=True)
    quality.add_argument("--claims", default="")
    quality.add_argument("--decisions", default="", help="Screening decisions JSONL; claims citing excluded records fail.")
    quality.add_argument("--plan", default="", help="Research plan JSON; enforces the plan's own quality_gates thresholds.")
    quality.add_argument("--out", required=True)
    quality.add_argument("--min-records", type=int, default=1)
    quality.add_argument("--min-sources", type=int, default=1)
    quality.add_argument(
        "--allow-empty-claims",
        action="store_true",
        help="Permit a passing gate with zero claims (off by default: an empty gate proves nothing).",
    )
    quality.set_defaults(func=command_quality_gate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
