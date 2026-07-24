from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
SKILL = ROOT / "skills" / "async-state-consistency" / "SKILL.md"
REFERENCE = ROOT / "references" / "async-state-consistency.md"
FIXTURE = ROOT / "tests" / "fixtures" / "async-state-consistency-trigger-probes.json"


def frontmatter_value(text: str, key: str) -> str:
    lines = text.splitlines()
    prefix = f"{key}:"
    for index, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        value = line.split(":", 1)[1].strip()
        if value in {">", ">-", "|", "|-"}:
            parts = []
            for continuation in lines[index + 1 :]:
                if not continuation.startswith("  "):
                    break
                parts.append(continuation.strip())
            return " ".join(parts)
        return value.strip("\"'")
    raise AssertionError(f"missing frontmatter key: {key}")


class AsyncStateConsistencySkillTest(unittest.TestCase):
    def test_trigger_contract_is_precise(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertEqual(frontmatter_value(text, "name"), "async-state-consistency")
        description = frontmatter_value(text, "description").lower()
        for signal in (
            "asynchronous state",
            "cache",
            "subscriber notifications",
            "memoized",
            "replay",
            "one-shot",
            "invalidation",
            "stale",
            "race",
        ):
            self.assertIn(signal, description)
        for boundary in ("ui-only", "deployment topology", "distributed consensus"):
            self.assertIn(boundary, description)

    def test_trigger_probes_cover_positive_and_near_miss_cases(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "architecture_intelligence.trigger_probes.v1")
        self.assertEqual(payload["skill"], "async-state-consistency")
        self.assertGreaterEqual(len(payload["should_trigger"]), 8)
        self.assertLessEqual(len(payload["should_trigger"]), 10)
        self.assertGreaterEqual(len(payload["should_not_trigger"]), 4)
        self.assertLessEqual(len(payload["should_not_trigger"]), 8)
        positive_ids = {item["id"] for item in payload["should_trigger"]}
        negative_ids = {item["id"] for item in payload["should_not_trigger"]}
        self.assertEqual(
            positive_ids,
            {
                "buried-context",
                "cancellation",
                "clear-in-flight",
                "direct-caller",
                "late-replay",
                "mutation-notification-gap",
                "read-side-race",
                "reverse-completion",
                "state-projection",
                "ttl-contract",
            },
        )
        self.assertEqual(len(positive_ids), len(payload["should_trigger"]))
        self.assertEqual(len(negative_ids), len(payload["should_not_trigger"]))
        self.assertTrue(positive_ids.isdisjoint(negative_ids))
        for item in payload["should_trigger"]:
            self.assertEqual(set(item), {"id", "prompt"})
            self.assertTrue(item["prompt"].strip())
        for item in payload["should_not_trigger"]:
            self.assertEqual(set(item), {"id", "prompt", "route"})
            self.assertTrue(item["prompt"].strip())
            self.assertTrue(item["route"].strip())

    def test_reference_covers_required_race_schedules(self):
        text = REFERENCE.read_text(encoding="utf-8")
        compact = " ".join(text.split()).lower()
        rows = {
            line.split("|")[1].strip()
            for line in text.splitlines()
            if line.startswith("| ASC-")
        }
        self.assertEqual(rows, {f"ASC-{index:02d}" for index in range(1, 18)})
        for invariant in (
            "empty dependency vector",
            "Stamped replay read",
            "same-domain A then B",
            "Mutation and notification",
            "Cancellation is not",
            "latest-start-wins",
            "post-invalidation caller",
            "neither joins nor waits behind",
            "start and finish markers",
            "user-supplied predicate or factory",
            "backpressure",
            "if rejected, record only a non-delivering caller-outcome intent",
            "delivery after release",
            "every outer and inner coordination layer",
            "inner-layer completion or unit proof is insufficient",
            "admission to shared work must linearize against invalidation",
            "later mutate the in-flight registry",
            "bypass is generation-scoped",
            "same-generation admission policy",
        ):
            self.assertIn(invariant.lower(), compact)
        asc_13 = next(
            line.lower()
            for line in text.splitlines()
            if line.startswith("| ASC-13 ")
        )
        for invariant in (
            "layer-locally",
            "public entry point",
            "authoritative publication",
            "before a is released",
            "every coordination layer",
            "a cannot commit",
        ):
            self.assertIn(invariant, asc_13)
        asc_17 = next(
            line.lower()
            for line in text.splitlines()
            if line.startswith("| ASC-17 ")
        )
        for invariant in (
            "whole atomic admission attempt",
            "invalidation-first",
            "admission-first",
            "current generation",
            "subsequently detached or revoked",
            "later callers neither join nor wait",
            "late commit is rejected",
            "speculative snapshot",
            "combined generation-and-membership snapshot",
            "expected generation while installing membership",
            "mismatched cas retries",
            "same-generation pair",
            "declared admission and publication-order policies",
        ):
            self.assertIn(invariant, asc_17)

    def test_skill_forbids_revoked_waits_and_owner_reentry(self):
        text = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "owner-local, non-delivering",
            "user-supplied predicates or factories",
            "synchronously resume or reenter",
            "backpressure",
            "neither join nor wait behind",
            "nested mutation",
            "every outer and inner coordination layer",
            "public entry point",
            "authoritative publication",
            "inner-layer unit proof alone is insufficient",
            "shared-work admission must linearize against invalidation",
            "mutate the in-flight registry",
            "bypass generation-scoped",
            "same-generation join, queue, serialization, coalescing",
            "separate same-generation admission policy",
            "immediately before the whole atomic admission attempt",
            "cas the combined generation-and-membership snapshot",
            "expected generation while installing membership",
            "combined shared-work admission",
        ):
            self.assertIn(invariant, text)

    def test_router_and_publication_surfaces_expose_the_skill(self):
        router = (ROOT / "skills" / "architecture-intelligence" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for skill_dir in (ROOT / "skills").iterdir():
            if skill_dir.is_dir():
                self.assertIn(skill_dir.name, router)

        self.assertIn(
            "- `async-state-consistency`: lifecycle state",
            router,
        )
        self.assertIn(
            "- `async-state-consistency`: async lifecycle",
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )

        codex_manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude_manifest = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(codex_manifest["version"], claude_manifest["version"])
        self.assertRegex(
            codex_manifest["version"],
            re.compile(
                r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
            ),
        )
        for manifest in (codex_manifest, claude_manifest):
            self.assertIn("async state consistency", manifest["description"])
            self.assertIn("async-state", manifest["keywords"])

        marketplace = json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        entry = next(
            item for item in marketplace["plugins"] if item["name"] == "architecture-intelligence"
        )
        self.assertIn("async state consistency", entry["description"])

        root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("| `async-state-consistency` |", root_readme)
        plugin_index = (REPO_ROOT / "plugins" / "README.md").read_text(encoding="utf-8")
        architecture_row = next(
            line for line in plugin_index.splitlines() if line.startswith("| `architecture-intelligence`")
        )
        self.assertIn("async state consistency", architecture_row)

    def test_new_capability_files_are_public_safe_ascii(self):
        for path in (SKILL, REFERENCE, FIXTURE):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            self.assertNotIn("/Users/", text)
            self.assertNotIn("\\Users\\", text)


if __name__ == "__main__":
    unittest.main()
