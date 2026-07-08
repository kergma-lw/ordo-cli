import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "ordo-help"
GOLDEN_DIR = ROOT / "tests" / "golden"
REAL_VENV_PYTHON = ROOT / ".venv" / "bin" / "python"


class OrdoHelpCliTest(unittest.TestCase):
    def run_help(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(LAUNCHER), *args],
            cwd=str(ROOT if cwd is None else cwd),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )

    def test_root_text_bootstrap_screen(self) -> None:
        result = self.run_help()

        self.assertEqual(result.returncode, 0)
        self.assertIn("ordo-help", result.stdout)
        self.assertIn("Recommended first calls:", result.stdout)
        self.assertIn("overview", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_root_json_matches_golden(self) -> None:
        result = self.run_help("--json")

        self.assertEqual(result.returncode, 0)
        actual = json.loads(result.stdout)
        expected = json.loads((GOLDEN_DIR / "ordo_help_root.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_overview_json_matches_golden(self) -> None:
        result = self.run_help("overview", "--json")

        self.assertEqual(result.returncode, 0)
        actual = json.loads(result.stdout)
        expected = json.loads((GOLDEN_DIR / "ordo_help_overview.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_examples_json_matches_golden(self) -> None:
        result = self.run_help("examples", "--json")

        self.assertEqual(result.returncode, 0)
        actual = json.loads(result.stdout)
        expected = json.loads((GOLDEN_DIR / "ordo_help_examples.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_command_line_json_matches_golden(self) -> None:
        result = self.run_help("command-line", "--json")

        self.assertEqual(result.returncode, 0)
        actual = json.loads(result.stdout)
        expected = json.loads((GOLDEN_DIR / "ordo_help_command_line.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_bootstrap_flow_commands_succeed(self) -> None:
        root = json.loads(self.run_help("--json").stdout)
        overview = json.loads(self.run_help("overview", "--json").stdout)
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)
        model = json.loads(self.run_help("model", "--json").stdout)
        command_line = json.loads(self.run_help("command-line", "--json").stdout)
        operations = json.loads(self.run_help("operations", "--json").stdout)
        examples = json.loads(self.run_help("examples", "--json").stdout)

        self.assertEqual(root["tool_name"], "ordo-help")
        self.assertEqual(overview["document_kind"], "overview")
        self.assertIn("capabilities", capabilities)
        self.assertEqual(model["document_kind"], "model")
        self.assertEqual(command_line["document_kind"], "command_line")
        self.assertIn("connectors", operations)
        self.assertEqual(examples["document_kind"], "examples_catalog")

    def test_search_indexes_capabilities_model_fields_and_examples(self) -> None:
        profile_result = json.loads(self.run_help("search", "profile", "--json").stdout)
        branching_result = json.loads(self.run_help("search", "branching", "--json").stdout)
        override_result = json.loads(self.run_help("search", "override", "--json").stdout)
        example_result = json.loads(self.run_help("search", "open-task", "--json").stdout)
        input_file_result = json.loads(self.run_help("search", "input-file", "--json").stdout)
        working_directory_result = json.loads(self.run_help("search", "working_directory", "--json").stdout)
        launcher_result = json.loads(self.run_help("search", "launcher", "--json").stdout)
        run_result = json.loads(self.run_help("search", "run", "--json").stdout)

        self.assertTrue(any(item["kind"] == "model_field" and item["name"].startswith("profile.") for item in profile_result["facts"]))
        self.assertTrue(any(item["kind"] == "capability" and item["name"] == "workflow.branching" for item in branching_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"].startswith("profile.") for item in override_result["facts"]))
        self.assertTrue(any(item["kind"] == "example" and item["name"] == "open-task-from-gitx" for item in example_result["facts"]))
        self.assertTrue(any(item["kind"] == "command_line_field" and item["name"] == "command-line.ordo-playbook.flag.input_file" for item in input_file_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "playbook.workflows.working_directory" for item in working_directory_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "profile.launchers" for item in launcher_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "workflow.step.launcher" for item in launcher_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "workflow.run_contract" for item in run_result["facts"]))

    def test_capabilities_publish_cross_links_for_branching(self) -> None:
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)
        branching = next(item for item in capabilities["capabilities"] if item["name"] == "workflow.branching")
        if_conflict = next(item for item in capabilities["negative_rules"] if item["name"] == "workflow_step.if_conflicts_with_register")

        self.assertIn("workflow.step.condition", branching["related_capabilities"])
        self.assertIn("workflow.step.register", branching["related_capabilities"])
        self.assertIn("workflow_step.if_conflicts_with_register", branching["related_negative_rules"])
        self.assertIn("workflow.step.if", branching["related_model_nodes"])
        self.assertIn("workflow.branching", if_conflict["related_capabilities"])
        self.assertIn("workflow.step.register", if_conflict["related_capabilities"])

    def test_model_publishes_runtime_effect_metadata_for_profiles(self) -> None:
        model = json.loads(self.run_help("model", "--json").stdout)
        profile_fields = {item["name"]: item for item in model["profile"]["top_level_fields"]}
        defaults_fields = {item["name"]: item for item in model["playbook"]["defaults_fields"]}
        workflow_entry_fields = {item["name"]: item for item in model["playbook"]["workflow_entry_fields"]}
        workflow_inputs = next(item for item in model["workflow"]["top_level_fields"] if item["name"] == "inputs")

        self.assertEqual(profile_fields["inputs"]["runtime_effect"], "applies_missing_workflow_inputs")
        self.assertEqual(profile_fields["checks"]["runtime_effect"], "published_metadata_only")
        self.assertEqual(profile_fields["overrides"]["runtime_effect"], "published_metadata_only")
        self.assertEqual(profile_fields["launchers"]["runtime_effect"], "publishes_profile_scoped_launchers")
        self.assertEqual(defaults_fields["profile"]["runtime_effect"], "selects_active_profile")
        self.assertEqual(workflow_inputs["authoring_role"], "declares_global_activation_inputs")
        self.assertEqual(workflow_entry_fields["working_directory"]["runtime_effect"], "sets_execution_working_directory")
        self.assertEqual(workflow_entry_fields["working_directory"]["resolution_base"], "playbook_dir")
        self.assertEqual(workflow_entry_fields["working_directory"]["expression_syntax"], "${...}")
        self.assertEqual(workflow_entry_fields["working_directory"]["expression_surface"], "activation_input_value_expression")
        self.assertEqual(workflow_entry_fields["working_directory"]["expression_allowed_roots"], ["inputs"])
        self.assertEqual(workflow_entry_fields["working_directory"]["expression_forbidden_roots"], ["state", "step"])

    def test_model_publishes_value_step_form(self) -> None:
        model = json.loads(self.run_help("model", "--json").stdout)
        step_forms = {item["name"]: item for item in model["workflow"]["step_forms"]}

        self.assertEqual(step_forms["value"]["required_fields"], ["name", "value"])
        self.assertIn("register", step_forms["value"]["optional_fields"])
        self.assertIn("launcher", step_forms["operation_call"]["optional_fields"])

    def test_capabilities_publish_explicit_non_inference_metadata(self) -> None:
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)
        branching = next(item for item in capabilities["capabilities"] if item["name"] == "workflow.branching")
        launchers = next(item for item in capabilities["capabilities"] if item["name"] == "runtime.launchers")

        self.assertEqual(branching["status"], "supported")
        self.assertEqual(branching["must_not_infer"], [])
        self.assertEqual(launchers["status"], "supported")
        self.assertIn("workflow.step.launcher", launchers["related_model_nodes"])

    def test_describe_resolves_capability_and_model_nodes(self) -> None:
        capability_node = json.loads(self.run_help("describe", "workflow.branching", "--json").stdout)
        model_node = json.loads(self.run_help("describe", "profile.inputs", "--json").stdout)
        input_contract_node = json.loads(self.run_help("describe", "workflow.inputs_contract", "--json").stdout)
        run_contract_node = json.loads(self.run_help("describe", "workflow.run_contract", "--json").stdout)
        command_line_node = json.loads(self.run_help("describe", "command-line.ordo-playbook.flag.input_file", "--json").stdout)
        working_directory_node = json.loads(self.run_help("describe", "playbook.workflows.working_directory", "--json").stdout)
        launcher_node = json.loads(self.run_help("describe", "profile.launchers", "--json").stdout)
        missing = self.run_help("describe", "missing.node", "--json")

        self.assertEqual(capability_node["document_kind"], "capability_node")
        self.assertEqual(capability_node["node_kind"], "capability")
        self.assertEqual(capability_node["name"], "workflow.branching")
        self.assertEqual(model_node["document_kind"], "model_node")
        self.assertEqual(model_node["name"], "profile.inputs")
        self.assertEqual(model_node["metadata"]["runtime_effect"], "applies_missing_workflow_inputs")
        self.assertEqual(input_contract_node["document_kind"], "model_node")
        self.assertEqual(input_contract_node["name"], "workflow.inputs_contract")
        self.assertTrue(input_contract_node["metadata"]["declared_keys_required_at_activation"])
        self.assertEqual(run_contract_node["document_kind"], "model_node")
        self.assertEqual(run_contract_node["name"], "workflow.run_contract")
        self.assertEqual(run_contract_node["metadata"]["directive_field"], "run")
        self.assertEqual(command_line_node["document_kind"], "command_line_node")
        self.assertEqual(command_line_node["name"], "command-line.ordo-playbook.flag.input_file")
        self.assertEqual(command_line_node["metadata"]["effect"], "override_input_from_file")
        self.assertEqual(working_directory_node["document_kind"], "model_node")
        self.assertEqual(working_directory_node["name"], "playbook.workflows.working_directory")
        self.assertEqual(working_directory_node["metadata"]["runtime_effect"], "sets_execution_working_directory")
        self.assertEqual(working_directory_node["metadata"]["expression_syntax"], "${...}")
        self.assertEqual(launcher_node["document_kind"], "model_node")
        self.assertEqual(launcher_node["name"], "profile.launchers")
        self.assertEqual(launcher_node["metadata"]["runtime_effect"], "publishes_profile_scoped_launchers")
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(json.loads(missing.stdout)["status"], "unknown_topic")

    def test_command_line_topic_publishes_playbook_flags_and_precedence(self) -> None:
        payload = json.loads(self.run_help("command-line", "--json").stdout)

        self.assertEqual(payload["document_kind"], "command_line")
        playbook = next(item for item in payload["commands"] if item["name"] == "ordo-playbook")
        flags = {item["name"]: item for item in playbook["flags"]}
        self.assertEqual(flags["--input-file"]["effect"], "override_input_from_file")
        self.assertEqual(flags["--input-file"]["value_shape"], "KEY=PATH")
        self.assertIn("workflow.inputs declares the allowed activation keys", playbook["input_override_precedence"][0])
        self.assertIn("unknown activation inputs are rejected=true", playbook["input_override_precedence"])
        self.assertIn("when both --input and --input-file set the same key, --input-file wins", playbook["input_override_precedence"])

    def test_operation_topic_publishes_structured_gh_issue_inputs(self) -> None:
        payload = json.loads(self.run_help("operation", "gh.issue", "--json").stdout)

        self.assertEqual(payload["document_kind"], "operation")
        self.assertEqual(payload["operation"]["inputs"]["repository"], "string")
        self.assertEqual(payload["operation"]["inputs"]["issue_number"], "integer")

    def test_examples_topic_publishes_launcher_step_example(self) -> None:
        payload = json.loads(self.run_help("examples", "--json").stdout)

        self.assertTrue(any(item["name"] == "launcher-step" for item in payload["examples"]))

    def test_launcher_reports_missing_virtualenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            launcher_copy = temp_root / "ordo-help"
            shutil.copy2(LAUNCHER, launcher_copy)
            launcher_copy.chmod(launcher_copy.stat().st_mode | stat.S_IXUSR)

            result = subprocess.run(
                [str(launcher_copy)],
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                env=os.environ.copy(),
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing project virtualenv interpreter", result.stderr)

    def test_launcher_reports_missing_help_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            launcher_copy = temp_root / "ordo-help"
            shutil.copy2(LAUNCHER, launcher_copy)
            launcher_copy.chmod(launcher_copy.stat().st_mode | stat.S_IXUSR)

            venv_bin = temp_root / ".venv" / "bin"
            venv_bin.mkdir(parents=True)
            os.symlink(REAL_VENV_PYTHON, venv_bin / "python")

            result = subprocess.run(
                [str(launcher_copy)],
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                env=os.environ.copy(),
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing ordo-help CLI module", result.stderr)


if __name__ == "__main__":
    unittest.main()
