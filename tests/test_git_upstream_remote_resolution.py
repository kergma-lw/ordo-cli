import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from connectors.git.probes import upstream
from ordo.plugin_sdk import MappedOutcomeError, fail, ok


class GitUpstreamRemoteResolutionTest(unittest.TestCase):
    def context(self, remote="team/origin\n", ref="team/origin/tracking/topic\n", canonical="refs/remotes/team/origin/tracking/topic\n"):
        ctx = Mock(reference="git.upstream")
        ctx.call.return_value = ok(
            outputs={"value": "feature/demo", "detached": False, "repository_root": "/tmp/demo-repo"},
            raw={"branch_evidence": True},
        )
        ctx.command.side_effect = [
            SimpleNamespace(stdout=ref, raw={"upstream_evidence": True}),
            remote if isinstance(remote, Exception) else SimpleNamespace(stdout=remote, raw={}),
            canonical if isinstance(canonical, Exception) else SimpleNamespace(stdout=canonical, raw={}),
        ]
        return ctx

    def assert_failure(self, ctx, diagnostic, calls):
        result = upstream.run(ctx)
        self.assertEqual(result.status, "probe_failed")
        self.assertEqual(result.diagnostics[0].code, f"probe.git_upstream.{diagnostic}")
        self.assertEqual(ctx.command.call_count, calls)
        return result

    def test_nested_remote_and_tracking_tail_use_exact_config(self):
        ctx = self.context()
        result = upstream.run(ctx)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["remote"], "team/origin")
        self.assertEqual(result.outputs["remote_branch"], "tracking/topic")
        self.assertEqual(result.outputs["upstream_ref"], "team/origin/tracking/topic")
        self.assertEqual(result.outputs["branch"], "feature/demo")
        self.assertEqual(result.raw, {"branch": {"branch_evidence": True}, "upstream": {"upstream_evidence": True}})
        self.assertEqual([item.args[0] for item in ctx.command.call_args_list], [
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            ["git", "config", "--get", "branch.feature/demo.remote"],
            ["git", "rev-parse", "--symbolic-full-name", "@{upstream}"],
        ])

    def test_full_original_ref_and_config_without_newline(self):
        result = upstream.run(self.context(remote="team/origin", ref="refs/remotes/team/origin/tracking/topic\n"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["upstream_ref"], "refs/remotes/team/origin/tracking/topic")
        self.assertEqual(result.outputs["remote_branch"], "tracking/topic")

    def test_ambiguous_remotes_abbreviation_is_preserved(self):
        result = upstream.run(self.context(ref="remotes/team/origin/tracking/topic\n"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["upstream_ref"], "remotes/team/origin/tracking/topic")

    def test_shorter_configured_remote_keeps_longer_tracking_tail(self):
        result = upstream.run(self.context(remote="team\n"))
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["remote"], "team")
        self.assertEqual(result.outputs["remote_branch"], "origin/tracking/topic")

    def test_custom_fetch_destination_cannot_hide_behind_abbreviation(self):
        self.assert_failure(
            self.context(canonical="refs/heads/team/origin/tracking/topic\n"), "invalid_ref", 3,
        )

    def test_other_remote_namespace_and_mismatched_original_are_rejected(self):
        self.assert_failure(self.context(canonical="refs/remotes/other/tracking/topic\n"), "invalid_ref", 3)
        self.assert_failure(self.context(ref="team/origin/other\n"), "invalid_ref", 3)

    def test_empty_or_malformed_canonical_ref_is_rejected(self):
        for canonical in ("", "refs/remotes/team/origin/\n", "refs/remotes/team/origin/tracking topic\n"):
            with self.subTest(canonical=canonical):
                self.assert_failure(self.context(canonical=canonical), "invalid_ref", 3)

    def test_remote_values_are_not_coerced_or_whitespace_normalized(self):
        for remote in (None, 123, "", " \n", " origin\n", "origin\r\n", "origin\n\n", "-origin\n"):
            with self.subTest(remote=remote):
                self.assert_failure(self.context(remote=remote), "invalid_remote", 2)

    def test_local_upstream_is_rejected_before_canonical_lookup(self):
        self.assert_failure(self.context(remote=".\n", ref="main\n"), "invalid_remote", 2)

    def test_missing_or_failed_config_lookup_uses_fixed_diagnostic(self):
        for returncode in (1, 128):
            with self.subTest(returncode=returncode):
                error = MappedOutcomeError(fail(
                    code="probe_failed", summary="private lookup error",
                    raw={"returncode": returncode, "stderr": "private lookup error"},
                ))
                result = self.assert_failure(self.context(remote=error), "remote_lookup_failed", 2)
                self.assertNotIn("private lookup error", repr(result))

    def test_canonical_exit128_is_failure_not_unconfigured(self):
        error = MappedOutcomeError(fail(
            code="probe_failed", summary="private lookup error",
            raw={"returncode": 128, "stderr": "private lookup error"},
        ))
        result = self.assert_failure(self.context(canonical=error), "ref_lookup_failed", 3)
        self.assertNotIn("private lookup error", repr(result))
