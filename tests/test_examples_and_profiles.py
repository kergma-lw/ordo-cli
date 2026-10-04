import unittest
import io
import json
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from ordo.introspection import describe_examples_catalog
from ordo.help_cli import main as help_main
from ordo.model.help_snippets import describe_help_snippets
from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.playbook import activate_playbook
from ordo.runtime import execute_workflow, assess_workflow_readiness, load_profile_file, load_workflow_file, plan_workflow, validate_profile_text, validate_workflow_text

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ExampleSurfaceTest(unittest.TestCase):
    def test_example_workflows_validate(self) -> None:
        for path in (
            Path("examples/gh-issue-maintenance.yaml"),
            Path("examples/samples/minimal.yaml"),
            Path("examples/samples/inspect-issue.yaml"),
            Path("examples/inspect-pr.yaml"),
            Path("examples/samples/git-branch-management.yaml"),
            Path("examples/samples/git-commit-management.yaml"),
            Path("examples/samples/git-ref-range-inspection.yaml"),
            Path("examples/samples/git-repo-upstream-inspection.yaml"),
            Path("examples/samples/git-tag-inspection.yaml"),
            Path("examples/samples/project-field-probes.yaml"),
            Path("examples/samples/project-item-collections.yaml"),
            Path("examples/samples/project-issue-membership.yaml"),
            Path("examples/samples/blocked-main-branch.yaml"),
            Path("examples/samples/launcher-step.yaml"),
            Path("examples/samples/let-bindings.yaml"),
            Path("examples/samples/local-expression-filters.yaml"),
            Path("examples/samples/run-step.yaml"),
            Path("examples/samples/run-fan-out.yaml"),
        ):
            report = validate_workflow_text(path.read_text(encoding="utf-8"), source=str(path))
            self.assertTrue(report.ok, path.as_posix())

    def test_included_example_workflows_load(self) -> None:
        for path in (
            Path("examples/samples/include-plain.yaml"),
            Path("examples/samples/include-args.yaml"),
        ):
            workflow = load_workflow_file(path)
            self.assertTrue(workflow.blocks, path.as_posix())

    def test_example_profiles_validate(self) -> None:
        for path in (
            Path("profiles/backend-default.yaml"),
            Path("profiles/compose-review.yaml"),
            Path("profiles/frontend-workdir.yaml"),
            Path("profiles/read-only-review.yaml"),
            Path("profiles/frontend-launcher.yaml"),
        ):
            report = validate_profile_text(path.read_text(encoding="utf-8"), source=str(path))
            self.assertTrue(report.ok, path.as_posix())

    def test_example_profile_with_launcher_file_loads(self) -> None:
        profile = load_profile_file(Path("profiles/frontend-launcher.yaml"))

        self.assertIn("shell_frontend", profile.launchers)

    def test_blocked_example_teaches_blocked_before_execution(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/blocked-main-branch.yaml"))

        result = assess_workflow_readiness(
            workflow,
            guard_probe=lambda resolved, _workflow: OperationResult(status="ok", outputs={"value": "main"})
            if resolved.reference == "git.branch"
            else OperationResult(status="guard_failed", summary="main branch"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.outputs["reason_category"], "guard")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "resolve_blocking_guards")

    def test_plan_surface_for_example_profile_and_workflow_is_machine_readable(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/inspect-issue.yaml"))
        profile = load_profile_file(Path("profiles/read-only-review.yaml"))

        result = plan_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertIn("guard_items", result.outputs)
        self.assertIn("step_items", result.outputs)
        self.assertEqual(result.outputs["active_profile"], "read-only-review")

    def test_let_bindings_example_executes_end_to_end(self) -> None:
        path = Path("examples/samples/let-bindings.yaml")
        workflow = load_workflow_file(path)
        example = describe_help_snippets()["examples.let-bindings"]["canonical_examples"][0]
        self.assertEqual(example["yaml"], path.read_text(encoding="utf-8").rstrip("\n"))
        self.assertTrue(validate_workflow_text(example["yaml"]).ok)
        self.assertTrue(any(item["name"] == "let-bindings" for item in describe_examples_catalog()["examples"]))
        for flags in ([], ["--json"]):
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(help_main(["describe", "examples.let-bindings", *flags]), 0)
            if flags:
                payload = json.loads(output.getvalue())
                self.assertEqual(payload["snippet_coverage"], "runner_verified")
                self.assertEqual(payload["canonical_examples"][0], example)
            else:
                self.assertIn("Publish branch", output.getvalue())
                self.assertIn("enabled: false blocks publication", output.getvalue())

        with patch("subprocess.run") as run:
            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        run.assert_not_called()

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["Publish branch"])
        self.assertEqual(result.to_contract()["published"], [{"branch": "task/7"}])

    def test_let_bindings_example_keeps_untrusted_type_as_data(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/let-bindings.yaml"))
        for task_type in ("Task; touch /tmp/ordo-injection", "$(id) `id` | cat &", "Task'\"\nNEXT"):
            with self.subTest(task_type=task_type), patch("subprocess.run") as run:
                result = execute_workflow(
                    replace(workflow, inputs={**workflow.inputs, "type": task_type}),
                    connector_provider=STANDARD_CONNECTOR_PROVIDER,
                )
                run.assert_not_called()
                self.assertEqual(result.status, RuntimeStatus.OK)
                self.assertEqual(result.to_contract()["published"], [{"branch": f"{task_type.lower()}/7"}])

    def test_let_bindings_example_disabled_guard_blocks_without_commands(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/let-bindings.yaml"))
        with patch("subprocess.run") as run:
            result = execute_workflow(
                replace(workflow, inputs={**workflow.inputs, "enabled": False}),
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )
        run.assert_not_called()
        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertFalse(result.to_contract().get("published"))

    def test_local_expression_filters_example_is_published_and_executes_end_to_end(self) -> None:
        catalog = describe_examples_catalog()
        workflow = load_workflow_file(Path("examples/samples/local-expression-filters.yaml"))

        self.assertTrue(any(item["name"] == "local-expression-filters" for item in catalog["examples"]))

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["Check allowed status", "Announce task"])
        self.assertEqual(result.operation_results[0].outputs.get("value"), True)
        self.assertEqual(result.operation_results[1].outputs.get("stdout"), "example-task")

    def test_playbook_workflows_example_is_published_and_activates(self) -> None:
        catalog = describe_examples_catalog()

        self.assertTrue(any(item["name"] == "playbook-workflows" for item in catalog["examples"]))

        activated = activate_playbook(
            workflow_name="remember-profile",
            playbook_path=Path("examples/samples/playbook-workflows.yaml"),
        )

        self.assertEqual(activated.workflow_name, "remember-profile")
        self.assertEqual(activated.workflow_description, "Read one remembered profile from shared state")
        self.assertEqual(activated.working_directory, Path("examples/samples").resolve())
        self.assertIsNotNone(activated.profile)

    def test_playbook_connectors_example_is_published_and_activates(self) -> None:
        catalog = describe_examples_catalog()

        self.assertTrue(any(item["name"] == "playbook-connectors" for item in catalog["examples"]))

        activated = activate_playbook(
            workflow_name="inspect-compose",
            playbook_path=Path("examples/samples/playbook-connectors.yaml"),
        )

        self.assertEqual(activated.workflow_name, "inspect-compose")
        self.assertEqual(activated.connector_contexts["compose"]["directory"], "./deploy")
        self.assertEqual(activated.connector_contexts["compose"]["file"], "compose.prod.yaml")
        self.assertIsNotNone(activated.profile)

    def test_inspect_pr_example_is_published_and_executes_end_to_end(self) -> None:
        catalog = describe_examples_catalog()
        workflow = load_workflow_file(Path("examples/inspect-pr.yaml"))

        self.assertTrue(any(item["name"] == "inspect-pr" for item in catalog["examples"]))

        with patch("subprocess.run") as run:
            run.side_effect = [
                _completed(returncode=0, stdout="authenticated\n", stderr=""),
                _completed(returncode=0, stdout='{"number":42,"title":"Add PR probes","body":"Body","state":"open","draft":false,"html_url":"https://github.com/kergma-lw/ordo-cli/pull/42","created_at":"2026-07-30T10:00:00Z","updated_at":"2026-07-30T11:00:00Z","user":{"login":"kergma-lw"},"base":{"ref":"main"},"head":{"ref":"feature/pr-probes","sha":"abc123"},"mergeable":true,"mergeable_state":"clean","review_decision":"APPROVED","additions":12,"deletions":3,"changed_files":2,"commits":4}', stderr=""),
                _completed(returncode=0, stdout="authenticated\n", stderr=""),
                _completed(returncode=0, stdout='[{"filename":"src/ordo/help_cli.py","status":"modified","additions":12,"deletions":3,"changes":15},{"filename":"docs/pr-checklist.md","status":"added","additions":8,"deletions":0,"changes":8}]', stderr=""),
                _completed(returncode=0, stdout="", stderr=""),
                _completed(returncode=0, stdout="authenticated\n", stderr=""),
                _completed(returncode=0, stdout='{"number":42,"comments":1}', stderr=""),
                _completed(returncode=0, stdout='[{"id":1,"body":"First","created_at":"2026-07-30T10:00:00Z","updated_at":"2026-07-30T10:00:00Z","html_url":"https://github.com/kergma-lw/ordo-cli/pull/42#issuecomment-1","user":{"login":"kergma-lw"}}]', stderr=""),
                _completed(returncode=0, stdout="authenticated\n", stderr=""),
                _completed(returncode=0, stdout='{"data":{"repository":{"pullRequest":{"reviews":{"totalCount":1,"nodes":[{"id":"PRR_1","url":"https://github.com/kergma-lw/ordo-cli/pull/42#pullrequestreview-1","body":"Looks good","state":"APPROVED","submittedAt":"2026-07-30T12:00:00Z","author":{"login":"ww"},"commit":{"oid":"abc123"}}]}}}}}', stderr=""),
                _completed(returncode=0, stdout="authenticated\n", stderr=""),
                _completed(returncode=0, stdout='{"number":42,"review_comments":1,"head":{"sha":"abc123"}}', stderr=""),
                _completed(returncode=0, stdout='[{"id":10,"body":"Please rename this","path":"src/ordo/help_cli.py","commit_id":"def456","original_commit_id":"abc123","line":12,"original_line":12,"side":"RIGHT","in_reply_to_id":null,"created_at":"2026-07-30T13:00:00Z","updated_at":"2026-07-30T13:00:00Z","html_url":"https://github.com/kergma-lw/ordo-cli/pull/42#discussion_r10","user":{"login":"reviewer"}}]', stderr=""),
                _completed(returncode=0, stdout="authenticated\n", stderr=""),
                _completed(returncode=0, stdout='{"number":42,"head":{"sha":"abc123"}}', stderr=""),
                _completed(returncode=0, stdout='[{"state":"success","sha":"abc123","total_count":1,"statuses":[{"id":101,"context":"lint","state":"success","target_url":"https://example.test/lint"}]}]', stderr=""),
                _completed(returncode=0, stdout='[{"total_count":1,"check_runs":[{"id":201,"name":"unit","head_sha":"abc123","status":"completed","conclusion":"success","html_url":"https://example.test/unit"}]}]', stderr=""),
                _completed(returncode=0, stdout="authenticated\n", stderr=""),
                _completed(returncode=0, stdout='{"number":42,"state":"open"}', stderr=""),
                _completed(returncode=0, stdout='[{"event":"ready_for_review","created_at":"2026-07-30T10:00:00Z","actor":{"login":"kergma-lw"}}]', stderr=""),
            ]

            result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        published = result.to_contract()["published"][0]
        self.assertEqual(published["pull_ref"], "kergma-lw/ordo-cli#42")
        self.assertEqual(published["title"], "Add PR probes")
        self.assertEqual(published["head_sha"], "abc123")
        self.assertEqual(published["changed_file_count"], 2)
        self.assertEqual(published["comment_count"], 1)
        self.assertEqual(published["review_count"], 1)
        self.assertEqual(published["review_comment_count"], 1)
        self.assertEqual(published["check_count"], 2)
        self.assertEqual(published["timeline_count"], 1)

    def test_project_field_probes_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/project-field-probes.yaml"))

        self.assertEqual(workflow.workflow, "inspect-project-field-probes")

    def test_project_issue_membership_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/project-issue-membership.yaml"))

        self.assertEqual(workflow.workflow, "prepare-project-issue-membership")

    def test_project_item_collections_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/project-item-collections.yaml"))

        self.assertEqual(workflow.workflow, "inspect-project-item-collections")

    def test_git_branch_management_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/git-branch-management.yaml"))

        self.assertEqual(workflow.workflow, "manage-git-branches")

    def test_git_commit_management_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/git-commit-management.yaml"))

        self.assertEqual(workflow.workflow, "manage-git-commits")
        steps = workflow.blocks[1].steps
        self.assertEqual([step.if_ for step in steps[:4]], [None, 'inputs.operation == "create"', 'inputs.operation == "amend"', 'inputs.operation == "revert"'])

    def test_git_sync_roundtrip_publishes_git_range_ahead_count(self) -> None:
        workflow = load_workflow_file(Path("examples/git-sync-roundtrip.yaml"))

        published = workflow.blocks[1].steps[-1].publish
        self.assertEqual(published["ahead"], "step.branch_range.outputs.ahead_count")

    def test_git_tag_inspection_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/git-tag-inspection.yaml"))

        self.assertEqual(workflow.workflow, "inspect-git-tags")

    def test_git_ref_range_inspection_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/git-ref-range-inspection.yaml"))

        self.assertEqual(workflow.workflow, "inspect-git-ref-range")

    def test_git_repo_upstream_inspection_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/samples/git-repo-upstream-inspection.yaml"))

        self.assertEqual(workflow.workflow, "inspect-git-repo-upstream")


def _completed(*, returncode: int, stdout: str, stderr: str) -> CompletedProcess[str]:
    return CompletedProcess(args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr)


if __name__ == "__main__":
    unittest.main()
