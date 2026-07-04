import unittest
from pathlib import Path

from ordo.model.runtime import OperationResult
from ordo.runtime import explain_workflow, load_profile_file, load_workflow_file, plan_workflow, validate_profile_text, validate_workflow_text

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ExampleSurfaceTest(unittest.TestCase):
    def test_example_workflows_validate(self) -> None:
        for path in (
            Path("examples/minimal.yaml"),
            Path("examples/inspect-issue.yaml"),
            Path("examples/blocked-main-branch.yaml"),
        ):
            report = validate_workflow_text(path.read_text(encoding="utf-8"), source=str(path))
            self.assertTrue(report.ok, path.as_posix())

    def test_example_profiles_validate(self) -> None:
        for path in (
            Path("profiles/backend-default.yaml"),
            Path("profiles/read-only-review.yaml"),
        ):
            report = validate_profile_text(path.read_text(encoding="utf-8"), source=str(path))
            self.assertTrue(report.ok, path.as_posix())

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


if __name__ == "__main__":
    unittest.main()
