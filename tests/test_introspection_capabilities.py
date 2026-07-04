import unittest

from ordo.introspection import describe_capabilities, describe_system


class IntrospectionCapabilitiesTest(unittest.TestCase):
    def test_describe_capabilities_publishes_runtime_capability_states(self) -> None:
        payload = describe_capabilities()

        capabilities = {item["name"]: item for item in payload["capabilities"]}
        self.assertEqual(capabilities["workflow.value_expressions"]["status"], "supported")
        self.assertEqual(capabilities["workflow.step.condition"]["status"], "unsupported")
        self.assertEqual(capabilities["workflow.step.register"]["status"], "supported")

    def test_describe_capabilities_publishes_expression_roots_and_surfaces(self) -> None:
        payload = describe_capabilities()

        roots = {item["name"]: item for item in payload["expression_roots"]}
        surfaces = {item["name"]: item for item in payload["expression_surfaces"]}
        self.assertIn("value_expression", roots["state"]["surfaces"])
        self.assertIn("value_expression", roots["step"]["surfaces"])
        self.assertEqual(surfaces["value_expression"]["filters"], ["lower", "trim", "slug"])
        self.assertEqual(surfaces["value_expression"]["builtins"], ["format"])
        self.assertIn("step", surfaces["value_expression"]["roots"])

    def test_describe_capabilities_publishes_high_value_negative_rules(self) -> None:
        payload = describe_capabilities()

        rules = {item["name"]: item for item in payload["negative_rules"]}
        self.assertEqual(rules["guard_expression.no_state_root"]["surface"], "guard_expression")
        self.assertEqual(rules["workflow_step.with_requires_uses"]["related_codes"], ["validation.workflow.step.with_without_uses"])
        self.assertEqual(rules["guard_expression.no_step_root"]["related_codes"], ["validation.workflow.guard_expr.step_ref"])
        self.assertEqual(rules["value_expression.step_refs_must_be_backward"]["related_codes"], ["validation.workflow.step_ref.forward"])
        self.assertEqual(rules["format_value.args_must_be_list"]["related_codes"], ["validation.workflow.value_expr.format.args_type"])

    def test_root_introspection_publishes_capabilities_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["capabilities"]["producer"], "describe_capabilities")
        self.assertIn("capabilities", payload["sections"])


if __name__ == "__main__":
    unittest.main()
