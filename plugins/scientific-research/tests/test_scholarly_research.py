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


def _plan_file(mod, tmp_path: Path, sources: list[str], total_records: int = 10, **gates) -> Path:
    plan = tmp_path / "plan.json"
    payload = {
        "schema": mod.SCHEMA_PLAN,
        "created_at_utc": mod.utc_now(),
        "topic": "merge test",
        "questions": ["merge test"],
        "sources": sources,
        "limits": {"per_source": 5, "total_records": total_records, "download_limit": 0},
        "contact_email": "",
        "policy": {"open_copy_only": True, "no_paywall_bypass": True},
    }
    if gates:
        payload["quality_gates"] = gates
    plan.write_text(json.dumps(payload), encoding="utf-8")
    return plan


def _fake_crossref(records: list[dict]):
    def fetch(query: str, limit: int, timeout: float, contact_email: str = ""):
        return (list(records), {"endpoint": "https://api.crossref.org/works", "count": len(records)})

    return fetch


def test_search_merges_existing_index_and_backs_it_up() -> None:
    mod = load_module()
    tmp_path = fresh_dir("merge-search")
    plan = _plan_file(mod, tmp_path, ["crossref"], total_records=10)
    out_dir = tmp_path / "corpus"
    original = mod.FETCHERS.copy()
    try:
        mod.FETCHERS["crossref"] = _fake_crossref(
            [{"source": "crossref", "doi": "10.1/a", "title": "Paper A", "query": "q"}]
        )
        assert mod.main(["search", "--plan", str(plan), "--out-dir", str(out_dir), "--sleep-seconds", "0"]) == 0
        mod.FETCHERS["crossref"] = _fake_crossref(
            [{"source": "crossref", "doi": "10.1/b", "title": "Paper B", "query": "q"}]
        )
        assert mod.main(["search", "--plan", str(plan), "--out-dir", str(out_dir), "--sleep-seconds", "0"]) == 0
    finally:
        mod.FETCHERS.clear()
        mod.FETCHERS.update(original)
    records = [json.loads(line) for line in (out_dir / "01_index" / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    dois = {record["doi"] for record in records}
    assert dois == {"10.1/a", "10.1/b"}, "second search must merge, not replace"
    backups = list((out_dir / "03_runs").glob("records-pre-search-*.jsonl"))
    assert backups, "prior index must be backed up before rewriting"
    summary = json.loads((out_dir / "03_runs" / "search-summary.json").read_text(encoding="utf-8"))
    assert summary["records_existing"] == 1
    assert summary["records_accepted"] == 2


def test_search_logs_records_dropped_over_limit() -> None:
    mod = load_module()
    tmp_path = fresh_dir("cap-drop")
    plan = _plan_file(mod, tmp_path, ["crossref"], total_records=1)
    out_dir = tmp_path / "corpus"
    original = mod.FETCHERS.copy()
    try:
        mod.FETCHERS["crossref"] = _fake_crossref(
            [
                {"source": "crossref", "doi": "10.1/a", "title": "Paper A", "query": "q"},
                {"source": "crossref", "doi": "10.1/b", "title": "Paper B", "query": "q"},
            ]
        )
        assert mod.main(["search", "--plan", str(plan), "--out-dir", str(out_dir), "--sleep-seconds", "0"]) == 0
    finally:
        mod.FETCHERS.clear()
        mod.FETCHERS.update(original)
    summary = json.loads((out_dir / "03_runs" / "search-summary.json").read_text(encoding="utf-8"))
    assert summary["records_dropped_over_limit"] == 1
    dropped = [json.loads(line) for line in (out_dir / "03_runs" / "dropped-over-limit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert dropped and dropped[0]["key"]


def test_quality_gate_fails_with_zero_claims() -> None:
    mod = load_module()
    tmp_path = fresh_dir("vacuous-gate")
    records = tmp_path / "records.jsonl"
    records.write_text(json.dumps({"key": "doi-10-1-x", "source": "crossref"}) + "\n", encoding="utf-8")
    out = tmp_path / "gate.json"
    rc = mod.main(["quality-gate", "--records", str(records), "--out", str(out)])
    assert rc == 1
    gate = json.loads(out.read_text(encoding="utf-8"))
    assert "no_claims_provided" in gate["failures"]
    rc = mod.main(["quality-gate", "--records", str(records), "--out", str(out), "--allow-empty-claims"])
    assert rc == 0


def test_quality_gate_requires_claim_text() -> None:
    mod = load_module()
    tmp_path = fresh_dir("claim-text")
    records = tmp_path / "records.jsonl"
    records.write_text(json.dumps({"key": "doi-10-1-x", "source": "crossref"}) + "\n", encoding="utf-8")
    claims = tmp_path / "claims.jsonl"
    claims.write_text(
        json.dumps({"claim_id": "c1", "evidence_keys": ["doi-10-1-x"], "confidence": "medium", "limitations": "fixture"}) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "gate.json"
    rc = mod.main(["quality-gate", "--records", str(records), "--claims", str(claims), "--out", str(out)])
    assert rc == 1
    gate = json.loads(out.read_text(encoding="utf-8"))
    assert any("missing_claim_text" in item for item in gate["unsupported_claims"])


def test_quality_gate_flags_claims_citing_excluded_records() -> None:
    mod = load_module()
    tmp_path = fresh_dir("excluded-cite")
    records = tmp_path / "records.jsonl"
    records.write_text(json.dumps({"key": "doi-10-1-x", "source": "crossref"}) + "\n", encoding="utf-8")
    decisions = tmp_path / "decisions.jsonl"
    decisions.write_text(json.dumps({"record_key": "doi-10-1-x", "decision": "exclude", "reason": "off-topic"}) + "\n", encoding="utf-8")
    claims = tmp_path / "claims.jsonl"
    claims.write_text(
        json.dumps({"claim_id": "c1", "claim": "Cites excluded.", "evidence_keys": ["doi-10-1-x"], "confidence": "medium", "limitations": "fixture"}) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "gate.json"
    rc = mod.main(["quality-gate", "--records", str(records), "--claims", str(claims), "--decisions", str(decisions), "--out", str(out)])
    assert rc == 1
    gate = json.loads(out.read_text(encoding="utf-8"))
    assert any("cites_excluded_record" in item for item in gate["unsupported_claims"])


def test_quality_gate_enforces_plan_thresholds() -> None:
    mod = load_module()
    tmp_path = fresh_dir("plan-thresholds")
    plan = _plan_file(mod, tmp_path, ["crossref"], min_records=5, min_sources=2, claims_require_evidence=True)
    records = tmp_path / "records.jsonl"
    records.write_text(json.dumps({"key": "doi-10-1-x", "source": "crossref"}) + "\n", encoding="utf-8")
    claims = tmp_path / "claims.jsonl"
    claims.write_text(
        json.dumps({"claim_id": "c1", "claim": "ok", "evidence_keys": ["doi-10-1-x"], "confidence": "medium", "limitations": "fixture"}) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "gate.json"
    rc = mod.main(["quality-gate", "--records", str(records), "--claims", str(claims), "--plan", str(plan), "--out", str(out)])
    assert rc == 1
    gate = json.loads(out.read_text(encoding="utf-8"))
    assert any(item.startswith("record_count_below_min") for item in gate["failures"])
    assert any(item.startswith("source_count_below_min") for item in gate["failures"])


def test_screening_summary_fails_with_zero_decisions() -> None:
    mod = load_module()
    tmp_path = fresh_dir("zero-screening")
    records = tmp_path / "records.jsonl"
    records.write_text(json.dumps({"key": "doi-10-1-x", "source": "crossref"}) + "\n", encoding="utf-8")
    out = tmp_path / "summary.json"
    rc = mod.main(["screening-summary", "--records", str(records), "--out", str(out)])
    assert rc == 1
    summary = json.loads(out.read_text(encoding="utf-8"))
    assert "no_screening_decisions" in summary["failures"]


def test_openalex_query_sanitizer_strips_wildcards() -> None:
    mod = load_module()
    assert mod.sanitize_openalex_query("Which methods are source-grounded?") == "Which methods are source-grounded"
    assert mod.sanitize_openalex_query("retrieval * evaluation ?") == "retrieval evaluation"


def test_http_400_classified_as_query_error_without_cooldown() -> None:
    mod = load_module()
    exc = mod.ScholarlyHttpError("https://api.openalex.org/works", 400, {"Retry-After": "50000"}, "Invalid query parameters error.")
    state, code, retry_after = mod.classify_fetch_error("openalex", exc)
    assert state == "query_error"
    assert code == 400
    assert retry_after == 0


def test_xml_unescape_handles_numeric_entities() -> None:
    mod = load_module()
    assert mod.xml_unescape("It&#39;s &#x41; test &amp; more") == "It's A test & more"


def test_search_rerun_is_idempotent() -> None:
    mod = load_module()
    tmp_path = fresh_dir("idempotent-search")
    plan = _plan_file(mod, tmp_path, ["crossref"], total_records=10)
    out_dir = tmp_path / "corpus"
    fake = _fake_crossref([{"source": "crossref", "doi": "10.1/a", "title": "Paper A", "query": "q"}])
    original = mod.FETCHERS.copy()
    try:
        mod.FETCHERS["crossref"] = fake
        assert mod.main(["search", "--plan", str(plan), "--out-dir", str(out_dir), "--sleep-seconds", "0"]) == 0
        first_index = (out_dir / "01_index" / "records.jsonl").read_text(encoding="utf-8")
        assert mod.main(["search", "--plan", str(plan), "--out-dir", str(out_dir), "--sleep-seconds", "0"]) == 0
        second_index = (out_dir / "01_index" / "records.jsonl").read_text(encoding="utf-8")
    finally:
        mod.FETCHERS.clear()
        mod.FETCHERS.update(original)
    assert first_index == second_index, "re-running the same search must not change the index"
    summary = json.loads((out_dir / "03_runs" / "search-summary.json").read_text(encoding="utf-8"))
    assert summary["index_changed"] is False
    assert summary["index_backup_path"] == ""
    assert list((out_dir / "03_runs").glob("records-pre-search-*.jsonl")) == [], "unchanged index must not accumulate backups"


def test_normalize_record_is_idempotent() -> None:
    mod = load_module()
    raw = {
        "source": "crossref",
        "doi": "https://doi.org/10.1000/ABC",
        "title": "  Some   Paper  ",
        "summary": "x" * 9000,
        "query": "q",
    }
    once = mod.normalize_record(raw)
    twice = mod.normalize_record(json.loads(json.dumps(once)))
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)
    assert len(once["summary"]) <= mod.MAX_SUMMARY_CHARS


def test_corrupt_index_fails_cleanly_named() -> None:
    mod = load_module()
    tmp_path = fresh_dir("corrupt-index")
    plan = _plan_file(mod, tmp_path, ["crossref"], total_records=10)
    out_dir = tmp_path / "corpus"
    (out_dir / "01_index").mkdir(parents=True, exist_ok=True)
    (out_dir / "01_index" / "records.jsonl").write_text('{"key": "ok"}\n{broken json\n', encoding="utf-8")
    original = mod.FETCHERS.copy()
    try:
        mod.FETCHERS["crossref"] = _fake_crossref([])
        try:
            mod.main(["search", "--plan", str(plan), "--out-dir", str(out_dir), "--sleep-seconds", "0"])
            raise AssertionError("expected SystemExit for corrupt index")
        except SystemExit as exc:
            assert "invalid_jsonl" in str(exc) and "line_2" in str(exc)
    finally:
        mod.FETCHERS.clear()
        mod.FETCHERS.update(original)
    assert (out_dir / "01_index" / "records.jsonl").read_text(encoding="utf-8").startswith('{"key": "ok"}'), "corrupt index must be left untouched for repair"


def test_corrupt_claims_fail_cleanly_named() -> None:
    mod = load_module()
    tmp_path = fresh_dir("corrupt-claims")
    records = tmp_path / "records.jsonl"
    records.write_text(json.dumps({"key": "doi-10-1-x", "source": "crossref"}) + "\n", encoding="utf-8")
    claims = tmp_path / "claims.jsonl"
    claims.write_text("{not json}\n", encoding="utf-8")
    out = tmp_path / "gate.json"
    try:
        mod.main(["quality-gate", "--records", str(records), "--claims", str(claims), "--out", str(out)])
        raise AssertionError("expected SystemExit for corrupt claims")
    except SystemExit as exc:
        assert "invalid_jsonl" in str(exc)


def test_malformed_plan_fails_cleanly_named() -> None:
    mod = load_module()
    tmp_path = fresh_dir("corrupt-plan")
    plan = tmp_path / "plan.json"
    plan.write_text("{broken", encoding="utf-8")
    try:
        mod.main(["validate-plan", str(plan)])
        raise AssertionError("expected SystemExit for corrupt plan")
    except SystemExit as exc:
        assert "invalid_json" in str(exc)


def test_fetch_ncbi_parses_esearch_and_esummary() -> None:
    mod = load_module()
    payloads = {
        "esearch": {"esearchresult": {"idlist": ["12345"]}},
        "esummary": {
            "result": {
                "uids": ["12345"],
                "12345": {
                    "title": "A PubMed Paper",
                    "pubdate": "2024 Mar 5",
                    "fulljournalname": "Journal of Tests",
                    "authors": [{"name": "Smith J"}, {"name": "Doe A"}],
                    "articleids": [
                        {"idtype": "doi", "value": "10.1000/pm1"},
                        {"idtype": "pmc", "value": "PMC999"},
                    ],
                },
            }
        },
    }
    original = mod.http_json
    mod.http_json = lambda url, **kw: payloads["esearch"] if "esearch.fcgi" in url else payloads["esummary"]
    try:
        records, meta = mod.fetch_ncbi("test query", 5, 10.0, "a@b.c")
    finally:
        mod.http_json = original
    assert len(records) == 1
    rec = records[0]
    assert rec["pmid"] == "12345" and rec["doi"] == "10.1000/pm1" and rec["pmcid"] == "PMC999"
    assert rec["year"] == "2024"
    assert "pmc/articles/PMC999" in rec["open_copy_url"]


def test_fetch_dblp_parses_hits_and_single_author() -> None:
    mod = load_module()
    payload = {
        "result": {
            "hits": {
                "hit": [
                    {
                        "info": {
                            "key": "conf/test/1",
                            "title": "A CS Paper",
                            "authors": {"author": {"text": "Solo Author"}},
                            "year": "2025",
                            "venue": "TestConf",
                            "doi": "10.1000/dblp1",
                            "ee": "https://example.org/paper.pdf",
                            "access": "open",
                        }
                    }
                ]
            }
        }
    }
    original = mod.http_json
    mod.http_json = lambda url, **kw: payload
    try:
        records, _ = mod.fetch_dblp("cs query", 5, 10.0)
    finally:
        mod.http_json = original
    assert len(records) == 1
    assert records[0]["creators"] == "Solo Author"
    assert records[0]["open_copy_url"] == "https://example.org/paper.pdf"


def test_fetch_doaj_extracts_doi_and_fulltext() -> None:
    mod = load_module()
    payload = {
        "results": [
            {
                "id": "doaj1",
                "bibjson": {
                    "title": "An OA Paper",
                    "year": "2023",
                    "journal": {"title": "Open Journal"},
                    "author": [{"name": "A. Author"}],
                    "identifier": [{"type": "doi", "id": "10.1000/oa1"}],
                    "link": [{"type": "fulltext", "url": "https://oa.example/full"}],
                    "abstract": "Abstract text.",
                },
            }
        ]
    }
    original = mod.http_json
    mod.http_json = lambda url, **kw: payload
    try:
        records, _ = mod.fetch_doaj("oa query", 5, 10.0)
    finally:
        mod.http_json = original
    assert records[0]["doi"] == "10.1000/oa1"
    assert records[0]["open_copy_url"] == "https://oa.example/full"


def test_fetch_opencitations_requires_doi_query() -> None:
    mod = load_module()
    try:
        mod.fetch_opencitations("not a doi", 5, 10.0)
        raise AssertionError("expected RuntimeError for non-DOI query")
    except RuntimeError as exc:
        state, _, _ = mod.classify_fetch_error("opencitations", exc)
        assert state == "query_error"


def test_fetch_opencitations_parses_doi_metadata() -> None:
    mod = load_module()
    payload = json.dumps([
        {
            "id": "doi:10.1000/oc1 omid:br/123",
            "title": "A Cited Paper",
            "author": "Family, Given [omid:ra/1]; Other, Name [omid:ra/2]",
            "pub_date": "2022-05",
            "venue": "Some Venue [issn:1234-5678]",
        }
    ])
    original = mod.http_text
    mod.http_text = lambda url, **kw: payload
    try:
        records, _ = mod.fetch_opencitations("https://doi.org/10.1000/oc1", 5, 10.0)
    finally:
        mod.http_text = original
    assert records[0]["doi"] == "10.1000/oc1"
    assert "omid" not in records[0]["creators"]
    assert records[0]["container"] == "Some Venue"
    assert records[0]["year"] == "2022"


def test_fetch_core_without_key_is_auth_required() -> None:
    mod = load_module()
    original = mod.env_value
    mod.env_value = lambda name: ""
    try:
        try:
            mod.fetch_core("query", 5, 10.0)
            raise AssertionError("expected RuntimeError without CORE_API_KEY")
        except RuntimeError as exc:
            state, _, _ = mod.classify_fetch_error("core", exc)
            assert state == "auth_required"
    finally:
        mod.env_value = original


def test_all_allowed_sources_have_fetchers() -> None:
    mod = load_module()
    assert set(mod.FETCHERS) == mod.ALLOWED_SOURCES, "every allowed source must be implemented"
