import unittest

from ordo.model.playbook_contract import PLAYBOOK_CONTRACT
from ordo.model.profile_contract import PROFILE_CONTRACT
from ordo.model.workflow_contract import WORKFLOW_CONTRACT
from ordo.playbook import (
    DEFAULTS_ALLOWED_FIELDS,
    PLAYBOOK_ALLOWED_FIELDS,
    PLAYBOOK_DISCOVERY_PATH,
    PLAYBOOK_VERSION,
    PROFILE_ENTRY_ALLOWED_FIELDS,
    STATE_ENTRY_ALLOWED_FIELDS,
    WORKFLOW_ENTRY_ALLOWED_FIELDS,
)
from ordo.runtime.validation import OVERRIDE_ALLOWED_FIELDS, PROFILE_ALLOWED_FIELDS, STEP_ALLOWED_FIELDS, WORKFLOW_ALLOWED_FIELDS


def _field_names(items):
    return {item["name"] for item in items}


class ContractValidationAlignmentTest(unittest.TestCase):
    def test_workflow_validation_fields_derive_from_canonical_contract(self) -> None:
        self.assertEqual(set(WORKFLOW_ALLOWED_FIELDS), _field_names(WORKFLOW_CONTRACT["top_level_fields"]))
        step_fields = set().union(*(set(form["required_fields"]) | set(form["optional_fields"]) for form in WORKFLOW_CONTRACT["step_forms"]))
        self.assertEqual(set(STEP_ALLOWED_FIELDS), step_fields)

    def test_profile_validation_fields_derive_from_canonical_contract(self) -> None:
        self.assertEqual(set(PROFILE_ALLOWED_FIELDS), _field_names(PROFILE_CONTRACT["top_level_fields"]))
        self.assertEqual(set(OVERRIDE_ALLOWED_FIELDS), _field_names(PROFILE_CONTRACT["override_fields"]))

    def test_playbook_surface_constants_derive_from_canonical_contract(self) -> None:
        self.assertEqual(PLAYBOOK_VERSION, PLAYBOOK_CONTRACT["version"])
        self.assertEqual(PLAYBOOK_DISCOVERY_PATH, PLAYBOOK_CONTRACT["discovery"]["path"])
        self.assertEqual(set(PLAYBOOK_ALLOWED_FIELDS), _field_names(PLAYBOOK_CONTRACT["top_level_fields"]))
        self.assertEqual(set(DEFAULTS_ALLOWED_FIELDS), _field_names(PLAYBOOK_CONTRACT["defaults_fields"]))
        self.assertEqual(set(PROFILE_ENTRY_ALLOWED_FIELDS), _field_names(PLAYBOOK_CONTRACT["profile_entry_fields"]))
        self.assertEqual(set(STATE_ENTRY_ALLOWED_FIELDS), _field_names(PLAYBOOK_CONTRACT["state_entry_fields"]))
        self.assertEqual(set(WORKFLOW_ENTRY_ALLOWED_FIELDS), _field_names(PLAYBOOK_CONTRACT["workflow_entry_fields"]))


if __name__ == "__main__":
    unittest.main()
