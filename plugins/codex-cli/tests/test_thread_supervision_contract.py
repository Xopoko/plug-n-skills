from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "codex-thread-supervisor" / "SKILL.md"
REFERENCE = ROOT / "references" / "thread-supervision-contract.md"


def checkpoint_example(text: str) -> dict:
    match = re.search(r"## Checkpoint.*?```json\n(.*?)\n```", text, re.DOTALL)
    if match is None:
        raise AssertionError("checkpoint JSON example not found")
    return json.loads(match.group(1))


def adoption_verdict_example(text: str) -> dict:
    match = re.search(
        r"Keep pair, lineage, protection, commit, readback, and adoption.*?"
        r"```json\n(.*?)\n```",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("adoption verdict JSON example not found")
    return json.loads(match.group(1))


def adoption_failure_schedule(text: str) -> dict[str, str]:
    match = re.search(
        r"Use this deterministic failure schedule:\n\n"
        r"\| Condition \| Required verdict \|\n"
        r"\| --- \| --- \|\n"
        r"(.*?)\n\nThe pre-CAS intent",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("adoption failure schedule not found")

    rows = {}
    for line in match.group(1).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            raise AssertionError(f"malformed adoption schedule row: {line}")
        condition, verdict = cells
        rows[condition.lower()] = verdict.lower()
    return rows


class ThreadSupervisionContractTests(unittest.TestCase):
    def test_checkpoint_binds_one_supervisor_owned_continuation(self):
        contract = checkpoint_example(REFERENCE.read_text(encoding="utf-8"))
        continuation = contract["continuation_owner"]
        heartbeat = contract["heartbeat"]
        self.assertTrue(contract["supervisor_host_id"])
        self.assertEqual(continuation["kind"], "goal-runtime|heartbeat")
        self.assertEqual(continuation["id"], heartbeat["id"])
        self.assertEqual(continuation["owner_task_id"], contract["supervisor_task_id"])
        self.assertEqual(continuation["owner_host_id"], contract["supervisor_host_id"])
        self.assertEqual(heartbeat["owner_task_id"], contract["supervisor_task_id"])
        self.assertEqual(heartbeat["owner_host_id"], contract["supervisor_host_id"])
        self.assertTrue(heartbeat["logical_key"])
        self.assertNotEqual(
            heartbeat["logical_key"], heartbeat["definition_fingerprint"]
        )
        self.assertIn("create-pending", heartbeat["state"].split("|"))
        self.assertIn("update-pending", heartbeat["state"].split("|"))
        self.assertIn("result-unknown", heartbeat["state"].split("|"))
        self.assertIn("idle", contract["targets"][0]["state"].split("|"))
        self.assertIn("terminal", contract["targets"][0]["state"].split("|"))

    def test_skill_keeps_one_continuation_owner_and_never_blocks_on_no_change(self):
        compact = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "exactly one native continuation owner",
            "prefer an already active native goal continuation",
            "do not add a heartbeat while it remains active",
            "verified handoff that retires or defers the prior continuation",
            "exact supervisor task id and host id",
            "inspect existing native wakeups",
            "stored heartbeat id first",
            "supervisor task and host plus stable logical key",
            "persist `create-pending`",
            "persist `result-unknown`",
            "never blind retry",
            "persist `update-pending`",
            "not a replacement create or blind update retry",
            "multiple or ambiguous matches, create nothing",
            "never a target task or an os scheduler",
            "owner task and host",
            "performs one bounded wait",
            "persists every returned cursor",
            "reporting remains transition-only",
            "must not mark the supervision goal blocked",
            "completed latest turn is `idle`, not `terminal`",
            "never use goal `blocked` as a pause",
        ):
            self.assertIn(invariant, compact)

    def test_reference_distinguishes_idle_terminal_and_unchanged(self):
        compact = " ".join(REFERENCE.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "| `idle` |",
            "| `terminal` |",
            "completed latest turn alone is `idle`, not `terminal`",
            "unchanged timeout is not a transition and preserves the prior state",
            "ongoing watch has exactly one continuation owner",
            "`continuation_owner.kind` is `goal-runtime` and `heartbeat` is `null`",
            "active goal continuation takes precedence",
            "create no heartbeat unless a verified handoff",
            "resolve the stored heartbeat id first",
            "exact `supervisor_host_id`, `supervisor_task_id`, and `logical_key`",
            "definition fingerprint records mutable desired configuration",
            "with zero matches, persist `create-pending`",
            "persist `result-unknown`",
            "never blind-retry create",
            "with one match, reuse that exact id",
            "persist `update-pending` before an update",
            "never a blind update retry or create",
            "with multiple or ambiguous matches, create nothing",
            "perform exactly one bounded wait",
            "persist every returned cursor",
            "not by themselves goal blockers",
            "goal `blocked` is a status report, not a pause",
            "missing the supervisor task or host",
            "heartbeat logical key",
            "heartbeat lifecycle state",
            "do not create, update, or retire a wakeup",
            "confirm its owner task and host",
        ):
            self.assertIn(invariant, compact)

    def test_attention_and_failure_take_precedence_over_idle(self):
        compact = " ".join(REFERENCE.read_text(encoding="utf-8").split()).lower()
        self.assertIn("classify `attention` and `failed` before `idle`", compact)
        self.assertIn(
            "only when no approval, input, explicit attention, system error, "
            "or terminal failure signal exists",
            compact,
        )

    def test_aggregate_claims_fail_closed_without_exact_coverage(self):
        compact = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "separate universe breadth from per-item evidence depth",
            "bind the item set and cutoff",
            "exact item-by-dimension coverage",
            "`capability-workbench:capability-auditor`",
            "do not install or activate another plugin",
            "report the claim as bounded or partial",
            "independent enumeration evidence",
        ):
            self.assertIn(invariant, compact)

    def test_open_gates_require_current_eligible_targets(self):
        skill = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "current live subject or explicit policy requirement",
            "a possible action or available authority is not a gate",
            "zero eligible targets",
            "`not-applicable` outside `open_gates`",
            "never create a discussion, note, approval, or other external write",
        ):
            self.assertIn(invariant, skill)

        contract = " ".join(
            REFERENCE.read_text(encoding="utf-8").split()
        ).lower()
        for invariant in (
            "`open_gates` contains only currently applicable blockers",
            "eligibility evidence, and an owner",
            "capability availability, mutation authority, or a possible workflow",
            "complete inventory contains zero eligible targets",
            "never create an external object or write merely to make a checkpoint",
            '"gate_id": "stable-public-safe-gate-id"',
            '"eligibility_state": "eligible"',
            '"eligibility_evidence_ref": "opaque-current-evidence-ref"',
            '"eligibility_owner": "owning-workflow-or-policy"',
            '"required_transition": "bounded evidence-backed terminal condition"',
            "the supervisor may normalize the receipt into the checkpoint",
            "it must not synthesize eligibility",
            "subject, cutoff, eligibility, or owner drift",
            "a previously evidenced applicable gate",
            "a present empty `open_gates` list is valid",
            "must not be repopulated from prose",
        ):
            self.assertIn(invariant, contract)

    def test_canonical_adoption_contract_fails_closed(self):
        skill = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "validating a supplied `previous -> current` pair is not canonical adoption",
            "explicit mutation authority",
            "existing store interface",
            "never emulate cas",
            "guardrails, not a canonical store or adopter",
            "full retained head token",
            "basis head-token fingerprint",
            "pair-only receipt",
            "generation and creating-intent fingerprint",
            "prevents fork and aba adoption",
            "`reconciliation-required`, not `not-adopted`",
            "independent closed verdicts",
        ):
            self.assertIn(invariant, skill)

        reference = REFERENCE.read_text(encoding="utf-8")
        contract = " ".join(reference.split()).lower()
        for invariant in (
            "## canonical checkpoint adoption",
            "producer-owned transition receipt",
            "separate consumer-owned commit",
            "candidate-supplied predecessor metadata is not authority",
            "existing canonical store interface",
            "never emulate this with a read followed by an ordinary write",
            "full head token",
            "unique monotonic generation",
            "a-to-b-to-a",
            "versioned canonical serialization and digest algorithm",
            "basis head-token fingerprint",
            "pair-only receipt without that binding",
            "reject a store or chain mismatch",
            "cannot repair a namespace mismatch",
            "protected-contract fingerprint",
            "immutable pre-cas adoption intent",
            "this order is non-circular",
            "terminal adoption receipt",
            "never an input to the candidate token",
            "exact replay of the same operation id and intent is idempotent",
            "same id with a different intent",
            "separately authorized baseline receipt",
            "read back the full token and native operation result",
            "`reconciliation-required`",
        ):
            self.assertIn(invariant, contract)

        verdict = adoption_verdict_example(reference)
        self.assertEqual(verdict["schema"], "codex.checkpoint_adoption.v1")
        expected_fields = {
            "pair": {"valid", "invalid", "unknown"},
            "lineage": {
                "valid",
                "baseline-valid",
                "unbound",
                "mismatch",
                "namespace-mismatch",
                "unknown",
            },
            "protection": {"valid", "mismatch", "authorized-new-chain", "unknown"},
            "commit": {
                "not-attempted",
                "committed",
                "conflict",
                "id-conflict",
                "outcome-unknown",
            },
            "readback": {"not-run", "matched", "different", "unavailable"},
            "adoption": {
                "not-eligible",
                "capability-unavailable",
                "adopted",
                "already-adopted",
                "head-conflict",
                "protected-mismatch",
                "namespace-mismatch",
                "id-conflict",
                "reconciliation-required",
            },
        }
        self.assertEqual(set(verdict) - {"schema"}, set(expected_fields))
        for field, states in expected_fields.items():
            self.assertEqual(set(verdict[field].split("|")), states)

        self.assertEqual(
            adoption_failure_schedule(reference),
            {
                "valid pair, but no authorized atomic store": (
                    "`pair=valid`, `commit=not-attempted`, "
                    "`adoption=capability-unavailable`"
                ),
                "missing basis head-token binding": (
                    "`lineage=unbound`, `commit=not-attempted`, "
                    "`adoption=not-eligible`"
                ),
                "wrong retained predecessor, generation, or aba token": (
                    "`lineage=mismatch`, `commit=not-attempted`, "
                    "`adoption=not-eligible`"
                ),
                "store or chain differs": (
                    "`lineage=namespace-mismatch`, `commit=not-attempted`, "
                    "`adoption=namespace-mismatch`"
                ),
                "protected goal or authority differs": (
                    "`protection=mismatch`, `commit=not-attempted`, "
                    "`adoption=protected-mismatch`"
                ),
                "compare-and-swap observes another full head token": (
                    "`commit=conflict`, `adoption=head-conflict`"
                ),
                "store confirms commit but readback is unavailable": (
                    "`commit=committed`, "
                    "`readback=unavailable`, `adoption=reconciliation-required`"
                ),
                "native commit outcome and readback are unavailable": (
                    "`commit=outcome-unknown`, `readback=unavailable`, "
                    "`adoption=reconciliation-required`"
                ),
                "store confirms commit but readback names a different token": (
                    "`commit=committed`, `readback=different`, "
                    "`adoption=reconciliation-required`"
                ),
                "exact operation replay and matching readback": (
                    "`commit=committed`, `readback=matched`, "
                    "`adoption=already-adopted`"
                ),
                "same operation id with different intent": (
                    "`commit=id-conflict`, `adoption=id-conflict`"
                ),
                "atomic commit and exact readback both succeed": (
                    "`commit=committed`, `readback=matched`, `adoption=adopted`"
                ),
            },
        )

    def test_supervision_docs_are_public_safe_and_use_no_raw_directives(self):
        for path in (SKILL, REFERENCE):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            for forbidden in (
                "/Users/",
                "\\Users\\",
                "::automation",
                "RRULE:",
                "BEGIN:VEVENT",
            ):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
