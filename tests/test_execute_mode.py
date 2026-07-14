import unittest
from pathlib import Path
import tempfile

from ordo.model.diagnostic import Diagnostic
from ordo.model.launcher import Launcher
from ordo.model.profile import Profile
from ordo.model.runtime import Mode, OperationResult, RuntimeStatus
from ordo.model.workflow import Guard, OperationRef, Step, Workflow
from ordo.playbook import activate_playbook
from ordo.runtime import execute_workflow, plan_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ExecuteModeTest(unittest.TestCase):
    def test_execute_preserves_blocked_before_execution(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(Guard(OperationRef("git.worktree")),),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )

        def probe(_resolved_guard, _workflow):
            return OperationResult(
                status="guard_failed",
                summary="Dirty worktree",
                diagnostics=(
                    Diagnostic(
                        code="guard.blocked",
                        level="error",
                        message="Worktree is dirty",
                        path=("guards", "0", "uses"),
                    ),
                ),
            )

        result = execute_workflow(workflow, guard_probe=probe, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.mode, Mode.EXECUTE)
        self.assertEqual(result.status, RuntimeStatus.GUARD_FAILED)
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["effectful-step"])

    def test_execute_runs_steps_on_success(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])
        self.assertEqual(result.outputs["executed_steps"], ["effectful-step"])
        self.assertEqual(result.outputs["skipped_steps"], [])

    def test_execute_accepts_plan_derived_execution_tree_input(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )

        plan_result = plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        result = execute_workflow(
            workflow,
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
            execution_tree=plan_result.outputs["execution_tree"],
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["execution_tree"]["workflow"], "open-task")

    def test_execute_falls_back_when_no_execution_tree_is_supplied(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command")),),
        )

        result = execute_workflow(
            workflow,
            step_executor=lambda *_args: OperationResult(status="ok", summary="Executed"),
            connector_provider=STANDARD_CONNECTOR_PROVIDER,
        )

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["execution_tree"], None)

    def test_execute_normalizes_step_failure(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(
                Step(name="first-step", operation=OperationRef("shell.command")),
                Step(name="second-step", operation=OperationRef("shell.command")),
            ),
        )
        call_count = 0

        def executor(_resolved_step, _workflow):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return OperationResult(status="execution_error", summary="Boom", raw={"stderr": "failed"})
            return OperationResult(status="ok")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "first-step")
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["second-step"])
        self.assertEqual(result.operation_results[-1].raw["stderr"], "failed")

    def test_execute_skips_step_when_condition_is_false(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": False},
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, [])
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["effectful-step"])

    def test_execute_runs_step_when_condition_is_true(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"enabled": True},
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),),
        )
        seen_steps: list[str] = []

        def executor(resolved_step, _workflow):
            seen_steps.append(resolved_step.reference)
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(seen_steps, ["shell.command"])
        self.assertEqual(result.outputs["executed_steps"], ["effectful-step"])
        self.assertEqual(result.outputs["skipped_steps"], [])

    def test_execute_fails_when_step_condition_cannot_be_evaluated(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(
                Step(name="first-step", operation=OperationRef("shell.command"), if_="${inputs.enabled}"),
                Step(name="second-step", operation=OperationRef("shell.command")),
            ),
        )

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.EXECUTION_ERROR)
        self.assertEqual(result.failed_step, "first-step")
        self.assertEqual(result.outputs["executed_steps"], [])
        self.assertEqual(result.outputs["skipped_steps"], ["second-step"])
        self.assertEqual(result.diagnostics[-1].code, "runtime.value.input_missing")

    def test_execute_applies_launcher_to_shell_command(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command", with_={"command": "echo hi"}), launcher="shell_frontend"),),
        )
        profile = Profile(name="frontend", launchers={"shell_frontend": Launcher(connector="shell.command", before="nvm use", after="true")})
        seen_commands: list[object] = []

        def executor(resolved_step, _workflow):
            seen_commands.append(resolved_step.declared_with["command"])
            return OperationResult(status="ok", summary="Executed")

        result = execute_workflow(workflow, profile=profile, step_executor=executor, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(len(seen_commands), 1)
        self.assertIn("nvm use", seen_commands[0])
        self.assertIn("echo hi", seen_commands[0])
        self.assertEqual(result.outputs["launcher_details"][0]["launcher"], "shell_frontend")

    def test_execute_reports_unknown_launcher_as_validation_error(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(Step(name="effectful-step", operation=OperationRef("shell.command", with_={"command": "echo hi"}), launcher="missing"),),
        )
        profile = Profile(name="frontend")

        result = execute_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "validation.workflow.step.launcher.unknown")

    def test_execute_runtime_profile_use_switches_profile_for_nested_run_and_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frontend_dir = root / "frontend"
            backend_dir = root / "backend"
            frontend_dir.mkdir()
            backend_dir.mkdir()
            fragment = root / "fragment.yml"
            fragment.write_text(
                "steps:\n  - name: nested-command\n    uses: shell.command\n    with:\n      command: echo hi\n    launcher: shell_frontend\n",
                encoding="utf-8",
            )
            workflow = Workflow(
                version=0,
                workflow="open-task",
                source_path=str(root / "root.yml"),
                launch_dir=str(root),
                guards=(),
                steps=(
                    Step(name="switch", operation=OperationRef("runtime.profile.use", with_={"profile": "frontend"})),
                    Step(name="nested", run="fragment.yml", resolved_run_path=str(fragment)),
                ),
            )
            backend = Profile(name="backend")
            frontend = Profile(name="frontend", launchers={"shell_frontend": Launcher(connector="shell.command", before="nvm use", after="true")})
            seen = []

            def executor(resolved_step, _workflow):
                seen.append((resolved_step.reference, Path.cwd(), resolved_step.declared_with.get("command")))
                return OperationResult(status="ok", summary="Executed")

            result = execute_workflow(
                workflow,
                profile=backend,
                available_profiles={"backend": backend, "frontend": frontend},
                profile_working_directories={"backend": backend_dir, "frontend": frontend_dir},
                step_executor=executor,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["active_profile"], "frontend")
            self.assertEqual(seen[0][0], "shell.command")
            self.assertEqual(seen[0][1], frontend_dir)
            self.assertIn("nvm use", seen[0][2])

    def test_execute_pre_run_workflow_can_switch_profile_for_main_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo" / "workflows").mkdir(parents=True)
            (root / ".ordo" / "profiles").mkdir(parents=True)
            frontend_dir = root / "frontend"
            backend_dir = root / "backend"
            frontend_dir.mkdir()
            backend_dir.mkdir()
            (root / ".ordo" / "playbook.yml").write_text(
                "version: 1\npre_run:\n  - workflows/resolve-context.yml\ndefaults:\n  profile: backend\nworkflows:\n  close-task:\n    file: close-task.yml\nprofiles:\n  frontend:\n    file: frontend.yml\n  backend:\n    file: backend.yml\nstates: {}\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "resolve-context.yml").write_text(
                "steps:\n  - name: switch\n    profile_switch: frontend\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "workflows" / "close-task.yml").write_text(
                "version: 0\nworkflow: close-task\ninputs:\n  repo_dir: {}\nblocks:\n  - steps:\n      - name: main\n        uses: shell.command\n        with:\n          command: echo hi\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "frontend.yml").write_text(
                "name: frontend\ninputs:\n  repo_dir: ../frontend\nworking_directory: ${inputs.repo_dir}\nlaunchers:\n  shell_frontend:\n    before: nvm use\n    after: \"true\"\n",
                encoding="utf-8",
            )
            (root / ".ordo" / "profiles" / "backend.yml").write_text(
                "name: backend\ninputs:\n  repo_dir: ../backend\nworking_directory: ${inputs.repo_dir}\n",
                encoding="utf-8",
            )

            activated = activate_playbook(workflow_name="close-task", cwd=root)
            seen = []

            def executor(resolved_step, _workflow):
                seen.append((resolved_step.reference, Path.cwd(), resolved_step.declared_with.get("command")))
                return OperationResult(status="ok", summary="Executed")

            result = execute_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                profile_working_directories=activated.profile_working_directories,
                step_executor=executor,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

            self.assertEqual(result.status, RuntimeStatus.OK)
            self.assertEqual(result.outputs["active_profile"], "frontend")
            self.assertEqual(seen[0][1], frontend_dir)

    def test_runtime_profile_use_applies_profile_inputs_to_subsequent_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "explicit/repo"},
            guards=(),
            steps=(
                Step(name="switch", operation=OperationRef("runtime.profile.use", with_={"profile": "frontend"})),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend")
        frontend = Profile(name="frontend", inputs={"repository": "profile/repo", "repo_dir": "/tmp/frontend"})
        seen_inputs = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
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

    def test_execute_profile_switch_applies_profile_inputs_to_subsequent_steps(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "explicit/repo"},
            guards=(),
            steps=(
                Step(name="switch", profile_switch="frontend"),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend")
        frontend = Profile(name="frontend", inputs={"repository": "profile/repo", "repo_dir": "/tmp/frontend"})
        seen_inputs = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
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

    def test_execute_profile_switch_reapplies_context_after_repeated_switches(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            guards=(),
            steps=(
                Step(name="switch-frontend", profile_switch="frontend"),
                Step(name="switch-backend", profile_switch="backend"),
                Step(name="main", operation=OperationRef("shell.command", with_={"command": "echo hi"})),
            ),
        )
        backend = Profile(name="backend", inputs={"repo_kind": "backend"})
        frontend = Profile(name="frontend", inputs={"repo_kind": "frontend"})
        seen_inputs = []

        def executor(_resolved_step, runtime_workflow):
            seen_inputs.append(dict(runtime_workflow.inputs))
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
        self.assertEqual(result.outputs["active_profile"], "backend")
        self.assertEqual(seen_inputs[0]["repo_kind"], "backend")


if __name__ == "__main__":
    unittest.main()
