from __future__ import annotations

import base64
import concurrent.futures
import importlib.util
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "git_commit_signing_guard.py"
SPEC = importlib.util.spec_from_file_location(
    "git_commit_signing_guard",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def synthetic_public_key() -> str:
    key_type = b"ssh-ed25519"
    key_data = b"\x42" * 32
    blob = (
        len(key_type).to_bytes(4, "big")
        + key_type
        + len(key_data).to_bytes(4, "big")
        + key_data
    )
    encoded = base64.b64encode(blob).decode("ascii")
    return f"ssh-ed25519 {encoded}"


class GitCommitSigningGuardTests(unittest.TestCase):
    def setUp(self):
        if guard.system_executable("git") is None:
            self.skipTest("system Git is unavailable")
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.receipt = self.root / "receipt.json"
        self.authorization = self.root / "authorization.json"
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic User")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        public_key = synthetic_public_key()
        self.allowed_signers = self.root / "allowed-signers"
        self.allowed_signers.write_text(
            f"synthetic@example.invalid {public_key}\n",
            encoding="ascii",
        )
        self.git("config", "gpg.format", "ssh")
        self.git("config", "user.signingkey", f"key::{public_key}")
        self.git(
            "config",
            "gpg.ssh.allowedSignersFile",
            str(self.allowed_signers),
        )
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        (self.repo / "residue.txt").write_text("stable\n", encoding="utf-8")
        self.git("add", "tracked.txt", "residue.txt")
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "base")
        (self.repo / "tracked.txt").write_text(
            "base\nnext\n",
            encoding="utf-8",
        )
        self.git("add", "tracked.txt")
        self.message_path().write_text("next\n", encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return self.git_at(self.repo, *arguments)

    def git_at(
        self,
        repo: Path,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        executable = guard.system_executable("git")
        assert executable is not None
        return subprocess.run(
            [str(executable), "-C", str(repo), *arguments],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def message_path(self) -> Path:
        path = Path(
            self.git(
                "rev-parse",
                "--git-path",
                "COMMIT_EDITMSG",
            ).stdout.strip()
        )
        return path if path.is_absolute() else self.repo / path

    def baseline(
        self,
        policy: str = "required",
        repo: Path | None = None,
    ):
        code, payload = guard.execute(
            [
                "audit",
                "--repo",
                str(repo or self.repo),
                "--policy",
                policy,
                "--receipt",
                str(self.receipt),
                "--authorization",
                str(self.authorization),
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "snapshot")
        return payload

    def authorize(
        self,
        probe: str = "verified",
        repo: Path | None = None,
    ):
        return guard.execute(
            [
                "authorize",
                "--repo",
                str(repo or self.repo),
                "--receipt",
                str(self.receipt),
                "--authorization",
                str(self.authorization),
                "--signer-probe",
                probe,
                "--commit-shape",
                "verified-plain-index",
            ]
        )

    def verify(self, repo: Path | None = None):
        return guard.execute(
            [
                "verify",
                "--repo",
                str(repo or self.repo),
                "--receipt",
                str(self.receipt),
                "--authorization",
                str(self.authorization),
            ]
        )

    def make_key(self, name: str) -> Path:
        executable = guard.system_executable("ssh-keygen")
        if executable is None:
            self.skipTest("system ssh-keygen is unavailable")
        path = self.root / name
        subprocess.run(
            [
                str(executable),
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-f",
                str(path),
            ],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return path

    def configure_real_ssh_keys(self, *keys: Path) -> None:
        verifier = guard.system_executable("ssh-keygen")
        if verifier is None:
            self.skipTest("system ssh-keygen is unavailable")
        lines = [
            (
                "synthetic@example.invalid "
                + key.with_name(f"{key.name}.pub").read_text(
                    encoding="ascii"
                ).strip()
            )
            for key in keys
        ]
        self.allowed_signers.write_text("\n".join(lines) + "\n", encoding="ascii")
        self.git("config", "user.signingkey", str(keys[0]))
        self.git("config", "gpg.ssh.program", str(verifier))
        self.git("config", "commit.gpgsign", "true")

    def commit_unsigned_and_verify_as_expected(
        self,
        baseline: dict,
        *,
        repo: Path | None = None,
    ):
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        expected_identity = baseline["state"]["signing"]["signing_key"][
            "identity_id"
        ]
        with mock.patch.object(
            guard,
            "signature_evidence",
            return_value=(True, expected_identity),
        ):
            return self.verify(repo=repo)

    def test_baseline_is_redacted_and_creates_private_state(self):
        sensitive_program = "/private/signer/program"
        self.git("config", "gpg.ssh.program", sensitive_program)
        payload = self.baseline()
        encoded = guard.serialize_payload(payload)
        self.assertFalse(payload["decision"]["signed_retry_allowed"])
        self.assertFalse(payload["decision"]["unsigned_fallback_allowed"])
        self.assertIn("single_use_authorization_required", encoded)
        self.assertNotIn(str(self.repo), encoded)
        self.assertNotIn(sensitive_program, encoded)
        self.assertNotIn("authorization_nonce", encoded)
        for path in (self.receipt, self.authorization):
            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)

    def test_authorization_is_consumed_exactly_once(self):
        self.baseline(policy="unknown")
        code, payload = self.authorize()
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["decision"]["signed_retry_allowed"])

        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertFalse(payload["decision"]["signed_retry_allowed"])
        self.assertIn("retry_budget_exhausted", payload["decision"]["reasons"])

    def test_concurrent_authorization_has_one_winner(self):
        self.baseline()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.authorize(), range(2)))
        self.assertEqual(sorted(code for code, _ in results), [0, 2])
        ready = [
            payload
            for code, payload in results
            if code == 0
        ]
        blocked = [
            payload
            for code, payload in results
            if code == 2
        ]
        self.assertEqual(len(ready), 1)
        self.assertEqual(len(blocked), 1)
        self.assertIn(
            "retry_budget_exhausted",
            blocked[0]["decision"]["reasons"],
        )

    def test_duplicate_snapshot_cannot_mint_another_authorization(self):
        self.baseline()
        alternate_receipt = self.root / "alternate-receipt.json"
        alternate_authorization = self.root / "alternate-authorization.json"
        code, payload = guard.execute(
            [
                "audit",
                "--repo",
                str(self.repo),
                "--policy",
                "required",
                "--receipt",
                str(alternate_receipt),
                "--authorization",
                str(alternate_authorization),
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(payload["error_code"], "safety_refusal")
        self.assertFalse(alternate_receipt.exists())
        self.assertFalse(alternate_authorization.exists())

    def test_failed_probe_does_not_consume_authorization(self):
        self.baseline()
        code, payload = self.authorize(probe="failed")
        self.assertEqual(code, 2)
        self.assertIn(
            "signer_change_not_verified",
            payload["decision"]["reasons"],
        )
        code, payload = self.authorize()
        self.assertEqual(code, 0)
        self.assertTrue(payload["decision"]["signed_retry_allowed"])

    def test_unverified_commit_shape_does_not_consume_authorization(self):
        self.baseline()
        code, payload = guard.execute(
            [
                "authorize",
                "--repo",
                str(self.repo),
                "--receipt",
                str(self.receipt),
                "--authorization",
                str(self.authorization),
                "--signer-probe",
                "verified",
                "--commit-shape",
                "unverified",
            ]
        )
        self.assertEqual(code, 2)
        self.assertIn(
            "commit_invocation_not_verified",
            payload["decision"]["reasons"],
        )
        self.assertEqual(self.authorize()[0], 0)

    def test_late_state_drift_burns_the_authorization_token(self):
        self.baseline()
        original_write = guard.write_private_json_exclusive

        def write_then_drift(path, payload):
            original_write(path, payload)
            if payload.get("schema") == guard.CONSUMED_SCHEMA:
                (self.repo / "residue.txt").write_text(
                    "late drift\n",
                    encoding="utf-8",
                )

        with mock.patch.object(
            guard,
            "write_private_json_exclusive",
            side_effect=write_then_drift,
        ):
            code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "state_drift_after_token_consumption",
            payload["decision"]["reasons"],
        )
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "retry_budget_exhausted",
            payload["decision"]["reasons"],
        )

    def test_state_drift_blocks_retry(self):
        self.baseline()
        (self.repo / "tracked.txt").write_text(
            "base\nchanged-after-failure\n",
            encoding="utf-8",
        )
        self.git("add", "tracked.txt")
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "recovery_state_drift",
            payload["decision"]["reasons"],
        )

    def test_semantic_index_flags_are_bound_to_recovery_state(self):
        baseline = self.baseline()
        baseline_flags = baseline["state"]["tracked_index_flags_fingerprint"]
        self.git("update-index", "--skip-worktree", "residue.txt")
        skip_state = guard.collect_state(self.repo)
        self.assertNotEqual(
            skip_state["tracked_index_flags_fingerprint"],
            baseline_flags,
        )
        self.git("update-index", "--no-skip-worktree", "residue.txt")
        self.git("update-index", "--assume-unchanged", "residue.txt")
        assume_state = guard.collect_state(self.repo)
        self.assertNotEqual(
            assume_state["tracked_index_flags_fingerprint"],
            baseline_flags,
        )
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "recovery_state_drift",
            payload["decision"]["reasons"],
        )

    def test_head_ref_change_blocks_authorization(self):
        baseline = self.baseline()
        original_ref = baseline["state"]["head_ref"]
        self.git("branch", "alternate", "HEAD")
        self.git("switch", "-q", "alternate")
        changed = guard.collect_state(self.repo)
        self.assertNotEqual(changed["head_ref"], original_ref)
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "recovery_state_drift",
            payload["decision"]["reasons"],
        )

    def test_indirect_head_ref_retarget_blocks_authorization(self):
        original = self.git("symbolic-ref", "HEAD").stdout.strip()
        self.git("branch", "alternate", "HEAD")
        self.git("symbolic-ref", "refs/heads/alias", original)
        self.git("symbolic-ref", "HEAD", "refs/heads/alias")
        baseline = self.baseline()
        self.git(
            "symbolic-ref",
            "refs/heads/alias",
            "refs/heads/alternate",
        )
        changed = guard.collect_state(self.repo)
        self.assertNotEqual(
            changed["head_ref"]["resolved_ref_id"],
            baseline["state"]["head_ref"]["resolved_ref_id"],
        )
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "recovery_state_drift",
            payload["decision"]["reasons"],
        )

    def test_head_ref_change_fails_postcondition(self):
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git("branch", "alternate", "HEAD")
        self.git("switch", "-q", "alternate")
        code, payload = self.commit_unsigned_and_verify_as_expected(baseline)
        self.assertEqual(code, 2)
        self.assertFalse(payload["verification"]["head_ref_matches"])
        self.assertIn("head_ref_changed", payload["decision"]["reasons"])

    def test_linked_worktree_cannot_reuse_recovery_receipt(self):
        linked = self.root / "linked"
        self.git(
            "worktree",
            "add",
            "-q",
            "-b",
            "linked-candidate",
            str(linked),
            "HEAD",
        )
        (linked / "tracked.txt").write_text(
            "base\nnext\n",
            encoding="utf-8",
        )
        self.git_at(linked, "add", "tracked.txt")
        message = Path(
            self.git_at(
                linked,
                "rev-parse",
                "--git-path",
                "COMMIT_EDITMSG",
            ).stdout.strip()
        )
        if not message.is_absolute():
            message = linked / message
        message.write_text("next\n", encoding="utf-8")
        baseline = self.baseline()
        linked_state = guard.collect_state(linked)
        self.assertNotEqual(linked_state["repo_id"], baseline["state"]["repo_id"])
        code, payload = self.authorize(repo=linked)
        self.assertEqual(code, 2)
        self.assertIn(
            "recovery_state_drift",
            payload["decision"]["reasons"],
        )

    def test_hook_policy_change_blocks_retry(self):
        self.baseline()
        hook = Path(self.git("rev-parse", "--git-path", "hooks/pre-commit").stdout.strip())
        if not hook.is_absolute():
            hook = self.repo / hook
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        hook.chmod(0o755)
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "recovery_state_drift",
            payload["decision"]["reasons"],
        )

    def test_configured_relative_hook_content_change_blocks_retry(self):
        hooks = self.repo / ".git" / "configured-hooks"
        hooks.mkdir()
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        hook.chmod(0o755)
        self.git("config", "core.hooksPath", ".git/configured-hooks")
        baseline = self.baseline()
        self.assertTrue(
            baseline["state"]["hooks"]["hooks"]["pre-commit"]["exists"]
        )
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="ascii")
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "recovery_state_drift",
            payload["decision"]["reasons"],
        )

    def test_empty_configured_hook_path_uses_git_effective_location(self):
        self.git("config", "core.hooksPath", "")
        effective = guard.git_path(self.repo, "hooks/pre-commit")
        if effective.exists():
            self.skipTest("effective root hook exists on this host")
        repo_hook = self.repo / "pre-commit"
        repo_hook.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        repo_hook.chmod(0o755)
        baseline = self.baseline()
        self.assertEqual(effective, Path("/pre-commit"))
        self.assertFalse(
            baseline["state"]["hooks"]["hooks"]["pre-commit"]["exists"]
        )

    def test_active_git_operation_blocks_retry(self):
        self.baseline()
        marker = Path(self.git("rev-parse", "--git-path", "MERGE_HEAD").stdout.strip())
        if not marker.is_absolute():
            marker = self.repo / marker
        marker.write_text(
            self.git("rev-parse", "HEAD").stdout,
            encoding="ascii",
        )
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "git_operation_in_progress",
            payload["decision"]["reasons"],
        )

    def test_ssh_retry_requires_readable_trust_evidence(self):
        self.git(
            "config",
            "gpg.ssh.allowedSignersFile",
            str(self.root / "missing-allowed-signers"),
        )
        self.baseline()
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "ssh_trust_evidence_unavailable",
            payload["decision"]["reasons"],
        )

    def test_ssh_trust_file_content_is_bound_to_recovery_fingerprint(self):
        self.baseline()
        self.allowed_signers.write_text(
            f"other@example.invalid {synthetic_public_key()}\n",
            encoding="ascii",
        )
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "recovery_state_drift",
            payload["decision"]["reasons"],
        )

    def test_unsigned_commit_fails_signature_verification(self):
        self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertTrue(payload["verification"]["one_parent_advance"])
        self.assertTrue(payload["verification"]["committed_diff_matches"])
        self.assertFalse(payload["verification"]["signature_valid"])
        self.assertIn(
            "signature_verification_failed",
            payload["decision"]["reasons"],
        )

    def test_verification_does_not_execute_configured_signer_program(self):
        marker = self.root / "configured-signer-ran"
        fake_signer = self.root / "configured-signer"
        fake_signer.write_text(
            f"#!/bin/sh\n: > '{marker}'\nexit 99\n",
            encoding="ascii",
        )
        fake_signer.chmod(0o755)
        self.git("config", "gpg.ssh.program", str(fake_signer))
        self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertFalse(marker.exists())
        self.assertIn(
            "signature_verification_failed",
            payload["decision"]["reasons"],
        )

    def test_verification_ignores_ambient_path_wrappers(self):
        marker = self.root / "ambient-wrapper-ran"
        binary_dir = self.root / "bin"
        binary_dir.mkdir()
        for name in ("git", "ssh-keygen"):
            wrapper = binary_dir / name
            wrapper.write_text(
                f"#!/bin/sh\n: > '{marker}'\nexit 99\n",
                encoding="ascii",
            )
            wrapper.chmod(0o755)
        self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        with mock.patch.dict(
            os.environ,
            {"PATH": f"{binary_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
        ):
            code, _ = self.verify()
        self.assertEqual(code, 2)
        self.assertFalse(marker.exists())

    def test_git_probes_force_object_substitution_off(self):
        observed: list[tuple[list[str], dict[str, str]]] = []
        real_run = subprocess.run

        def capture(*args, **kwargs):
            observed.append((list(args[0]), dict(kwargs["env"])))
            return real_run(*args, **kwargs)

        with mock.patch.dict(
            os.environ,
            {
                "GIT_NO_REPLACE_OBJECTS": "0",
                "GIT_GRAFT_FILE": str(self.root / "hostile-grafts"),
                "GIT_REPLACE_REF_BASE": "refs/hostile/",
            },
        ), mock.patch.object(guard.subprocess, "run", side_effect=capture):
            guard.run_git(self.repo, ["rev-parse", "--verify", "HEAD"])

        self.assertEqual(len(observed), 1)
        argv, environment = observed[0]
        self.assertIn("--no-replace-objects", argv)
        self.assertEqual(environment["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(environment["GIT_GRAFT_FILE"], os.devnull)
        self.assertNotIn("GIT_REPLACE_REF_BASE", environment)

    def test_state_collection_never_executes_configured_filters(self):
        marker = self.root / "configured-filter-ran"
        configured_filter = self.root / "configured-filter"
        configured_filter.write_text(
            f"#!/bin/sh\n: > '{marker}'\ncat\n",
            encoding="ascii",
        )
        configured_filter.chmod(0o755)
        (self.repo / ".gitattributes").write_text(
            "residue.txt filter=probe\n",
            encoding="ascii",
        )
        self.git("add", ".gitattributes")
        self.git("config", "filter.probe.clean", str(configured_filter))
        self.git("config", "filter.probe.smudge", str(configured_filter))
        self.git("config", "filter.probe.process", str(configured_filter))
        (self.repo / "residue.txt").write_text(
            "unstaged change\n",
            encoding="utf-8",
        )

        self.baseline()
        self.assertFalse(marker.exists())
        self.assertEqual(self.authorize()[0], 0)
        self.assertFalse(marker.exists())

    def test_worktree_diff_mode_is_refused(self):
        with self.assertRaisesRegex(
            guard.EvidenceError,
            "unsafe_worktree_diff_refused",
        ):
            guard.diff_bytes(self.repo)

    def test_replacement_ref_blocks_authorization(self):
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("update-ref", f"refs/replace/{head}", head)
        baseline = self.baseline()
        self.assertIn(
            "object_substitution_present",
            baseline["decision"]["reasons"],
        )
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "object_substitution_present",
            payload["decision"]["reasons"],
        )

    def test_legacy_grafts_file_blocks_authorization(self):
        common = Path(
            self.git("rev-parse", "--git-common-dir").stdout.strip()
        )
        if not common.is_absolute():
            common = self.repo / common
        grafts = common / "info" / "grafts"
        grafts.parent.mkdir(parents=True, exist_ok=True)
        grafts.write_text("", encoding="ascii")
        baseline = self.baseline()
        self.assertIn(
            "object_substitution_present",
            baseline["decision"]["reasons"],
        )
        code, payload = self.authorize()
        self.assertEqual(code, 2)
        self.assertIn(
            "object_substitution_present",
            payload["decision"]["reasons"],
        )

    def test_legacy_graft_cannot_forge_parent_transition(self):
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        git = guard.system_executable("git")
        assert git is not None
        old_head = self.git("rev-parse", "HEAD").stdout.strip()
        base_tree = self.git("rev-parse", "HEAD^{tree}").stdout.strip()
        staged_tree = self.git("write-tree").stdout.strip()

        def commit_tree(tree: str, *parents: str, message: str) -> str:
            arguments = [
                str(git),
                "-C",
                str(self.repo),
                "commit-tree",
                tree,
            ]
            for parent in parents:
                arguments.extend(["-p", parent])
            return subprocess.run(
                arguments,
                check=True,
                input=f"{message}\n",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout.strip()

        unrelated = commit_tree(base_tree, message="unrelated")
        new_head = commit_tree(staged_tree, unrelated, message="next")
        self.git("update-ref", "HEAD", new_head, old_head)
        common = Path(
            self.git("rev-parse", "--git-common-dir").stdout.strip()
        )
        if not common.is_absolute():
            common = self.repo / common
        grafts = common / "info" / "grafts"
        grafts.parent.mkdir(parents=True, exist_ok=True)
        grafts.write_text(f"{new_head} {old_head}\n", encoding="ascii")
        expected_identity = baseline["state"]["signing"]["signing_key"][
            "identity_id"
        ]
        with mock.patch.object(
            guard,
            "signature_evidence",
            return_value=(True, expected_identity),
        ):
            code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertFalse(payload["verification"]["one_parent_advance"])
        self.assertTrue(payload["verification"]["committed_diff_matches"])
        self.assertTrue(payload["verification"]["commit_message_matches"])
        self.assertIn(
            "unexpected_parent_transition",
            payload["decision"]["reasons"],
        )
        self.assertIn(
            "object_substitution_present",
            payload["decision"]["reasons"],
        )

    def test_replacement_cannot_lend_signature_to_unsigned_head(self):
        key = self.make_key("replacement-key")
        self.configure_real_ssh_keys(key)
        self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        unsigned = self.git("rev-parse", "HEAD").stdout.strip()
        parent = self.git("rev-parse", "HEAD^").stdout.strip()
        tree = self.git("rev-parse", "HEAD^{tree}").stdout.strip()
        git = guard.system_executable("git")
        verifier = guard.system_executable("ssh-keygen")
        assert git is not None and verifier is not None
        signed = subprocess.run(
            [
                str(git),
                "-C",
                str(self.repo),
                "-c",
                f"gpg.ssh.program={verifier}",
                "commit-tree",
                "-S",
                tree,
                "-p",
                parent,
            ],
            check=True,
            input="next\n",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()
        self.git("replace", unsigned, signed)

        code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertFalse(payload["verification"]["signature_valid"])
        self.assertFalse(
            payload["verification"]["object_substitution_matches"]
        )
        self.assertIn(
            "object_substitution_present",
            payload["decision"]["reasons"],
        )
        self.assertIn(
            "signature_verification_failed",
            payload["decision"]["reasons"],
        )

    def test_verified_signature_path_accepts_exact_commit_and_residue(self):
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        expected_identity = baseline["state"]["signing"]["signing_key"][
            "identity_id"
        ]
        with mock.patch.object(
            guard,
            "signature_evidence",
            return_value=(True, expected_identity),
        ):
            code, payload = self.verify()
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "verified")
        self.assertTrue(payload["decision"]["verified"])
        self.assertTrue(payload["verification"]["committed_diff_matches"])
        self.assertTrue(payload["verification"]["commit_message_matches"])
        self.assertTrue(payload["verification"]["signing_identity_matches"])

    def test_changed_commit_message_fails_postcondition(self):
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git(
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            "different message",
        )
        expected_identity = baseline["state"]["signing"]["signing_key"][
            "identity_id"
        ]
        with mock.patch.object(
            guard,
            "signature_evidence",
            return_value=(True, expected_identity),
        ):
            code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertIn(
            "commit_message_changed",
            payload["decision"]["reasons"],
        )

    def test_hook_change_after_authorization_fails_postcondition(self):
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        hook = Path(self.git("rev-parse", "--git-path", "hooks/pre-commit").stdout.strip())
        if not hook.is_absolute():
            hook = self.repo / hook
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        hook.chmod(0o755)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        expected_identity = baseline["state"]["signing"]["signing_key"][
            "identity_id"
        ]
        with mock.patch.object(
            guard,
            "signature_evidence",
            return_value=(True, expected_identity),
        ):
            code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertIn("hook_policy_changed", payload["decision"]["reasons"])

    def test_untracked_content_change_fails_postcondition(self):
        untracked = self.repo / "untracked-note.txt"
        untracked.write_text("before\n", encoding="utf-8")
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        untracked.write_text("after\n", encoding="utf-8")
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        expected_identity = baseline["state"]["signing"]["signing_key"][
            "identity_id"
        ]
        with mock.patch.object(
            guard,
            "signature_evidence",
            return_value=(True, expected_identity),
        ):
            code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertFalse(payload["verification"]["untracked_content_matches"])
        self.assertIn(
            "untracked_content_changed",
            payload["decision"]["reasons"],
        )

    def test_untracked_mode_change_fails_postcondition(self):
        untracked = self.repo / "untracked-mode.txt"
        untracked.write_text("stable\n", encoding="utf-8")
        untracked.chmod(0o600)
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        untracked.chmod(0o644)
        code, payload = self.commit_unsigned_and_verify_as_expected(baseline)
        self.assertEqual(code, 2)
        self.assertFalse(payload["verification"]["untracked_content_matches"])
        self.assertIn(
            "untracked_content_changed",
            payload["decision"]["reasons"],
        )

    def test_untracked_regular_to_symlink_change_fails_postcondition(self):
        untracked = self.repo / "untracked-type.txt"
        untracked.write_text("stable\n", encoding="utf-8")
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        untracked.unlink()
        untracked.symlink_to("replacement-target")
        code, payload = self.commit_unsigned_and_verify_as_expected(baseline)
        self.assertEqual(code, 2)
        self.assertFalse(payload["verification"]["untracked_content_matches"])
        self.assertIn(
            "untracked_content_changed",
            payload["decision"]["reasons"],
        )

    def test_untracked_symlink_target_change_fails_postcondition(self):
        untracked = self.repo / "untracked-link"
        untracked.symlink_to("target-before")
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        untracked.unlink()
        untracked.symlink_to("target-after")
        code, payload = self.commit_unsigned_and_verify_as_expected(baseline)
        self.assertEqual(code, 2)
        self.assertFalse(payload["verification"]["untracked_content_matches"])
        self.assertIn(
            "untracked_content_changed",
            payload["decision"]["reasons"],
        )

    def test_untracked_content_over_bound_refuses_authorization(self):
        (self.repo / "untracked-large.txt").write_text(
            "too large for patched bound\n",
            encoding="utf-8",
        )
        with mock.patch.object(guard, "MAX_UNTRACKED_TOTAL_BYTES", 1):
            baseline = self.baseline()
        self.assertFalse(
            baseline["state"]["untracked_content_evidence_available"]
        )
        self.assertIn(
            "untracked_content_evidence_unavailable",
            baseline["decision"]["reasons"],
        )

    def test_nested_repo_argument_still_covers_root_untracked_state(self):
        nested = self.repo / "nested"
        nested.mkdir()
        untracked = self.repo / "root-untracked.txt"
        untracked.write_text("before\n", encoding="utf-8")
        baseline = self.baseline(repo=nested)
        self.assertEqual(self.authorize(repo=nested)[0], 0)
        untracked.write_text("after\n", encoding="utf-8")
        code, payload = self.commit_unsigned_and_verify_as_expected(
            baseline,
            repo=nested,
        )
        self.assertEqual(code, 2)
        self.assertFalse(payload["verification"]["untracked_content_matches"])
        self.assertIn(
            "untracked_content_changed",
            payload["decision"]["reasons"],
        )

    def test_verifier_repository_mutation_is_detected(self):
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        expected_identity = baseline["state"]["signing"]["signing_key"][
            "identity_id"
        ]

        def mutating_verifier(repo, commit, signing):
            del commit, signing
            (repo / "residue.txt").write_text("mutated\n", encoding="utf-8")
            return True, expected_identity

        with mock.patch.object(
            guard,
            "signature_evidence",
            side_effect=mutating_verifier,
        ):
            code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertIn(
            "verifier_changed_repository_state",
            payload["decision"]["reasons"],
        )

    def test_second_commit_and_residual_drift_fail_postcondition(self):
        baseline = self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        (self.repo / "residue.txt").write_text("drift\n", encoding="utf-8")
        (self.repo / "second.txt").write_text("second\n", encoding="utf-8")
        self.git("add", "second.txt")
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "second")
        expected_identity = baseline["state"]["signing"]["signing_key"][
            "identity_id"
        ]
        with mock.patch.object(
            guard,
            "signature_evidence",
            return_value=(True, expected_identity),
        ):
            code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertIn(
            "unexpected_parent_transition",
            payload["decision"]["reasons"],
        )
        self.assertIn(
            "tracked_content_changed",
            payload["decision"]["reasons"],
        )

    def test_verify_requires_a_consumed_authorization(self):
        self.baseline()
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "next")
        code, payload = self.verify()
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "invalid_input")

    def test_real_ssh_signature_matches_recorded_identity(self):
        key = self.make_key("key-one")
        self.configure_real_ssh_keys(key)
        self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        self.git("commit", "-q", "-S", "-m", "next")
        code, payload = self.verify()
        self.assertEqual(code, 0)
        self.assertTrue(payload["verification"]["signature_valid"])
        self.assertTrue(payload["verification"]["signing_identity_matches"])

    def test_different_trusted_ssh_key_is_rejected(self):
        key_one = self.make_key("key-one")
        key_two = self.make_key("key-two")
        self.configure_real_ssh_keys(key_one, key_two)
        self.baseline()
        self.assertEqual(self.authorize()[0], 0)
        verifier = guard.system_executable("ssh-keygen")
        assert verifier is not None
        self.git(
            "-c",
            f"user.signingkey={key_two}",
            "-c",
            f"gpg.ssh.program={verifier}",
            "commit",
            "-q",
            "-S",
            "-m",
            "next",
        )
        code, payload = self.verify()
        self.assertEqual(code, 2)
        self.assertTrue(payload["verification"]["signature_valid"])
        self.assertFalse(payload["verification"]["signing_identity_matches"])
        self.assertIn(
            "signing_identity_changed",
            payload["decision"]["reasons"],
        )


if __name__ == "__main__":
    unittest.main()
