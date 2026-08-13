import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "plugin_catalog.py"
SPEC = importlib.util.spec_from_file_location("plugin_catalog", SCRIPT)
assert SPEC and SPEC.loader
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


def git(cwd, *args):
    result = subprocess.run(["git", *args], cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


class FirstPartyPluginsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "catalog"
        self.source = self.base / "source"
        self.remote = self.base / "remote.git"
        (self.root / "docs" / "first-party-plugins").mkdir(parents=True)
        (self.root / "assets" / "first-party-plugins").mkdir(parents=True)
        self.source.mkdir()
        git(self.source, "init", "--quiet")
        git(self.source, "config", "user.email", "test@example.invalid")
        git(self.source, "config", "user.name", "Test")
        self._write_plugin()
        git(self.source, "add", ".")
        git(self.source, "commit", "--quiet", "-m", "fixture")
        self.commit = git(self.source, "rev-parse", "HEAD")
        self.tree = git(self.source, "rev-parse", "HEAD^{tree}")
        git(self.base, "clone", "--quiet", "--bare", str(self.source), str(self.remote))
        self.lock = self._lock()
        self._write_receipt()
        self._write_lock()
        self.validator = self.base / "validator.py"
        self.validator.write_text("raise SystemExit(0)\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _manifest(self):
        return {
            "name": "sample-plugin", "version": "1.2.3", "description": "Fixture plugin.",
            "author": {"name": "Example"}, "license": "MIT", "skills": "./skills/",
            "interface": {"displayName": "Sample", "shortDescription": "Fixture.", "longDescription": "Fixture plugin for tests.", "developerName": "Example", "category": "Productivity", "capabilities": [], "defaultPrompt": ["Use sample."], "brandColor": "#112233", "composerIcon": "./assets/icon.png", "logo": "./assets/icon.png"},
        }

    def _write_plugin(self):
        manifest = self._manifest()
        for folder in (".codex-plugin", ".claude-plugin"):
            (self.source / folder).mkdir()
            payload = manifest if folder == ".codex-plugin" else {key: manifest[key] for key in ("name", "version", "description", "author", "license")}
            (self.source / folder / "plugin.json").write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        (self.source / "skills" / "sample").mkdir(parents=True)
        (self.source / "skills" / "sample" / "SKILL.md").write_text("---\nname: sample\ndescription: Sample.\n---\n", encoding="utf-8")
        (self.source / "references").mkdir(); (self.source / "references" / "one.md").write_text("one\n", encoding="utf-8")
        (self.source / "scripts").mkdir(); (self.source / "scripts" / "one.py").write_text("pass\n", encoding="utf-8")
        (self.source / "assets").mkdir()
        icon = Image.new("RGB", (1024, 1024), (17, 34, 51))
        for x in range(256, 768):
            for y in range(256, 768):
                icon.putpixel((x, y), (220, 120, 40))
        icon.save(self.source / "assets" / "icon.png")

    def _lock(self):
        def digest(relative):
            result = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=self.source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return hashlib.sha256(result.stdout).hexdigest()
        return {"schemaVersion": 1, "publishers": [{"id": "example", "displayName": "Example", "githubOwner": "example", "homepage": "https://example.invalid"}], "plugins": [{
            "name": "sample-plugin", "displayName": "Sample Plugin", "publisher": "example", "description": "Fixture plugin.",
            "source": {"provider": "github", "repository": "example/sample-plugin", "commit": self.commit, "tree": self.tree},
            "manifest": {"version": "1.2.3", "codexSha256": digest(".codex-plugin/plugin.json"), "claudeSha256": digest(".claude-plugin/plugin.json")},
            "license": "MIT", "selection": {"default": True}, "receipt": "docs/first-party-plugins/sample-plugin.json"
        }]}

    def _write_receipt(self):
        plugin = self.lock["plugins"][0]
        icon_bytes = (self.source / "assets" / "icon.png").read_bytes()
        snapshot = self.root / "assets" / "first-party-plugins" / "sample-plugin.png"
        snapshot.write_bytes(icon_bytes)
        receipt = {"schemaVersion": 1, "name": plugin["name"], "source": plugin["source"], "version": plugin["manifest"]["version"], "manifest": {"codexSha256": plugin["manifest"]["codexSha256"], "claudeSha256": plugin["manifest"]["claudeSha256"]}, "license": "MIT", "verifiedAt": "2026-08-13", "skills": {"count": 1, "items": [{"name": "sample", "path": "skills/sample/SKILL.md", "description": "Sample.", "startupTokens": 12, "bodyTokens": 4}]}, "counts": {"references": 1, "scripts": 1}, "tokens": {"encoding": "o200k_base", "startup": 12, "body": 4}, "icons": {"composerIcon": "./assets/icon.png", "logo": "./assets/icon.png", "brandColor": "#112233", "sha256": hashlib.sha256(icon_bytes).hexdigest(), "catalogAsset": "assets/first-party-plugins/sample-plugin.png"}}
        (self.root / "docs" / "first-party-plugins" / "sample-plugin.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    def _write_lock(self):
        (self.root / "first-party-plugins.lock.json").write_text(json.dumps(self.lock, indent=2) + "\n", encoding="utf-8")

    def resolver(self, _plugin): return str(self.remote)

    def test_valid_catalog_and_materialize_offline_cache(self):
        self.assertEqual(catalog.validate_catalog(self.root), self.lock)
        cache = self.base / "cache"
        materialized = catalog.materialize(self.root, "sample-plugin", cache_root=cache, repository_url_resolver=self.resolver)
        self.assertEqual(git(materialized, "rev-parse", "HEAD"), self.commit)
        self.remote.rename(self.base / "remote-gone.git")
        self.assertEqual(catalog.materialize(self.root, "sample-plugin", offline=True, cache_root=cache, repository_url_resolver=lambda _: self.fail("network")), materialized)

    def test_offline_cache_miss_is_deterministic(self):
        with self.assertRaisesRegex(catalog.SourceError, "offline cache miss"):
            catalog.materialize(self.root, "sample-plugin", offline=True, cache_root=self.base / "empty", validator=self.validator)

    def test_rejects_mutable_and_wrong_pins(self):
        self.lock["plugins"][0]["source"]["commit"] = "main"
        self._write_lock()
        with self.assertRaisesRegex(catalog.ValidationError, "immutable digest"):
            catalog.validate_catalog(self.root)
        self.lock = self._lock(); self.lock["plugins"][0]["source"]["tree"] = "0" * 40; self._write_receipt(); self._write_lock()
        with self.assertRaisesRegex(catalog.SourceError, "fetched source does not match"):
            catalog.materialize(self.root, "sample-plugin", cache_root=self.base / "cache2", repository_url_resolver=self.resolver, validator=self.validator)

    def test_rejects_manifest_hash_mismatch(self):
        self.lock["plugins"][0]["manifest"]["codexSha256"] = "0" * 64
        self._write_receipt(); self._write_lock()
        with self.assertRaisesRegex(catalog.SourceError, "codexSha256 mismatch"):
            catalog.materialize(self.root, "sample-plugin", cache_root=self.base / "cache3", repository_url_resolver=self.resolver, validator=self.validator)

    def test_rejects_catalog_icon_snapshot_drift(self):
        snapshot = self.root / "assets" / "first-party-plugins" / "sample-plugin.png"
        snapshot.write_bytes(snapshot.read_bytes() + b"drift")
        with self.assertRaisesRegex(catalog.ValidationError, "does not match icons.sha256"):
            catalog.validate_catalog(self.root)

    def test_rejects_unknown_and_duplicate_json_keys(self):
        self.lock["plugins"][0]["executable"] = "install.py"; self._write_lock()
        with self.assertRaisesRegex(catalog.ValidationError, "unknown keys executable"):
            catalog.validate_catalog(self.root)
        self._write_lock(); path = self.root / "first-party-plugins.lock.json"; text = path.read_text(encoding="utf-8").replace('"schemaVersion": 1,', '"schemaVersion": 1,\n  "schemaVersion": 1,', 1); path.write_text(text, encoding="utf-8")
        with self.assertRaisesRegex(catalog.ValidationError, "duplicate key"):
            catalog.validate_catalog(self.root)

    def test_checkout_rejects_nonmatching_nonempty_destination(self):
        dest = self.base / "checkout"; dest.mkdir(); (dest / "user.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(catalog.SourceError, "destination is nonempty"):
            catalog.checkout(self.root, "sample-plugin", dest, repository_url_resolver=self.resolver, validator=self.validator)
        self.assertEqual((dest / "user.txt").read_text(encoding="utf-8"), "keep")

    def test_checkout_creates_detached_exact_workspace_and_mapping(self):
        dest = self.base / "checkout-good"
        result = catalog.checkout(self.root, "sample-plugin", dest, cache_root=self.base / "checkout-cache", repository_url_resolver=self.resolver, validator=self.validator)
        self.assertEqual(result, dest)
        self.assertEqual(git(dest, "rev-parse", "HEAD"), self.commit)
        detached = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=dest, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(detached.returncode, 1)
        mapping = json.loads((self.root / ".agents" / "first-party-workspaces.json").read_text(encoding="utf-8"))
        self.assertEqual(mapping["workspaces"]["sample-plugin"]["commit"], self.commit)

    def test_rejects_symlink_mode_before_checkout(self):
        link_source = self.base / "link-source"; subprocess.run(["git", "clone", "--quiet", str(self.source), str(link_source)], check=True)
        git(link_source, "config", "user.email", "test@example.invalid"); git(link_source, "config", "user.name", "Test")
        target = link_source / "linked"; target.write_text("references/one.md", encoding="utf-8"); git(link_source, "add", "linked"); git(link_source, "update-index", "--cacheinfo", "120000," + git(link_source, "hash-object", "-w", "linked") + ",linked"); git(link_source, "commit", "--quiet", "-m", "link")
        commit, tree = git(link_source, "rev-parse", "HEAD"), git(link_source, "rev-parse", "HEAD^{tree}")
        remote = self.base / "link.git"; git(self.base, "clone", "--quiet", "--bare", str(link_source), str(remote))
        self.lock = self._lock(); self.lock["plugins"][0]["source"].update(commit=commit, tree=tree); self._write_receipt(); self._write_lock()
        with self.assertRaisesRegex(catalog.SourceError, "symbolic links are forbidden"):
            catalog.materialize(self.root, "sample-plugin", cache_root=self.base / "cache4", repository_url_resolver=lambda _: str(remote), validator=self.validator)

    def test_rejects_gitlink_submodule_mode_before_checkout(self):
        module_source = self.base / "module-source"; subprocess.run(["git", "clone", "--quiet", str(self.source), str(module_source)], check=True)
        git(module_source, "config", "user.email", "test@example.invalid"); git(module_source, "config", "user.name", "Test")
        git(module_source, "update-index", "--add", "--cacheinfo", "160000," + self.commit + ",vendor/module")
        git(module_source, "commit", "--quiet", "-m", "gitlink")
        commit, tree = git(module_source, "rev-parse", "HEAD"), git(module_source, "rev-parse", "HEAD^{tree}")
        remote = self.base / "module.git"; git(self.base, "clone", "--quiet", "--bare", str(module_source), str(remote))
        self.lock = self._lock(); self.lock["plugins"][0]["source"].update(commit=commit, tree=tree); self._write_receipt(); self._write_lock()
        with self.assertRaisesRegex(catalog.SourceError, "submodules are forbidden"):
            catalog.materialize(self.root, "sample-plugin", cache_root=self.base / "cache5", repository_url_resolver=lambda _: str(remote), validator=self.validator)


if __name__ == "__main__": unittest.main()
