"""Acceptance and boundary tests for the checkpoint-only task CLI."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (Path(__file__).resolve().parents[1] / "skills" / "personal-cowork" /
          "scripts" / "task_state.py")


class TaskStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state = self.new_task()

    def cli(self, *arguments, succeeds=True):
        process = subprocess.run([sys.executable, str(SCRIPT), *map(str, arguments)],
                                 text=True, capture_output=True, check=False)
        if succeeds:
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(process.stdout)
        self.assertNotEqual(process.returncode, 0, process.stdout)
        self.assertIn("error", process.stderr.lower())
        return process

    def new_task(self):
        result = self.cli("init", "--workspace", self.workspace, "--goal", "검증된 보고서 작성",
                          "--step", "자료 확인", "--step", "결과 작성",
                          "--criterion", "필수 항목 확인", "--criterion", "수치 대조")
        return Path(result["state"])

    def reject_without_change(self, *arguments):
        original = self.state.read_bytes()
        process = self.cli(*arguments, succeeds=False)
        self.assertEqual(self.state.read_bytes(), original)
        self.assertEqual(list(self.state.parent.iterdir()), [self.state])
        return process

    def ready(self):
        for step in ("1", "2"):
            self.cli("step", "--state", self.state, "--id", step, "--status", "done",
                     "--evidence", f"step {step}: inspected generated output")
        for criterion in ("1", "2"):
            self.cli("check", "--state", self.state, "--id", criterion, "--status", "passed",
                     "--evidence", f"check {criterion}: compared against input")

    def artifact(self, content="verified result\n"):
        path = self.workspace / "outputs" / "result.txt"
        path.parent.mkdir(exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.cli("artifact", "--state", self.state, "--path", "outputs/result.txt",
                 "--description", "검토한 결과물")
        return path

    def write_state(self, transform):
        data = json.loads(self.state.read_text(encoding="utf-8"))
        transform(data)
        self.state.write_text(json.dumps(data), encoding="utf-8")

    def test_end_to_end_unicode_hashes_and_completed_immutability(self):
        result = self.cli("show", "--state", self.state)
        self.assertEqual(result["goal"], "검증된 보고서 작성")
        self.cli("step", "--state", self.state, "--id", "1", "--status", "in_progress")
        path = self.artifact()
        self.ready()
        record = self.cli("show", "--state", self.state)["artifacts"][0]
        self.assertEqual(record["size"], path.stat().st_size)
        self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(self.cli("finish", "--state", self.state)["status"], "completed")
        self.assertEqual(self.cli("show", "--state", self.state)["status"], "completed")
        for command in (("step", "--id", "1", "--status", "pending"),
                        ("check", "--id", "1", "--status", "failed", "--evidence", "later issue"),
                        ("artifact", "--path", "outputs/result.txt", "--description", "later edit"),
                        ("finish",)):
            self.reject_without_change(command[0], "--state", self.state, *command[1:])

    def test_fresh_tasks_never_overwrite_prior_state(self):
        original = self.state.read_bytes()
        second = self.new_task()
        self.assertNotEqual(second, self.state)
        self.assertEqual(self.state.read_bytes(), original)
        self.assertTrue(second.exists())

    def test_pending_steps_and_pending_checks_prevent_finish(self):
        self.reject_without_change("finish", "--state", self.state)
        for step in ("1", "2"):
            self.cli("step", "--state", self.state, "--id", step, "--status", "done",
                     "--evidence", "confirmed")
        self.reject_without_change("finish", "--state", self.state)

    def test_failed_check_prevents_finish_and_can_be_rechecked(self):
        self.ready()
        self.cli("check", "--state", self.state, "--id", "2", "--status", "failed",
                 "--evidence", "count mismatch")
        self.reject_without_change("finish", "--state", self.state)
        self.cli("check", "--state", self.state, "--id", "2", "--status", "passed",
                 "--evidence", "fixed and compared again")
        self.cli("finish", "--state", self.state)

    def test_evidence_and_existing_checkpoint_are_required(self):
        for arguments in (("step", "--id", "1", "--status", "done"),
                          ("step", "--id", "1", "--status", "done", "--evidence", "  "),
                          ("step", "--id", "999", "--status", "pending"),
                          ("check", "--id", "1", "--status", "passed"),
                          ("check", "--id", "1", "--status", "failed", "--evidence", " ")):
            self.reject_without_change(arguments[0], "--state", self.state, *arguments[1:])

    def test_changed_missing_and_empty_artifacts_prevent_finish(self):
        self.ready()
        path = self.artifact()
        for content in ("different bytes", ""):
            path.write_text(content, encoding="utf-8")
            self.reject_without_change("finish", "--state", self.state)
        path.unlink()
        self.reject_without_change("finish", "--state", self.state)

    def test_rejected_artifact_paths_preserve_state(self):
        empty = self.workspace / "empty.txt"
        empty.touch()
        outside = self.root / "outside.txt"
        outside.write_text("external", encoding="utf-8")
        (self.workspace / "escape.txt").symlink_to(outside)
        for path in ("../outside.txt", str(outside), "empty.txt", "missing.txt", ".", "escape.txt"):
            self.reject_without_change("artifact", "--state", self.state,
                                      "--path", path, "--description", "result")

    def test_artifact_symlink_retargeting_prevents_finish(self):
        self.ready()
        path = self.artifact()
        path.unlink()
        outside = self.root / "outside.txt"
        outside.write_text("verified result\n", encoding="utf-8")
        path.symlink_to(outside)
        self.reject_without_change("finish", "--state", self.state)

    def test_inside_workspace_symlink_artifact_is_supported(self):
        target = self.workspace / "actual.txt"
        target.write_text("result", encoding="utf-8")
        (self.workspace / "alias.txt").symlink_to(target)
        self.cli("artifact", "--state", self.state, "--path", "alias.txt", "--description", "result")
        self.ready()
        self.cli("finish", "--state", self.state)

    def test_state_is_not_a_registerable_artifact(self):
        self.reject_without_change("artifact", "--state", self.state,
                                  "--path", self.state.relative_to(self.workspace), "--description", "state")

    def test_malformed_and_crafted_state_is_rejected_unchanged(self):
        initial = self.state.read_text(encoding="utf-8")
        changes = (lambda data: data.update(schema="other.schema"),
                   lambda data: data.update(workspace=str(self.root)),
                   lambda data: data.update(criteria=[]),
                   lambda data: data.update(extra="unexpected"),
                   lambda data: data["steps"][0].update(status="done", evidence=""),
                   lambda data: data.update(status="completed"),
                   lambda data: data.update(created_at="invalid timestamp"))
        for transform in changes:
            self.state.write_text(initial, encoding="utf-8")
            self.write_state(transform)
            self.reject_without_change("step", "--state", self.state, "--id", "1", "--status", "pending")
        for content in ("{bad", '["unexpected"]', '{"schema": 1, "schema": 2}'):
            self.state.write_text(content, encoding="utf-8")
            self.reject_without_change("show", "--state", self.state)

    def test_state_symlink_and_directory_symlink_are_rejected(self):
        outside = self.root / "external-state.json"
        original = self.state.read_bytes()
        outside.write_bytes(original)
        self.state.unlink()
        self.state.symlink_to(outside)
        self.cli("step", "--state", self.state, "--id", "1", "--status", "pending", succeeds=False)
        self.assertEqual(outside.read_bytes(), original)
        self.state.unlink()
        self.state.write_bytes(original)
        external_directory = self.root / "external-task"
        self.state.parent.rename(external_directory)
        self.state.parent.symlink_to(external_directory, target_is_directory=True)
        self.cli("finish", "--state", self.state, succeeds=False)
        self.assertEqual((external_directory / "task.json").read_bytes(), original)

    def test_unrecognized_and_traversal_state_locations_are_rejected(self):
        copy = self.workspace / "task.json"
        original = self.state.read_bytes()
        copy.write_bytes(original)
        self.cli("finish", "--state", copy, succeeds=False)
        self.assertEqual(copy.read_bytes(), original)
        traversal = self.state.parent / ".." / self.state.parent.name / "task.json"
        self.reject_without_change("finish", "--state", traversal)

    def test_init_rejects_escaping_work_directory_symlink(self):
        workspace = self.root / "fresh"
        workspace.mkdir()
        outside = self.root / "outside-directory"
        outside.mkdir()
        (workspace / "work").symlink_to(outside, target_is_directory=True)
        self.cli("init", "--workspace", workspace, "--goal", "goal", "--step", "step",
                 "--criterion", "criterion", succeeds=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_requires_nonempty_plan_and_acceptance_criteria(self):
        for tail in (("--step", "step"),
                     ("--criterion", "criterion"),
                     ("--step", " ", "--criterion", "criterion"),
                     ("--step", "step", "--criterion", " ")):
            self.cli("init", "--workspace", self.workspace, "--goal", "goal", *tail, succeeds=False)


if __name__ == "__main__":
    unittest.main()
