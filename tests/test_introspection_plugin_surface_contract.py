import unittest

from ordo.introspection import describe_plugin_surface_contract, describe_system
from ordo.model.plugin_surface_contract import PLUGIN_SURFACE_CONTRACT


class IntrospectionPluginSurfaceContractTest(unittest.TestCase):
    def test_plugin_surface_contract_publishes_required_metadata_boundary(self) -> None:
        payload = describe_plugin_surface_contract()

        self.assertEqual(payload["connector_requirements"]["required_fields"], ["namespace", "bootstrap", "operations"])
        self.assertIn("summary", payload["operation_requirements"]["required_fields"])
        self.assertIn("preflight_observations", payload["operation_requirements"]["required_fields"])
        self.assertFalse(payload["participation_rules"]["special_case_help_logic_required"])

    def test_plugin_surface_contract_matches_published_contract(self) -> None:
        payload = describe_plugin_surface_contract()

        self.assertEqual(payload, PLUGIN_SURFACE_CONTRACT)
        self.assertEqual(payload["document_kind"], "plugin_surface_contract")

    def test_root_introspection_publishes_plugin_surface_contract_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["plugin_surface_contract"]["producer"], "describe_plugin_surface_contract")
        self.assertIn("plugin_surface_contract", payload["sections"])


if __name__ == "__main__":
    unittest.main()
