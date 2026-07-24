from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "git_worktree_recovery_guard.py"
SPEC = importlib.util.spec_from_file_location(
    "git_worktree_recovery_guard",
    SCRIPT,
)
assert SPEC is not None
guard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(guard)


def git(cwd: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True,
        env={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        },
    )
    return result.stdout.strip()


class RepositoryFixture:
    def __init__(
        self,
        raw_old_target: str | None = None,
        object_format: str = "sha1",
    ):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repository with spaces"
        self.replacement = self.base / "registered replacement with spaces"
        self.link = self.base / "current worktree link"
        self.old_path = self.base / "missing original worktree"
        self.branch_ref = "refs/heads/recovery/branch"

        self.repo.mkdir()
        init_arguments = ["init", "-b", "main"]
        if object_format != "sha1":
            init_arguments.insert(1, f"--object-format={object_format}")
        git(self.repo, *init_arguments)
        git(self.repo, "config", "user.name", "Synthetic Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "tracked.txt")
        git(self.repo, "commit", "-m", "base")
        git(
            self.repo,
            "worktree",
            "add",
            "-b",
            "recovery/branch",
            str(self.replacement),
        )
        self.expected_commit = git(self.replacement, "rev-parse", "HEAD")
        self.raw_old_target = (
            raw_old_target
            if raw_old_target is not None
            else os.path.relpath(self.old_path, self.link.parent)
        )
        os.symlink(self.raw_old_target, self.link)
        self.raw_new_target = os.path.relpath(
            self.replacement,
            self.link.parent,
        )

    def close(self) -> None:
        self.temporary.cleanup()

    def audit_args(self, **overrides: object) -> list[str]:
        values: dict[str, object] = {
            "repo": str(self.repo),
            "branch_ref": self.branch_ref,
            "replacement": str(self.replacement),
            "link": str(self.link),
            "expected_commit": [self.expected_commit],
            "expected_old_target": self.raw_old_target,
            "new_target": self.raw_new_target,
        }
        values.update(overrides)
        arguments = [
            "--repo",
            str(values["repo"]),
            "--branch-ref",
            str(values["branch_ref"]),
            "--replacement",
            str(values["replacement"]),
            "--link",
            str(values["link"]),
        ]
        for oid in values["expected_commit"]:
            arguments.extend(("--expected-commit", str(oid)))
        if values.get("expected_old_target") is not None:
            arguments.extend(
                ("--expected-old-target", str(values["expected_old_target"]))
            )
        if values.get("new_target") is not None:
            arguments.extend(("--new-target", str(values["new_target"])))
        return arguments

    def audit(self, **overrides: object) -> tuple[int, dict]:
        return guard.execute(self.audit_args(**overrides))

    def repair_args(
        self,
        fingerprint: str,
        **overrides: object,
    ) -> list[str]:
        return [
            "--mode",
            "repair-link",
            *self.audit_args(**overrides),
            "--expected-fingerprint",
            fingerprint,
            "--apply",
        ]


class FixtureTestCase(unittest.TestCase):
    fixture: RepositoryFixture

    def setUp(self) -> None:
        self.fixture = RepositoryFixture()

    def tearDown(self) -> None:
        self.fixture.close()


class AuditHappyPathTests(FixtureTestCase):
    def test_relative_broken_link_is_ready_and_json_omits_paths(self):
        code, payload = self.fixture.audit()
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["authority"], "repoint")
        self.assertTrue(payload["decision"]["repair_allowed"])
        encoded = guard.serialize_payload(payload)
        self.assertNotIn(str(self.fixture.base), encoded)
        self.assertLessEqual(len(encoded.encode("ascii")), guard.MAX_JSON_BYTES)

    def test_absolute_broken_link_is_ready(self):
        self.fixture.link.unlink()
        absolute_old = str(self.fixture.old_path)
        os.symlink(absolute_old, self.fixture.link)
        code, payload = self.fixture.audit(expected_old_target=absolute_old)
        self.assertEqual(code, 0)
        self.assertEqual(payload["link"]["state"], "broken")
        self.assertEqual(payload["status"], "ready")

    def test_current_link_is_idempotent_noop(self):
        self.fixture.link.unlink()
        os.symlink(self.fixture.raw_new_target, self.fixture.link)
        code, payload = self.fixture.audit()
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "noop")
        self.assertFalse(payload["decision"]["repair_allowed"])

    def test_default_mode_is_read_only_audit(self):
        code, payload = self.fixture.audit()
        self.assertEqual(code, 0)
        self.assertEqual(payload["operation"], "audit")
        self.assertEqual(os.readlink(self.fixture.link), self.fixture.raw_old_target)

    def test_missing_target_uncommitted_state_is_explicitly_unverifiable(self):
        code, payload = self.fixture.audit()
        self.assertEqual(code, 0)
        self.assertIn(
            "missing_target_uncommitted_state_unverifiable",
            payload["decision"]["warnings"],
        )

    def test_paths_with_spaces_survive_nul_safe_inventory(self):
        code, payload = self.fixture.audit()
        self.assertEqual(code, 0)
        self.assertEqual(payload["worktree"]["branch_registration_count"], 1)
        self.assertEqual(payload["worktree"]["replacement_registration_count"], 1)


