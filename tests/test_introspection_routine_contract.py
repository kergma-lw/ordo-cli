import unittest

from ordo.introspection import describe_routine_contract, describe_system


class IntrospectionRoutineContractTest(unittest.TestCase):
    def test_routine_contract_publishes_discovery_and_entry_fields(self) -> None:
        payload = describe_routine_contract()

        self.assertEqual(payload["discovery"]["path"], ".ordo/routines.yaml")
        self.assertEqual(payload["authoring_status"], "exception_path")
        self.assertEqual(payload["authoring_guidance"]["default_recommendation"], "avoid_by_default")
        self.assertTrue(payload["authoring_guidance"]["not_a_connector_family"])
        top_level_fields = {field["name"] for field in payload["top_level_fields"]}
        routine_entry_fields = {field["name"] for field in payload["routine_entry_fields"]}
        self.assertEqual(top_level_fields, {"version", "routines"})
        self.assertIn("kind", routine_entry_fields)
        self.assertIn("implementation", routine_entry_fields)
        self.assertIn("failure_modes", routine_entry_fields)
        workflow_call_fields = {field["name"] for field in payload["workflow_call_surface"]["fields"]}
        self.assertEqual(workflow_call_fields, {"args", "env"})
        self.assertFalse(payload["workflow_call_surface"]["automatic_input_env_projection"])
        self.assertEqual(payload["workflow_call_surface"]["env_reference_roots"], ["inputs", "step", "state"])
        self.assertEqual(payload["workflow_call_surface"]["generated_env_name_prefix"], "ORDO_")
        self.assertTrue(payload["workflow_call_surface"]["env_scalar_only"])
        self.assertEqual(payload["workflow_call_surface"]["generated_env_name_examples"]["inputs.profile"], "ORDO_INPUTS_PROFILE")
        self.assertEqual(
            payload["workflow_call_surface"]["generated_env_name_examples"]["step.collect.outputs.value.path"],
            "ORDO_STEP_COLLECT_OUTPUTS_VALUE_PATH",
        )
        implementation_argv = next(field for field in payload["implementation_fields"] if field["name"] == "argv")
        self.assertEqual(implementation_argv["authoring_status"], "bounded_execution_only")

    def test_root_introspection_publishes_routine_contract_section(self) -> None:
        payload = describe_system()

        self.assertIn("routine_contract", payload["sections"])
        self.assertEqual(payload["sections"]["discovery"]["sections"]["routine_contract"]["producer"], "describe_routine_contract")


if __name__ == "__main__":
    unittest.main()
