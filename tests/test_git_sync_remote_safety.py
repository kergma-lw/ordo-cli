import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call

from connectors.git.actions.sync import fetch, push
from connectors.git.actions.sync._shared import require_configured_remote
from ordo.plugin_sdk import MappedOutcomeError, OperationOutcome, fail, ok


class GitSyncRemoteSafetyTest(unittest.TestCase):
    def context(self, inventory="origin\n", **inputs):
        ctx = Mock(reference="git.sync")
        ctx.input.side_effect = inputs.__getitem__
        ctx.command.return_value = SimpleNamespace(stdout=inventory, raw={})
        return ctx

    def assert_failure(self, result, status, diagnostic):
        self.assertIsInstance(result, OperationOutcome)
        self.assertEqual(result.status, status)
        self.assertEqual(result.diagnostics[0].code, diagnostic)
        self.assertEqual(result.raw, {})

    def test_malformed_values_are_rejected_before_any_command(self):
        for value in (None, True, 123, "", " ", " origin", "origin ", "ori gin", "ori\tgin", "origin\n", "ori\u00a0gin", "--all", "-origin"):
            with self.subTest(value=value):
                ctx = self.context()
                result = require_configured_remote(ctx, value, "fetch_blocked")
                self.assert_failure(result, "remote_not_found", "action.git.invalid_remote")
                ctx.command.assert_not_called()

    def test_unconfigured_targets_are_rejected_by_exact_membership(self):
        for value in ("https://example.test/repo", "git@example.test:repo", "/tmp/repo", "../repo", ".", "unknown", "ori", "group"):
            with self.subTest(value=value):
                ctx = self.context()
                result = require_configured_remote(ctx, value, "fetch_blocked")
                self.assert_failure(result, "remote_not_found", "action.git.remote_not_found")
                ctx.command.assert_called_once_with(
                    ["git", "remote"], failures={"os_error": "fetch_blocked", "nonzero": "fetch_blocked"}
                )

    def test_configured_names_are_authoritative_even_when_pathlike(self):
        for name in ("team/origin", "../repo", "/tmp/repo", "https://example.test/repo"):
            with self.subTest(name=name):
                ctx = self.context(f"origin\n{name}\n")
                self.assertEqual(require_configured_remote(ctx, name, "fetch_blocked"), name)

    def test_final_newline_is_optional(self):
        ctx = self.context("origin")
        self.assertEqual(require_configured_remote(ctx, "origin", "fetch_blocked"), "origin")

    def test_empty_inventory_means_unknown_remote(self):
        ctx = self.context("")
        self.assert_failure(
            require_configured_remote(ctx, "origin", "fetch_blocked"),
            "remote_not_found", "action.git.remote_not_found",
        )

    def test_malformed_inventory_fails_closed_without_trimming(self):
        for inventory in (None, "\n", "origin\n\nother\n", "origin\n\n", "origin\norigin\n", "origin\n other\n", "origin\nother \n", "origin\noth\ter\n", "origin\n--all\n"):
            with self.subTest(inventory=inventory):
                ctx = self.context(inventory)
                self.assert_failure(
                    require_configured_remote(ctx, "origin", "fetch_blocked"),
                    "fetch_blocked", "action.git.remote_inventory_failed",
                )

    def test_fetch_invalid_remote_never_runs_a_command(self):
        ctx = self.context(remote="--all")
        self.assert_failure(fetch.run(ctx), "remote_not_found", "action.git.invalid_remote")
        ctx.command.assert_not_called()

    def test_push_preserves_raw_type_and_branch_check(self):
        ctx = self.context(branch="main", remote=True)
        self.assert_failure(push.run(ctx), "remote_not_found", "action.git.invalid_remote")
        ctx.command.assert_called_once_with(
            ["git", "show-ref", "--verify", "--quiet", "refs/heads/main"],
            failures={"os_error": "action_failed", "nonzero": "branch_not_found"},
        )
        ctx.call.assert_not_called()

    def test_fetch_inventory_failure_does_not_expose_error_context(self):
        ctx = self.context(remote="origin")
        ctx.command.side_effect = MappedOutcomeError(fail(
            code="fetch_blocked", summary="https://secret@example.test/repo",
            raw={"stderr": "https://secret@example.test/repo"},
        ))
        result = fetch.run(ctx)
        self.assert_failure(result, "fetch_blocked", "action.git.remote_inventory_failed")
        self.assertNotIn("secret", repr(result))
        self.assertEqual(ctx.command.call_count, 1)

    def test_push_inventory_failure_prevents_transport(self):
        ctx = self.context(branch="main", remote="origin")
        ctx.command.side_effect = [
            SimpleNamespace(stdout="", raw={}),
            MappedOutcomeError(fail(code="push_blocked", raw={"stderr": "private URL"})),
        ]
        self.assert_failure(push.run(ctx), "push_blocked", "action.git.remote_inventory_failed")
        self.assertEqual(ctx.command.call_count, 2)
        self.assertEqual(ctx.command.call_args, call(
            ["git", "remote"], failures={"os_error": "push_blocked", "nonzero": "push_blocked"},
        ))

    def test_explicit_configured_slash_remote_keeps_transport_argv(self):
        ctx = self.context("team/origin\n", branch="main", remote="team/origin")
        self.assertEqual(push.run(ctx).status, "ok")
        self.assertEqual([item.args[0] for item in ctx.command.call_args_list], [
            ["git", "show-ref", "--verify", "--quiet", "refs/heads/main"],
            ["git", "remote"],
            ["git", "push", "team/origin", "main"],
        ])
        ctx.call.assert_not_called()

    def test_explicit_null_uses_and_validates_upstream_remote(self):
        ctx = self.context(branch="main", remote=None)
        ctx.call.return_value = ok(outputs={"configured": True, "branch": "main", "remote": "origin"})
        result = push.run(ctx)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["remote"], "origin")
        ctx.call.assert_called_once_with("upstream")
        self.assertEqual([item.args[0] for item in ctx.command.call_args_list][1:], [
            ["git", "remote"], ["git", "push", "origin", "main"],
        ])

    def test_omitted_remote_requires_the_requested_branch_to_match_current_upstream(self):
        ctx = self.context(branch="topic", remote=None)
        ctx.call.return_value = ok(outputs={"configured": True, "branch": "main", "remote": "origin"})

        result = push.run(ctx)
        self.assertIsInstance(result, OperationOutcome)
        self.assertEqual(result.status, "upstream_remote_missing")
        self.assertEqual(result.diagnostics[0].code, "action.git.upstream_remote_missing")
        self.assertEqual(result.raw, {"upstream": {}})
        ctx.command.assert_called_once_with(
            ["git", "show-ref", "--verify", "--quiet", "refs/heads/topic"],
            failures={"os_error": "action_failed", "nonzero": "branch_not_found"},
        )

    def test_omitted_remote_fallback_must_still_be_configured(self):
        ctx = self.context()
        ctx.input.side_effect = ["main", MappedOutcomeError(fail(code="input_error"))]
        ctx.call.return_value = ok(outputs={"configured": True, "branch": "main", "remote": "missing"})
        self.assert_failure(push.run(ctx), "remote_not_found", "action.git.remote_not_found")
        ctx.call.assert_called_once_with("upstream")
        self.assertEqual([item.args[0] for item in ctx.command.call_args_list], [
            ["git", "show-ref", "--verify", "--quiet", "refs/heads/main"], ["git", "remote"],
        ])
