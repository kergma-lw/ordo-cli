import unittest

from ordo.introspection import describe_playbook_contract, describe_system
from ordo.playbook import PLAYBOOK_ALLOWED_FIELDS, PLAYBOOK_DISCOVERY_PATH, WORKFLOW_ENTRY_ALLOWED_FIELDS


class IntrospectionPlaybookContractTest(unittest.TestCase):
    def test_playbook_contract_publishes_discovery_and_entry_fields(self) -> None:
        payload = describe_playbook_contract()

        self.assertEqual(payload["discovery"]["path"], ".ordo/playbook.yml")
        workflow_entry_fields = {field["name"] for field in payload["workflow_entry_fields"]}
        self.assertEqual(workflow_entry_fields, {"file", "working_directory", "state_bindings"})
        working_directory = next(field for field in payload["workflow_entry_fields"] if field["name"] == "working_directory")
        self.assertEqual(working_directory["runtime_effect"], "sets_execution_working_directory")
        self.assertEqual(working_directory["resolution_base"], "playbook_dir")
        self.assertEqual(working_directory["expression_syntax"], "${...}")
        self.assertEqual(working_directory["expression_surface"], "activation_input_value_expression")
        self.assertEqual(working_directory["expression_allowed_roots"], ["inputs"])
        self.assertEqual(working_directory["expression_forbidden_roots"], ["state", "step"])
        self.assertEqual(payload["activation_semantics"]["discovery"]["missing"], "playbook.discovery.missing")
        self.assertIn("working_directory", payload["activation_semantics"]["workflow_entries"]["optional"])
        self.assertEqual(payload["activation_semantics"]["state_entries"]["requires"], ["path"])

    def test_playbook_contract_stays_aligned_with_playbook_surface_constants(self) -> None:
        payload = describe_playbook_contract()

        top_level_fields = {field["name"] for field in payload["top_level_fields"]}
        workflow_entry_fields = {field["name"] for field in payload["workflow_entry_fields"]}
        self.assertEqual(payload["discovery"]["path"], PLAYBOOK_DISCOVERY_PATH)
        self.assertEqual(top_level_fields, set(PLAYBOOK_ALLOWED_FIELDS))
        self.assertEqual(workflow_entry_fields, set(WORKFLOW_ENTRY_ALLOWED_FIELDS))

    def test_root_introspection_publishes_playbook_contract_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["playbook_contract"]["producer"], "describe_playbook_contract")
        self.assertIn("playbook_contract", payload["sections"])


if __name__ == "__main__":
    unittest.main()
