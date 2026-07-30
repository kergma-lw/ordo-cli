import unittest

from ordo.introspection import describe_system, describe_workflow_contract
from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_FILTERS
from ordo.runtime.validation import STEP_ALLOWED_FIELDS, WORKFLOW_ALLOWED_FIELDS


class IntrospectionWorkflowContractTest(unittest.TestCase):
    def test_workflow_contract_publishes_top_level_fields_and_step_forms(self) -> None:
        payload = describe_workflow_contract()

        field_names = {field["name"] for field in payload["top_level_fields"]}
        step_forms = {item["name"]: item for item in payload["step_forms"]}
        step_rules = {item["name"]: item for item in payload["step_form_rules"]}
        self.assertEqual(field_names, {"version", "workflow", "inputs", "let", "state_needs", "blocks"})
        self.assertEqual(step_forms["run_invocation"]["required_fields"], ["name", "run"])
        self.assertIn("for_each", step_forms["run_invocation"]["optional_fields"])
        self.assertIn("register", step_forms["run_invocation"]["optional_fields"])
        self.assertEqual(step_forms["inline_fan_out_invocation"]["required_fields"], ["name", "for_each", "steps"])
        self.assertEqual(step_forms["profile_switch"]["required_fields"], ["name", "profile_switch"])
        self.assertEqual(step_forms["value"]["required_fields"], ["name", "value"])
        self.assertEqual(step_forms["result"]["required_fields"], ["name", "result"])
        self.assertEqual(step_forms["publish"]["required_fields"], ["name", "publish"])
        self.assertEqual(step_forms["state_set"]["required_fields"], ["name", "state_set"])
        self.assertEqual(step_forms["state_delete"]["required_fields"], ["name", "state_delete"])
        self.assertEqual(step_rules["exactly_one_step_form"]["fields"], ["uses", "run", "steps", "profile_switch", "value", "result", "publish", "state_set", "state_delete"])
        guard_surface = payload["surface_constraints"]["guard_expression"]
        self.assertIn("state", guard_surface["allowed_roots"])
        self.assertIn("is_number", guard_surface["allowed_filters"])
        self.assertEqual(guard_surface["allowed_builtins"], ["format", "is_missing", "is_present"])
        self.assertTrue(guard_surface["representation_adapter_policy"]["read_only_allowed"])
        self.assertTrue(guard_surface["representation_adapter_policy"]["write_paths_forbidden"])
        self.assertEqual(guard_surface["representation_adapter_policy"]["forbidden_write_surface"], "->...")
        self.assertEqual(guard_surface["result_contract"]["required_output_type"], "boolean")
        self.assertEqual(guard_surface["result_contract"]["non_boolean_result"], "error")
        self.assertTrue(payload["inputs_contract"]["declared_keys_required_at_activation"])
        input_fields = {item["name"]: item for item in payload["inputs_contract"]["declaration_fields"]}
        self.assertEqual(input_fields["hint"]["validation_effect"], "none")
        self.assertEqual(payload["include_contract"]["search_order"][0], "including_file_dir")
        self.assertEqual(payload["include_contract"]["fragment_argument_declaration_forms"][0]["name"], "required_short_form")
        self.assertTrue(payload["include_contract"]["fragment_argument_default_semantics"]["default_null_is_valid"])
        self.assertEqual(payload["run_contract"]["directive_field"], "run")
        self.assertIn("step", payload["run_contract"]["caller_scoped_condition_surface"])
        self.assertEqual(payload["run_contract"]["body_forms"], ["named_run_target", "inline_repeated_steps"])

    def test_workflow_contract_stays_aligned_with_validator_field_sets(self) -> None:
        payload = describe_workflow_contract()

        field_names = {field["name"] for field in payload["top_level_fields"]}
        step_fields: set[str] = set()
        for form in payload["step_forms"]:
            step_fields.update(form["required_fields"])
            step_fields.update(form["optional_fields"])
        self.assertEqual(field_names, set(WORKFLOW_ALLOWED_FIELDS))
        self.assertEqual(step_fields | {"__run_path__"}, set(STEP_ALLOWED_FIELDS))

    def test_workflow_contract_filter_lists_follow_runtime_registry(self) -> None:
        payload = describe_workflow_contract()
        published_filters = list(VALUE_EXPRESSION_FILTERS)

        self.assertEqual(payload["surface_constraints"]["guard_expression"]["allowed_filters"], published_filters)
        self.assertEqual(payload["surface_constraints"]["runtime_value_surface"]["allowed_filters"], published_filters)

    def test_root_introspection_publishes_workflow_contract_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["workflow_contract"]["producer"], "describe_workflow_contract")
        self.assertIn("workflow_contract", payload["sections"])


if __name__ == "__main__":
    unittest.main()