class EvidenceFramingTests(unittest.TestCase):
    oid = "1" * 40

    def test_worktree_inventory_requires_final_record_delimiter(self):
        malformed = (
            b"worktree /tmp/replacement\x00"
            + f"HEAD {self.oid}\x00".encode("ascii")
            + b"branch refs/heads/recovery\x00"
        )
        with self.assertRaises(guard.EvidenceError):
            guard.parse_worktree_porcelain(malformed)

    def test_worktree_inventory_requires_worktree_first_and_core_fields(self):
        cases = (
            (
                f"HEAD {self.oid}\x00".encode("ascii")
                + b"worktree /tmp/replacement\x00"
                + b"branch refs/heads/recovery\x00\x00"
            ),
            b"worktree /tmp/replacement\x00\x00",
            (
                b"worktree /tmp/replacement\x00"
                + b"branch refs/heads/recovery\x00"
                + f"HEAD {self.oid}\x00\x00".encode("ascii")
            ),
        )
        for malformed in cases:
            with self.subTest(malformed=malformed):
                with self.assertRaises(guard.EvidenceError):
                    guard.parse_worktree_porcelain(malformed)

    def test_clean_status_requires_nul_framing_and_branch_headers(self):
        valid_oid = f"# branch.oid {self.oid}".encode("ascii")
        cases = (
            b"",
            valid_oid + b"\x00# branch.head recovery",
            valid_oid + b"\x00# branch.head recovery\x00# fake header\x00",
            b"# branch.head recovery\x00" + valid_oid + b"\x00",
        )
        for malformed in cases:
            with self.subTest(malformed=malformed):
                with self.assertRaises(guard.EvidenceError):
                    guard.parse_status_evidence(malformed)


