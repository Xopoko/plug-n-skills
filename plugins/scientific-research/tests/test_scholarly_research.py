from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "scientific-research" / "scripts" / "scholarly_research.py"
TEST_ROOT = Path("/tmp/scientific-research-plugin-tests")


def load_module():
    spec = importlib.util.spec_from_file_location("scholarly_research", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def fresh_dir(name: str) -> Path:
    path = TEST_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_plan_validation_accepts_generated_plan() -> None:
    mod = load_module()
    out = fresh_dir("plan") / "plan.json"
    assert mod.main(["plan", "--topic", "source grounded evaluation", "--question", "What methods are used?", "--out", str(out)]) == 0
    plan = json.loads(out.read_text(encoding="utf-8"))
    assert mod.validate_plan_payload(plan) == []
    assert plan["policy"]["open_copy_only"] is True


def test_dedupe_prefers_doi_and_title() -> None:
    mod = load_module()
    records = [
        {"source": "openalex", "doi": "https://doi.org/10.1000/ABC", "title": "Same Paper"},
        {"source": "crossref", "doi": "10.1000/abc", "title": "Same Paper"},
        {"source": "arxiv", "title": "Different Paper"},
    ]
    accepted, duplicates = mod.dedupe_records(records)
    assert len(accepted) == 2
    assert duplicates == 1
    assert accepted[0]["key"] == "doi-10-1000-abc"


def test_quality_gate_requires_claim_evidence() -> None:
    mod = load_module()
    tmp_path = fresh_dir("quality")
    records = tmp_path / "records.jsonl"
    records.write_text(
        json.dumps({"schema": mod.SCHEMA_RECORD, "key": "doi-10-1-example", "source": "crossref"}) + "\n",
        encoding="utf-8",
    )
    claims = tmp_path / "claims.jsonl"
    claims.write_text(
        json.dumps(
            {
                "claim_id": "claim-001",
                "claim": "Example claim",
                "evidence_keys": ["doi-10-1-example"],
                "confidence": "medium",
                "limitations": "Single source fixture.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "gate.json"
    rc = mod.main(["quality-gate", "--records", str(records), "--claims", str(claims), "--out", str(out)])
    assert rc == 0
    gate = json.loads(out.read_text(encoding="utf-8"))
    assert gate["passed"] is True


def test_screening_summary_counts_decisions_and_reasons() -> None:
    mod = load_module()
    tmp_path = fresh_dir("screening")
    records = tmp_path / "records.jsonl"
    records.write_text(
        "\n".join(
            [
                json.dumps({"schema": mod.SCHEMA_RECORD, "key": "doi-10-1-example", "source": "crossref"}),
                json.dumps({"schema": mod.SCHEMA_RECORD, "key": "title-second-paper", "source": "openalex"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    decisions = tmp_path / "screening-decisions.jsonl"
    decisions.write_text(
        "\n".join(
            [
                json.dumps({"record_key": "doi-10-1-example", "decision": "include", "reason": "Meets scope."}),
                json.dumps({"record_key": "title-second-paper", "decision": "exclude", "reason": "Wrong population."}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "screening_summary.json"
    rc = mod.main(["screening-summary", "--records", str(records), "--decisions", str(decisions), "--out", str(out)])
    assert rc == 0
    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["identified_records"] == 2
    assert summary["included_records"] == 1
    assert summary["excluded_records"] == 1
    assert summary["exclusion_reasons"] == {"Wrong population.": 1}


def test_openalex_fetch_uses_current_per_page_limit() -> None:
    mod = load_module()
    captured: dict[str, str] = {}
    original_http_json = mod.http_json

    def fake_http_json(url: str, **kwargs):
        captured["url"] = url
        return {"results": [], "meta": {"count": 0}}

    try:
        mod.http_json = fake_http_json
        records, meta = mod.fetch_openalex("machine learning", 150, 1.0)
    finally:
        mod.http_json = original_http_json

    assert records == []
    assert meta["count"] == 0
    assert "per_page=100" in captured["url"]
    assert "per-page" not in captured["url"]


def test_search_records_cooldown_and_continues_with_fallback() -> None:
    mod = load_module()
    tmp_path = fresh_dir("cooldown-fallback")
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema": mod.SCHEMA_PLAN,
                "created_at_utc": mod.utc_now(),
                "topic": "rate limit test",
                "questions": ["rate limit test"],
                "sources": ["openalex", "crossref"],
                "limits": {"per_source": 5, "total_records": 10, "download_limit": 0},
                "contact_email": "",
                "policy": {"open_copy_only": True, "no_paywall_bypass": True},
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "corpus"
    original_fetchers = mod.FETCHERS.copy()

    def fail_openalex(query: str, limit: int, timeout: float, contact_email: str = ""):
        raise mod.ScholarlyHttpError("https://api.openalex.org/works", 429, {"Retry-After": "120"}, "Rate limit exceeded")

    def ok_crossref(query: str, limit: int, timeout: float, contact_email: str = ""):
        return (
            [{"source": "crossref", "doi": "10.1000/example", "title": "Fallback Paper", "query": query}],
            {"endpoint": "https://api.crossref.org/works", "count": 1},
        )

    try:
        mod.FETCHERS["openalex"] = fail_openalex
        mod.FETCHERS["crossref"] = ok_crossref
        rc = mod.main(["search", "--plan", str(plan), "--out-dir", str(out_dir), "--sleep-seconds", "0"])
    finally:
        mod.FETCHERS.clear()
        mod.FETCHERS.update(original_fetchers)

    assert rc == 0
    summary = json.loads((out_dir / "03_runs" / "search-summary.json").read_text(encoding="utf-8"))
    statuses = {row["source"]: row["status"] for row in summary["query_statuses"]}
    assert statuses == {"openalex": "cooldown", "crossref": "ok"}
    assert summary["records_accepted"] == 1
    source_status = json.loads((out_dir / "03_runs" / "source-status.json").read_text(encoding="utf-8"))
    assert source_status["sources"]["openalex"]["last_http_status"] == 429
    assert source_status["sources"]["openalex"]["cooldown_until_utc"]


def test_search_skips_source_during_local_cooldown() -> None:
    mod = load_module()
    tmp_path = fresh_dir("local-cooldown")
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema": mod.SCHEMA_PLAN,
                "created_at_utc": mod.utc_now(),
                "topic": "cooldown skip test",
                "questions": ["cooldown skip test"],
                "sources": ["openalex"],
                "limits": {"per_source": 5, "total_records": 10, "download_limit": 0},
                "contact_email": "",
                "policy": {"open_copy_only": True, "no_paywall_bypass": True},
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "corpus"
    (out_dir / "03_runs").mkdir(parents=True, exist_ok=True)
    (out_dir / "03_runs" / "source-status.json").write_text(
        json.dumps(
            {
                "schema": mod.SCHEMA_SOURCE_STATUS,
                "generated_at_utc": mod.utc_now(),
                "sources": {
                    "openalex": {
                        "status": "cooldown",
                        "cooldown_until_utc": mod.utc_from_now(600),
                        "last_error": "previous rate limit",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    original_fetchers = mod.FETCHERS.copy()

    def fail_if_called(query: str, limit: int, timeout: float, contact_email: str = ""):
        raise AssertionError("openalex fetcher should not be called during local cooldown")

    try:
        mod.FETCHERS["openalex"] = fail_if_called
        rc = mod.main(["search", "--plan", str(plan), "--out-dir", str(out_dir), "--sleep-seconds", "0"])
    finally:
        mod.FETCHERS.clear()
        mod.FETCHERS.update(original_fetchers)

    assert rc == 0
    summary = json.loads((out_dir / "03_runs" / "search-summary.json").read_text(encoding="utf-8"))
    assert summary["records_accepted"] == 0
    assert summary["query_statuses"][0]["status"] == "cooldown"
    assert "local_cooldown_until_utc=" in summary["query_statuses"][0]["error"]


def test_source_policies_only_reference_allowed_fallbacks() -> None:
    mod = load_module()
    for source, policy in mod.SOURCE_POLICIES.items():
        assert source in mod.ALLOWED_SOURCES
        assert set(policy.get("fallbacks", [])) <= mod.ALLOWED_SOURCES


def test_openalex_409_is_auth_required() -> None:
    mod = load_module()
    exc = mod.ScholarlyHttpError("https://api.openalex.org/works", 409, {}, "API key required")

    status, code, retry_after = mod.classify_fetch_error("openalex", exc)

    assert status == "auth_required"
    assert code == 409
    assert retry_after == 0


if __name__ == "__main__":
    test_plan_validation_accepts_generated_plan()
    test_dedupe_prefers_doi_and_title()
    test_quality_gate_requires_claim_evidence()
    test_screening_summary_counts_decisions_and_reasons()
    test_openalex_fetch_uses_current_per_page_limit()
    test_search_records_cooldown_and_continues_with_fallback()
    test_search_skips_source_during_local_cooldown()
    test_source_policies_only_reference_allowed_fallbacks()
    test_openalex_409_is_auth_required()
    print("direct_tests=passed")
