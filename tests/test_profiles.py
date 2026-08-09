import unittest

from ordo.model.launcher import Launcher
from ordo.model.profile import Override, Profile
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Workflow
from ordo.runtime import apply_profile_defaults_to_subsequent_steps, apply_profile_to_workflow, compose_profiles


class ProfileCompositionTest(unittest.TestCase):
    def test_profiles_compose_discoverable_defaults(self) -> None:
        repo_defaults = Profile(name="repo-defaults", inputs={"branch": "keep"}, checks=("unit",))
        verify = Profile(
            name="verify",
            inputs={"test_command": ".venv/bin/python -m pytest"},
            overrides=(Override(target="shell.command", with_={"command": ".venv/bin/python -m pytest"}, reason="repo default verify command"),),
        )

        result = compose_profiles(repo_defaults, verify, name="backend-default")

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.profile.name, "backend-default")
        self.assertEqual(result.profile.inputs["branch"], "keep")
        self.assertEqual(result.profile.inputs["test_command"], ".venv/bin/python -m pytest")
        self.assertEqual(result.active_profiles, ("repo-defaults", "verify"))
        self.assertEqual(result.active_overrides[0].target, "shell.command")

    def test_profile_composition_rejects_silent_input_override(self) -> None:
        first = Profile(name="repo-a", inputs={"branch": "keep"})
        second = Profile(name="repo-b", inputs={"branch": "replace"})

        result = compose_profiles(first, second)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "composition.profile.input_conflict")

    def test_profile_composition_rejects_duplicate_override_target(self) -> None:
        first = Profile(name="repo-a", overrides=(Override(target="shell.command"),))
        second = Profile(name="repo-b", overrides=(Override(target="shell.command"),))

        result = compose_profiles(first, second)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "composition.profile.override_conflict")

    def test_profile_composition_rejects_conflicting_launcher_definition(self) -> None:
        first = Profile(name="repo-a", launchers={"shell_frontend": Launcher(connector="shell.command", before="nvm use")})
        second = Profile(name="repo-b", launchers={"shell_frontend": Launcher(connector="shell.command", before="fnm use")})

        result = compose_profiles(first, second)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "composition.profile.launcher_conflict")

    def test_profile_applies_defaults_without_overriding_workflow_inputs(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", inputs={"issue_ref": "repo#1"})
        profile = Profile(name="repo-defaults", inputs={"branch": "keep"})

        result = apply_profile_to_workflow(workflow, profile)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.workflow.inputs["issue_ref"], "repo#1")
        self.assertEqual(result.workflow.inputs["branch"], "keep")
        self.assertEqual(result.active_profile, "repo-defaults")

    def test_profile_application_rejects_silent_workflow_override(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", inputs={"branch": "feature"}, explicit_input_keys=("branch",))
        profile = Profile(name="repo-defaults", inputs={"branch": "keep"})

        result = apply_profile_to_workflow(workflow, profile)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "composition.workflow.input_conflict")

    def test_subsequent_profile_application_fills_only_missing_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "explicit/repo"},
            explicit_input_keys=("repository",),
        )
        profile = Profile(name="frontend", inputs={"repository": "profile/repo", "repo_dir": "../frontend"})

        result = apply_profile_defaults_to_subsequent_steps(workflow, profile)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.workflow.inputs["repository"], "explicit/repo")
        self.assertEqual(result.workflow.inputs["repo_dir"], "../frontend")

    def test_profile_composition_preserves_launchers_when_non_conflicting(self) -> None:
        first = Profile(name="repo-a", launchers={"shell_frontend": Launcher(connector="shell.command", before="nvm use")})
        second = Profile(name="repo-b", inputs={"branch": "keep"})

        result = compose_profiles(first, second)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertIn("shell_frontend", result.profile.launchers)

    def test_profile_composition_rejects_conflicting_working_directory(self) -> None:
        first = Profile(name="repo-a", working_directory="repos/a")
        second = Profile(name="repo-b", working_directory="repos/b")

        result = compose_profiles(first, second)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "composition.profile.working_directory_conflict")

    def test_profile_composition_merges_non_conflicting_connector_contexts(self) -> None:
        first = Profile(name="repo-a", connectors={"git": {"directory": "/repos/a"}})
        second = Profile(name="repo-b", connectors={"compose": {"file": "compose.yaml"}})

        result = compose_profiles(first, second)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.profile.connectors["git"]["directory"], "/repos/a")
        self.assertEqual(result.profile.connectors["compose"]["file"], "compose.yaml")


if __name__ == "__main__":
    unittest.main()
