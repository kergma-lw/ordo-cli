import unittest

from ordo.introspection import describe_profile_contract, describe_system
from ordo.model.profile_contract import PROFILE_CONTRACT
from ordo.runtime.validation import OVERRIDE_ALLOWED_FIELDS, PROFILE_ALLOWED_FIELDS


class IntrospectionProfileContractTest(unittest.TestCase):
    def test_profile_contract_publishes_fields_and_semantics(self) -> None:
        payload = describe_profile_contract()

        field_names = {field["name"] for field in payload["top_level_fields"]}
        override_fields = {field["name"] for field in payload["override_fields"]}
        self.assertEqual(field_names, {"name", "inputs", "checks", "overrides"})
        self.assertEqual(override_fields, {"target", "with", "reason"})
        self.assertIn("first-writer wins", payload["compose_semantics"]["inputs"])
        self.assertIn("may add missing workflow inputs", payload["workflow_apply_semantics"]["inputs"])

    def test_profile_contract_stays_aligned_with_validation_field_sets(self) -> None:
        payload = describe_profile_contract()

        self.assertEqual({field["name"] for field in payload["top_level_fields"]}, set(PROFILE_ALLOWED_FIELDS))
        self.assertEqual({field["name"] for field in payload["override_fields"]}, set(OVERRIDE_ALLOWED_FIELDS))
        self.assertEqual(payload, PROFILE_CONTRACT)

    def test_root_introspection_publishes_profile_contract_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["profile_contract"]["producer"], "describe_profile_contract")
        self.assertIn("profile_contract", payload["sections"])


if __name__ == "__main__":
    unittest.main()
