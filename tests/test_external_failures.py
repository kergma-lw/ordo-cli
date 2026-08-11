import unittest

from ordo.external_failures import build_external_failure_details, classify_external_command_failure, excerpt_text
from ordo.plugin_sdk import fail_external_command


class ExternalFailuresTest(unittest.TestCase):
    def test_excerpt_text_normalizes_whitespace_and_truncates(self) -> None:
        value = excerpt_text("line one\n\n   line two   ", limit=12)

        self.assertEqual(value, "line one...")

    def test_classify_github_auth_failure(self) -> None:
        info = classify_external_command_failure(
            raw={
                "argv": ["gh", "api", "repos/owner/repo/pulls/7"],
                "stderr": "authentication required; run gh auth login",
                "stdout": "",
                "returncode": 1,
            },
            tool="gh",
            system="github",
        )

        self.assertEqual(info.classification, "auth_failed")
        self.assertEqual(info.external_tool, "gh")
        self.assertEqual(info.external_system, "github")
        self.assertIn("gh auth status", info.suggested_checks[0])

    def test_classify_binary_missing_from_os_error(self) -> None:
        info = classify_external_command_failure(
            raw={
                "argv": ["docker", "compose", "up"],
                "stderr": "",
                "stdout": "",
                "os_error": "[Errno 2] No such file or directory: 'docker'",
            },
            tool="docker",
        )

        self.assertEqual(info.classification, "binary_missing")
        self.assertIn("PATH", info.suggested_checks[0])

    def test_build_external_failure_details_keeps_context_and_excerpts(self) -> None:
        details = build_external_failure_details(
            raw={
                "argv": ["gh", "api", "graphql"],
                "stderr": "could not resolve host: api.github.com",
                "stdout": "",
                "returncode": 1,
            },
            tool="gh",
            system="github",
            extra_details={"pull_ref": "owner/repo#7"},
        )

        self.assertTrue(details["is_external"])
        self.assertEqual(details["classification"], "network_failed")
        self.assertEqual(details["external_tool"], "gh")
        self.assertEqual(details["external_system"], "github")
        self.assertEqual(details["pull_ref"], "owner/repo#7")
        self.assertEqual(details["argv_summary"], "gh api graphql")
        self.assertEqual(details["returncode"], 1)
        self.assertIn("network", details["suggested_checks"][0].lower())

    def test_fail_external_command_uses_shared_details_payload(self) -> None:
        outcome = fail_external_command(
            code="probe_failed",
            summary="GitHub pull request probe failed",
            diagnostic_code="probe.gh_pr.command_failed",
            raw={
                "argv": ["gh", "api", "repos/owner/repo/pulls/7"],
                "stderr": "rate limit exceeded",
                "stdout": "",
                "returncode": 1,
            },
            reference="gh.pr",
            details={"pull_ref": "owner/repo#7"},
            tool="gh",
            system="github",
        )

        self.assertEqual(outcome.status, "probe_failed")
        self.assertEqual(outcome.diagnostics[0].code, "probe.gh_pr.command_failed")
        self.assertEqual(outcome.diagnostics[0].details["classification"], "rate_limited")
        self.assertEqual(outcome.diagnostics[0].details["reference"], "gh.pr")
        self.assertEqual(outcome.diagnostics[0].details["pull_ref"], "owner/repo#7")
        self.assertEqual(outcome.raw["returncode"], 1)


if __name__ == "__main__":
    unittest.main()
