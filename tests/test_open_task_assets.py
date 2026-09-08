from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from ordo.runtime import check_workflow, execute_workflow, load_workflow_file, review_workflow, validate_profile_text, validate_workflow_text
from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.runtime.resolution import ResolvedExpressionProbe
from tests.support import STANDARD_CONNECTOR_PROVIDER


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "set-active-task-from-gitx.yaml"


class OpenTaskAssetTest(unittest.TestCase):
    def run_example(self, *, inputs=None, local=True, target=False, remote=True,
                    project_type="Task", status="Ready", fail_branch=None,
                    initial=None, mode=execute_workflow):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        state_path = Path(directory) / "task-memory.json"
        workflow = load_workflow_file(EXAMPLE)
        workflow = replace(
            workflow,
            inputs={**workflow.inputs, "repository": "sample/repository", "project_id": "PVT_SAMPLE",
                    **(inputs or {})},
            states={"test_memory": str(state_path)},
            state_bindings={"task_memory": "test_memory"},
        )
        calls = []
        created = False

        def fake(resolved, _workflow):
            nonlocal created
            ref = resolved.reference
            args = ({name: node.value for name, node in resolved.arguments}
                    if isinstance(resolved, ResolvedExpressionProbe) else dict(resolved.resolved_inputs))
            calls.append((ref, args))
            if ref == "git.worktrees":
                outputs = {"count": 1}
            elif ref == "git.state":
                outputs = {"worktree_clean": True}
            elif ref == "gh.issue":
                outputs = {"state": "OPEN", "title": "Not the input title"}
            elif ref == "gh.project.issue":
                self.assertIn("gh.project.issue.add", [name for name, _ in calls])
                outputs = {"exists": True, "type": project_type, "status": status}
            elif ref == "git.ref":
                if args["ref"] == f"refs/heads/{workflow.inputs['base_branch']}":
                    outputs = {"exists": local}
                elif args["ref"].startswith("refs/remotes/"):
                    self.assertIn(("git.sync.fetch", {"remote": workflow.inputs["remote"]}), calls)
                    outputs = {"exists": remote}
                else:
                    outputs = {"exists": target or created}
            else:
                self.assertIn(ref, {"gh.project.issue.add", "gh.project.issue.field_single_select.set",
                                    "git.sync.fetch", "git.branch.switch", "git.branch.create",
                                    "git.integrate.merge_ff_only", "shell.command"})
                if ref == "git.branch.switch" and args["branch"] == fail_branch:
                    return OperationResult(status="execution_error", summary="switch failed")
                if ref == "git.branch.create":
                    created = True
                if ref == "shell.command":
                    self.assertEqual(len(json.loads(state_path.read_text())[workflow.inputs["task_key"]]), 5)
                outputs = {}
            if initial and ref in initial:
                outputs.update(initial[ref])
            return OperationResult(status="ok", outputs=outputs)

        kwargs = {"step_executor": fake} if mode is execute_workflow else {}
        with patch("subprocess.run", side_effect=AssertionError("real subprocess forbidden")):
            result = mode(workflow, guard_probe=fake, connector_provider=STANDARD_CONNECTOR_PROVIDER, **kwargs)
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        return result, calls, state

    def test_open_task_example_validates(self) -> None:
        path = ROOT / "examples" / "set-active-task-from-gitx.yaml"

        report = validate_workflow_text(path.read_text(encoding="utf-8"), source=str(path))

        self.assertEqual(report.status, RuntimeStatus.OK, report.diagnostics)

    def test_open_task_profiles_validate(self) -> None:
        for name in ("sample-backend-set-active-task.yaml", "sample-frontend-set-active-task.yaml"):
            path = ROOT / "tests" / "fixtures" / "profiles" / name

            report = validate_profile_text(path.read_text(encoding="utf-8"), source=str(path))

            self.assertEqual(report.status, RuntimeStatus.OK, name)

    def test_bundled_ordo_workflows_load_with_fragment_assets(self) -> None:
        for name in ("set-active-task.yml", "close-task.yml"):
            path = ROOT / ".ordo" / "workflows" / name

            workflow = load_workflow_file(path)

            self.assertTrue(workflow.blocks, name)

    def test_native_asset_structure_and_trusted_hook(self):
        document = yaml.safe_load(EXAMPLE.read_text())
        steps = [step for block in document["blocks"] for step in block.get("steps", [])]
        commands = [step for step in steps if step.get("uses") == "shell.command"]
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["with"], {"command": "inputs.post_open_command"})
        self.assertEqual(commands[0]["if"], 'inputs.post_open_command != ""')
        self.assertEqual(sum("state_set" in step for step in steps), 5)
        self.assertFalse(any("run" in step or "steps" in step for step in steps))
        self.assertEqual({step["uses"] for step in steps if "uses" in step}, {
            "gh.project.issue.add", "gh.project.issue", "gh.project.issue.field_single_select.set",
            "git.ref", "git.sync.fetch", "git.branch.switch", "git.integrate.merge_ff_only",
            "git.branch.create", "shell.command",
        })
        self.assertEqual(document["inputs"]["repository"], {})
        self.assertEqual(document["inputs"]["project_id"], {})
        self.assertEqual(document["inputs"]["allowed_issue_types"], {"default": ["Task", "Bug"]})
        for name in ("backend", "frontend"):
            profile = yaml.safe_load((ROOT / "tests/fixtures/profiles" / f"sample-{name}-set-active-task.yaml").read_text())
            self.assertEqual(profile["inputs"]["allowed_issue_types"], ["Task", "Bug"])
            self.assertNotIn("allowed_issue_types_csv", profile["inputs"])

    def test_local_base_new_target_sequence_and_state(self):
        result, calls, state = self.run_example(inputs={"remote": "upstream", "base_branch": "trunk"})
        self.assertEqual(result.status, RuntimeStatus.OK, result.diagnostics)
        self.assertEqual(calls[-8:], [
            ("git.ref", {"ref": "refs/heads/trunk"}),
            ("git.sync.fetch", {"remote": "upstream"}),
            ("git.ref", {"ref": "refs/remotes/upstream/trunk"}),
            ("git.branch.switch", {"branch": "trunk"}),
            ("git.integrate.merge_ff_only", {"ref": "refs/remotes/upstream/trunk"}),
            ("git.ref", {"ref": "refs/heads/task/16-keep-issue-workflow-in-sync"}),
            ("git.branch.create", {"branch": "task/16-keep-issue-workflow-in-sync", "start_point": "refs/heads/trunk"}),
            ("git.branch.switch", {"branch": "task/16-keep-issue-workflow-in-sync"}),
        ])
        self.assertEqual(state, {"sample-task-16": {
            "issue_number": 16, "issue_type": "Task", "issue_title": "Keep issue workflow in sync",
            "branch": "task/16-keep-issue-workflow-in-sync", "repository_kind": "backend",
        }})

    def test_remote_base_creation_and_existing_target(self):
        for local, target in ((False, False), (True, True)):
            with self.subTest(local=local, target=target):
                result, calls, state = self.run_example(local=local, target=target)
                self.assertEqual(result.status, RuntimeStatus.OK, result.diagnostics)
                creates = [args for ref, args in calls if ref == "git.branch.create"]
                self.assertEqual(creates, [] if target else [{
                    "branch": "task/16-keep-issue-workflow-in-sync", "start_point": "refs/remotes/origin/main"}])
                self.assertEqual(sum(ref == "git.integrate.merge_ff_only" for ref, _ in calls), int(local))
                self.assertEqual(sum(ref == "git.sync.fetch" for ref, _ in calls), 1)
                self.assertEqual(calls[-1], ("git.branch.switch", {"branch": "task/16-keep-issue-workflow-in-sync"}))
                self.assertTrue(state)

    def test_switch_failure_and_missing_remote_stop(self):
        for kwargs in ({"fail_branch": "main"}, {"remote": False},
                       {"fail_branch": "task/16-keep-issue-workflow-in-sync"}):
            with self.subTest(**kwargs):
                result, calls, state = self.run_example(inputs={"post_open_command": "trusted hook"}, **kwargs)
                self.assertNotEqual(result.status, RuntimeStatus.OK)
                self.assertFalse(state)
                self.assertNotIn("shell.command", [ref for ref, _ in calls])
                if kwargs.get("fail_branch") == "main" or "remote" in kwargs:
                    self.assertNotIn("git.branch.create", [ref for ref, _ in calls])
                    self.assertNotIn("git.integrate.merge_ff_only", [ref for ref, _ in calls])
                else:
                    self.assertEqual(sum(ref == "git.branch.create" for ref, _ in calls), 1)

    def test_project_policy_after_add_and_initial_guards(self):
        for kwargs in ({"project_type": "Story"}, {"project_type": None}, {"status": "Done"},
                       {"status": "In review"}, {"status": "Backlog"},
                       {"initial": {"gh.project.issue": {"exists": False}}},
                       {"inputs": {"allowed_issue_types": "Task,Bug"}}):
            with self.subTest(**kwargs):
                result, calls, state = self.run_example(**kwargs)
                self.assertNotEqual(result.status, RuntimeStatus.OK)
                refs = [ref for ref, _ in calls]
                self.assertIn("gh.project.issue.add", refs)
                self.assertNotIn("gh.project.issue.field_single_select.set", refs)
                self.assertFalse(any(ref.startswith("git.") and ref not in {"git.state", "git.worktrees"} for ref in refs))
                self.assertFalse(state)
        for kwargs in ({"inputs": {"allow_backlog": "false"}}, {"initial": {"git.worktrees": {"count": 2}}},
                       {"initial": {"git.state": {"worktree_clean": False}}}, {"initial": {"gh.issue": {"state": "CLOSED"}}}):
            with self.subTest(**kwargs):
                result, calls, state = self.run_example(**kwargs)
                self.assertNotEqual(result.status, RuntimeStatus.OK)
                self.assertNotIn("gh.project.issue.add", [ref for ref, _ in calls])
                self.assertFalse(state)
        for kwargs in ({"status": None}, {"status": "Backlog", "inputs": {"allow_backlog": True}}):
            with self.subTest(**kwargs):
                result, _, state = self.run_example(**kwargs)
                self.assertEqual(result.status, RuntimeStatus.OK, result.diagnostics)
                self.assertTrue(state)

    def test_untrusted_data_stays_typed_and_hook_is_exact_after_writes(self):
        malicious = 'quotes\'"\n$(not-a-command); data'
        hook = "printf 'explicit trusted code'\nprintf second"
        result, calls, state = self.run_example(
            project_type=malicious,
            inputs={"repository": malicious, "project_id": malicious, "allowed_issue_types": [malicious],
                    "issue_type": "Bug", "issue_title": '  Quoted "title"\nline  ', "post_open_command": hook},
        )
        self.assertEqual(result.status, RuntimeStatus.OK, result.diagnostics)
        # These fakes test data plumbing, not the real connectors' input validation.
        for ref, args in calls:
            if ref.startswith("gh."):
                self.assertEqual(args["repository"], malicious)
                if ref != "gh.issue":
                    self.assertEqual(args["project_id"], malicious)
        self.assertEqual([args for ref, args in calls if ref == "shell.command"], [{"command": hook}])
        self.assertEqual(calls[-1], ("shell.command", {"command": hook}))
        self.assertEqual(state["sample-task-16"]["issue_title"], '  Quoted "title"\nline  ')
        self.assertEqual(state["sample-task-16"]["branch"], "bug/16-quoted-title-line")

    def test_source_check_and_review_do_not_execute_late_policy(self):
        for mode in (check_workflow, review_workflow):
            with self.subTest(mode=mode.__name__):
                result, calls, state = self.run_example(mode=mode)
                self.assertEqual(result.status, RuntimeStatus.OK, result.diagnostics)
                self.assertFalse(state)
                self.assertTrue(all(ref in {"git.worktrees", "git.state", "gh.issue"} for ref, _ in calls))
                # Source analysis completes the initial guards, not the later runtime gates.
                snapshot = result.outputs if mode is check_workflow else result.outputs["check_snapshot"]
                self.assertTrue(snapshot["analysis_complete"])
                self.assertEqual(snapshot["allowed_state"], "allowed")


if __name__ == "__main__":
    unittest.main()
