import unittest

from ordo.introspection import describe_state_contract, describe_system
from ordo.model.state_contract import STATE_CONTRACT
from ordo.playbook import PLAYBOOK_ALLOWED_FIELDS
from ordo.runtime.state import STATE_FILE_VERSION
from ordo.runtime.state_paths import parse_state_path


class IntrospectionStateContractTest(unittest.TestCase):
    def test_state_contract_publishes_path_and_storage_rules(self) -> None:
        payload = describe_state_contract()

        self.assertEqual(payload["path_forms"]["shape"], "state.<role>[inputs.<key>][.<field>...]")
        self.assertEqual(payload["storage_document"]["required_fields"], ["version", "values"])
        self.assertIn("state role must be bound before runtime access", payload["runtime_rules"])

    def test_state_contract_stays_aligned_with_runtime_constants(self) -> None:
        payload = describe_state_contract()

        parsed = parse_state_path("state.task_memory[inputs.issue_ref].branch")
        self.assertEqual(payload["path_forms"]["root"], "state")
        self.assertEqual(payload["storage_document"]["version"], STATE_FILE_VERSION)
        self.assertEqual(parsed.state_role, "task_memory")
        self.assertIn("states", PLAYBOOK_ALLOWED_FIELDS)
        self.assertEqual(payload, STATE_CONTRACT)

    def test_root_introspection_publishes_state_contract_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["state_contract"]["producer"], "describe_state_contract")
        self.assertIn("state_contract", payload["sections"])


if __name__ == "__main__":
    unittest.main()
