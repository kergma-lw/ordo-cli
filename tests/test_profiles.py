import unittest

from ordo.model.profile import Override, Profile
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Workflow
from ordo.runtime import apply_profile_to_workflow, compose_profiles


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

    def test_profile_applies_defaults_without_overriding_workflow_inputs(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", inputs={"issue_ref": "repo#1"})
        profile = Profile(name="repo-defaults", inputs={"branch": "keep"})

        result = apply_profile_to_workflow(workflow, profile)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.workflow.inputs["issue_ref"], "repo#1")
        self.assertEqual(result.workflow.inputs["branch"], "keep")
        self.assertEqual(result.active_profile, "repo-defaults")

    def test_profile_application_rejects_silent_workflow_override(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", inputs={"branch": "feature"})
        profile = Profile(name="repo-defaults", inputs={"branch": "keep"})

        result = apply_profile_to_workflow(workflow, profile)

        self.assertEqual(result.status, RuntimeStatus.VALIDATION_ERROR)
        self.assertEqual(result.diagnostics[0].code, "composition.workflow.input_conflict")


if __name__ == "__main__":
    unittest.main()
