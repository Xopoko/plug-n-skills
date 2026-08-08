import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "gitlab-review-response"
    / "references"
    / "review-transaction-contract.md"
)
SKILL = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "gitlab-review-response"
    / "SKILL.md"
)
PUSH_GUARD = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "gitlab-review-response"
    / "scripts"
    / "gitlab_push_binding_guard.py"
)
PUSH_GUARD_SPEC = importlib.util.spec_from_file_location(
    "gitlab_push_binding_guard",
    PUSH_GUARD,
)
push_guard = importlib.util.module_from_spec(PUSH_GUARD_SPEC)
assert PUSH_GUARD_SPEC.loader is not None
PUSH_GUARD_SPEC.loader.exec_module(push_guard)


class ReviewTransactionGitIntegrationTests(unittest.TestCase):
    def run_git(self, cwd, *arguments, check=True):
        environment = os.environ.copy()
        for name in tuple(environment):
            if name.startswith("GIT_"):
                del environment[name]
        environment.update(
            {
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(
                f"git {' '.join(arguments)} failed with {result.returncode}: "
                f"{result.stderr.strip()}"
            )
        return result

    def write_private_json(self, path, value):
        path.write_text(
            json.dumps(value, sort_keys=True),
            encoding="utf-8",
        )
        path.chmod(0o600)

    def guard_environment(self, **updates):
        environment = os.environ.copy()
        for name in tuple(environment):
            if name.lower() in {"all_proxy", "http_proxy", "https_proxy"}:
                del environment[name]
        environment.update(updates)
        return environment

    def execution_environment(self, manifest):
        self.assertEqual(manifest["environment"]["base"], "empty")
        self.assertEqual(
            manifest["environment"]["operation_order"],
            ["clear", "preserve_exact", "set"],
        )
        environment = {}
        environment.update(manifest["environment"]["preserve_exact"])
        environment.update(manifest["environment"]["set"])
        return environment

    def run_guard(self, *arguments, environment=None, cwd=None):
        return subprocess.run(
            [sys.executable, str(PUSH_GUARD), *arguments],
            env=environment or self.guard_environment(),
            cwd=cwd,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def make_guard_fixture(
        self,
        root,
        *,
        object_format="sha1",
        endpoint="https://gitlab.example.test/group/project.git",
    ):
        root = root.resolve()
        checkout = root / "checkout"
        init_arguments = ["init"]
        if object_format == "sha256":
            init_arguments.append("--object-format=sha256")
        init_arguments.append(str(checkout))
        self.run_git(root, *init_arguments)
        self.run_git(checkout, "config", "user.name", "Contract Test")
        self.run_git(
            checkout,
            "config",
            "user.email",
            "contract-test@example.test",
        )
        self.run_git(checkout, "commit", "--allow-empty", "-m", "epoch")
        expected_old = self.run_git(
            checkout,
            "rev-parse",
            "HEAD",
        ).stdout.strip()
        self.run_git(checkout, "commit", "--allow-empty", "-m", "prepared")
        prepared = self.run_git(
            checkout,
            "rev-parse",
            "HEAD",
        ).stdout.strip()
        self.run_git(checkout, "branch", "-M", "topic")
        self.run_git(
            checkout,
            "remote",
            "add",
            "publish",
            endpoint,
        )
        project = root / "project.json"
        merge_request = root / "mr.json"
        branch = root / "branch.json"
        self.write_private_json(
            project,
            {"id": 41, "http_url_to_repo": endpoint},
        )
        self.write_private_json(
            merge_request,
            {
                "source_project_id": 41,
                "source_branch": "topic",
                "sha": expected_old,
                "diff_refs": {"head_sha": expected_old},
            },
        )
        self.write_private_json(
            branch,
            {
                "name": "topic",
                "commit": {"id": expected_old},
            },
        )
        transaction = root / "transaction"
        common = [
            "--repository",
            str(checkout),
            "--discovery-remote",
            "publish",
            "--transaction-dir",
            str(transaction),
            "--project",
            str(project),
            "--mr",
            str(merge_request),
            "--branch",
            str(branch),
            "--prepared-sha",
            prepared,
        ]
        return {
            "checkout": checkout,
            "expected_old": expected_old,
            "prepared": prepared,
            "project": project,
            "mr": merge_request,
            "branch": branch,
            "transaction": transaction,
            "common": common,
        }

    def test_push_binding_guard_parses_scoped_config_nul_framing(self):
        self.assertEqual(
            push_guard._parse_config_records(
                b"command\x00credential.helper\nGENERIC\x00"
            ),
            [("command", "credential.helper", "GENERIC")],
        )

    def test_push_binding_guard_refuses_nonabsolute_home_blocker(self):
        with (
            mock.patch.object(push_guard.os, "devnull", "relative-null"),
            self.assertRaises(push_guard.ReportOnly) as raised,
        ):
            push_guard._execution_home_blocker()
        self.assertEqual(raised.exception.codes, ["HTTPS_BASELINE_UNAVAILABLE"])

    def test_exact_sha_refspec_requires_explicit_tracking_readback(self):
        contract = CONTRACT.read_text(encoding="utf-8")
        self.assertIn("Exact-SHA refspec tracking", contract)
        self.assertIn("SHA:refs/heads/PUSH_BRANCH", contract)
        self.assertIn("@{upstream}", contract)
        self.assertIn("source Project Branch API", contract)
        self.assertIn("STATE_PRESENT_ATTRIBUTION_UNKNOWN", contract)
        self.assertIn("same-OID", contract)
        self.assertIn("unobservable", contract)
        self.assertIn("never retry", contract)
        self.assertIn("--no-verify", contract)
        self.assertIn("--no-signed", contract)
        self.assertIn("--no-follow-tags", contract)
        self.assertIn("--no-force-if-includes", contract)
        self.assertIn("--recurse-submodules=no", contract)
        self.assertNotIn(
            "`git ls-remote --refs PUSH_REMOTE",
            contract,
        )
        self.assertIn("git branch --set-upstream-to", contract)
        self.assertIn("non-detached `LOCAL_BRANCH`", contract)
        self.assertIn("do not overwrite it", contract)
        self.assertIn("branch.*.pushRemote", contract)
        self.assertIn("PUSH_REMOTE", contract)
        self.assertIn("UPSTREAM_REMOTE", contract)
        self.assertIn("never derive them", contract)
        self.assertIn("asks Git's own", contract)
        self.assertIn("URL matcher about the exact endpoint", contract)
        self.assertIn("clear the entire inherited environment", contract)
        self.assertIn("captured all-absolute `PATH`", contract)
        self.assertIn("non-directory null device", contract)
        self.assertIn("execution working directory", contract)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            publish_remote = root / "publish.git"
            upstream_remote = root / "upstream.git"
            checkout = root / "checkout"
            self.run_git(root, "init", "--bare", str(publish_remote))
            self.run_git(root, "init", "--bare", str(upstream_remote))
            self.run_git(root, "init", str(checkout))
            self.run_git(checkout, "config", "user.name", "Contract Test")
            self.run_git(
                checkout,
                "config",
                "user.email",
                "contract-test@example.test",
            )
            (checkout / "example.txt").write_text("example\n", encoding="utf-8")
            self.run_git(checkout, "add", "example.txt")
            self.run_git(checkout, "commit", "-m", "initial")
            self.run_git(checkout, "branch", "-M", "topic")
            self.run_git(
                checkout,
                "remote",
                "add",
                "publish",
                str(publish_remote),
            )
            self.run_git(
                checkout,
                "remote",
                "add",
                "upstream",
                str(upstream_remote),
            )
            head = self.run_git(checkout, "rev-parse", "HEAD").stdout.strip()

            self.run_git(
                checkout,
                "push",
                "-u",
                "publish",
                f"{head}:refs/heads/topic",
            )
            injected_config = {
                "GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_0": "branch.topic.remote",
                "GIT_CONFIG_VALUE_0": "wrong",
                "GIT_CONFIG_KEY_1": "branch.topic.merge",
                "GIT_CONFIG_VALUE_1": "refs/heads/wrong",
            }
            with mock.patch.dict(os.environ, injected_config):
                missing_upstream = self.run_git(
                    checkout,
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    "@{upstream}",
                    check=False,
                )
                self.assertNotEqual(missing_upstream.returncode, 0)
                self.assertNotEqual(
                    self.run_git(
                        checkout,
                        "config",
                        "--get",
                        "branch.topic.remote",
                        check=False,
                    ).returncode,
                    0,
                )
                self.assertNotEqual(
                    self.run_git(
                        checkout,
                        "config",
                        "--get",
                        "branch.topic.merge",
                        check=False,
                    ).returncode,
                    0,
                )

            published_head = self.run_git(
                root,
                "--git-dir",
                str(publish_remote),
                "rev-parse",
                "refs/heads/topic",
            ).stdout.strip()
            self.assertEqual(published_head, head)

            self.run_git(
                checkout,
                "push",
                "upstream",
                f"{head}:refs/heads/base",
            )
            selected_upstream_head = self.run_git(
                checkout,
                "ls-remote",
                "--refs",
                "upstream",
                "refs/heads/base",
            ).stdout.split()
            self.assertEqual(
                selected_upstream_head,
                [head, "refs/heads/base"],
            )

            self.run_git(
                checkout,
                "fetch",
                "--no-tags",
                "upstream",
                "+refs/heads/base:refs/remotes/upstream/base",
            )
            self.run_git(
                checkout,
                "config",
                "branch.topic.pushRemote",
                "publish",
            )
            self.run_git(
                checkout,
                "branch",
                "--set-upstream-to=upstream/base",
                "topic",
            )
            upstream_name = self.run_git(
                checkout,
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{upstream}",
            ).stdout.strip()
            upstream_head = self.run_git(
                checkout,
                "rev-parse",
                "@{upstream}",
            ).stdout.strip()
            self.assertEqual(upstream_name, "upstream/base")
            self.assertEqual(upstream_head, head)
            self.assertEqual(
                self.run_git(
                    checkout,
                    "config",
                    "--get",
                    "branch.topic.remote",
                ).stdout.strip(),
                "upstream",
            )
            self.assertEqual(
                self.run_git(
                    checkout,
                    "config",
                    "--get",
                    "branch.topic.merge",
                ).stdout.strip(),
                "refs/heads/base",
            )
            self.assertEqual(
                self.run_git(
                    checkout,
                    "config",
                    "--get",
                    "branch.topic.pushRemote",
                ).stdout.strip(),
                "publish",
            )

    def test_hot_skill_routes_source_project_bound_publication(self):
        skill = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()

        for invariant in (
            "source project branch api",
            "gitlab_push_binding_guard.py",
            "expected-old-oid lease",
            "sha:refs/heads/branch",
            "do not infer or set upstream tracking",
            "remote-tracking ref",
            "live account ownership",
        ):
            self.assertIn(invariant, skill)

    def test_exact_oid_lease_does_not_claim_same_oid_aba_detection(self):
        contract = CONTRACT.read_text(encoding="utf-8")
        self.assertIn("same-OID", contract)
        self.assertIn("unobservable", contract)
        self.assertIn("OID-state", contract)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            checkout = root / "checkout"
            self.run_git(root, "init", "--bare", str(remote))
            self.run_git(root, "init", str(checkout))
            self.run_git(checkout, "config", "user.name", "Contract Test")
            self.run_git(
                checkout,
                "config",
                "user.email",
                "contract-test@example.test",
            )
            self.run_git(checkout, "commit", "--allow-empty", "-m", "epoch")
            expected_old = self.run_git(
                checkout,
                "rev-parse",
                "HEAD",
            ).stdout.strip()
            self.run_git(checkout, "commit", "--allow-empty", "-m", "prepared")
            prepared = self.run_git(
                checkout,
                "rev-parse",
                "HEAD",
            ).stdout.strip()
            self.run_git(
                checkout,
                "push",
                str(remote),
                f"{expected_old}:refs/heads/topic",
            )

            self.run_git(
                root,
                "--git-dir",
                str(remote),
                "update-ref",
                "-d",
                "refs/heads/topic",
                expected_old,
            )
            self.run_git(
                root,
                "--git-dir",
                str(remote),
                "update-ref",
                "refs/heads/topic",
                expected_old,
            )
            push = self.run_git(
                checkout,
                "push",
                f"--force-with-lease=refs/heads/topic:{expected_old}",
                str(remote),
                f"{prepared}:refs/heads/topic",
                check=False,
            )
            self.assertEqual(push.returncode, 0)
            self.assertEqual(
                self.run_git(
                    root,
                    "--git-dir",
                    str(remote),
                    "rev-parse",
                    "refs/heads/topic",
                ).stdout.strip(),
                prepared,
            )

    def test_push_binding_guard_is_local_only_and_discoverable(self):
        source = PUSH_GUARD.read_text(encoding="utf-8")
        self.assertIn("gitlab_push_binding_guard.receipt.v1", source)
        self.assertIn('"prepare"', source)
        self.assertIn('"verify"', source)
        self.assertNotIn("git push", source)
        self.assertNotIn("git fetch", source)
        self.assertNotIn("requests.", source)
        self.assertNotIn("urllib.request", source)
        self.assertIn('"--no-verify"', source)
        self.assertIn('"--no-signed"', source)
        self.assertIn('"--no-follow-tags"', source)
        self.assertIn('"--no-force-if-includes"', source)
        self.assertIn('"--recurse-submodules=no"', source)
        self.assertIn('("protocol.allow", "never")', source)
        self.assertIn('("protocol.https.allow", "always")', source)
        self.assertIn('"fail-closed"', source)
        self.assertNotIn('"gitlab-review-bound::"', source)

    def test_push_binding_guard_rejects_git_before_path_format_support(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            fake_git = root / "git-2.30"
            fake_git.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "--version" ]; then\n'
                "  printf '%s\\n' 'git version 2.30.0'\n"
                "  exit 0\n"
                "fi\n"
                "exit 99\n",
                encoding="utf-8",
            )
            fake_git.chmod(0o700)

            result = self.run_guard(
                "prepare",
                *fixture["common"],
                "--git",
                str(fake_git),
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                json.loads(result.stdout)["reason_codes"],
                ["UNSUPPORTED_GIT"],
            )
            self.assertNotIn(str(fake_git), result.stdout)
            self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_prepares_and_verifies_exact_local_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)

            prepared = self.run_guard("prepare", *fixture["common"])
            self.assertEqual(prepared.returncode, 0, prepared.stdout)
            self.assertEqual(prepared.stderr, "")
            prepare_receipt = json.loads(prepared.stdout)
            self.assertEqual(prepare_receipt["status"], "READY")
            self.assertEqual(prepare_receipt["phase"], "prepare")
            self.assertEqual(prepare_receipt["reason_codes"], [])
            self.assertEqual(
                set(prepare_receipt["hashes"]),
                set(push_guard.HASH_KEYS),
            )
            self.assertNotIn("gitlab.example.test", prepared.stdout)
            self.assertNotIn(str(root), prepared.stdout)
            self.assertNotIn(fixture["prepared"], prepared.stdout)
            self.assertNotIn(fixture["expected_old"], prepared.stdout)
            self.assertTrue(
                (
                    fixture["transaction"]
                    / "repository.git"
                    / "objects"
                    / "info"
                    / "alternates"
                ).is_file()
            )
            self.assertEqual(
                list((fixture["transaction"] / "hooks").iterdir()),
                [],
            )
            execution_path = fixture["transaction"] / "execution.json"
            execution_manifest = json.loads(execution_path.read_text(encoding="utf-8"))
            self.assertEqual(
                execution_manifest["schema"],
                push_guard.EXECUTION_SCHEMA,
            )
            self.assertEqual(
                execution_manifest["cwd"],
                str(fixture["transaction"]),
            )
            self.assertTrue(Path(execution_manifest["git_binary"]).is_absolute())
            for option in (
                "--no-verify",
                "--no-signed",
                "--no-follow-tags",
                "--no-force-if-includes",
                "--no-push-option",
                "--recurse-submodules=no",
            ):
                self.assertIn(option, execution_manifest["argv"])
            self.assertEqual(
                execution_manifest["environment"]["base"],
                "empty",
            )
            self.assertEqual(
                execution_manifest["environment"]["operation_order"],
                ["clear", "preserve_exact", "set"],
            )
            self.assertEqual(
                execution_manifest["environment"]["preserve_exact"],
                {"PATH": os.environ.get("PATH", "")},
            )
            self.assertEqual(
                execution_manifest["environment"]["set"]["HOME"],
                os.devnull,
            )
            self.assertEqual(
                execution_manifest["environment"]["set"]["XDG_CONFIG_HOME"],
                os.devnull,
            )
            self.assertFalse(Path(os.devnull).is_dir())
            self.assertEqual(
                execution_manifest["environment"]["set"]["GIT_CONFIG_NOSYSTEM"],
                "1",
            )
            self.assertFalse((fixture["transaction"] / ".netrc").exists())
            self.assertFalse((fixture["transaction"] / "git" / "config").exists())
            self.assertEqual(
                execution_path.stat().st_mode & 0o777,
                0o600,
            )
            transaction_git = fixture["transaction"] / "repository.git"
            fail_local_token = self.run_git(
                root,
                "--git-dir",
                str(transaction_git),
                "config",
                "--get",
                "remote.gitlab-review-bound.url",
            ).stdout.strip()
            self.assertTrue(fail_local_token.startswith("file://"))
            self.assertIn("/fail-closed/", fail_local_token)
            self.assertNotIn("gitlab-review-bound::", fail_local_token)
            self.assertEqual(
                self.run_git(
                    root,
                    "--git-dir",
                    str(transaction_git),
                    "config",
                    "--get",
                    "protocol.allow",
                ).stdout.strip(),
                "never",
            )
            self.assertEqual(
                self.run_git(
                    root,
                    "--git-dir",
                    str(transaction_git),
                    "config",
                    "--get",
                    "protocol.https.allow",
                ).stdout.strip(),
                "always",
            )

            receipt_path = fixture["project"].parent / "prepare-receipt.json"
            receipt_path.write_text(prepared.stdout, encoding="utf-8")
            receipt_path.chmod(0o600)
            verified = self.run_guard(
                "verify",
                *fixture["common"],
                "--receipt",
                str(receipt_path),
            )
            self.assertEqual(verified.returncode, 0, verified.stdout)
            verify_receipt = json.loads(verified.stdout)
            self.assertEqual(verify_receipt["status"], "READY")
            self.assertEqual(verify_receipt["phase"], "verify")
            self.assertEqual(
                verify_receipt["hashes"]["prior_receipt_sha256"],
                prepare_receipt["receipt_sha256"],
            )

    def test_push_binding_guard_refuses_duplicate_urls_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            endpoint = "https://gitlab.example.test/group/project.git"
            self.run_git(
                fixture["checkout"],
                "config",
                "--add",
                "remote.publish.pushurl",
                endpoint,
            )
            self.run_git(
                fixture["checkout"],
                "config",
                "--add",
                "remote.publish.pushurl",
                endpoint,
            )

            result = self.run_guard("prepare", *fixture["common"])
            self.assertEqual(result.returncode, 2)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt["status"], "REPORT_ONLY")
            self.assertEqual(
                receipt["reason_codes"],
                ["DUPLICATE_PUSH_URL"],
            )
            self.assertFalse(fixture["transaction"].exists())
            self.assertNotIn(endpoint, result.stdout)

    def test_push_binding_guard_refuses_rewritten_alias_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint = "https://gitlab.example.test/group/project.git"
            alias = "https://alias.example.test/group/project.git"
            fixture = self.make_guard_fixture(
                root,
                endpoint=endpoint,
            )
            self.run_git(
                fixture["checkout"],
                "remote",
                "set-url",
                "publish",
                alias,
            )
            self.run_git(
                fixture["checkout"],
                "config",
                f"url.{endpoint}.pushInsteadOf",
                alias,
            )

            result = self.run_guard("prepare", *fixture["common"])
            self.assertEqual(result.returncode, 2)
            receipt = json.loads(result.stdout)
            self.assertEqual(
                receipt["reason_codes"],
                ["ENDPOINT_MISMATCH"],
            )
            self.assertNotIn(endpoint, result.stdout)
            self.assertNotIn(alias, result.stdout)
            self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_refuses_proxy_and_symlinked_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            proxy = "https://proxy-canary.example.test"
            proxied = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(HTTPS_PROXY=proxy),
            )
            self.assertEqual(proxied.returncode, 2)
            self.assertEqual(
                json.loads(proxied.stdout)["reason_codes"],
                ["AMBIENT_PROXY"],
            )
            self.assertNotIn(proxy, proxied.stdout)
            self.assertFalse(fixture["transaction"].exists())

            self.run_git(
                fixture["checkout"],
                "config",
                "remote.publish.promisor",
                "true",
            )
            promisor = self.run_guard("prepare", *fixture["common"])
            self.assertEqual(promisor.returncode, 2)
            self.assertEqual(
                json.loads(promisor.stdout)["reason_codes"],
                ["INCOMPLETE_OBJECT_CLOSURE"],
            )
            self.assertFalse(fixture["transaction"].exists())
            self.run_git(
                fixture["checkout"],
                "config",
                "--unset",
                "remote.publish.promisor",
            )

            project_link = fixture["project"].parent / "project-link.json"
            project_link.symlink_to(fixture["project"])
            linked_arguments = list(fixture["common"])
            project_index = linked_arguments.index("--project") + 1
            linked_arguments[project_index] = str(project_link)
            linked = self.run_guard("prepare", *linked_arguments)
            self.assertEqual(linked.returncode, 2)
            self.assertEqual(
                json.loads(linked.stdout)["reason_codes"],
                ["UNSAFE_EVIDENCE_FILE"],
            )
            self.assertNotIn(str(project_link), linked.stdout)
            self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_isolates_ambient_bound_remote_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = fixture["project"].parent / "collision-home"
            home.mkdir(mode=0o700)
            collision = "receive-pack-canary"
            (home / ".gitconfig").write_text(
                '[remote "gitlab-review-bound"]\n' f"\treceivepack = {collision}\n",
                encoding="utf-8",
            )

            result = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(HOME=str(home)),
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertNotIn(collision, result.stdout)
            manifest = json.loads(
                (fixture["transaction"] / "execution.json").read_text(encoding="utf-8")
            )
            isolated = subprocess.run(
                [
                    manifest["git_binary"],
                    "--git-dir",
                    str(fixture["transaction"] / "repository.git"),
                    "config",
                    "--get",
                    "remote.gitlab-review-bound.receivepack",
                ],
                cwd=manifest["cwd"],
                env=self.execution_environment(manifest),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(isolated.returncode, 1)
            self.assertEqual(isolated.stdout, "")

    def test_push_binding_guard_isolates_alternate_refs_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = fixture["project"].parent / "alternate-command-home"
            marker = fixture["project"].parent / "alternate-command-marker"
            home.mkdir(mode=0o700)
            (home / ".gitconfig").write_text(
                "[core]\n" f"\talternateRefsCommand = touch {marker}\n",
                encoding="utf-8",
            )

            result = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(HOME=str(home)),
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertFalse(marker.exists())
            self.assertNotIn(str(marker), result.stdout)
            manifest = json.loads(
                (fixture["transaction"] / "execution.json").read_text(encoding="utf-8")
            )
            isolated = subprocess.run(
                [
                    manifest["git_binary"],
                    "--git-dir",
                    str(fixture["transaction"] / "repository.git"),
                    "config",
                    "--get",
                    "core.alternateRefsCommand",
                ],
                cwd=manifest["cwd"],
                env=self.execution_environment(manifest),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(isolated.returncode, 1)
            self.assertFalse(marker.exists())

    def test_push_binding_guard_detects_source_and_transaction_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            prepared = self.run_guard("prepare", *fixture["common"])
            self.assertEqual(prepared.returncode, 0, prepared.stdout)
            receipt_path = fixture["project"].parent / "prepare-receipt.json"
            receipt_path.write_text(prepared.stdout, encoding="utf-8")
            receipt_path.chmod(0o600)

            self.run_git(
                fixture["checkout"],
                "config",
                "contract.drift",
                "changed",
            )
            source_drift = self.run_guard(
                "verify",
                *fixture["common"],
                "--receipt",
                str(receipt_path),
            )
            self.assertEqual(source_drift.returncode, 2)
            self.assertEqual(
                json.loads(source_drift.stdout)["reason_codes"],
                ["CONFIGURATION_DRIFT"],
            )

            self.run_git(
                fixture["checkout"],
                "config",
                "--unset",
                "contract.drift",
            )
            self.run_git(
                root,
                "--git-dir",
                str(fixture["transaction"] / "repository.git"),
                "config",
                "push.followTags",
                "true",
            )
            transaction_drift = self.run_guard(
                "verify",
                *fixture["common"],
                "--receipt",
                str(receipt_path),
            )
            self.assertEqual(transaction_drift.returncode, 2)
            self.assertEqual(
                json.loads(transaction_drift.stdout)["reason_codes"],
                ["TRANSACTION_DRIFT"],
            )

    def test_push_binding_guard_verify_rejects_new_matching_scoped_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = root / "verify-scoped-home"
            home.mkdir(mode=0o700)
            environment = self.guard_environment(HOME=str(home))
            prepared = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=environment,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stdout)
            receipt_path = fixture["project"].parent / "prepare-receipt.json"
            receipt_path.write_text(prepared.stdout, encoding="utf-8")
            receipt_path.chmod(0o600)
            endpoint = "https://gitlab.example.test/group/project.git"
            (home / ".gitconfig").write_text(
                f'[credential "{endpoint}"]\n' "\tusername = changed-account-canary\n",
                encoding="utf-8",
            )

            verified = self.run_guard(
                "verify",
                *fixture["common"],
                "--receipt",
                str(receipt_path),
                environment=environment,
            )
            self.assertEqual(verified.returncode, 2, verified.stdout)
            self.assertEqual(
                json.loads(verified.stdout)["reason_codes"],
                ["CONFIGURATION_DRIFT"],
            )
            self.assertNotIn(endpoint, verified.stdout)
            self.assertNotIn("changed-account-canary", verified.stdout)

    def test_push_binding_guard_detects_execution_manifest_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            prepared = self.run_guard("prepare", *fixture["common"])
            self.assertEqual(prepared.returncode, 0, prepared.stdout)
            receipt_path = fixture["project"].parent / "prepare-receipt.json"
            receipt_path.write_text(prepared.stdout, encoding="utf-8")
            receipt_path.chmod(0o600)

            execution_path = fixture["transaction"] / "execution.json"
            manifest = json.loads(execution_path.read_text(encoding="utf-8"))
            manifest["argv"].append("--private-canary=secret.example.test")
            execution_path.write_text(
                push_guard._canonical(manifest) + "\n",
                encoding="utf-8",
            )

            result = self.run_guard(
                "verify",
                *fixture["common"],
                "--receipt",
                str(receipt_path),
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                json.loads(result.stdout)["reason_codes"],
                ["TRANSACTION_DRIFT"],
            )
            self.assertNotIn("secret.example.test", result.stdout)
            self.assertEqual(result.stderr, "")

    def test_push_binding_guard_rejects_tampered_receipt_without_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            prepared = self.run_guard("prepare", *fixture["common"])
            self.assertEqual(prepared.returncode, 0, prepared.stdout)
            tampered = json.loads(prepared.stdout)
            tampered["private-canary"] = (
                "https://secret.example.test/private/project.git"
            )
            receipt_path = fixture["project"].parent / "tampered-receipt.json"
            self.write_private_json(receipt_path, tampered)

            result = self.run_guard(
                "verify",
                *fixture["common"],
                "--receipt",
                str(receipt_path),
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(
                json.loads(result.stdout)["reason_codes"],
                ["RECEIPT_INVALID"],
            )
            self.assertNotIn("secret.example.test", result.stdout)
            self.assertEqual(result.stderr, "")

            noncanonical_path = fixture["project"].parent / "noncanonical-receipt.json"
            noncanonical_path.write_text(
                json.dumps(json.loads(prepared.stdout), indent=2) + "\n",
                encoding="utf-8",
            )
            noncanonical_path.chmod(0o600)
            noncanonical = self.run_guard(
                "verify",
                *fixture["common"],
                "--receipt",
                str(noncanonical_path),
            )
            self.assertEqual(noncanonical.returncode, 1)
            self.assertEqual(
                json.loads(noncanonical.stdout)["reason_codes"],
                ["RECEIPT_INVALID"],
            )

    def test_push_binding_guard_subprocess_allowlist_is_local_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            arguments = push_guard.build_parser().parse_args(
                ["prepare", *fixture["common"]]
            )
            observed = []
            real_run = push_guard._run

            def recording_run(command, **kwargs):
                observed.append(list(command))
                return real_run(command, **kwargs)

            with (
                mock.patch.dict(
                    os.environ,
                    self.guard_environment(),
                    clear=True,
                ),
                mock.patch.object(
                    push_guard,
                    "_run",
                    side_effect=recording_run,
                ),
            ):
                receipt = push_guard.command_prepare(arguments)

            self.assertEqual(receipt["status"], "READY")
            self.assertGreater(len(observed), 10)
            forbidden = {
                "credential",
                "fetch",
                "ls-remote",
                "push",
                "receive-pack",
                "upload-pack",
            }
            for command in observed:
                self.assertNotEqual(command, [])
                self.assertEqual(
                    Path(command[0]).name,
                    "git",
                )
                self.assertTrue(
                    forbidden.isdisjoint(command),
                    command,
                )

    def test_push_binding_guard_rejects_injected_transaction_auth_config(self):
        cases = (
            (
                "credential.https://gitlab.example.test/group/project.git.helper",
                "!touch AUTH_MARKER",
                "CONFIGURATION_DRIFT",
            ),
            (
                "http.extraHeader",
                "Authorization: transaction-canary",
                "CONFIGURATION_DRIFT",
            ),
            (
                "http.cookieFile",
                "transaction-cookie-canary",
                "CONFIGURATION_DRIFT",
            ),
            (
                "http.saveCookies",
                "true",
                "CONFIGURATION_DRIFT",
            ),
            (
                "http.emptyAuth",
                "true",
                "TRANSACTION_DRIFT",
            ),
            (
                "http.delegation",
                "always",
                "TRANSACTION_DRIFT",
            ),
        )
        for key, value_template, expected_code in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture = self.make_guard_fixture(root)
                marker = root / "transaction-auth-marker"
                value = value_template.replace("AUTH_MARKER", str(marker))
                arguments = push_guard.build_parser().parse_args(
                    ["prepare", *fixture["common"]]
                )
                real_prepare = push_guard._prepare_transaction

                def injecting_prepare(**kwargs):
                    real_prepare(**kwargs)
                    self.run_git(
                        root,
                        "--git-dir",
                        str(fixture["transaction"] / "repository.git"),
                        "config",
                        "--add",
                        key,
                        value,
                    )

                with (
                    mock.patch.dict(
                        os.environ,
                        self.guard_environment(),
                        clear=True,
                    ),
                    mock.patch.object(
                        push_guard,
                        "_prepare_transaction",
                        side_effect=injecting_prepare,
                    ),
                    self.assertRaises(push_guard.ReportOnly) as raised,
                ):
                    push_guard.command_prepare(arguments)

                self.assertEqual(raised.exception.codes, [expected_code])
                self.assertFalse(marker.exists())

    def test_push_binding_guard_rejects_injected_transaction_netrc(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            arguments = push_guard.build_parser().parse_args(
                ["prepare", *fixture["common"]]
            )
            real_prepare = push_guard._prepare_transaction

            def injecting_prepare(**kwargs):
                real_prepare(**kwargs)
                netrc = fixture["transaction"] / ".netrc"
                netrc.write_text(
                    "NETRC_CANARY\n",
                    encoding="utf-8",
                )
                netrc.chmod(0o600)

            with (
                mock.patch.dict(
                    os.environ,
                    self.guard_environment(),
                    clear=True,
                ),
                mock.patch.object(
                    push_guard,
                    "_prepare_transaction",
                    side_effect=injecting_prepare,
                ),
                self.assertRaises(push_guard.ReportOnly) as raised,
            ):
                push_guard.command_prepare(arguments)

            self.assertEqual(raised.exception.codes, ["TRANSACTION_DRIFT"])

    def test_push_binding_guard_ignores_hostile_init_template(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            template = root / "hostile-template"
            hooks = template / "hooks"
            home.mkdir(mode=0o700)
            hooks.mkdir(parents=True)
            canary = hooks / "pre-push"
            canary.write_text("HOSTILE_TEMPLATE_CANARY\n", encoding="utf-8")
            config = home / ".gitconfig"
            config.write_text(
                "[init]\n" f"\ttemplateDir = {template}\n",
                encoding="utf-8",
            )
            fixture = self.make_guard_fixture(root)

            result = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(HOME=str(home)),
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            transaction_text = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in fixture["transaction"].rglob("*")
                if path.is_file() and path.stat().st_size < 1024 * 1024
            )
            self.assertNotIn("HOSTILE_TEMPLATE_CANARY", transaction_text)
            self.assertEqual(
                list((fixture["transaction"] / "hooks").iterdir()),
                [],
            )

    def test_push_binding_guard_rejects_matching_scoped_credential_records(self):
        cases = (
            (
                "exact-empty-helper-reset",
                "[credential]\n"
                "\thelper = store\n"
                '[credential "https://gitlab.example.test/group/project.git"]\n'
                "\thelper =\n",
            ),
            (
                "host-username",
                '[credential "https://gitlab.example.test"]\n'
                "\tusername = intended-account\n",
            ),
            (
                "path-use-http-path",
                '[credential "https://gitlab.example.test/group"]\n'
                "\tuseHttpPath = false\n",
            ),
            (
                "wildcard-helper",
                '[credential "https://*.example.test"]\n' "\thelper = store\n",
            ),
            (
                "implicit-default-port",
                '[credential "https://gitlab.example.test:443"]\n'
                "\tusername = default-port-account\n",
            ),
        )
        for name, config_text in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture = self.make_guard_fixture(root)
                home = root / "matching-scoped-home"
                home.mkdir(mode=0o700)
                (home / ".gitconfig").write_text(config_text, encoding="utf-8")

                result = self.run_guard(
                    "prepare",
                    *fixture["common"],
                    environment=self.guard_environment(HOME=str(home)),
                )
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(
                    json.loads(result.stdout)["reason_codes"],
                    ["CONFIGURATION_DRIFT"],
                )
                self.assertNotIn("intended-account", result.stdout)
                self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_rejects_unrepresentable_scoped_credential_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = root / "unrepresentable-scoped-home"
            canary = "unrepresentable-private-canary"
            home.mkdir(mode=0o700)
            (home / ".gitconfig").write_text(
                '[credential "https://other.example.test/a=b"]\n'
                f"\tusername = {canary}\n",
                encoding="utf-8",
            )

            result = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(HOME=str(home)),
            )
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(
                json.loads(result.stdout)["reason_codes"],
                ["CONFIGURATION_DRIFT"],
            )
            self.assertNotIn(canary, result.stdout)
            self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_rejects_nonhelper_generic_credential_keys(self):
        cases = (
            ("username", "intended-account"),
            ("useHttpPath", "false"),
            ("interactive", "always"),
        )
        for key, value in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture = self.make_guard_fixture(root)
                home = root / "generic-credential-home"
                home.mkdir(mode=0o700)
                (home / ".gitconfig").write_text(
                    "[credential]\n" f"\t{key} = {value}\n",
                    encoding="utf-8",
                )

                result = self.run_guard(
                    "prepare",
                    *fixture["common"],
                    environment=self.guard_environment(HOME=str(home)),
                )
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(
                    json.loads(result.stdout)["reason_codes"],
                    ["CONFIGURATION_DRIFT"],
                )
                self.assertNotIn("intended-account", result.stdout)
                self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_isolates_unmatched_https_auth_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            endpoint = "https://gitlab.example.test/group/project.git"
            home = fixture["project"].parent / "ambient-auth-home"
            marker = fixture["project"].parent / "url-helper-marker"
            cookie = fixture["project"].parent / "cookie-canary"
            authorization_canary = "Authorization: ambient-canary"
            home.mkdir(mode=0o700)
            netrc = home / ".netrc"
            netrc.write_text(
                "NETRC_CANARY\n",
                encoding="utf-8",
            )
            netrc.chmod(0o600)
            (home / ".gitconfig").write_text(
                "[credential]\n"
                "\thelper =\n"
                '[credential "https://other.example.test"]\n'
                f"\thelper = !touch {marker}\n"
                '[credential "https://gitlab.example.test/groupish"]\n'
                "\tusername = path-boundary-canary\n"
                '[credential "https://gitlab.example.test:8443"]\n'
                "\tuseHttpPath = false\n"
                "[http]\n"
                f"\textraHeader = {authorization_canary}\n"
                f"\tcookieFile = {cookie}\n"
                "\tsaveCookies = true\n",
                encoding="utf-8",
            )
            prepared = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(HOME=str(home)),
            )
            self.assertEqual(prepared.returncode, 0, prepared.stdout)
            self.assertNotIn(authorization_canary, prepared.stdout)
            self.assertNotIn(str(marker), prepared.stdout)
            self.assertNotIn(str(cookie), prepared.stdout)
            manifest = json.loads(
                (fixture["transaction"] / "execution.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["environment"]["set"]["HOME"],
                os.devnull,
            )
            self.assertEqual(
                manifest["environment"]["set"]["XDG_CONFIG_HOME"],
                os.devnull,
            )
            isolated_environment = self.execution_environment(manifest)
            isolated_helper = subprocess.run(
                [
                    manifest["git_binary"],
                    "--git-dir",
                    str(fixture["transaction"] / "repository.git"),
                    "credential",
                    "fill",
                ],
                cwd=manifest["cwd"],
                env=isolated_environment,
                input=(
                    "protocol=https\n"
                    "host=gitlab.example.test\n"
                    "path=group/project.git\n\n"
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertNotEqual(isolated_helper.returncode, 0)
            self.assertFalse(marker.exists())
            self.assertFalse((fixture["transaction"] / ".netrc").exists())
            for key in (
                "http.extraHeader",
                "http.cookieFile",
                "http.saveCookies",
            ):
                isolated_http = subprocess.run(
                    [
                        manifest["git_binary"],
                        "--git-dir",
                        str(fixture["transaction"] / "repository.git"),
                        "config",
                        "--get-urlmatch",
                        key,
                        endpoint,
                    ],
                    cwd=manifest["cwd"],
                    env=isolated_environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(isolated_http.returncode, 1)
                self.assertEqual(isolated_http.stdout, "")

    def test_push_binding_guard_rejects_ambient_git_environment(self):
        cases = (
            ("GIT_CONFIG_COUNT", "count-private-canary"),
            ("GIT_CONFIG_GLOBAL", "private-config-canary"),
            ("GIT_TERMINAL_PROMPT", "prompt-private-canary"),
        )
        for name, value in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture = self.make_guard_fixture(root)
                environment = self.guard_environment(**{name: value})
                result = self.run_guard(
                    "prepare",
                    *fixture["common"],
                    environment=environment,
                )
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(
                    json.loads(result.stdout)["reason_codes"],
                    ["CONFIGURATION_DRIFT"],
                )
                self.assertNotIn(value, result.stdout)
                self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_normalizes_generic_helper_to_absolute_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = root / "normalized-helper-home"
            helper_directory = root / "helpers"
            helper = helper_directory / "git-credential-contract-helper"
            home.mkdir(mode=0o700)
            helper_directory.mkdir(mode=0o700)
            helper.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            helper.chmod(0o700)
            (home / ".gitconfig").write_text(
                "[credential]\n" "\thelper = contract-helper\n",
                encoding="utf-8",
            )
            execution_path = (
                str(helper_directory)
                + os.pathsep
                + self.guard_environment().get("PATH", "")
            )
            prepared = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(
                    HOME=str(home),
                    PATH=execution_path,
                ),
            )
            self.assertEqual(prepared.returncode, 0, prepared.stdout)
            manifest = json.loads(
                (fixture["transaction"] / "execution.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["environment"]["preserve_exact"]["PATH"],
                execution_path,
            )
            configured_helpers = self.run_git(
                root,
                "--git-dir",
                str(fixture["transaction"] / "repository.git"),
                "config",
                "--get-all",
                "credential.helper",
            ).stdout.splitlines()
            self.assertEqual(configured_helpers[0], "")
            self.assertEqual(configured_helpers[-1], str(helper.resolve()))
            self.assertTrue(
                all(Path(value).is_absolute() for value in configured_helpers[1:])
            )
            self.assertNotIn("contract-helper", configured_helpers)

    def test_push_binding_guard_rejects_cwd_dependent_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = root / "relative-path-home"
            cwd = root / "guard-cwd"
            helper = cwd / "git-credential-cwd-canary"
            marker = root / "cwd-helper-marker"
            home.mkdir(mode=0o700)
            cwd.mkdir(mode=0o700)
            helper.write_text(
                "#!/bin/sh\n" f'printf "ran\\n" > "{marker}"\n',
                encoding="utf-8",
            )
            helper.chmod(0o700)
            (home / ".gitconfig").write_text(
                "[credential]\n" "\thelper = cwd-canary\n",
                encoding="utf-8",
            )
            result = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(
                    HOME=str(home),
                    PATH="." + os.pathsep + os.environ.get("PATH", ""),
                ),
                cwd=cwd,
            )
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(
                json.loads(result.stdout)["reason_codes"],
                ["CONFIGURATION_DRIFT"],
            )
            self.assertFalse(marker.exists())
            self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_clears_arbitrary_ambient_helper_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = root / "helper-home"
            helper = root / "git-credential-env-canary"
            token_a = "AMBIENT_TOKEN_A_CANARY"
            token_b = "AMBIENT_TOKEN_B_CANARY"
            home.mkdir(mode=0o700)
            helper.write_text(
                "#!/bin/sh\n"
                'if [ "$1" = "get" ] && [ -n "$AUTH_TOKEN" ]; then\n'
                '  printf "username=test\\npassword=%s\\n" "$AUTH_TOKEN"\n'
                "fi\n",
                encoding="utf-8",
            )
            helper.chmod(0o700)
            (home / ".gitconfig").write_text(
                "[credential]\n" f"\thelper = {helper}\n",
                encoding="utf-8",
            )
            prepare_environment = self.guard_environment(
                HOME=str(home),
                AUTH_TOKEN=token_a,
            )
            prepared = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=prepare_environment,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stdout)
            self.assertNotIn(token_a, prepared.stdout)
            manifest = json.loads(
                (fixture["transaction"] / "execution.json").read_text(encoding="utf-8")
            )
            isolated_environment = self.execution_environment(manifest)
            self.assertNotIn("AUTH_TOKEN", isolated_environment)
            fill = subprocess.run(
                [
                    manifest["git_binary"],
                    "--git-dir",
                    str(fixture["transaction"] / "repository.git"),
                    "credential",
                    "fill",
                ],
                cwd=manifest["cwd"],
                env=isolated_environment,
                input=(
                    "protocol=https\n"
                    "host=gitlab.example.test\n"
                    "path=group/project.git\n\n"
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertNotIn(token_a, fill.stdout + fill.stderr)

            receipt = fixture["project"].parent / "prepare-receipt.json"
            receipt.write_text(prepared.stdout, encoding="utf-8")
            receipt.chmod(0o600)
            verified = self.run_guard(
                "verify",
                *fixture["common"],
                "--receipt",
                str(receipt),
                environment=self.guard_environment(
                    HOME=str(home),
                    AUTH_TOKEN=token_b,
                ),
            )
            self.assertEqual(verified.returncode, 0, verified.stdout)
            self.assertNotIn(token_b, verified.stdout)

    def test_push_binding_guard_rejects_generic_shell_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = fixture["project"].parent / "shell-helper-home"
            marker = fixture["project"].parent / "shell-helper-marker"
            home.mkdir(mode=0o700)
            (home / ".gitconfig").write_text(
                "[credential]\n" f"\thelper = !touch {marker}\n",
                encoding="utf-8",
            )
            shell_helper = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(HOME=str(home)),
            )
            self.assertEqual(shell_helper.returncode, 2)
            self.assertEqual(
                json.loads(shell_helper.stdout)["reason_codes"],
                ["CONFIGURATION_DRIFT"],
            )
            self.assertFalse(marker.exists())
            self.assertNotIn(str(marker), shell_helper.stdout)

    def test_push_binding_guard_rejects_generic_helper_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = fixture["project"].parent / "helper-argument-home"
            canary = "helper-argument-private-canary"
            home.mkdir(mode=0o700)
            (home / ".gitconfig").write_text(
                "[credential]\n" f"\thelper = cache --socket={canary}\n",
                encoding="utf-8",
            )
            result = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(HOME=str(home)),
            )
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(
                json.loads(result.stdout)["reason_codes"],
                ["CONFIGURATION_DRIFT"],
            )
            self.assertNotIn(canary, result.stdout)
            self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_reports_unsafe_generic_helper_as_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            home = fixture["project"].parent / "unsafe-helper-home"
            helper = fixture["project"].parent / "git-credential-unsafe-helper"
            home.mkdir(mode=0o700)
            helper.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            helper.chmod(0o770)
            (home / ".gitconfig").write_text(
                "[credential]\n" f"\thelper = {helper}\n",
                encoding="utf-8",
            )
            result = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(HOME=str(home)),
            )
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(result.stderr, "")
            self.assertEqual(
                json.loads(result.stdout)["reason_codes"],
                ["CONFIGURATION_DRIFT"],
            )
            self.assertNotIn(str(helper), result.stdout)
            self.assertFalse(fixture["transaction"].exists())

    def test_push_binding_guard_rejects_dot_path_and_custom_tls_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint = "https://gitlab.example.test/group/../project.git"
            fixture = self.make_guard_fixture(root, endpoint=endpoint)
            dot_path = self.run_guard("prepare", *fixture["common"])
            self.assertEqual(dot_path.returncode, 2)
            self.assertEqual(
                json.loads(dot_path.stdout)["reason_codes"],
                ["HTTPS_BASELINE_UNAVAILABLE"],
            )
            self.assertNotIn(endpoint, dot_path.stdout)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.make_guard_fixture(root)
            ca_canary = str(fixture["project"].parent / "custom-ca-canary.pem")
            custom_tls = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(SSL_CERT_FILE=ca_canary),
            )
            self.assertEqual(custom_tls.returncode, 2)
            self.assertEqual(
                json.loads(custom_tls.stdout)["reason_codes"],
                ["HTTPS_BASELINE_UNAVAILABLE"],
            )
            self.assertNotIn(ca_canary, custom_tls.stdout)
            self.assertFalse(fixture["transaction"].exists())

            askpass_canary = str(fixture["project"].parent / "ssh-askpass-canary")
            custom_askpass = self.run_guard(
                "prepare",
                *fixture["common"],
                environment=self.guard_environment(
                    SSH_ASKPASS=askpass_canary,
                ),
            )
            self.assertEqual(custom_askpass.returncode, 2)
            self.assertEqual(
                json.loads(custom_askpass.stdout)["reason_codes"],
                ["HTTPS_BASELINE_UNAVAILABLE"],
            )
            self.assertNotIn(askpass_canary, custom_askpass.stdout)
            self.assertFalse(Path(askpass_canary).exists())
            self.assertFalse(fixture["transaction"].exists())

    def test_transaction_mode_normalization_never_follows_directory_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            envelope = root / "envelope"
            external = root / "external"
            envelope.mkdir(mode=0o700)
            external.mkdir(mode=0o755)
            link = envelope / "injected-directory"
            link.symlink_to(external, target_is_directory=True)
            original_mode = external.stat().st_mode

            with self.assertRaises(push_guard.ReportOnly):
                push_guard._normalize_transaction_modes(envelope)

            self.assertEqual(external.stat().st_mode, original_mode)
            self.assertTrue(link.is_symlink())

    def test_push_binding_guard_sha256_transaction_matches_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            probe = self.run_git(
                root,
                "init",
                "--bare",
                "--object-format=sha256",
                str(root / "probe.git"),
                check=False,
            )
            if probe.returncode != 0:
                self.skipTest("installed Git does not support SHA-256 repos")
            fixture = self.make_guard_fixture(
                root,
                object_format="sha256",
            )
            result = self.run_guard("prepare", *fixture["common"])
            self.assertEqual(result.returncode, 0, result.stdout)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt["object_format"], "sha256")
            transaction_format = self.run_git(
                root,
                "--git-dir",
                str(fixture["transaction"] / "repository.git"),
                "rev-parse",
                "--show-object-format=storage",
            ).stdout.strip()
            self.assertEqual(transaction_format, "sha256")

    def test_transaction_nonce_rewrite_is_one_pass_and_clears_push_options(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "checkout"
            intended = root / "intended.git"
            unintended = root / "unintended.git"
            transaction = root / "transaction.git"
            hooks = root / "empty-hooks"
            home = root / "home"
            marker = root / "push-option-marker"
            ssh_marker = root / "ssh-helper-marker"
            fake_bin = root / "fake-bin"
            self.run_git(root, "init", str(checkout))
            self.run_git(root, "init", "--bare", str(intended))
            self.run_git(root, "init", "--bare", str(unintended))
            self.run_git(checkout, "config", "user.name", "Contract Test")
            self.run_git(
                checkout,
                "config",
                "user.email",
                "contract-test@example.test",
            )
            self.run_git(checkout, "commit", "--allow-empty", "-m", "epoch")
            expected_old = self.run_git(
                checkout,
                "rev-parse",
                "HEAD",
            ).stdout.strip()
            self.run_git(checkout, "commit", "--allow-empty", "-m", "prepared")
            prepared = self.run_git(
                checkout,
                "rev-parse",
                "HEAD",
            ).stdout.strip()
            self.run_git(
                checkout,
                "push",
                str(intended),
                f"{expected_old}:refs/heads/topic",
            )
            self.run_git(
                root,
                "--git-dir",
                str(intended),
                "config",
                "receive.advertisePushOptions",
                "true",
            )
            server_hook = intended / "hooks" / "pre-receive"
            server_hook.write_text(
                "#!/bin/sh\n"
                f'test "${{GIT_PUSH_OPTION_COUNT:-0}}" = 0 || '
                f'printf "%s\\n" option > "{marker}"\n'
                "exit 0\n",
                encoding="utf-8",
            )
            server_hook.chmod(0o700)

            self.run_git(root, "init", "--bare", str(transaction))
            hooks.mkdir(mode=0o700)
            alternate = transaction / "objects" / "info" / "alternates"
            alternate.write_text(
                str((checkout / ".git" / "objects").resolve()) + "\n",
                encoding="utf-8",
            )
            sentinel = root / "missing-sentinel" / ("a" * 64)
            token = sentinel.resolve(strict=False).as_uri()
            self.run_git(
                root,
                "--git-dir",
                str(transaction),
                "config",
                "remote.bound.url",
                token,
            )
            self.run_git(
                root,
                "--git-dir",
                str(transaction),
                "config",
                f"url.{intended}.pushInsteadOf",
                token,
            )
            self.run_git(
                root,
                "--git-dir",
                str(transaction),
                "config",
                "--add",
                "push.pushOption",
                "",
            )
            self.run_git(
                root,
                "--git-dir",
                str(transaction),
                "config",
                "core.hooksPath",
                str(hooks),
            )

            home.mkdir(mode=0o700)
            fake_bin.mkdir(mode=0o700)
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text(
                "#!/bin/sh\n" f'printf "%s\\n" invoked > "{ssh_marker}"\n' "exit 97\n",
                encoding="utf-8",
            )
            fake_ssh.chmod(0o700)
            (home / ".gitconfig").write_text(
                f'[url "{unintended}"]\n'
                f"\tpushInsteadOf = {intended}\n"
                "[push]\n"
                "\tpushOption = GLOBAL_CANARY\n",
                encoding="utf-8",
            )
            environment = self.guard_environment(HOME=str(home))
            environment["PATH"] = (
                str(fake_bin) + os.pathsep + environment.get("PATH", "")
            )
            environment["GIT_CONFIG_NOSYSTEM"] = "1"
            push = subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(transaction),
                    "push",
                    "--porcelain",
                    "--no-verify",
                    "--no-signed",
                    "--no-follow-tags",
                    "--no-tags",
                    "--no-set-upstream",
                    "--no-force-if-includes",
                    "--no-push-option",
                    "--recurse-submodules=no",
                    f"--force-with-lease=refs/heads/topic:{expected_old}",
                    "bound",
                    f"{prepared}:refs/heads/topic",
                ],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(push.returncode, 0, push.stderr)
            intended_head = self.run_git(
                root,
                "--git-dir",
                str(intended),
                "rev-parse",
                "refs/heads/topic",
            ).stdout.strip()
            self.assertEqual(intended_head, prepared)
            unintended_head = self.run_git(
                root,
                "--git-dir",
                str(unintended),
                "rev-parse",
                "--verify",
                "refs/heads/topic",
                check=False,
            )
            self.assertNotEqual(unintended_head.returncode, 0)
            self.assertFalse(marker.exists())

            self.run_git(
                root,
                "--git-dir",
                str(transaction),
                "config",
                "--unset-all",
                f"url.{intended}.pushInsteadOf",
            )
            self.run_git(
                root,
                "--git-dir",
                str(transaction),
                "config",
                "protocol.file.allow",
                "never",
            )
            rewrite_missing = subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(transaction),
                    "push",
                    "--porcelain",
                    "--no-verify",
                    "--no-signed",
                    "--no-follow-tags",
                    "--no-tags",
                    "--no-set-upstream",
                    "--no-force-if-includes",
                    "--no-push-option",
                    "--recurse-submodules=no",
                    f"--force-with-lease=refs/heads/topic:{prepared}",
                    "bound",
                    f"{prepared}:refs/heads/topic",
                ],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertNotEqual(rewrite_missing.returncode, 0)
            self.assertFalse(sentinel.exists())
            self.assertFalse(ssh_marker.exists())


if __name__ == "__main__":
    unittest.main()
