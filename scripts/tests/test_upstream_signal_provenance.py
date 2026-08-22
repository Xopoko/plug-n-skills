import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/capability-evaluations/2026-08-21-upstream-agent-signal.md"
LOCK = ROOT / "external-dependencies.lock.json"

EXPECTED = {
    "mattpocock-skills": ("mattpocock/skills", "5b15a47f2d7150f545fbcacbfe381787fc0230dc", "b067eb5ab717af0165a555ff7791afa3494053c4"),
    "cursor-plugins": ("cursor/plugins", "46125561306434d8a1d7745d540d8932ab0cd2a2", "1d1795c88013daf2470a40892d72664ec71b5061"),
    "ui-skills": ("ibelick/ui-skills", "33b35e7d13d4bce7e4358d2205e406c1b20263fc", "8ee92fe60983596fba48851664914a5acbedea20"),
    "i-have-adhd-eval-2026-08-21": ("ayghri/i-have-adhd", "e7555fcaf612dfa1739dc86610ea926a906db614", "42ce88189368a2612da7f6f841841b404334570d"),
    "revfactory-harness": ("revfactory/harness", "cceac68ea1d0ad198ef4b7b906cd238375836387", "b88c5ce9b73461bf6d92224863a9db91b6cedace"),
    "munder-difflin": ("chaitanyagiri/munder-difflin", "57a6ce65cb6d0b72bebd17a4b4ae92e60446c979", "7c52501ecb2f0ddc4dad4a69601e2dfe8775b398"),
    "caveman": ("JuliusBrussee/caveman", "2f49f0e1a352aa810e70056b7930aeb0b3d219b4", "603ece15f092a82703cb6e86d102050502775f25"),
    "rtk": ("rtk-ai/rtk", "29f9bb7161775cd807565fd3041eb2b7d1be071c", "deedf05df34a2e415a6cdc468ec8ae5d41c96276"),
    "loopy": ("Forward-Future/loopy", "75966cbd572a4185064971c9fe5e9c52e8f8456d", "f992d05d1517c24b3598bd4b43826f92e01e34e7"),
}


class UpstreamSignalProvenanceTests(unittest.TestCase):
    def test_report_rows_match_canonical_lock(self) -> None:
        text = REPORT.read_text(encoding="utf-8")
        self.assertIn("`external-dependencies.lock.json` is the canonical declaration surface", text)
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in lock["dependencies"]}

        for dependency_id, (repository, commit, tree) in EXPECTED.items():
            with self.subTest(dependency_id=dependency_id):
                dependency = by_id[dependency_id]
                self.assertEqual(dependency["source"]["repository"], repository)
                self.assertEqual(dependency["source"]["commit"], commit)
                self.assertEqual(dependency["source"]["tree"], tree)
                audit_path = dependency["audit"]["report"]
                self.assertTrue((ROOT / audit_path).is_file())
                expected_row = re.compile(
                    rf"^\| \[[^]]+\]\(https://github\.com/{re.escape(repository)}/tree/{commit}\) "
                    rf"\| \[{re.escape(dependency_id)}\]\(\.\./external-dependencies/{re.escape(Path(audit_path).name)}\) "
                    rf"\| `{commit}` \| `{tree}` \|",
                    re.MULTILINE,
                )
                self.assertRegex(text, expected_row)


if __name__ == "__main__":
    unittest.main()
