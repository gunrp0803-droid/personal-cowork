"""Check safe, deterministic preparation without account calls or source execution."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_account_sync.py"
SPEC = importlib.util.spec_from_file_location("account_sync", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)
PLUGIN_ID = "plugins_expected"
SKILL = "skills/personal-cowork/SKILL.md"


class AccountSyncTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "source"
        self.stage = self.root / "stage"
        self.skill = self.source / "skills" / "personal-cowork"
        self.skill.mkdir(parents=True)
        (self.source / "plugin.json").write_text(json.dumps({"name": "personal-cowork", "version": "0.2.0"}), encoding="utf-8")
        (self.skill / "SKILL.md").write_text("---\nname: personal-cowork\ndescription: Test workflow\n---\n\nNew workflow\n", encoding="utf-8")
        scripts = self.skill / "scripts"
        scripts.mkdir()
        (scripts / "task_state.py").write_text("raise RuntimeError('must never execute fetched source')\n", encoding="utf-8")
        root = {"name": "personal-cowork", "version": "0.1.0", "author": {"name": "Account owner"},
                "extensions": {"com.openai": {"interface": {"defaultPrompt": ["Second", "First"], "category": "Personal"}}}}
        legacy = {"interface": {"defaultPrompt": "Original string", "custom": {"preserve": True}},
                  "name": "personal-cowork", "version": "0.1.0", "skills": "./skills"}
        contents = {"plugin.json": json.dumps(root), ".codex-plugin/plugin.json": json.dumps(legacy),
                    SKILL: "---\nname: personal-cowork\ndescription: Older\n---\nOld workflow\n"}
        self.current = {"files": [{"path": name, "size_bytes": len(text.encode("utf-8"))} for name, text in contents.items()],
                        "contents": contents, "next_offset": None,
                        "plugin": {"plugin_id": PLUGIN_ID, "name": "personal-cowork", "version": "0.1.0",
                                   "current_release_id": "release_1", "scope": "USER", "discoverability": "PRIVATE"}}
        self.current["files"].append({"path": "assets/existing-binary.png", "size_bytes": 50})

    def source_version(self, version):
        (self.source / "plugin.json").write_text(json.dumps({"name": "personal-cowork", "version": version}), encoding="utf-8")

    def current_text(self, path, text):
        self.current["contents"][path] = text
        record = next((item for item in self.current["files"] if item["path"] == path), None)
        if record is None:
            self.current["files"].append({"path": path, "size_bytes": len(text.encode("utf-8"))})
        else:
            record["size_bytes"] = len(text.encode("utf-8"))

    def account_version(self, version):
        self.current["plugin"]["version"] = version
        for name in sync.MANIFESTS:
            value = json.loads(self.current["contents"][name])
            value["version"] = version
            self.current_text(name, json.dumps(value))

    def prepare(self, previous=None):
        return sync.prepare(self.source, self.current, PLUGIN_ID, previous, "a" * 40)

    def apply(self, report, overlay):
        for name, data in overlay.items():
            self.current_text(name, data.decode("utf-8"))
        self.current["plugin"].update(version=report["version"], current_release_id="release_2")
        state = copy.deepcopy(report["state_candidate"])
        state["release_id"] = "release_2"
        return state

    def cli(self, output=None, previous=None):
        current = self.root / "current.json"
        current.write_text(json.dumps(self.current), encoding="utf-8")
        command = [sys.executable, str(SCRIPT), "--source", str(self.source), "--current", str(current),
                   "--output", str(output or self.stage), "--plugin-id", PLUGIN_ID, "--commit", "a" * 40]
        if previous is not None:
            state = self.root / "state.json"
            state.write_text(json.dumps(previous), encoding="utf-8")
            command += ["--state", str(state)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return result, json.loads(result.stdout)

    def test_overlay_preserves_all_metadata_types_and_unmanaged_binary(self):
        old = copy.deepcopy(self.current)
        report, overlay = self.prepare()
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["version"], "0.2.0")
        self.assertIsNone(report["state_candidate"]["release_id"])
        self.assertEqual(set(overlay), {SKILL, "skills/personal-cowork/scripts/task_state.py", *sync.MANIFESTS})
        for name in sync.MANIFESTS:
            before = json.loads(old["contents"][name])
            after = json.loads(overlay[name])
            after.pop("version")
            before.pop("version")
            self.assertEqual(after.pop("repository"), sync.REPOSITORY)
            self.assertEqual(after, before)
        root = json.loads(overlay["plugin.json"])
        self.assertEqual(root["extensions"]["com.openai"]["interface"]["defaultPrompt"], ["Second", "First"])
        self.assertEqual(json.loads(overlay[".codex-plugin/plugin.json"])["interface"]["defaultPrompt"], "Original string")
        self.assertIn("assets/existing-binary.png", report["preserved_paths"])
        self.assertEqual(self.current, old)

    def test_existing_repository_is_preserved_and_missing_legacy_repository_copies_root(self):
        root = json.loads(self.current["contents"]["plugin.json"])
        root["repository"] = "https://github.com/owner/existing-repository"
        self.current_text("plugin.json", json.dumps(root))
        report, overlay = self.prepare()
        self.assertEqual(json.loads(overlay["plugin.json"])["repository"], root["repository"])
        self.assertEqual(json.loads(overlay[".codex-plugin/plugin.json"])["repository"], root["repository"])
        state = self.apply(report, overlay)
        repeat, overlay = self.prepare(state)
        self.assertEqual(repeat["status"], "noop")
        self.assertEqual(overlay, {})
        legacy = json.loads(self.current["contents"][".codex-plugin/plugin.json"])
        legacy["repository"] = "https://github.com/owner/legacy-repository"
        self.current_text(".codex-plugin/plugin.json", json.dumps(legacy))
        self.source_version("0.3.0")
        report, overlay = self.prepare()
        self.assertEqual(json.loads(overlay[".codex-plugin/plugin.json"])["repository"], legacy["repository"])

    def test_normal_token_named_files_are_included_and_sensitive_token_names_are_excluded(self):
        references = self.skill / "references"
        references.mkdir()
        guide = references / "token-efficiency.md"
        guide.write_text("Token efficiency guide\n")
        tokenizer = self.skill / "scripts" / "tokenizer.py"
        tokenizer.write_text("# Tokenizer source is packaged as data\n")
        sensitive = (".token", "token.json", "tokens.json", "token.txt", "access_token.json", "refresh-token.yaml")
        for name in sensitive:
            (self.skill / name).write_text("sensitive data\n")
        report, overlay = self.prepare()
        self.assertIn("skills/personal-cowork/references/token-efficiency.md", overlay)
        self.assertIn("skills/personal-cowork/scripts/tokenizer.py", overlay)
        self.assertEqual(overlay["skills/personal-cowork/references/token-efficiency.md"], guide.read_bytes())
        for name in sensitive:
            self.assertNotIn("skills/personal-cowork/" + name, report["state_candidate"]["skill_hashes"])

    def test_new_payload_uses_source_version_or_increments_current_patch(self):
        for source_version, account_version, expected in (("0.2.0", "0.1.0", "0.2.0"),
                                                           ("0.1.0", "0.1.0", "0.1.1"),
                                                           ("0.1.0", "0.3.9", "0.3.10"),
                                                           ("1.0.0", "1.0.0-beta.1", "1.0.0")):
            self.source_version(source_version)
            self.account_version(account_version)
            report, overlay = self.prepare()
            self.assertEqual(report["version"], expected)
            self.assertEqual(json.loads(overlay[".codex-plugin/plugin.json"])["version"], expected)

    def test_idempotence_checks_actual_files_and_recovers_stale_saved_state(self):
        first, overlay = self.prepare()
        state = self.apply(first, overlay)
        report, second_overlay = self.prepare(state)
        self.assertEqual(report["status"], "noop")
        self.assertEqual(second_overlay, {})
        state["release_id"] = "lost_response_old_release"
        state["manifest_hashes"]["plugin.json"] = "0" * 64
        self.assertEqual(self.prepare(state)[0]["status"], "noop")
        self.source_version("0.1.0")
        report, overlay = self.prepare(state)
        self.assertEqual(report["status"], "noop")
        self.assertEqual(report["version"], "0.2.0")
        self.assertEqual(overlay, {})

    def test_identical_files_with_greater_source_version_updates_version(self):
        first, overlay = self.prepare()
        state = self.apply(first, overlay)
        self.source_version("0.3.0")
        report, overlay = self.prepare(state)
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["version"], "0.3.0")
        self.assertEqual(set(overlay), set(sync.MANIFESTS))

    def test_account_manual_drift_blocks_new_update(self):
        first, overlay = self.prepare()
        state = self.apply(first, overlay)
        (self.skill / "SKILL.md").write_text((self.skill / "SKILL.md").read_text() + "Canonical update\n")
        self.current_text(SKILL, self.current["contents"][SKILL] + "Manual account edit\n")
        report, overlay = self.prepare(state)
        self.assertEqual(report["status"], "conflict")
        self.assertIn(SKILL, report["changed_paths"])
        self.assertEqual(overlay, {})

    def test_obsolete_managed_file_blocks_unsupported_deletion(self):
        reference = self.skill / "old.md"
        reference.write_text("previously managed")
        first, overlay = self.prepare()
        state = self.apply(first, overlay)
        reference.unlink()
        report, overlay = self.prepare(state)
        self.assertEqual(report["status"], "blocked_unsupported_deletion")
        self.assertEqual(report["obsolete_paths"], ["skills/personal-cowork/old.md"])
        self.assertEqual(overlay, {})

    def test_missing_relevant_text_or_partial_inventory_blocks(self):
        self.current["contents"].pop(SKILL)
        report, overlay = self.prepare()
        self.assertEqual(report["status"], "blocked_incomplete_inventory")
        self.assertIn(SKILL, report["missing_paths"])
        self.assertEqual(overlay, {})
        self.current["next_offset"] = 20
        self.assertEqual(self.prepare()[0]["status"], "blocked_incomplete_inventory")

    def test_scope_identity_and_unsafe_inventory_paths_are_rejected(self):
        for field, value in (("plugin_id", "different"), ("scope", "WORKSPACE"),
                             ("discoverability", "LISTED"), ("name", "other")):
            original = self.current["plugin"][field]
            self.current["plugin"][field] = value
            with self.assertRaises(ValueError):
                self.prepare()
            self.current["plugin"][field] = original
        for path in ("../outside", "/absolute", "skills\\wrong", "./plugin.json"):
            self.current["files"].append({"path": path, "size_bytes": 0})
            with self.assertRaises(ValueError):
                self.prepare()
            self.current["files"].pop()

    def test_invalid_manifests_and_skill_identity_are_rejected(self):
        self.current_text("plugin.json", '{"name": "wrong", "version": "0.1.0"}')
        with self.assertRaises(ValueError):
            self.prepare()
        self.current_text("plugin.json", '{"name": "personal-cowork", "version": "01.1.0"}')
        with self.assertRaises(ValueError):
            self.prepare()
        self.current_text("plugin.json", '{"name": "personal-cowork", "name": "personal-cowork", "version": "0.1.0"}')
        with self.assertRaises(ValueError):
            self.prepare()
        self.current_text("plugin.json", '{"name": "personal-cowork", "version": "0.1.0"}')
        (self.skill / "SKILL.md").write_text("---\nname: other\ndescription: Wrong\n---\n")
        with self.assertRaises(ValueError):
            self.prepare()

    def test_symlinks_are_rejected_and_private_cache_files_do_not_enter_payload(self):
        before = self.prepare()[0]["payload_hash"]
        (self.skill / ".env").write_text("never package")
        (self.skill / "credentials.json").write_text("never package")
        cache = self.skill / "__pycache__"
        cache.mkdir()
        (cache / "private.pyc").write_bytes(b"cache")
        self.assertEqual(self.prepare()[0]["payload_hash"], before)
        outside = self.root / "outside.md"
        outside.write_text("external")
        (self.skill / "escape.md").symlink_to(outside)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_skill_parent_symlink_is_rejected(self):
        original = self.source / "skills"
        moved = self.root / "external-skills"
        original.rename(moved)
        original.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_selected_binary_source_files_are_rejected(self):
        (self.skill / "unsupported.bin").write_bytes(b"\xff\x00")
        with self.assertRaises(UnicodeDecodeError):
            self.prepare()

    def test_cli_rejects_source_and_output_symlink_parents(self):
        alias = self.root / "source-alias"
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            sync.local_path(alias)
        external = self.root / "external-stage"
        external.mkdir()
        destination = self.root / "stage-alias"
        destination.symlink_to(external, target_is_directory=True)
        result, report = self.cli(output=destination / "nested")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["status"], "error")
        self.assertEqual(list(external.iterdir()), [])

    def test_deterministic_cli_zip_and_report_preserve_unrelated_output(self):
        self.stage.mkdir()
        keep = self.stage / "unrelated.keep"
        keep.write_bytes(b"preserve me")
        result, report = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = Path(report["archive"])
        original = archive.read_bytes()
        result, repeated = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(repeated["archive"]).read_bytes(), original)
        self.assertEqual(keep.read_bytes(), b"preserve me")
        self.assertEqual(json.loads(Path(report["report_path"]).read_text()), repeated)
        with ZipFile(archive) as bundle:
            names = bundle.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(all(name.startswith("personal-cowork/") for name in names))
            self.assertNotIn("personal-cowork/assets/existing-binary.png", names)
            self.assertEqual(bundle.testzip(), None)
            self.assertEqual(bundle.read("personal-cowork/" + SKILL), (self.skill / "SKILL.md").read_bytes())

    def test_cli_rejects_overlapping_output_without_creating_it(self):
        inside = self.source / "stage"
        result, report = self.cli(output=inside)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["status"], "error")
        self.assertFalse(inside.exists())


if __name__ == "__main__":
    unittest.main()
