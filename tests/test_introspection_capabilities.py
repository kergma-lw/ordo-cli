import unittest

from ordo.introspection import describe_capabilities, describe_system
from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_FILTERS


class IntrospectionCapabilitiesTest(unittest.TestCase):
    def test_describe_capabilities_publishes_runtime_capability_states(self) -> None:
        payload = describe_capabilities()

        capabilities = {item["name"]: item for item in payload["capabilities"]}
        self.assertEqual(capabilities["workflow.local_expressions"]["status"], "supported")
        self.assertEqual(capabilities["workflow.step.condition"]["status"], "supported")
        self.assertEqual(capabilities["workflow.step.register"]["status"], "supported")
        self.assertEqual(capabilities["workflow.step.value"]["status"], "supported")
        self.assertEqual(capabilities["workflow.branching"]["status"], "supported")

    def test_describe_capabilities_publishes_expression_roots_and_surfaces(self) -> None:
        payload = describe_capabilities()

        roots = {item["name"]: item for item in payload["expression_roots"]}
        surfaces = {item["name"]: item for item in payload["expression_surfaces"]}
        self.assertIn("guard_expression", roots["state"]["surfaces"])
        self.assertIn("step_condition", roots["probe"]["surfaces"])
        self.assertIn("embedded_value_expression", roots["state"]["surfaces"])
        self.assertIn("embedded_value_expression", roots["step"]["surfaces"])
        self.assertIn("probe", surfaces["step_condition"]["roots"])
        self.assertEqual(surfaces["guard_expression"]["filters"], ["lower", "trim", "slug", "eq", "ne", "not", "is_string", "is_number", "is_integer", "is_boolean", "in", "field", "lookup", "only", "flatten", "first", "last", "length", "unique", "catch", "not_found"])
        self.assertEqual(surfaces["guard_expression"]["builtins"], ["format", "is_missing", "is_present"])
        self.assertEqual(surfaces["step_condition"]["filters"], ["lower", "trim", "slug", "eq", "ne", "not", "is_string", "is_number", "is_integer", "is_boolean", "in", "field", "lookup", "only", "flatten", "first", "last", "length", "unique", "catch", "not_found"])
        self.assertEqual(surfaces["step_condition"]["builtins"], ["format", "is_missing", "is_present"])
        self.assertEqual(surfaces["embedded_value_expression"]["filters"], ["lower", "trim", "slug", "eq", "ne", "not", "is_string", "is_number", "is_integer", "is_boolean", "in", "field", "lookup", "only", "flatten", "first", "last", "length", "unique", "catch", "not_found"])
        self.assertEqual(surfaces["embedded_value_expression"]["builtins"], ["format", "is_missing", "is_present"])
        self.assertEqual(surfaces["embedded_value_expression"]["boolean_operators"], ["and", "or", "not", "parentheses"])
        self.assertEqual(surfaces["guard_expression"]["boolean_operators"], ["and", "or", "not", "parentheses"])
        self.assertIn("step", surfaces["embedded_value_expression"]["roots"])

    def test_capability_filter_lists_follow_runtime_registry(self) -> None:
        payload = describe_capabilities()
        surfaces = {item["name"]: item for item in payload["expression_surfaces"]}
        published_filters = list(VALUE_EXPRESSION_FILTERS)

        self.assertEqual(surfaces["guard_expression"]["filters"], published_filters)
        self.assertEqual(surfaces["step_condition"]["filters"], published_filters)
        self.assertEqual(surfaces["embedded_value_expression"]["filters"], published_filters)

    def test_describe_capabilities_publishes_high_value_negative_rules(self) -> None:
        payload = describe_capabilities()

        rules = {item["name"]: item for item in payload["negative_rules"]}
        self.assertEqual(rules["workflow_step.with_requires_uses"]["related_codes"], ["validation.workflow.step.with_without_uses"])
        self.assertEqual(rules["workflow_step.if_conflicts_with_register"]["related_codes"], ["validation.workflow.step.if_with_register"])
        self.assertEqual(rules["guard_expression.no_step_root"]["related_codes"], ["validation.workflow.local_expression.guard.step_ref"])
        self.assertEqual(rules["guard_expression.no_adapter_write_path"]["surface"], "guard_expression")
        self.assertEqual(rules["guard_expression.boolean_result_required"]["surface"], "guard_expression")
        self.assertEqual(rules["embedded_value_expression.step_refs_must_be_backward"]["related_codes"], ["validation.workflow.step_ref.forward"])
        self.assertEqual(rules["workflow_fragment.no_state_surface"]["related_codes"], ["load.workflow.include.state_forbidden"])
        self.assertEqual(rules["workflow_state_role.write_after_last_read"]["related_codes"], ["validation.workflow.state_role.write_before_last_read"])
        self.assertEqual(rules["format_value.args_must_be_list"]["related_codes"], ["validation.workflow.value_expr.format.args_type"])

    def test_root_introspection_publishes_capabilities_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["capabilities"]["producer"], "describe_capabilities")
        self.assertIn("capabilities", payload["sections"])


if __name__ == "__main__":
    unittest.main()
