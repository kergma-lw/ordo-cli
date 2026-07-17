import unittest

from ordo.introspection import describe_profile_contract, describe_system
from ordo.model.profile_contract import PROFILE_CONTRACT
from ordo.runtime.validation import LAUNCHER_ALLOWED_FIELDS, OVERRIDE_ALLOWED_FIELDS, PROFILE_ALLOWED_FIELDS


class IntrospectionProfileContractTest(unittest.TestCase):
    def test_profile_contract_publishes_fields_and_semantics(self) -> None:
        payload = describe_profile_contract()

        field_names = {field["name"] for field in payload["top_level_fields"]}
        override_fields = {field["name"] for field in payload["override_fields"]}
        launcher_fields = {field["name"] for field in payload["launcher_fields"]}
        self.assertEqual(field_names, {"name", "inputs", "working_directory", "checks", "overrides", "launchers"})
        self.assertEqual(override_fields, {"target", "with", "reason"})
        self.assertEqual(launcher_fields, {"file", "connector", "before", "after"})
        self.assertEqual(payload["compose_semantics"]["inputs"]["strategy"], "first_writer_wins")
        self.assertEqual(payload["compose_semantics"]["overrides"]["conflict"], "validation_error")
        self.assertEqual(payload["compose_semantics"]["launchers"]["conflict"], "validation_error")
        self.assertTrue(payload["workflow_apply_semantics"]["inputs"]["may_add_missing"])
        self.assertFalse(payload["workflow_apply_semantics"]["inputs"]["may_override_explicit_workflow_values"])

    def test_profile_contract_stays_aligned_with_validation_field_sets(self) -> None:
        payload = describe_profile_contract()

        self.assertEqual({field["name"] for field in payload["top_level_fields"]}, set(PROFILE_ALLOWED_FIELDS))
        self.assertEqual({field["name"] for field in payload["override_fields"]}, set(OVERRIDE_ALLOWED_FIELDS))
        self.assertEqual({field["name"] for field in payload["launcher_fields"]}, set(LAUNCHER_ALLOWED_FIELDS))
        self.assertEqual(payload, PROFILE_CONTRACT)

    def test_root_introspection_publishes_profile_contract_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["profile_contract"]["producer"], "describe_profile_contract")
        self.assertIn("profile_contract", payload["sections"])


if __name__ == "__main__":
    unittest.main()