class WorktreeRefusalTests(FixtureTestCase):
    def assert_blocked(self, reason: str, **overrides: object) -> dict:
        code, payload = self.fixture.audit(**overrides)
        self.assertEqual(code, 2, payload)
        self.assertEqual(payload["status"], "blocked")
        self.assertIn(reason, payload["decision"]["reasons"])
        return payload

    def test_dirty_replacement_refuses(self):
        (self.fixture.replacement / "untracked.txt").write_text(
            "dirty\n",
            encoding="utf-8",
        )
        self.assert_blocked("replacement_dirty")

    def test_detached_replacement_refuses(self):
        git(self.fixture.replacement, "switch", "--detach")
        payload = self.assert_blocked("replacement_detached")
        self.assertIn(
            "status_branch_mismatch",
            payload["decision"]["reasons"],
        )

    def test_wrong_branch_refuses(self):
        git(self.fixture.replacement, "switch", "-c", "other-branch")
        self.assert_blocked("replacement_wrong_branch")

    def audit_with_status_replacement(
        self,
        original: bytes,
        replacement: bytes,
    ) -> tuple[int, dict]:
        original_run = guard.GitRunner.run

        def altered_run(runner, arguments, *, accepted=(0,)):
            result = original_run(runner, arguments, accepted=accepted)
            if (
                tuple(arguments) == guard.STATUS_ARGS
                and guard.same_path(runner.cwd, str(self.fixture.replacement))
            ):
                altered = result.stdout.replace(original, replacement, 1)
                self.assertNotEqual(altered, result.stdout)
                return subprocess.CompletedProcess(
                    result.args,
                    result.returncode,
                    altered,
                    result.stderr,
                )
            return result

        with mock.patch.object(guard.GitRunner, "run", new=altered_run):
            return self.fixture.audit()

    def test_status_oid_must_match_separately_proven_head(self):
        code, payload = self.audit_with_status_replacement(
            f"# branch.oid {self.fixture.expected_commit}".encode("ascii"),
            b"# branch.oid " + b"f" * 40,
        )
        self.assertEqual(code, 2, payload)
        self.assertIn(
            "status_oid_mismatch",
            payload["decision"]["reasons"],
        )
        self.assertFalse(payload["worktree"]["status_oid_matches_head"])

    def test_initial_status_oid_is_not_authority(self):
        code, payload = self.audit_with_status_replacement(
            f"# branch.oid {self.fixture.expected_commit}".encode("ascii"),
            b"# branch.oid (initial)",
        )
        self.assertEqual(code, 2, payload)
        self.assertIn(
            "status_oid_mismatch",
            payload["decision"]["reasons"],
        )
        self.assertFalse(payload["worktree"]["status_oid_matches_head"])

    def test_status_head_must_match_requested_short_branch(self):
        code, payload = self.audit_with_status_replacement(
            b"# branch.head recovery/branch",
            b"# branch.head (detached)",
        )
        self.assertEqual(code, 2, payload)
        self.assertIn(
            "status_branch_mismatch",
            payload["decision"]["reasons"],
        )
        self.assertFalse(payload["worktree"]["status_branch_matches_ref"])

    def test_duplicate_same_branch_records_refuse(self):
        duplicate = self.fixture.base / "duplicate registered worktree"
        git(
            self.fixture.repo,
            "worktree",
            "add",
            "--force",
            str(duplicate),
            "recovery/branch",
        )
        self.assert_blocked("branch_registration_ambiguous")

    def test_unregistered_replacement_refuses(self):
        clone = self.fixture.base / "standalone clone"
        subprocess.run(
            ["git", "clone", str(self.fixture.repo), str(clone)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        git(
            clone,
            "switch",
            "-c",
            "recovery/branch",
            "origin/recovery/branch",
        )
        self.assert_blocked(
            "replacement_not_registered",
            replacement=str(clone),
        )

    def test_locked_replacement_refuses(self):
        git(
            self.fixture.repo,
            "worktree",
            "lock",
            str(self.fixture.replacement),
        )
        self.assert_blocked("replacement_locked")

    def test_prunable_replacement_refuses(self):
        moved = self.fixture.base / "moved without metadata repair"
        os.rename(self.fixture.replacement, moved)
        self.assert_blocked("replacement_prunable")

    def test_stale_duplicate_metadata_refuses(self):
        duplicate = self.fixture.base / "stale duplicate"
        hidden = self.fixture.base / "stale duplicate moved"
        git(
            self.fixture.repo,
            "worktree",
            "add",
            "--force",
            str(duplicate),
            "recovery/branch",
        )
        os.rename(duplicate, hidden)
        payload = self.assert_blocked("branch_registration_ambiguous")
        self.assertEqual(payload["worktree"]["branch_registration_count"], 2)

    def test_in_progress_git_state_refuses_even_when_status_is_clean(self):
        git_dir_raw = git(self.fixture.replacement, "rev-parse", "--git-dir")
        git_dir = Path(git_dir_raw)
        if not git_dir.is_absolute():
            git_dir = self.fixture.replacement / git_dir
        (git_dir / "MERGE_HEAD").write_text(
            self.fixture.expected_commit + "\n",
            encoding="ascii",
        )
        payload = self.assert_blocked("git_operation_in_progress")
        self.assertTrue(payload["worktree"]["clean"])

    def test_link_inside_registered_worktree_refuses(self):
        inside = self.fixture.replacement / "dangling alias"
        os.symlink("../missing", inside)
        self.assert_blocked(
            "link_inside_git_or_worktree",
            link=str(inside),
            expected_old_target="../missing",
            new_target=str(self.fixture.replacement),
        )


class RetentionClassificationTests(FixtureTestCase):
    def test_sha1_expected_commit_is_full_and_ready(self):
        code, payload = self.fixture.audit()
        self.assertEqual(code, 0)
        self.assertEqual(payload["branch"]["object_format"], "sha1")
        self.assertEqual(payload["branch"]["oid_length"], 40)
        self.assertEqual(len(self.fixture.expected_commit), 40)

    def test_sha256_full_expected_commit_is_ready(self):
        fixture = RepositoryFixture(object_format="sha256")
        try:
            code, payload = fixture.audit()
            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["branch"]["object_format"], "sha256")
            self.assertEqual(payload["branch"]["oid_length"], 64)
            self.assertEqual(len(fixture.expected_commit), 64)
        finally:
            fixture.close()

    def test_sha256_40_character_prefix_refuses(self):
        fixture = RepositoryFixture(object_format="sha256")
        try:
            prefix = fixture.expected_commit[:40]
            code, payload = fixture.audit(expected_commit=[prefix])
            self.assertEqual(code, 2)
            self.assertIn(
                "expected_commit_not_full_oid",
                payload["decision"]["reasons"],
            )
            self.assertEqual(
                payload["branch"]["expected_commits"][0]["retention"],
                "non-canonical-oid",
            )
        finally:
            fixture.close()

    def test_annotated_tag_object_is_not_accepted_as_commit(self):
        git(
            self.fixture.repo,
            "tag",
            "-a",
            "synthetic-tag",
            "-m",
            "synthetic annotated tag",
            self.fixture.expected_commit,
        )
        tag_oid = git(
            self.fixture.repo,
            "rev-parse",
            "refs/tags/synthetic-tag",
        )
        code, payload = self.fixture.audit(expected_commit=[tag_oid])
        self.assertEqual(code, 2)
        self.assertIn(
            "expected_object_not_commit",
            payload["decision"]["reasons"],
        )
        self.assertEqual(
            payload["branch"]["expected_commits"][0]["retention"],
            "not-commit",
        )

    def test_old_side_reflog_oid_is_salvage_only(self):
        old = self.fixture.expected_commit
        tree = git(self.fixture.replacement, "rev-parse", "HEAD^{tree}")
        rewritten = git(
            self.fixture.repo,
            "commit-tree",
            tree,
            "-m",
            "synthetic rewritten root",
        )
        git(self.fixture.replacement, "switch", "--detach", old)
        git(
            self.fixture.repo,
            "branch",
            "-f",
            "recovery/branch",
            rewritten,
        )
        git(self.fixture.replacement, "switch", "recovery/branch")

        code, payload = self.fixture.audit(expected_commit=[old])
        self.assertEqual(code, 2)
        self.assertEqual(payload["authority"], "salvage-only")
        self.assertEqual(
            payload["branch"]["expected_commits"][0]["retention"],
            "reflog-only",
        )

    def test_object_only_commit_is_salvage_only(self):
        tree = git(self.fixture.replacement, "rev-parse", "HEAD^{tree}")
        orphan = git(
            self.fixture.repo,
            "commit-tree",
            tree,
            "-m",
            "synthetic unreferenced object",
        )
        code, payload = self.fixture.audit(expected_commit=[orphan])
        self.assertEqual(code, 2)
        self.assertEqual(payload["authority"], "salvage-only")
        self.assertEqual(
            payload["branch"]["expected_commits"][0]["retention"],
            "object-only",
        )

    def test_incomplete_reflog_never_claims_object_only(self):
        tree = git(self.fixture.replacement, "rev-parse", "HEAD^{tree}")
        orphan = git(
            self.fixture.repo,
            "commit-tree",
            tree,
            "-m",
            "synthetic bounded evidence object",
        )
        common_raw = git(self.fixture.repo, "rev-parse", "--git-common-dir")
        common = Path(common_raw)
        if not common.is_absolute():
            common = self.fixture.repo / common
        reflog = common / "logs" / "refs" / "heads" / "recovery" / "branch"
        with reflog.open("ab") as stream:
            stream.write(b"x" * (guard.MAX_REFLOG_BYTES + 1))
        code, payload = self.fixture.audit(expected_commit=[orphan])
        self.assertEqual(code, 2)
        self.assertEqual(
            payload["branch"]["expected_commits"][0]["retention"],
            "retention-unknown",
        )
        self.assertFalse(payload["branch"]["reflog_complete"])

    def test_legacy_graft_cannot_create_false_branch_authority(self):
        tree = git(self.fixture.replacement, "rev-parse", "HEAD^{tree}")
        unrelated = git(
            self.fixture.repo,
            "commit-tree",
            tree,
            "-m",
            "synthetic unrelated graft parent",
        )
        tip = git(self.fixture.replacement, "rev-parse", "HEAD")
        common_raw = git(self.fixture.repo, "rev-parse", "--git-common-dir")
        common = Path(common_raw)
        if not common.is_absolute():
            common = self.fixture.repo / common
        graft_file = common / "info" / "grafts"
        graft_file.parent.mkdir(parents=True, exist_ok=True)
        graft_file.write_text(f"{tip} {unrelated}\n", encoding="ascii")

        git(
            self.fixture.repo,
            "merge-base",
            "--is-ancestor",
            unrelated,
            tip,
        )
        code, payload = self.fixture.audit(expected_commit=[unrelated])

        self.assertEqual(code, 2, payload)
        self.assertEqual(payload["authority"], "salvage-only")
        self.assertEqual(
            payload["branch"]["expected_commits"][0]["retention"],
            "object-only",
        )

    def test_replace_ref_cannot_create_false_branch_authority(self):
        tree = git(self.fixture.replacement, "rev-parse", "HEAD^{tree}")
        unrelated = git(
            self.fixture.repo,
            "commit-tree",
            tree,
            "-m",
            "synthetic unrelated replace parent",
        )
        tip = git(self.fixture.replacement, "rev-parse", "HEAD")
        synthetic_tip = git(
            self.fixture.repo,
            "commit-tree",
            tree,
            "-p",
            unrelated,
            "-m",
            "synthetic replacement tip",
        )
        git(self.fixture.repo, "replace", tip, synthetic_tip)

        git(
            self.fixture.repo,
            "merge-base",
            "--is-ancestor",
            unrelated,
            tip,
        )
        code, payload = self.fixture.audit(expected_commit=[unrelated])

        self.assertEqual(code, 2, payload)
        self.assertEqual(payload["authority"], "salvage-only")
        self.assertEqual(
            payload["branch"]["expected_commits"][0]["retention"],
            "object-only",
        )


class LinkRefusalTests(FixtureTestCase):
    def assert_link_blocked(self, reason: str) -> None:
        code, payload = self.fixture.audit()
        self.assertEqual(code, 2, payload)
        self.assertIn(reason, payload["decision"]["reasons"])

    def test_missing_link_refuses(self):
        self.fixture.link.unlink()
        self.assert_link_blocked("link_missing")

    def test_regular_file_refuses(self):
        self.fixture.link.unlink()
        self.fixture.link.write_text("not a link\n", encoding="utf-8")
        self.assert_link_blocked("link_not_symlink")

    def test_directory_refuses(self):
        self.fixture.link.unlink()
        self.fixture.link.mkdir()
        self.assert_link_blocked("link_is_directory")

    def test_existing_old_target_refuses(self):
        self.fixture.old_path.mkdir()
        self.assert_link_blocked("link_target_exists")

    def test_changed_raw_target_refuses(self):
        self.fixture.link.unlink()
        os.symlink("another missing target", self.fixture.link)
        self.assert_link_blocked("link_raw_target_mismatch")

    def test_symlink_loop_is_evidence_unavailable_not_broken(self):
        loop = self.fixture.base / "target loop"
        os.symlink(loop.name, loop)
        self.fixture.link.unlink()
        os.symlink(loop.name, self.fixture.link)
        code, payload = self.fixture.audit(
            expected_old_target=loop.name,
        )
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "evidence_unavailable")

    @unittest.skipIf(
        os.name != "posix",
        "POSIX permissions are required for this synthetic refusal.",
    )
    def test_inaccessible_target_is_evidence_unavailable_not_broken(self):
        blocked_parent = self.fixture.base / "inaccessible"
        blocked_target = blocked_parent / "target"
        blocked_parent.mkdir()
        blocked_target.mkdir()
        self.fixture.link.unlink()
        raw = os.path.relpath(blocked_target, self.fixture.link.parent)
        os.symlink(raw, self.fixture.link)
        blocked_parent.chmod(0)
        try:
            code, payload = self.fixture.audit(expected_old_target=raw)
        finally:
            blocked_parent.chmod(0o700)
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "evidence_unavailable")


