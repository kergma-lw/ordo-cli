import unittest

from ordo.introspection import describe_operations, describe_system


class IntrospectionSystemTest(unittest.TestCase):
    def test_describe_operations_returns_public_connector_contract(self) -> None:
        operations = describe_operations()

        self.assertEqual([connector["namespace"] for connector in operations["connectors"]], ["git", "gh", "shell"])
        self.assertIn("issue", {operation["name"] for operation in operations["connectors"][1]["operations"]})

    def test_describe_system_exposes_root_discovery_and_operations(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["entrypoint"], "describe_system")
        self.assertEqual(payload["sections"]["discovery"]["sections"]["operations"]["producer"], "describe_operations")
        self.assertEqual(payload["sections"]["operations"], describe_operations())


if __name__ == "__main__":
    unittest.main()
