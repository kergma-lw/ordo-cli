import unittest

from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import check_workflow, explain_workflow, review_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ComposeModesTest(unittest.TestCase):
    def test_check_review_and_explain_know_compose_preflight_support(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="compose-demo",
            blocks=(
                GuardBlock(guards=(Guard(OperationRef("compose.project")),)),
                StepBlock(
                    steps=(
                        Step(name="start-project", operation=OperationRef("compose.start")),
                    )
                ),
            ),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "compose.project":
                return OperationResult(
                    status="ok",
                    outputs={
                        "project": "demo",
                        "declared_services": ["api"],
                        "state": "running",
                        "service_counts": {"declared": 1, "running": 1, "stopped": 0, "unhealthy": 0},
                        "services": {"api": {"state": "running", "healthy": True}},
                    },
                )
            return OperationResult(status="ok", outputs={})

        checked = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        reviewed = review_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        explained = explain_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(checked.status, RuntimeStatus.OK)
        self.assertEqual(checked.outputs["preflight_step_items"][0]["preflight_support"]["strength"], "strong")
        self.assertEqual(checked.outputs["preflight_step_items"][0]["preflight_support"]["missing_probes"], [])
        self.assertFalse(any(item["code"] == "review.workflow.missing_recommended_probe_coverage" for item in reviewed.outputs["findings"]))
        self.assertEqual(explained.outputs["explanation"]["preflight_support_steps"][0]["name"], "start-project")
        self.assertEqual(explained.outputs["explanation"]["preflight_support_steps"][0]["preflight_support"]["strength"], "strong")

    def test_remove_action_uses_service_probe_for_preflight_support(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="compose-remove-demo",
            blocks=(
                GuardBlock(guards=(Guard(OperationRef("compose.service", with_={"service": "api"})),)),
                StepBlock(
                    steps=(
                        Step(name="remove-service", operation=OperationRef("compose.remove", with_={"service": "api"})),
                    )
                ),
            ),
        )

        def probe(resolved_guard, _workflow):
            if resolved_guard.reference == "compose.service":
                return OperationResult(
                    status="ok",
                    outputs={
                        "service": "api",
                        "declared": True,
                        "state": "stopped",
                        "healthy": None,
                        "containers": {"total": 1, "running": 0},
                        "published_ports": [],
                    },
                )
            return OperationResult(status="ok", outputs={})

        checked = check_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        explained = explain_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(checked.status, RuntimeStatus.OK)
        self.assertEqual(checked.outputs["preflight_step_items"][0]["preflight_support"]["strength"], "strong")
        self.assertEqual(explained.outputs["explanation"]["preflight_support_steps"][0]["name"], "remove-service")
        self.assertEqual(explained.outputs["explanation"]["preflight_support_steps"][0]["preflight_support"]["strength"], "strong")


if __name__ == "__main__":
    unittest.main()
