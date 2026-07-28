import unittest

from ordo.introspection import describe_routine_contract, describe_system


class IntrospectionRoutineContractTest(unittest.TestCase):
    def test_routine_contract_publishes_discovery_and_entry_fields(self) -> None:
        payload = describe_routine_contract()

        self.assertEqual(payload["discovery"]["path"], ".ordo/routines.yaml")
        top_level_fields = {field["name"] for field in payload["top_level_fields"]}
        routine_entry_fields = {field["name"] for field in payload["routine_entry_fields"]}
        self.assertEqual(top_level_fields, {"version", "routines"})
        self.assertIn("kind", routine_entry_fields)
        self.assertIn("implementation", routine_entry_fields)
        self.assertIn("failure_modes", routine_entry_fields)

    def test_root_introspection_publishes_routine_contract_section(self) -> None:
        payload = describe_system()

        self.assertIn("routine_contract", payload["sections"])
        self.assertEqual(payload["sections"]["discovery"]["sections"]["routine_contract"]["producer"], "describe_routine_contract")


if __name__ == "__main__":
    unittest.main()
