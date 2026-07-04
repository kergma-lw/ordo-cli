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

    def test_bootstrap_flow_commands_succeed(self) -> None:
        root = json.loads(self.run_help("--json").stdout)
        overview = json.loads(self.run_help("overview", "--json").stdout)
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)
        model = json.loads(self.run_help("model", "--json").stdout)
        operations = json.loads(self.run_help("operations", "--json").stdout)
        examples = json.loads(self.run_help("examples", "--json").stdout)

        self.assertEqual(root["tool_name"], "ordo-help")
        self.assertEqual(overview["document_kind"], "overview")
        self.assertIn("capabilities", capabilities)
        self.assertEqual(model["document_kind"], "model")
        self.assertIn("connectors", operations)
        self.assertEqual(examples["document_kind"], "examples_catalog")

    def test_search_indexes_capabilities_model_fields_and_examples(self) -> None:
        profile_result = json.loads(self.run_help("search", "profile", "--json").stdout)
        branching_result = json.loads(self.run_help("search", "branching", "--json").stdout)
        override_result = json.loads(self.run_help("search", "override", "--json").stdout)
        example_result = json.loads(self.run_help("search", "open-task", "--json").stdout)

        self.assertTrue(any(item["kind"] == "model_field" and item["name"].startswith("profile.") for item in profile_result["facts"]))
        self.assertTrue(any(item["kind"] == "capability" and item["name"] == "workflow.branching" for item in branching_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"].startswith("profile.") for item in override_result["facts"]))
        self.assertTrue(any(item["kind"] == "example" and item["name"] == "open-task-from-gitx" for item in example_result["facts"]))

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

        self.assertEqual(profile_fields["inputs"]["runtime_effect"], "applies_missing_workflow_inputs")
        self.assertEqual(profile_fields["checks"]["runtime_effect"], "published_metadata_only")
        self.assertEqual(profile_fields["overrides"]["runtime_effect"], "published_metadata_only")
        self.assertEqual(defaults_fields["profile"]["runtime_effect"], "selects_active_profile")

    def test_capabilities_publish_explicit_non_inference_metadata(self) -> None:
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)
        branching = next(item for item in capabilities["capabilities"] if item["name"] == "workflow.branching")

        self.assertIn("workflow.step.condition is unsupported", branching["must_not_infer"])
        self.assertIn("workflow.step.register is unsupported", branching["must_not_infer"])

    def test_describe_resolves_capability_and_model_nodes(self) -> None:
        capability_node = json.loads(self.run_help("describe", "workflow.branching", "--json").stdout)
        model_node = json.loads(self.run_help("describe", "profile.inputs", "--json").stdout)
        missing = self.run_help("describe", "missing.node", "--json")

        self.assertEqual(capability_node["document_kind"], "capability_node")
        self.assertEqual(capability_node["node_kind"], "capability")
        self.assertEqual(capability_node["name"], "workflow.branching")
        self.assertEqual(model_node["document_kind"], "model_node")
        self.assertEqual(model_node["name"], "profile.inputs")
        self.assertEqual(model_node["metadata"]["runtime_effect"], "applies_missing_workflow_inputs")
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(json.loads(missing.stdout)["status"], "unknown_topic")

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