class RepairTests(FixtureTestCase):
    def test_repair_preserves_git_fingerprint_and_updates_only_link(self):
        audit_code, audit = self.fixture.audit()
        self.assertEqual(audit_code, 0)
        code, payload = guard.execute(
            self.fixture.repair_args(audit["fingerprint"])
        )
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "repaired")
        self.assertTrue(payload["mutation_performed"])
        self.assertEqual(
            payload["git_fingerprint_before"],
            payload["git_fingerprint_after"],
        )
        self.assertEqual(os.readlink(self.fixture.link), self.fixture.raw_new_target)
        follow_code, follow = self.fixture.audit()
        self.assertEqual(follow_code, 0)
        self.assertEqual(follow["status"], "noop")

    def test_changed_after_audit_fails_fingerprint_cas(self):
        _, audit = self.fixture.audit()
        self.fixture.link.unlink()
        os.symlink("changed missing target", self.fixture.link)
        code, payload = guard.execute(
            self.fixture.repair_args(audit["fingerprint"])
        )
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(os.readlink(self.fixture.link), "changed missing target")

    def test_replace_failure_cleans_temp_and_preserves_original_link(self):
        _, audit = self.fixture.audit()
        with mock.patch.object(
            guard,
            "replace_link_entry",
            side_effect=OSError("synthetic"),
        ):
            code, payload = guard.execute(
                self.fixture.repair_args(audit["fingerprint"])
            )
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "repair_io_error")
        self.assertEqual(os.readlink(self.fixture.link), self.fixture.raw_old_target)
        leftovers = list(
            self.fixture.link.parent.glob(
                ".git-worktree-safety-*"
            )
        )
        self.assertEqual(leftovers, [])

    def test_equivalent_but_different_raw_target_fails_postcondition(self):
        _, audit = self.fixture.audit()

        def substitute_equivalent_target(
            descriptor: int,
            source_name: str,
            destination_name: str,
        ) -> None:
            os.unlink(source_name, dir_fd=descriptor)
            alternate_name = ".git-worktree-safety-adversarial"
            os.symlink(
                str(self.fixture.replacement),
                alternate_name,
                dir_fd=descriptor,
            )
            os.replace(
                alternate_name,
                destination_name,
                src_dir_fd=descriptor,
                dst_dir_fd=descriptor,
            )

        with mock.patch.object(
            guard,
            "replace_link_entry",
            side_effect=substitute_equivalent_target,
        ):
            code, payload = guard.execute(
                self.fixture.repair_args(audit["fingerprint"])
            )

        self.assertEqual(code, 2, payload)
        self.assertEqual(payload["status"], "postcondition-failed")
        self.assertIn(
            "link_raw_target_postcondition_failed",
            payload["decision"]["reasons"],
        )
        self.assertEqual(
            os.readlink(self.fixture.link),
            str(self.fixture.replacement),
        )
        self.assertNotIn(
            str(self.fixture.base),
            guard.serialize_payload(payload),
        )

    def test_post_audit_blocker_fails_even_with_same_git_fingerprint(self):
        _, audit = self.fixture.audit()
        original_collect_audit = guard.collect_audit
        call_count = 0

        def block_only_post_audit(options):
            nonlocal call_count
            call_count += 1
            public, private = original_collect_audit(options)
            if call_count == 2:
                public = copy.deepcopy(public)
                public["status"] = "blocked"
                public["decision"]["reasons"] = [
                    "synthetic_post_only_safety_gate"
                ]
            return public, private

        with mock.patch.object(
            guard,
            "collect_audit",
            side_effect=block_only_post_audit,
        ):
            code, payload = guard.execute(
                self.fixture.repair_args(audit["fingerprint"])
            )

        self.assertEqual(call_count, 2)
        self.assertEqual(code, 2, payload)
        self.assertEqual(payload["status"], "postcondition-failed")
        self.assertIn(
            "post_audit_not_authoritative",
            payload["decision"]["reasons"],
        )
        self.assertEqual(
            payload["git_fingerprint_before"],
            payload["git_fingerprint_after"],
        )

    def test_immediate_post_replace_readlink_failure_reports_mutation(self):
        _, audit = self.fixture.audit()
        with mock.patch.object(
            guard,
            "read_replaced_link",
            side_effect=OSError("synthetic immediate read failure"),
        ):
            code, payload = guard.execute(
                self.fixture.repair_args(audit["fingerprint"])
            )

        self.assertEqual(code, 1, payload)
        self.assertEqual(payload["schema"], guard.REPAIR_SCHEMA)
        self.assertEqual(payload["status"], "postcondition-unavailable")
        self.assertTrue(payload["mutation_performed"])
        self.assertIsNone(payload["immediate_raw_target_id"])
        self.assertIn(
            "immediate_link_postcondition_unavailable",
            payload["decision"]["reasons"],
        )
        self.assertEqual(
            os.readlink(self.fixture.link),
            self.fixture.raw_new_target,
        )
        self.assertNotIn(
            str(self.fixture.base),
            guard.serialize_payload(payload),
        )

    def test_post_replace_close_failure_reports_mutation(self):
        _, audit = self.fixture.audit()
        original_close = os.close

        def close_then_report_failure(descriptor: int) -> None:
            original_close(descriptor)
            raise OSError("synthetic close reporting failure")

        with mock.patch.object(
            guard,
            "close_repair_descriptor",
            side_effect=close_then_report_failure,
        ):
            code, payload = guard.execute(
                self.fixture.repair_args(audit["fingerprint"])
            )

        self.assertEqual(code, 1, payload)
        self.assertEqual(payload["schema"], guard.REPAIR_SCHEMA)
        self.assertEqual(payload["status"], "postcondition-unavailable")
        self.assertTrue(payload["mutation_performed"])
        self.assertEqual(
            payload["immediate_raw_target_id"],
            guard.raw_string_id(self.fixture.raw_new_target),
        )
        self.assertIn(
            "link_parent_close_unavailable",
            payload["decision"]["reasons"],
        )
        self.assertEqual(
            os.readlink(self.fixture.link),
            self.fixture.raw_new_target,
        )
        self.assertNotIn(
            str(self.fixture.base),
            guard.serialize_payload(payload),
        )

    def test_post_audit_unavailable_reports_completed_mutation(self):
        _, audit = self.fixture.audit()
        original_collect_audit = guard.collect_audit
        call_count = 0

        def fail_post_audit(options):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise guard.EvidenceError("synthetic post audit failure")
            return original_collect_audit(options)

        with mock.patch.object(
            guard,
            "collect_audit",
            side_effect=fail_post_audit,
        ):
            code, payload = guard.execute(
                self.fixture.repair_args(audit["fingerprint"])
            )

        self.assertEqual(call_count, 2)
        self.assertEqual(code, 1, payload)
        self.assertEqual(payload["schema"], guard.REPAIR_SCHEMA)
        self.assertEqual(payload["status"], "postcondition-unavailable")
        self.assertTrue(payload["mutation_performed"])
        self.assertEqual(
            payload["immediate_raw_target_id"],
            guard.raw_string_id(self.fixture.raw_new_target),
        )
        self.assertIn(
            "post_audit_unavailable",
            payload["decision"]["reasons"],
        )
        self.assertEqual(
            os.readlink(self.fixture.link),
            self.fixture.raw_new_target,
        )
        self.assertNotIn(
            str(self.fixture.base),
            guard.serialize_payload(payload),
        )

    def test_long_valid_link_basename_audits_and_repairs(self):
        long_link = self.fixture.base / ("l" * 240)
        os.rename(self.fixture.link, long_link)
        old_link = self.fixture.link
        self.fixture.link = long_link
        try:
            audit_code, audit = self.fixture.audit()
            self.assertEqual(audit_code, 0, audit)
            code, payload = guard.execute(
                self.fixture.repair_args(audit["fingerprint"])
            )
            self.assertEqual(code, 0, payload)
            self.assertEqual(payload["status"], "repaired")
            self.assertEqual(
                os.readlink(self.fixture.link),
                self.fixture.raw_new_target,
            )
        finally:
            self.fixture.link = old_link


