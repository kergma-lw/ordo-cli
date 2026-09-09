import tempfile
import unittest
from pathlib import Path

import yaml

from ordo.playbook import activate_playbook
from ordo.runtime.reviewing import review_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


ROOT = Path(__file__).resolve().parents[1]


class ProfileDrivenSetActiveTaskTest(unittest.TestCase):
    def test_set_active_task_has_only_input_documentation_findings_from_profile_plus_issue_number_entry(self) -> None:
        assets = ROOT / ".ordo"
        playbook = yaml.safe_load((assets / "ordo.yaml").read_text(encoding="utf-8"))
        workflow_entry = playbook["workflows"]["set-active-task"]
        workflow_entry["file"] = str(assets / workflow_entry["file"])
        playbook["workflows"] = {"set-active-task": workflow_entry}
        profile_entry = playbook["profiles"]["ordo"]
        profile = yaml.safe_load((assets / profile_entry["file"]).read_text(encoding="utf-8"))
        playbook["profiles"] = {"ordo": profile_entry}

        # Keep context profile-owned, including working_directory's repo_dir expression.
        # Only the temporary profile replaces the machine-specific checkout path.
        profile["inputs"]["repo_dir"] = str(ROOT)
        with tempfile.TemporaryDirectory() as temp_dir:
            playbook_path = Path(temp_dir) / "ordo.yaml"
            profile_path = playbook_path.parent / profile_entry["file"]
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            profile_path.write_text(yaml.safe_dump(profile), encoding="utf-8")
            playbook_path.write_text(yaml.safe_dump(playbook), encoding="utf-8")

            activated = activate_playbook(
                workflow_name="set-active-task",
                profile_name="ordo",
                input_overrides={"issue_number": 106},
                playbook_path=playbook_path,
                cwd=ROOT,
            )

            self.assertEqual(
                activated.workflow.explicit_input_keys,
                ("issue_number",),
                "Repository context must come from the profile, not caller overrides",
            )
            self.assertEqual(
                activated.working_directory,
                ROOT,
                f"Profile working_directory must resolve to this checkout; diagnostics: {activated.diagnostics!r}",
            )

            result = review_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=activated.available_profiles,
                connector_provider=STANDARD_CONNECTOR_PROVIDER,
            )

        diagnostics = f"diagnostics: {result.diagnostics!r}; outputs: {result.outputs!r}"
        self.assertEqual(result.status.value, "ok", diagnostics)
        self.assertEqual(result.outputs["active_profile"], "ordo", diagnostics)
        unexpected_findings = [
            item for item in result.outputs["findings"]
            if item["code"] != "review.workflow.input_description_missing"
        ]
        self.assertFalse(unexpected_findings, f"Unexpected review findings: {unexpected_findings!r}; {diagnostics}")


if __name__ == "__main__":
    unittest.main()
