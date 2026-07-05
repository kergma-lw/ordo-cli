import unittest

from ordo.introspection import describe_system, describe_workflow_contract
from ordo.runtime.validation import STEP_ALLOWED_FIELDS, WORKFLOW_ALLOWED_FIELDS


class IntrospectionWorkflowContractTest(unittest.TestCase):
    def test_workflow_contract_publishes_top_level_fields_and_step_forms(self) -> None:
        payload = describe_workflow_contract()

        field_names = {field["name"] for field in payload["top_level_fields"]}
        step_forms = {item["name"]: item for item in payload["step_forms"]}
        step_rules = {item["name"]: item for item in payload["step_form_rules"]}
        self.assertEqual(field_names, {"version", "workflow", "inputs", "state_needs", "blocks"})
        self.assertEqual(step_forms["value"]["required_fields"], ["name", "value"])
        self.assertEqual(step_forms["state_set"]["required_fields"], ["name", "state_set"])
        self.assertEqual(step_forms["state_delete"]["required_fields"], ["name", "state_delete"])
        self.assertEqual(step_rules["exactly_one_step_form"]["fields"], ["uses", "value", "state_set", "state_delete"])
        self.assertIn("state_references", payload["surface_constraints"]["guard_expression"]["forbidden_features"])

    def test_workflow_contract_stays_aligned_with_validator_field_sets(self) -> None:
        payload = describe_workflow_contract()

        field_names = {field["name"] for field in payload["top_level_fields"]}
        step_fields: set[str] = set()
        for form in payload["step_forms"]:
            step_fields.update(form["required_fields"])
            step_fields.update(form["optional_fields"])
        self.assertEqual(field_names, set(WORKFLOW_ALLOWED_FIELDS))
        self.assertEqual(step_fields, set(STEP_ALLOWED_FIELDS))

    def test_root_introspection_publishes_workflow_contract_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["workflow_contract"]["producer"], "describe_workflow_contract")
        self.assertIn("workflow_contract", payload["sections"])


if __name__ == "__main__":
    unittest.main()
