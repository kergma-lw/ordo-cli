import unittest

from ordo.connectors import get_public_connector_registry
from ordo.model.profile import Profile
from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import compose_profiles, explain_workflow, validate_workflow_text

from tests.support import STANDARD_CONNECTOR_PROVIDER


class AuthoringVerificationTest(unittest.TestCase):
    def test_public_operations_are_discoverable_without_connector_internals(self) -> None:
        registry = get_public_connector_registry()
        contract = registry.to_contract()

        namespaces = [connector["namespace"] for connector in contract["connectors"]]
        namespaces = [connector["namespace"] for connector in contract["connectors"]]
        gh_connector = next(connector for connector in contract["connectors"] if connector["namespace"] == "gh")
        gh_ops = [op["name"] for op in gh_connector["operations"]]

        self.assertEqual(namespaces, ["runtime", "git", "compose", "gh", "shell", "fs"])
        self.assertIn("issue", gh_ops)

    def test_agent_can_compose_non_trivial_workflow_and_profile(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="review-issue",
            inputs={"repository": "kergma-lw/ordo-cli", "issue_number": 1, "command": "echo review"},
            blocks=(
                GuardBlock(
                    guards=(
                        Guard(OperationRef("git.worktree")),
                        Guard(expr='git.branch.value != "main"'),
                    )
                ),
                StepBlock(
                    steps=(
                        Step(name="inspect-issue", operation=OperationRef("gh.issue", with_={"repository": "kergma-lw/ordo-cli", "issue_number": 1})),
                        Step(name="verify-command", operation=OperationRef("shell.command", with_={"command": "echo review"})),
                    )
                ),
            ),
        )
        profile = Profile(name="review-defaults", inputs={"command": "echo review"})

        composed = compose_profiles(profile)

        self.assertTrue(composed.ok)
        self.assertEqual(workflow.steps[0].operation.uses, "gh.issue")
        self.assertEqual(composed.profile.name, "review-defaults")

    def test_structured_feedback_supports_iterative_repair(self) -> None:
        invalid = validate_workflow_text(
            "version: 0\nworkflow: review-issue\nextra: true\nblocks:\n  - guards: []\n  - steps: []\n"
        )
        repaired = Workflow(
            version=0,
            workflow="review-issue",
            blocks=(
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
                StepBlock(steps=(Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "kergma-lw/ordo-cli", "issue_number": 1})),)),
            ),
        )

        explanation = explain_workflow(
            repaired,
            guard_probe=lambda _resolved, _workflow: OperationResult(status="ok", summary="clean", outputs={"clean": True, "dirty_paths": []}),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(invalid.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(invalid.diagnostics[0].path, ("extra",))
        self.assertEqual(explanation.status, RuntimeStatus.OK)
        self.assertEqual(explanation.outputs["next_actions"][0]["action"], "execute_workflow")


if __name__ == "__main__":
    unittest.main()
