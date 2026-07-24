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
