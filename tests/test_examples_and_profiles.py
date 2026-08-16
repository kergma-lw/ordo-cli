import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from ordo.introspection import describe_examples_catalog
from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.playbook import activate_playbook
from ordo.runtime import execute_workflow, explain_workflow, load_profile_file, load_workflow_file, plan_workflow, validate_profile_text, validate_workflow_text

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ExampleSurfaceTest(unittest.TestCase):
    def test_example_workflows_validate(self) -> None:
        for path in (
            Path("examples/gh-issue-maintenance.yaml"),
            Path("examples/minimal.yaml"),
            Path("examples/inspect-issue.yaml"),
            Path("examples/inspect-pr.yaml"),
            Path("examples/git-branch-management.yaml"),
            Path("examples/git-commit-management.yaml"),
            Path("examples/project-field-probes.yaml"),
            Path("examples/project-item-collections.yaml"),
            Path("examples/project-issue-membership.yaml"),
            Path("examples/blocked-main-branch.yaml"),
            Path("examples/launcher-step.yaml"),
            Path("examples/let-bindings.yaml"),
            Path("examples/local-expression-filters.yaml"),
            Path("examples/run-step.yaml"),
        ):
            report = validate_workflow_text(path.read_text(encoding="utf-8"), source=str(path))
            self.assertTrue(report.ok, path.as_posix())

    def test_included_example_workflows_load(self) -> None:
        for path in (
            Path("examples/include-plain.yaml"),
            Path("examples/include-args.yaml"),
        ):
            workflow = load_workflow_file(path)
            self.assertTrue(workflow.blocks, path.as_posix())

    def test_example_profiles_validate(self) -> None:
        for path in (
            Path("profiles/backend-default.yaml"),
            Path("profiles/read-only-review.yaml"),
            Path("profiles/frontend-launcher.yaml"),
        ):
            report = validate_profile_text(path.read_text(encoding="utf-8"), source=str(path))
            self.assertTrue(report.ok, path.as_posix())

    def test_example_profile_with_launcher_file_loads(self) -> None:
        profile = load_profile_file(Path("profiles/frontend-launcher.yaml"))

        self.assertIn("shell_frontend", profile.launchers)

    def test_blocked_example_teaches_blocked_before_execution(self) -> None:
        workflow = load_workflow_file(Path("examples/blocked-main-branch.yaml"))

        result = explain_workflow(
            workflow,
            guard_probe=lambda resolved, _workflow: OperationResult(status="ok", outputs={"value": "main"})
            if resolved.reference == "git.branch"
            else OperationResult(status="guard_failed", summary="main branch"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.outputs["reason_category"], "guard")
        self.assertEqual(result.outputs["next_actions"][0]["action"], "resolve_blocking_guards")

    def test_plan_surface_for_example_profile_and_workflow_is_machine_readable(self) -> None:
        workflow = load_workflow_file(Path("examples/inspect-issue.yaml"))
        profile = load_profile_file(Path("profiles/read-only-review.yaml"))

        result = plan_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertIn("guard_items", result.outputs)
        self.assertIn("step_items", result.outputs)
        self.assertEqual(result.outputs["active_profile"], "read-only-review")

    def test_let_bindings_example_executes_end_to_end(self) -> None:
        workflow = load_workflow_file(Path("examples/let-bindings.yaml"))

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["print-branch"])

    def test_local_expression_filters_example_is_published_and_executes_end_to_end(self) -> None:
        catalog = describe_examples_catalog()
        workflow = load_workflow_file(Path("examples/local-expression-filters.yaml"))

        self.assertTrue(any(item["name"] == "local-expression-filters" for item in catalog["examples"]))

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["executed_steps"], ["compute-membership", "announce"])
        self.assertEqual(result.operation_results[0].outputs.get("value"), True)
        self.assertEqual(result.operation_results[1].outputs.get("stdout"), "example-task")

    def test_playbook_workflows_example_is_published_and_activates(self) -> None:
        catalog = describe_examples_catalog()

        self.assertTrue(any(item["name"] == "playbook-workflows" for item in catalog["examples"]))

        activated = activate_playbook(
            workflow_name="remember-profile",
            playbook_path=Path("examples/playbook-workflows.yaml"),
        )

        self.assertEqual(activated.workflow_name, "remember-profile")
        self.assertEqual(activated.workflow_description, "Read one remembered profile from shared state")
        self.assertEqual(activated.working_directory, Path("examples").resolve())
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
                _completed(returncode=0, stdout='{"state":"success","statuses":[{"context":"lint","state":"success","target_url":"https://example.test/lint"}]}', stderr=""),
                _completed(returncode=0, stdout='{"total_count":1,"check_runs":[{"name":"unit","status":"completed","conclusion":"success","html_url":"https://example.test/unit"}]}', stderr=""),
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
        workflow = load_workflow_file(Path("examples/project-field-probes.yaml"))

        self.assertEqual(workflow.workflow, "inspect-project-field-probes")

    def test_project_issue_membership_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/project-issue-membership.yaml"))

        self.assertEqual(workflow.workflow, "prepare-project-issue-membership")

    def test_project_item_collections_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/project-item-collections.yaml"))

        self.assertEqual(workflow.workflow, "inspect-project-item-collections")

    def test_git_branch_management_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/git-branch-management.yaml"))

        self.assertEqual(workflow.workflow, "manage-git-branches")

    def test_git_commit_management_example_loads(self) -> None:
        workflow = load_workflow_file(Path("examples/git-commit-management.yaml"))

        self.assertEqual(workflow.workflow, "manage-git-commits")


def _completed(*, returncode: int, stdout: str, stderr: str) -> CompletedProcess[str]:
    return CompletedProcess(args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr)


if __name__ == "__main__":
    unittest.main()
