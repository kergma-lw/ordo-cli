import unittest

from ordo.runtime.local_expression_contexts import (
    LocalExpressionContext,
    LocalExpressionContextFamily,
    LocalExpressionRoot,
    get_local_expression_context_policy,
)
from ordo.runtime.local_expressions import (
    extract_embedded_local_expression,
    parse_embedded_local_expression,
    parse_local_expression,
    validate_parsed_local_expression,
)


class LocalExpressionContextsTest(unittest.TestCase):
    def test_guard_context_is_launch_time_known_and_disallows_step(self) -> None:
        policy = get_local_expression_context_policy(LocalExpressionContext.GUARD)

        self.assertEqual(policy.family, LocalExpressionContextFamily.CONDITION)
        self.assertTrue(policy.native_surface)
        self.assertTrue(policy.launch_time_known_only)
        self.assertTrue(policy.allows_root(LocalExpressionRoot.INPUTS))
        self.assertTrue(policy.allows_root(LocalExpressionRoot.ARGS))
        self.assertTrue(policy.allows_root(LocalExpressionRoot.STATE))
        self.assertFalse(policy.allows_root(LocalExpressionRoot.STEP))

    def test_step_condition_context_allows_step(self) -> None:
        policy = get_local_expression_context_policy(LocalExpressionContext.STEP_CONDITION)

        self.assertEqual(policy.family, LocalExpressionContextFamily.CONDITION)
        self.assertFalse(policy.launch_time_known_only)
        self.assertTrue(policy.allows_root(LocalExpressionRoot.STEP))

    def test_include_binding_context_is_value_oriented_caller_scope_policy(self) -> None:
        policy = get_local_expression_context_policy(LocalExpressionContext.INCLUDE_BINDING)

        self.assertEqual(policy.family, LocalExpressionContextFamily.VALUE)
        self.assertFalse(policy.native_surface)
        self.assertFalse(policy.allows_root(LocalExpressionRoot.ARGS))
        self.assertTrue(policy.allows_root(LocalExpressionRoot.INPUTS))
        self.assertTrue(policy.allows_root(LocalExpressionRoot.STATE))
        self.assertTrue(policy.allows_root(LocalExpressionRoot.STEP))

    def test_all_contexts_apply_restrictions_to_whole_tree(self) -> None:
        for context in LocalExpressionContext:
            with self.subTest(context=context):
                policy = get_local_expression_context_policy(context)
                self.assertTrue(policy.whole_tree_restrictions)
                self.assertTrue(policy.pure_only)
                self.assertTrue(policy.hidden_control_forbidden)

    def test_guard_context_uses_shared_local_expression_entrypoint(self) -> None:
        parsed = parse_local_expression("git.worktree.clean and inputs.force", context=LocalExpressionContext.GUARD)

        self.assertEqual(parsed.context, LocalExpressionContext.GUARD)
        self.assertIsNotNone(parsed.guard)
        self.assertEqual(validate_parsed_local_expression(parsed), ())

    def test_step_condition_uses_shared_embedded_local_expression_entrypoint(self) -> None:
        parsed = parse_embedded_local_expression("${step.issue.outputs.open and inputs.enabled}", context=LocalExpressionContext.STEP_CONDITION)

        assert parsed is not None
        self.assertEqual(parsed.context, LocalExpressionContext.STEP_CONDITION)
        self.assertIsNotNone(parsed.value)
        self.assertEqual(extract_embedded_local_expression("${inputs.enabled}"), "inputs.enabled")
