import unittest

from ordo.connectors import get_public_connector_registry


class ConnectorRegistryTest(unittest.TestCase):
    def test_registry_exposes_fixed_v0_connector_families(self) -> None:
        registry = get_public_connector_registry()

        self.assertEqual(
            tuple(connector.namespace for connector in registry.list_connectors()),
            ("git", "gh", "shell"),
        )

    def test_registry_exposes_discoverable_operation_metadata(self) -> None:
        registry = get_public_connector_registry()

        operation = registry.get_operation("gh.issue")

        self.assertIsNotNone(operation)
        self.assertEqual(operation.kind, "probe")
        self.assertEqual(operation.inputs["issue"], "string")
        self.assertEqual(operation.outputs["state"], "string")
        self.assertIn("issue_not_found", operation.failure_modes)

        project_issue = registry.get_operation("gh.project.issue")
        self.assertIsNotNone(project_issue)
        self.assertEqual(project_issue.kind, "probe")
        self.assertEqual(project_issue.inputs["project"], "string")
        self.assertEqual(project_issue.outputs["exists"], "boolean")
        self.assertIn("project_not_found", project_issue.failure_modes)

    def test_registry_contract_is_public_json_shaped_surface(self) -> None:
        registry = get_public_connector_registry()

        contract = registry.to_contract()

        self.assertEqual(contract["connectors"][0]["namespace"], "git")
        self.assertIn(
            "issue",
            {operation["name"] for operation in contract["connectors"][1]["operations"]},
        )
        self.assertIn(
            "project.issue",
            {operation["name"] for operation in contract["connectors"][1]["operations"]},
        )
        self.assertNotIn(
            "issue.view",
            {operation["name"] for operation in contract["connectors"][1]["operations"]},
        )
        self.assertIn(
            "action",
            {operation["kind"] for operation in contract["connectors"][2]["operations"]},
        )


if __name__ == "__main__":
    unittest.main()