class ProcessSafetyTests(FixtureTestCase):
    def test_forbidden_git_mutations_are_unreachable(self):
        runner = guard.GitRunner(str(self.fixture.repo))
        forbidden = (
            ("worktree", "prune"),
            ("worktree", "add", "path"),
            ("worktree", "remove", "path"),
            ("worktree", "repair"),
            ("update-ref", "refs/heads/x", "0" * 40),
            ("checkout", "main"),
            ("reset", "--hard"),
            ("branch", "-f", "x", "0" * 40),
        )
        with mock.patch.object(subprocess, "Popen") as process:
            for arguments in forbidden:
                with self.subTest(arguments=arguments):
                    with self.assertRaises(guard.InputError):
                        runner.run(arguments)
            process.assert_not_called()

    def test_git_output_is_bounded_during_capture(self):
        runner = guard.GitRunner(str(self.fixture.repo))
        original_popen = subprocess.Popen

        def oversized_process(_command, **kwargs):
            return original_popen(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys;"
                        "sys.stdout.buffer.write("
                        f"b'x'*{guard.MAX_COMMAND_BYTES + 4096}"
                        ");sys.stdout.buffer.flush()"
                    ),
                ],
                **kwargs,
            )

        with mock.patch.object(
            subprocess,
            "Popen",
            side_effect=oversized_process,
        ):
            with self.assertRaises(guard.EvidenceError) as raised:
                runner.run(("rev-parse", "--git-common-dir"))
        self.assertEqual(
            str(raised.exception),
            "git_probe_output_too_large",
        )

    def test_helper_has_no_shell_or_recursive_delete_surface(self):
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "shell=True",
            "os.system(",
            "shutil.rmtree",
            "rm -rf",
        ):
            self.assertNotIn(forbidden, source)

    def test_hostile_ambient_git_environment_cannot_redirect_audit(self):
        hostile = self.fixture.base / "hostile git dir"
        hostile.mkdir()
        seen_environments: list[dict[str, str]] = []
        original_popen = subprocess.Popen

        def recording_popen(*args, **kwargs):
            environment = kwargs.get("env")
            if environment is not None and args[0][0] == "git":
                seen_environments.append(environment)
            return original_popen(*args, **kwargs)

        with mock.patch.dict(
            os.environ,
            {
                "GIT_DIR": str(hostile),
                "GIT_WORK_TREE": str(hostile),
                "GIT_INDEX_FILE": str(hostile / "index"),
                "GIT_OBJECT_DIRECTORY": str(hostile),
                "GIT_REPLACE_REF_BASE": "refs/replace/hostile/",
                "GIT_GRAFT_FILE": str(hostile / "grafts"),
                "GIT_NAMESPACE": "hostile",
                "GIT_SHALLOW_FILE": str(hostile / "shallow"),
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.worktree",
                "GIT_CONFIG_VALUE_0": str(hostile),
            },
        ), mock.patch.object(
            subprocess,
            "Popen",
            side_effect=recording_popen,
        ):
            code, payload = self.fixture.audit()

        self.assertEqual(code, 0, payload)
        self.assertTrue(seen_environments)
        for environment in seen_environments:
            for key in (
                "GIT_DIR",
                "GIT_WORK_TREE",
                "GIT_INDEX_FILE",
                "GIT_OBJECT_DIRECTORY",
                "GIT_REPLACE_REF_BASE",
                "GIT_NAMESPACE",
                "GIT_SHALLOW_FILE",
                "GIT_CONFIG_COUNT",
                "GIT_CONFIG_KEY_0",
                "GIT_CONFIG_VALUE_0",
            ):
                self.assertNotIn(key, environment)
            self.assertEqual(environment["GIT_OPTIONAL_LOCKS"], "0")
            self.assertEqual(environment["GIT_NO_LAZY_FETCH"], "1")
            self.assertEqual(environment["GIT_NO_REPLACE_OBJECTS"], "1")
            self.assertEqual(environment["GIT_GRAFT_FILE"], os.devnull)
            self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(
                {
                    key
                    for key in environment
                    if key.startswith("GIT_")
                },
                {
                    "GIT_GRAFT_FILE",
                    "GIT_NO_LAZY_FETCH",
                    "GIT_NO_REPLACE_OBJECTS",
                    "GIT_OPTIONAL_LOCKS",
                    "GIT_TERMINAL_PROMPT",
                },
            )


if __name__ == "__main__":
    unittest.main()
