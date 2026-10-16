"""Exercise update safety against real local Git histories, without the game or network."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("sync_upstream", Path(__file__).with_name("sync_upstream.py"))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def setUp(self):
        test_root = sync.ROOT / "build/android/test-runs"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        # Windows: verify the recursive cleanup target before TemporaryDirectory removes it.
        if not Path(self.temp.name).resolve().is_relative_to(test_root.resolve()):
            raise RuntimeError("Test directory escaped the workspace")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        self.g(self.upstream, "init", "-b", "main")
        (self.upstream / "shared.c").write_text("initial\n")
        (self.upstream / ".gitignore").write_text("build/\n")
        self.commit(self.upstream, "Initial upstream")
        base = self.g(self.upstream, "rev-parse", "HEAD")
        self.port = self.root / "port"
        self.g(self.root, "clone", "--no-hardlinks", str(self.upstream), str(self.port))
        self.g(self.port, "switch", "-c", "codex/android")
        (self.port / "android").mkdir()
        (self.port / "android/port.json").write_text(json.dumps({
            "upstream_url": str(self.upstream), "upstream_branch": "main", "upstream_base": base,
            "development_branch": "codex/android", "testing_branch": "codex/android-testing",
            "stable_branch": "codex/android-stable", "playable": False,
        }))
        self.commit(self.port, "Android foundation")
        self.initial = self.g(self.port, "rev-parse", "HEAD")
        self.stable_initial = self.initial
        self.g(self.port, "branch", "codex/android-stable", self.initial)

    def g(self, repo, *args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout.strip()

    def commit(self, repo, message):
        self.g(repo, "add", ".")
        self.g(repo, *sync.BOT, "commit", "-m", message)

    def update(self, filename="fix.c", text="fix\n"):
        (self.upstream / filename).write_text(text)
        self.commit(self.upstream, "Upstream fix")

    def assert_source_untouched(self):
        self.assertEqual(self.g(self.port, "rev-parse", "HEAD"), self.initial)
        self.assertEqual(self.g(self.port, "rev-parse", "codex/android-stable"), self.stable_initial)
        self.assertEqual(self.g(self.port, "status", "--porcelain"), "")

    def test_unchanged_creates_no_candidate(self):
        self.assertEqual(sync.prepare(self.port)["status"], "unchanged")
        self.assertFalse((self.port / "build").exists())
        self.assert_source_untouched()

    def test_merges_new_commit_and_bundle_is_recoverable(self):
        self.update()
        result = sync.prepare(self.port)
        self.assertEqual(result["status"], "prepared")
        trial = Path(result["candidate_directory"])
        self.assertEqual((trial / "fix.c").read_text(), "fix\n")
        self.assertEqual(sync.config(trial)["upstream_base"], result["upstream_target"])
        self.g(self.port, "bundle", "verify", result["candidate_bundle"])
        restored = self.root / "restored"
        self.g(self.root, "clone", "-b", "codex/android-testing", result["candidate_bundle"], str(restored))
        self.assertEqual(self.g(restored, "rev-parse", "HEAD"), result["candidate_commit"])
        self.assert_source_untouched()
        self.assertEqual(sync.prepare(trial)["status"], "unchanged")

    def test_conflict_keeps_stable_and_working_tree(self):
        (self.port / "shared.c").write_text("Android change\n")
        self.commit(self.port, "Android change")
        self.initial = self.g(self.port, "rev-parse", "HEAD")
        self.update("shared.c", "upstream change\n")
        result = sync.prepare(self.port)
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["conflicts"], ["shared.c"])
        self.assertNotIn("candidate_bundle", result)
        self.assertEqual(self.g(self.port, "rev-parse", "HEAD"), self.initial)
        self.assertEqual(self.g(self.port, "status", "--porcelain"), "")
        self.assertEqual((self.port / "shared.c").read_text(), "Android change\n")
        self.assertEqual(self.g(self.port, "rev-parse", "codex/android-stable"), self.stable_initial)

    def test_dirty_tree_refused(self):
        (self.port / "shared.c").write_text("unsaved change\n")
        with self.assertRaisesRegex(RuntimeError, "working changes"):
            sync.prepare(self.port)
        self.assertEqual((self.port / "shared.c").read_text(), "unsaved change\n")

    def test_rewritten_upstream_refused(self):
        self.g(self.upstream, "switch", "--orphan", "rewritten")
        (self.upstream / "other.c").write_text("replacement\n")
        self.commit(self.upstream, "Rewritten history")
        self.g(self.upstream, "branch", "-f", "main", "HEAD")
        self.assertEqual(sync.prepare(self.port)["status"], "upstream-history-changed")
        self.assert_source_untouched()

    def test_regenerator_change_reported(self):
        self.update("Makefile", "updated compiler flags\n")
        result = sync.prepare(self.port)
        self.assertEqual(result["status"], "prepared")
        self.assertTrue(result["regenerate_game_code"])
        self.assert_source_untouched()


if __name__ == "__main__":
    unittest.main()
