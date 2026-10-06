import unittest

from ordo.model.profile import Profile
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import OperationRef, Step, Workflow
from ordo.runtime import execute_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class RuntimeProfileSwitchTest(unittest.TestCase):
    def test_profile_switch_injects_profile_inputs_when_not_explicitly_overridden(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "declared/repo"},
            guards=(),
            steps=(
                Step(name="switch", profile_switch="frontend"),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend")
        frontend = Profile(name="frontend", inputs={"repository": "profile/repo", "repo_dir": "/tmp/frontend"})
        seen_inputs: list[dict[str, object]] = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
            from ordo.model.runtime import OperationResult

            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            profile=backend,
            available_profiles={"backend": backend, "frontend": frontend},
            profile_working_directories={"backend": None, "frontend": None},
            step_executor=executor,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "frontend")
        self.assertEqual(seen_inputs[0]["repository"], "profile/repo")
        self.assertEqual(seen_inputs[0]["repo_dir"], "/tmp/frontend")

    def test_profile_switch_preserves_explicit_activation_override(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "explicit/repo"},
            declared_inputs={"repository": {}},
            explicit_input_keys=("repository",),
            guards=(),
            steps=(
                Step(name="switch", profile_switch="frontend"),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend")
        frontend = Profile(name="frontend", inputs={"repository": "profile/repo", "repo_dir": "/tmp/frontend"})
        seen_inputs: list[dict[str, object]] = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
            from ordo.model.runtime import OperationResult

            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(
            workflow,
            profile=backend,
            available_profiles={"backend": backend, "frontend": frontend},
            profile_working_directories={"backend": None, "frontend": None},
            step_executor=executor,
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["active_profile"], "frontend")
        self.assertEqual(seen_inputs[0]["repository"], "explicit/repo")
        self.assertEqual(seen_inputs[0]["repo_dir"], "/tmp/frontend")

    def test_profile_switch_rejects_value_outside_allowed_values(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"status": "ready"},
            declared_inputs={"status": {"allowed_values": ["ready", "queued"]}},
            guards=(),
            steps=(
                Step(name="switch", profile_switch="frontend"),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        frontend = Profile(name="frontend", inputs={"status": "closed"})

        result = execute_workflow(
            workflow,
            available_profiles={"frontend": frontend},
            profile_working_directories={"frontend": None},
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "runtime.workflow.input_not_allowed")
        self.assertNotIn("main", result.outputs["executed_steps"])


if __name__ == "__main__":
    unittest.main()
