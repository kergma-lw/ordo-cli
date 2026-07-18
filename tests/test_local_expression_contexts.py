import unittest

import ordo.runtime as runtime

from ordo.runtime.local_expression_contexts import (
    LocalExpressionContext,
    LocalExpressionContextFamily,
    LocalExpressionRoot,
    get_local_expression_context_policy,
)
from ordo.runtime.local_expressions import (
    extract_embedded_local_expression,
    parse_condition_local_expression,
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

    def test_step_condition_accepts_bare_condition_entrypoint(self) -> None:
        parsed = parse_condition_local_expression("step.issue.outputs.open and inputs.enabled", context=LocalExpressionContext.STEP_CONDITION)

        self.assertEqual(parsed.context, LocalExpressionContext.STEP_CONDITION)
        self.assertIsNotNone(parsed.value)

    def test_include_binding_uses_shared_embedded_local_expression_entrypoint(self) -> None:
        parsed = parse_embedded_local_expression("${step.issue.outputs.id}", context=LocalExpressionContext.INCLUDE_BINDING)

        assert parsed is not None
        self.assertEqual(parsed.context, LocalExpressionContext.INCLUDE_BINDING)
        self.assertIsNotNone(parsed.value)

    def test_runtime_package_exports_local_expression_api(self) -> None:
        self.assertIs(runtime.LocalExpressionContext, LocalExpressionContext)
        self.assertIs(runtime.parse_local_expression, parse_local_expression)
        self.assertIs(runtime.parse_embedded_local_expression, parse_embedded_local_expression)
        self.assertIs(runtime.parse_condition_local_expression, parse_condition_local_expression)

    def test_guard_context_rejects_nested_step_dependency(self) -> None:
        parsed = parse_local_expression(
            "gh.issue(repository=step.issue.outputs.id, issue_number=inputs.issue_number).state != \"CLOSED\"",
            context=LocalExpressionContext.GUARD,
        )

        diagnostics = validate_parsed_local_expression(parsed)
        self.assertEqual(
            {diagnostic.code for diagnostic in diagnostics},
            {"validation.workflow.local_expression.guard.step_ref"},
        )

    def test_guard_context_allows_state_dependency(self) -> None:
        parsed = parse_local_expression(
            'gh.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == state.task_memory[inputs.issue_ref].status',
            context=LocalExpressionContext.GUARD,
        )

        self.assertEqual(validate_parsed_local_expression(parsed), ())

    def test_step_condition_context_allows_step_dependency(self) -> None:
        parsed = parse_embedded_local_expression(
            "${step.issue.outputs.open and inputs.enabled}",
            context=LocalExpressionContext.STEP_CONDITION,
        )

        assert parsed is not None
        self.assertEqual(parsed.context, LocalExpressionContext.STEP_CONDITION)
        self.assertIsNotNone(parsed.value)

    def test_include_binding_context_allows_step_dependency(self) -> None:
        parsed = parse_embedded_local_expression(
            "${step.issue.outputs.id}",
            context=LocalExpressionContext.INCLUDE_BINDING,
        )

        assert parsed is not None
        self.assertEqual(parsed.context, LocalExpressionContext.INCLUDE_BINDING)
        self.assertIsNotNone(parsed.value)
