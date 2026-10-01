import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "fetch_sync_source", Path(__file__).resolve().parents[1] / "scripts/fetch_sync_source.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SourceBoundaryTests(unittest.TestCase):
    def record(self, path, mode=b"100644", kind=b"blob"):
        return mode + b" " + kind + b" " + b"a" * 40 + b"\t" + path

    def test_regular_scoped_files(self):
        self.assertEqual(sync.entry(self.record(b"skills/personal-cowork/SKILL.md")),
                         ("skills/personal-cowork/SKILL.md", "a" * 40))

    def test_symlinks_and_submodules_rejected(self):
        for mode, kind in [(b"120000", b"blob"), (b"160000", b"commit")]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                sync.entry(self.record(b"skills/personal-cowork/link", mode, kind))

    def test_paths_outside_scope_and_traversal_rejected(self):
        for path in [b"scripts/injected.py", b"skills/personal-cowork/../escape",
                     b"skills/personal-cowork/.git/config", b"skills/personal-cowork/a\\b",
                     b"skills/personal-cowork//nested"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                sync.entry(self.record(path))

    def test_symlink_destination_parent_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "real").mkdir()
            (root / "link").symlink_to(root / "real", target_is_directory=True)
            with self.assertRaises(ValueError):
                sync.safe_destination(root / "link" / "snapshot")

    def test_case_and_unicode_collision_keys(self):
        self.assertEqual(sync.path_key("skills/personal-cowork/SKILL.md"),
                         sync.path_key("skills/personal-cowork/skill.md"))
        self.assertEqual(sync.path_key("skills/personal-cowork/\u00e9.md"),
                         sync.path_key("skills/personal-cowork/e\u0301.md"))


if __name__ == "__main__":
    unittest.main()
