import unittest

from ordo.model.connector import Connector, OperationContract
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.runtime import resolve_workflow_references

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ResolutionTest(unittest.TestCase):
    def test_runtime_resolution_requires_explicit_provider_or_configured_default(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(), steps=())

        with self.assertRaises(RuntimeError):
            resolve_workflow_references(workflow)

    def test_known_public_operations_resolve(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue")),),
        )

        result = resolve_workflow_references(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.resolved_guards[0].source, "public")
        self.assertEqual(result.resolved_steps[0].operation.kind, "probe")

    def test_unknown_operation_fails_as_resolution_error(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("gh.issue.missing")),),
        )

        result = resolve_workflow_references(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "resolution.unknown_operation")
        self.assertEqual(result.diagnostics[0].path, ("steps", "0", "uses"))

    def test_public_namespace_shadowing_is_rejected(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", guards=(), steps=())
        local_connectors = (
            Connector(
                namespace="gh",
                operations=(OperationContract(name="issue", kind="probe"),),
            ),
        )

        result = resolve_workflow_references(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER, local_connectors=local_connectors)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "resolution.namespace_shadowing")

    def test_explicit_local_namespace_is_allowed(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="inspect", operation=OperationRef("local.issue")),),
        )
        local_connectors = (
            Connector(
                namespace="local",
                operations=(OperationContract(name="issue", kind="probe"),),
            ),
        )

        result = resolve_workflow_references(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER, local_connectors=local_connectors)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.resolved_steps[0].source, "local")
        self.assertEqual(result.resolved_steps[0].reference, "local.issue")

    def test_expr_guard_resolves_probe_call_and_documented_field_path(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(expr='gh.issue(issue_ref=inputs.issue_ref).state != "CLOSED"'),),
            steps=(),
        )

        result = resolve_workflow_references(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.resolved_guards[0].reference, 'gh.issue(issue_ref=inputs.issue_ref).state != "CLOSED"')
        self.assertEqual(result.resolved_guards[0].probes[0].reference, "gh.issue")
        self.assertEqual(result.resolved_guards[0].probes[0].fields, ("state",))

    def test_expr_guard_rejects_action_reference(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"issue_ref": "owner/repo#1", "project_id": "PVT_demo"},
            guards=(Guard(expr='gh.project.issue.status.set(issue_ref=inputs.issue_ref, project_id=inputs.project_id, status="Done").status == "Done"'),),
            steps=(),
        )

        result = resolve_workflow_references(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "resolution.guard_expr.action_forbidden")

    def test_expr_guard_rejects_undocumented_field_path(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(expr='gh.issue(issue_ref=inputs.issue_ref).project.owner == "me"'),),
            steps=(),
        )

        result = resolve_workflow_references(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.RESOLUTION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "resolution.guard_expr.field_unknown")

    def test_expr_guard_resolves_nested_project_issue_probe_call(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"issue_ref": "owner/repo#1", "project_id": "PVT_demo"},
            guards=(Guard(expr='gh.project.issue(issue_ref=inputs.issue_ref, project_id=inputs.project_id).exists'),),
            steps=(),
        )

        result = resolve_workflow_references(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.resolved_guards[0].probes[0].reference, "gh.project.issue")
        self.assertEqual(result.resolved_guards[0].probes[0].fields, ("exists",))


if __name__ == "__main__":
    unittest.main()
