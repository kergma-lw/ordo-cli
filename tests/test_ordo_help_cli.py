import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_FILTERS


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

    def test_workflow_authoring_json_matches_golden(self) -> None:
        result = self.run_help("workflow-authoring", "--json")

        self.assertEqual(result.returncode, 0)
        actual = json.loads(result.stdout)
        expected = json.loads((GOLDEN_DIR / "ordo_help_workflow_authoring.json").read_text(encoding="utf-8"))
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
        model = json.loads(self.run_help("model", "--json").stdout)
        workflow_authoring = json.loads(self.run_help("workflow-authoring", "--json").stdout)
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)
        command_line = json.loads(self.run_help("command-line", "--json").stdout)
        operations = json.loads(self.run_help("operations", "--json").stdout)
        examples = json.loads(self.run_help("examples", "--json").stdout)

        self.assertEqual(root["tool_name"], "ordo-help")
        self.assertEqual(overview["document_kind"], "overview")
        self.assertEqual(model["document_kind"], "model")
        self.assertEqual(workflow_authoring["document_kind"], "workflow_authoring")
        self.assertIn("capabilities", capabilities)
        self.assertEqual(command_line["document_kind"], "command_line")
        self.assertIn("connectors", operations)
        self.assertEqual(examples["document_kind"], "examples_catalog")

    def test_search_indexes_capabilities_model_fields_and_examples(self) -> None:
        profile_result = json.loads(self.run_help("search", "profile", "--json").stdout)
        branching_result = json.loads(self.run_help("search", "branching", "--json").stdout)
        override_result = json.loads(self.run_help("search", "override", "--json").stdout)
        example_result = json.loads(self.run_help("search", "set-active-task", "--json").stdout)
        input_file_result = json.loads(self.run_help("search", "input-file", "--json").stdout)
        working_directory_result = json.loads(self.run_help("search", "working_directory", "--json").stdout)
        category_result = json.loads(self.run_help("search", "category", "--json").stdout)
        launcher_result = json.loads(self.run_help("search", "launcher", "--json").stdout)
        run_result = json.loads(self.run_help("search", "run", "--json").stdout)
        pre_run_result = json.loads(self.run_help("search", "pre_run", "--json").stdout)

        self.assertTrue(any(item["kind"] == "model_field" and item["name"].startswith("profile.") for item in profile_result["facts"]))
        self.assertTrue(any(item["kind"] == "capability" and item["name"] == "workflow.branching" for item in branching_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"].startswith("profile.") for item in override_result["facts"]))
        self.assertTrue(any(item["kind"] == "example" and item["name"] == "set-active-task-from-gitx" for item in example_result["facts"]))
        self.assertTrue(any(item["kind"] == "command_line_field" and item["name"] == "command-line.ordo-playbook.flag.input_file" for item in input_file_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "playbook.workflows.working_directory" for item in working_directory_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "playbook.workflows.category" for item in category_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "profile.launchers" for item in launcher_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "workflow.step.launcher" for item in launcher_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "workflow.run_contract" for item in run_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "playbook.pre_run" for item in pre_run_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "playbook.pre_run_contract" for item in pre_run_result["facts"]))

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

    def test_capabilities_publish_representation_adapter_capability(self) -> None:
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)
        adapter_capability = next(item for item in capabilities["capabilities"] if item["name"] == "workflow.local_expression.adapters")

        self.assertEqual(adapter_capability["status"], "supported")
        self.assertIn("workflow.local_expression.adapter.key_value", adapter_capability["related_model_nodes"])
        self.assertIn("workflow.local_expression.adapter.markdown", adapter_capability["related_model_nodes"])
        self.assertIn("workflow.local_expression.adapter.text", adapter_capability["related_model_nodes"])

    def test_model_publishes_runtime_effect_metadata_for_profiles(self) -> None:
        model = json.loads(self.run_help("model", "--json").stdout)
        profile_fields = {item["name"]: item for item in model["profile"]["top_level_fields"]}
        defaults_fields = {item["name"]: item for item in model["playbook"]["defaults_fields"]}
        workflow_entry_fields = {item["name"]: item for item in model["playbook"]["workflow_entry_fields"]}
        workflow_inputs = next(item for item in model["workflow"]["top_level_fields"] if item["name"] == "inputs")

        self.assertEqual(model["playbook"]["activation_semantics"]["pre_run"]["item_type"], "pre_run_entry")
        self.assertEqual(model["playbook"]["activation_semantics"]["pre_run"]["launch_context_boundary"], "playbook_owned")
        self.assertEqual(profile_fields["inputs"]["runtime_effect"], "applies_missing_workflow_inputs")
        self.assertEqual(profile_fields["working_directory"]["runtime_effect"], "sets_profile_execution_working_directory")
        self.assertEqual(profile_fields["checks"]["runtime_effect"], "published_metadata_only")
        self.assertEqual(profile_fields["overrides"]["runtime_effect"], "published_metadata_only")
        self.assertEqual(profile_fields["launchers"]["runtime_effect"], "publishes_profile_scoped_launchers")
        self.assertEqual(profile_fields["launchers"]["status"], "deprecated")
        self.assertEqual(profile_fields["launchers"]["preferred_alternative"], "published_routines")
        self.assertEqual(defaults_fields["profile"]["runtime_effect"], "selects_active_profile")
        self.assertEqual(defaults_fields["working_directory"]["runtime_effect"], "sets_default_execution_working_directory")
        self.assertEqual(workflow_inputs["authoring_role"], "declares_global_activation_inputs")
        self.assertEqual(workflow_entry_fields["category"]["runtime_effect"], "published_metadata_only")
        self.assertEqual(workflow_entry_fields["when"]["runtime_effect"], "published_metadata_only")
        self.assertEqual(workflow_entry_fields["working_directory"]["runtime_effect"], "sets_execution_working_directory")
        self.assertEqual(workflow_entry_fields["working_directory"]["resolution_base"], "playbook_dir")
        self.assertEqual(workflow_entry_fields["working_directory"]["expression_syntax"], "${...}")
        self.assertEqual(workflow_entry_fields["working_directory"]["expression_surface"], "activation_input_value_expression")
        self.assertEqual(workflow_entry_fields["working_directory"]["expression_allowed_roots"], ["inputs"])
        self.assertEqual(workflow_entry_fields["working_directory"]["expression_forbidden_roots"], ["state", "step"])

    def test_model_publishes_value_step_form(self) -> None:
        model = json.loads(self.run_help("model", "--json").stdout)
        step_forms = {item["name"]: item for item in model["workflow"]["step_forms"]}

        self.assertEqual(step_forms["run_invocation"]["required_fields"], ["name", "run"])
        self.assertIn("for_each", step_forms["run_invocation"]["optional_fields"])
        self.assertIn("register", step_forms["run_invocation"]["optional_fields"])
        self.assertEqual(step_forms["value"]["required_fields"], ["name", "value"])
        self.assertEqual(step_forms["result"]["required_fields"], ["name", "result"])
        self.assertEqual(step_forms["publish"]["required_fields"], ["name", "publish"])
        self.assertIn("register", step_forms["value"]["optional_fields"])
        self.assertIn("launcher", step_forms["operation_call"]["optional_fields"])
        self.assertIn("launcher", step_forms["operation_call"]["deprecated_optional_fields"])

    def test_model_publishes_workflow_input_hint_metadata(self) -> None:
        model = json.loads(self.run_help("model", "--json").stdout)
        input_fields = {item["name"]: item for item in model["workflow"]["inputs_contract"]["declaration_fields"]}

        self.assertEqual(input_fields["hint"]["type"], "string")
        self.assertEqual(input_fields["hint"]["validation_effect"], "none")

    def test_model_publishes_representation_adapter_surface(self) -> None:
        model = json.loads(self.run_help("model", "--json").stdout)
        adapter_surface = model["representation_adapters"]
        key_value = next(item for item in adapter_surface["families"] if item["name"] == "key_value")
        markdown = next(item for item in adapter_surface["families"] if item["name"] == "markdown")
        text = next(item for item in adapter_surface["families"] if item["name"] == "text")

        self.assertEqual(adapter_surface["shared_seam"]["outer_binding_form"], " with{...}")
        self.assertIn("literal separator parameter", key_value["summary"])
        self.assertEqual(key_value["selectors"], [])
        self.assertEqual(key_value["actions"], [])
        self.assertEqual(key_value["shortcuts"], [])
        self.assertIn("prelude", markdown["selectors"])
        self.assertIn('["title"]', markdown["selectors"])
        self.assertIn("add", markdown["actions"])
        self.assertIn("append", markdown["actions"])
        self.assertIn("list", markdown["shortcuts"])
        self.assertIn("prelude", markdown["shortcuts"])
        self.assertIn("lines", text["selectors"])
        self.assertIn('find("literal")', text["selectors"])
        self.assertIn("append", text["actions"])
        self.assertEqual(text["shortcuts"], [])

    def test_model_publishes_local_expression_filter_surface(self) -> None:
        model = json.loads(self.run_help("model", "--json").stdout)
        filters = {item["name"]: item for item in model["local_expressions"]["pipeline_filters"]}

        self.assertIn("lower", filters)
        self.assertIn("field", filters)
        self.assertIn("flatten", filters)
        self.assertIn("first", filters)
        self.assertIn("last", filters)
        self.assertIn("length", filters)
        self.assertIn("unique", filters)
        self.assertIn("is_integer", filters)
        self.assertIn("in", filters)
        self.assertEqual(filters["lower"]["argument_count"], 0)
        self.assertEqual(filters["field"]["argument_count"], 1)
        self.assertEqual(filters["flatten"]["argument_count"], 0)
        self.assertEqual(filters["unique"]["argument_count"], 0)
        self.assertEqual(filters["eq"]["argument_count"], 1)
        self.assertEqual(filters["length"]["output_type"], "number")
        self.assertEqual(filters["is_boolean"]["output_type"], "boolean")
        self.assertEqual(filters["in"]["input_type"], "json")

    def test_model_filter_surface_follows_runtime_registry(self) -> None:
        model = json.loads(self.run_help("model", "--json").stdout)

        self.assertEqual([item["name"] for item in model["local_expressions"]["pipeline_filters"]], list(VALUE_EXPRESSION_FILTERS))

    def test_model_and_capabilities_publish_guard_contract_details(self) -> None:
        model = json.loads(self.run_help("model", "--json").stdout)
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)

        guard_surface = model["workflow"]["surface_constraints"]["guard_expression"]
        capability_guard_surface = next(item for item in capabilities["expression_surfaces"] if item["name"] == "guard_expression")
        negative_rules = {item["name"]: item for item in capabilities["negative_rules"]}

        self.assertEqual(guard_surface["allowed_roots"], ["inputs", "probe", "state"])
        self.assertIn("is_number", guard_surface["allowed_filters"])
        self.assertEqual(guard_surface["allowed_builtins"], ["format", "is_missing", "is_present"])
        self.assertTrue(guard_surface["representation_adapter_policy"]["read_only_allowed"])
        self.assertTrue(guard_surface["representation_adapter_policy"]["write_paths_forbidden"])
        self.assertEqual(guard_surface["representation_adapter_policy"]["forbidden_write_surface"], "->...")
        self.assertEqual(guard_surface["result_contract"]["required_output_type"], "boolean")
        self.assertEqual(capability_guard_surface["builtins"], ["format", "is_missing", "is_present"])
        self.assertIn("in", capability_guard_surface["filters"])
        self.assertEqual(negative_rules["guard_expression.no_adapter_write_path"]["surface"], "guard_expression")
        self.assertEqual(negative_rules["guard_expression.boolean_result_required"]["surface"], "guard_expression")

    def test_capabilities_publish_explicit_non_inference_metadata(self) -> None:
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)
        branching = next(item for item in capabilities["capabilities"] if item["name"] == "workflow.branching")
        launchers = next(item for item in capabilities["capabilities"] if item["name"] == "runtime.launchers")

        self.assertEqual(branching["status"], "supported")
        self.assertEqual(branching["must_not_infer"], [])
        self.assertEqual(launchers["status"], "deprecated")
        self.assertIn("workflow.step.launcher", launchers["related_model_nodes"])
        self.assertTrue(any("preferred" in item for item in launchers["must_not_infer"]))

    def test_describe_resolves_capability_and_model_nodes(self) -> None:
        capability_node = json.loads(self.run_help("describe", "workflow.branching", "--json").stdout)
        model_node = json.loads(self.run_help("describe", "profile.inputs", "--json").stdout)
        input_contract_node = json.loads(self.run_help("describe", "workflow.inputs_contract", "--json").stdout)
        run_contract_node = json.loads(self.run_help("describe", "workflow.run_contract", "--json").stdout)
        command_line_node = json.loads(self.run_help("describe", "command-line.ordo-playbook.flag.input_file", "--json").stdout)
        working_directory_node = json.loads(self.run_help("describe", "playbook.workflows.working_directory", "--json").stdout)
        category_node = json.loads(self.run_help("describe", "playbook.workflows.category", "--json").stdout)
        launcher_node = json.loads(self.run_help("describe", "profile.launchers", "--json").stdout)
        pre_run_node = json.loads(self.run_help("describe", "playbook.pre_run_contract", "--json").stdout)
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
        self.assertEqual(pre_run_node["document_kind"], "model_node")
        self.assertEqual(pre_run_node["name"], "playbook.pre_run_contract")
        self.assertEqual(pre_run_node["metadata"]["effect"], "executes_before_requested_workflow_in_same_runtime_session")
        self.assertEqual(pre_run_node["metadata"]["launch_context_boundary"], "playbook_owned")
        self.assertEqual(command_line_node["document_kind"], "command_line_node")
        self.assertEqual(command_line_node["name"], "command-line.ordo-playbook.flag.input_file")
        self.assertEqual(command_line_node["metadata"]["effect"], "override_input_from_file")
        self.assertEqual(working_directory_node["document_kind"], "model_node")
        self.assertEqual(working_directory_node["name"], "playbook.workflows.working_directory")
        self.assertEqual(working_directory_node["metadata"]["runtime_effect"], "sets_execution_working_directory")
        self.assertEqual(working_directory_node["metadata"]["expression_syntax"], "${...}")
        self.assertEqual(category_node["document_kind"], "model_node")
        self.assertEqual(category_node["name"], "playbook.workflows.category")
        self.assertEqual(category_node["metadata"]["runtime_effect"], "published_metadata_only")
        self.assertEqual(launcher_node["document_kind"], "model_node")
        self.assertEqual(launcher_node["name"], "profile.launchers")
        self.assertEqual(launcher_node["metadata"]["runtime_effect"], "publishes_profile_scoped_launchers")
        self.assertEqual(launcher_node["metadata"]["status"], "deprecated")
        self.assertEqual(missing.returncode, 1)
        self.assertEqual(json.loads(missing.stdout)["status"], "unknown_topic")

    def test_describe_resolves_representation_adapter_model_nodes(self) -> None:
        seam_node = json.loads(self.run_help("describe", "workflow.local_expression.adapter_seam", "--json").stdout)
        key_value_node = json.loads(self.run_help("describe", "workflow.local_expression.adapter.key_value", "--json").stdout)
        markdown_node = json.loads(self.run_help("describe", "workflow.local_expression.adapter.markdown", "--json").stdout)
        text_node = json.loads(self.run_help("describe", "workflow.local_expression.adapter.text", "--json").stdout)

        self.assertEqual(seam_node["document_kind"], "model_node")
        self.assertEqual(seam_node["metadata"]["outer_binding_form"], " with{...}")
        self.assertEqual(key_value_node["metadata"]["name"], "key_value")
        self.assertEqual(key_value_node["metadata"]["selectors"], [])
        self.assertEqual(key_value_node["metadata"]["actions"], [])
        self.assertEqual(markdown_node["metadata"]["name"], "markdown")
        self.assertIn("prelude", markdown_node["metadata"]["selectors"])
        self.assertIn("add", markdown_node["metadata"]["actions"])
        self.assertEqual(text_node["metadata"]["name"], "text")
        self.assertIn("lines", text_node["metadata"]["selectors"])
        self.assertIn("remove", text_node["metadata"]["actions"])

    def test_describe_resolves_local_expression_filter_model_nodes(self) -> None:
        surface_node = json.loads(self.run_help("describe", "workflow.local_expression.filter_surface", "--json").stdout)
        filter_node = json.loads(self.run_help("describe", "workflow.local_expression.filter.is_integer", "--json").stdout)

        self.assertEqual(surface_node["document_kind"], "model_node")
        self.assertTrue(any(item["name"] == "is_integer" for item in surface_node["metadata"]["pipeline_filters"]))
        self.assertEqual(filter_node["metadata"]["name"], "is_integer")
        self.assertEqual(filter_node["metadata"]["argument_count"], 0)
        self.assertEqual(filter_node["metadata"]["output_type"], "boolean")

    def test_search_indexes_representation_adapter_topics(self) -> None:
        result = json.loads(self.run_help("search", "markdown", "--json").stdout)
        key_value_result = json.loads(self.run_help("search", "separator", "--json").stdout)
        text_result = json.loads(self.run_help("search", "text", "--json").stdout)

        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "workflow.local_expression.adapter.markdown" for item in result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "workflow.local_expression.adapter.key_value" for item in key_value_result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "workflow.local_expression.adapter.text" for item in text_result["facts"]))

    def test_search_indexes_local_expression_filter_topics(self) -> None:
        result = json.loads(self.run_help("search", "is_integer", "--json").stdout)
        surface_result = json.loads(self.run_help("search", "pipeline filter", "--json").stdout)

        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "workflow.local_expression.filter.is_integer" for item in result["facts"]))
        self.assertTrue(any(item["kind"] == "model_field" and item["name"] == "workflow.local_expression.filter_surface" for item in surface_result["facts"]))

    def test_search_indexes_workflow_authoring_rules(self) -> None:
        shell_result = json.loads(self.run_help("search", "shell.command", "--json").stdout)
        routine_result = json.loads(self.run_help("search", "routine.*", "--json").stdout)
        guards_result = json.loads(self.run_help("search", "runner", "--json").stdout)
        input_validation_result = json.loads(self.run_help("search", "missing input validation", "--json").stdout)
        adapters_result = json.loads(self.run_help("search", "published results", "--json").stdout)
        publish_result = json.loads(self.run_help("search", "outward-facing contract", "--json").stdout)
        state_result = json.loads(self.run_help("search", "general-purpose cache", "--json").stdout)
        context_result = json.loads(self.run_help("search", "ambient environment requirements", "--json").stdout)
        control_result = json.loads(self.run_help("search", "workflow applicability", "--json").stdout)
        delegated_result = json.loads(self.run_help("search", "downstream action validation", "--json").stdout)
        let_result = json.loads(self.run_help("search", "repetition", "--json").stdout)

        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.shell.command" for item in shell_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.routine.*" for item in routine_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.early_guards" for item in guards_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.input_validation_default" for item in input_validation_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.representation_adapters" for item in adapters_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.publish_outputs" for item in publish_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.lifecycle_state" for item in state_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.explicit_execution_context" for item in context_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.separate_control_surfaces" for item in control_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.delegated_applicability" for item in delegated_result["facts"]))
        self.assertTrue(any(item["kind"] == "workflow_authoring_rule" and item["name"] == "workflow-authoring.early_let" for item in let_result["facts"]))

    def test_workflow_authoring_topic_prioritizes_routine_caution_and_early_guards(self) -> None:
        payload = json.loads(self.run_help("workflow-authoring", "--json").stdout)

        self.assertEqual(payload["document_kind"], "workflow_authoring")
        self.assertEqual(payload["audience"], ["workflow_authors", "agents"])
        self.assertIn("treat semantic ambiguity as a reason to clarify rather than improvise", payload["authoring_heuristic"])
        self.assertIn("when adding or changing inputs, validate them before continuing", payload["authoring_heuristic"])
        self.assertIn("validate both the request shape and the observed target context", payload["authoring_heuristic"])
        self.assertIn("use ordo-playbook check <workflow> during authoring to catch guard and observation gaps early", payload["authoring_heuristic"])
        decision_rule = next(item for item in payload["rules"] if item["name"] == "decision_order")
        structured_rule = next(item for item in payload["rules"] if item["name"] == "structured_surface_bias")
        shell_rule = next(item for item in payload["rules"] if item["name"] == "shell.command")
        routine_rule = next(item for item in payload["rules"] if item["name"] == "routine.*")
        ambiguity_rule = next(item for item in payload["rules"] if item["name"] == "semantic_ambiguity")
        local_rule = next(item for item in payload["rules"] if item["name"] == "local_artifacts_are_context")
        guards_rule = next(item for item in payload["rules"] if item["name"] == "early_guards")
        input_validation_rule = next(item for item in payload["rules"] if item["name"] == "input_validation_default")
        delegated_rule = next(item for item in payload["rules"] if item["name"] == "delegated_applicability")
        adapters_rule = next(item for item in payload["rules"] if item["name"] == "representation_adapters")
        publish_rule = next(item for item in payload["rules"] if item["name"] == "publish_outputs")
        state_rule = next(item for item in payload["rules"] if item["name"] == "lifecycle_state")
        context_rule = next(item for item in payload["rules"] if item["name"] == "explicit_execution_context")
        control_rule = next(item for item in payload["rules"] if item["name"] == "separate_control_surfaces")
        let_rule = next(item for item in payload["rules"] if item["name"] == "early_let")
        guard_result_rule = next(item for item in payload["rules"] if item["name"] == "guard_result_contract")

        self.assertEqual(decision_rule["priority"], "critical_decision_policy")
        self.assertTrue(any("composed" in item for item in decision_rule["prefer"]))
        self.assertEqual(structured_rule["priority"], "strong_recommendation")
        self.assertTrue(any("product terms" in item for item in structured_rule["why"]))
        self.assertEqual(shell_rule["priority"], "critical_caution")
        self.assertEqual(shell_rule["guidance_level"], "forbidden")
        self.assertTrue(any("riskiest" in reason for reason in shell_rule["why"]))
        self.assertTrue(any("legacy" in reason for reason in shell_rule["why"]))
        self.assertTrue(any("routine.<id>" in item for item in shell_rule["prefer"]))
        self.assertTrue(any("legacy shell fallback" in item for item in shell_rule["prefer"]))
        self.assertEqual(
            shell_rule["stop_when"],
            [
                "the proposed authoring change still depends on adding a new shell.command step",
                "the only argument for shell.command is speed, familiarity, or historical precedent",
            ],
        )
        self.assertEqual(routine_rule["priority"], "critical_caution")
        self.assertEqual(routine_rule["guidance_level"], "strong_restriction")
        self.assertTrue(any("project-local semantics" in reason for reason in routine_rule["why"]))
        self.assertTrue(any("exception path" in reason or "exception surface" in routine_rule["rule"] for reason in routine_rule["why"]))
        self.assertTrue(any("capability gap remains" in item for item in routine_rule["prefer"]))
        self.assertTrue(any("remaining gap is semantic" in item for item in routine_rule["prefer"]))
        self.assertTrue(any("connector publication" in item for item in routine_rule["prefer"]))
        self.assertTrue(any("repository-local automation" in item for item in routine_rule["avoid"]))
        self.assertTrue(any("general extension API" in item for item in routine_rule["avoid"]))
        self.assertEqual(
            routine_rule["stop_when"],
            [
                "no explicit capability-gap statement has been made",
                "the remaining gap is semantic rather than mechanical or intentionally project-local",
                "routine.* is being chosen mainly because it is faster, familiar, or already available locally",
                "routine.* is starting to look like the default implementation path rather than a narrow exception",
            ],
        )
        self.assertEqual(ambiguity_rule["priority"], "strong_recommendation")
        self.assertTrue(any("ask" in item for item in ambiguity_rule["prefer"]))
        self.assertEqual(local_rule["priority"], "recommended_caution")
        self.assertEqual(local_rule["guidance_level"], "strong_restriction")
        self.assertTrue(any("public model" in item for item in local_rule["why"] + local_rule["prefer"]))
        self.assertTrue(any("implementation approval" in item for item in local_rule["prefer"]))
        self.assertTrue(any("routine.*" in item for item in local_rule["avoid"]))
        self.assertEqual(
            local_rule["must_not_infer"],
            [
                "there is a script for this => routine.* is acceptable here",
                "the repo already does it this way => this is the correct workflow contract",
                "a local helper covers the semantic gap => no clarification is needed",
            ],
        )
        self.assertEqual(guards_rule["priority"], "critical_applicability_policy")
        self.assertEqual(guards_rule["guidance_level"], "required_default")
        self.assertTrue(any("just a runner" in reason for reason in guards_rule["why"]))
        self.assertTrue(any("phase guards in a stable order" in item and "input validation" in item for item in guards_rule["prefer"]))
        self.assertTrue(any("when adding or changing workflow inputs" in item for item in guards_rule["prefer"]))
        self.assertTrue(any("externally observable fact" in item for item in guards_rule["prefer"]))
        self.assertTrue(any("is_integer" in item and "in(...)" in item for item in guards_rule["prefer"]))
        self.assertTrue(any("check and explain" in item for item in guards_rule["prefer"]))
        self.assertTrue(any("ordo-playbook check <workflow>" in item for item in guards_rule["prefer"]))
        self.assertEqual(input_validation_rule["priority"], "strong_recommendation")
        self.assertEqual(input_validation_rule["guidance_level"], "required_default")
        self.assertTrue(any("pause and decide" in item for item in input_validation_rule["prefer"]))
        self.assertTrue(any("target context" in item for item in input_validation_rule["prefer"]))
        self.assertTrue(any("style references" in item for item in input_validation_rule["prefer"]))
        self.assertTrue(any("type-valid input" in item for item in input_validation_rule["why"]))
        self.assertTrue(any("neighboring workflow" in item for item in input_validation_rule["avoid"]))
        self.assertTrue(any("request-shape validation" in item for item in input_validation_rule["avoid"]))
        self.assertEqual(delegated_rule["priority"], "critical_explainability_policy")
        self.assertEqual(delegated_rule["guidance_level"], "required_default")
        self.assertTrue(any("safety net" in item for item in delegated_rule["prefer"]))
        self.assertTrue(any("capability gap" in item for item in delegated_rule["prefer"]))
        self.assertTrue(any("action preflight" in item for item in delegated_rule["avoid"]))
        self.assertEqual(adapters_rule["priority"], "strong_recommendation")
        self.assertTrue(any("published results" in item for item in adapters_rule["rule"].splitlines() + adapters_rule["why"] + adapters_rule["prefer"]))
        self.assertTrue(any("read-only adapter projections" in item for item in adapters_rule["prefer"]))
        self.assertTrue(any("->..." in item for item in adapters_rule["avoid"]))
        self.assertEqual(publish_rule["priority"], "strong_recommendation")
        self.assertTrue(any("weak outward-facing contract" in item for item in publish_rule["why"] + publish_rule["avoid"]))
        self.assertEqual(state_rule["priority"], "recommended_caution")
        self.assertTrue(any("lifecycle" in item for item in [state_rule["rule"], *state_rule["why"], *state_rule["prefer"]]))
        self.assertEqual(context_rule["priority"], "strong_recommendation")
        self.assertTrue(any("routines" in item for item in context_rule["prefer"]))
        self.assertEqual(control_rule["priority"], "strong_recommendation")
        self.assertTrue(any("step-local" in item for item in control_rule["prefer"]))
        self.assertEqual(let_rule["priority"], "recommended_readability_pattern")
        self.assertEqual(guard_result_rule["priority"], "critical_guard_contract")
        self.assertEqual(guard_result_rule["guidance_level"], "required")
        self.assertTrue(any("non-boolean" in item for item in guard_result_rule["prefer"] + guard_result_rule["avoid"]))

    def test_command_line_topic_publishes_playbook_flags_and_precedence(self) -> None:
        payload = json.loads(self.run_help("command-line", "--json").stdout)

        self.assertEqual(payload["document_kind"], "command_line")
        playbook = next(item for item in payload["commands"] if item["name"] == "ordo-playbook")
        flags = {item["name"]: item for item in playbook["flags"]}
        self.assertEqual(playbook["usage"], "ordo-playbook [--file PATH] [--profile NAME] [--input KEY=VALUE] [--input-file KEY=PATH] [--json] <command>")
        self.assertEqual(playbook["discovery_commands"][0]["name"], "workflows list")
        self.assertEqual(playbook["modes"][0]["name"], "review <workflow>")
        self.assertEqual(playbook["modes"][1]["name"], "check <workflow>")
        self.assertEqual(playbook["run_success_surface"], "successful run emits workflow-local results, may also surface global published values, and may synthesize one top-level fallback result when neither results nor published output were produced")
        self.assertIn("ordo-playbook workflows list", playbook["examples"])
        self.assertIn("ordo-playbook plan inspect-issue", playbook["examples"])
        self.assertNotIn("--workflow", flags)
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

    def test_operation_topic_publishes_narrow_git_commits_boundary(self) -> None:
        payload = json.loads(self.run_help("operation", "git.commits", "--json").stdout)

        self.assertEqual(payload["document_kind"], "operation")
        self.assertEqual(payload["operation"]["inputs"], {"limit": "integer", "rev": "string"})
        self.assertIn("does not expose patch text", payload["operation"]["summary"])
        self.assertEqual(payload["operation"]["outputs"]["items"][0]["text"], "string")
        self.assertEqual(payload["operation"]["outputs"]["items"][0]["author_name"], "string")

    def test_operation_topic_publishes_gh_project_items_examples_and_filter_shape(self) -> None:
        payload = json.loads(self.run_help("operation", "gh.project.items", "--json").stdout)

        self.assertEqual(payload["document_kind"], "operation")
        self.assertEqual(payload["operation"]["inputs"]["content_kind"], "string")
        self.assertEqual(payload["operation"]["inputs"]["filters"][0]["field"], "string")
        self.assertTrue(any(example["reference"] == "gh.project.items" for example in payload["operation"]["examples"]))

    def test_operation_topic_publishes_preflight_observations_for_declaring_action(self) -> None:
        payload = json.loads(self.run_help("operation", "git.sync.push", "--json").stdout)

        self.assertEqual(
            payload["operation"]["preflight_observations"],
            [
                {"probe": "git.branch", "with": {}},
                {"probe": "git.upstream", "with": {}},
                {"probe": "git.range", "with": {"base": "@{upstream}", "head": "{branch}"}},
            ],
        )

    def test_operation_topic_publishes_preflight_observations_for_number_field_setter(self) -> None:
        payload = json.loads(self.run_help("operation", "gh.project.issue.field_number.set", "--json").stdout)

        self.assertEqual(
            payload["operation"]["preflight_observations"],
            [
                {
                    "probe": "gh.project.issue",
                    "with": {
                        "repository": "{repository}",
                        "issue_number": "{issue_number}",
                        "project_id": "{project_id}",
                    },
                    "fields": ["exists"],
                },
                {
                    "probe": "gh.project.field",
                    "with": {"project_id": "{project_id}", "field": "{field}"},
                    "fields": ["exists"],
                },
            ],
        )

    def test_examples_topic_publishes_launcher_step_example(self) -> None:
        payload = json.loads(self.run_help("examples", "--json").stdout)

        self.assertTrue(any(item["name"] == "launcher-step" for item in payload["examples"]))
        launcher_example = next(item for item in payload["examples"] if item["name"] == "launcher-step")
        self.assertEqual(launcher_example["status"], "legacy_compatibility_example")
        self.assertTrue(any(item["name"] == "text-adapter" for item in payload["examples"]))
        self.assertTrue(any(item["name"] == "project-items-let" for item in payload["examples"]))

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
