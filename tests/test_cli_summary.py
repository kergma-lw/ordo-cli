import unittest

from ordo.cli import _summarize_check_payload


class CliSummaryTest(unittest.TestCase):
    def test_check_summary_hides_weakened_scopes_when_verdict_not_weakened(self) -> None:
        payload = {
            "mode": "check",
            "status": "ok",
            "workflow": "close-story",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "backend",
            "diagnostics": [],
            "outputs": {
                "can_execute": True,
                "guard_details": [],
                "stale_probe_scopes": ["gh.issue", "gh.project.issue"],
                "verdict_basis_stale": False,
                "unevaluated_relevant_guards": [],
            },
        }

        summary = _summarize_check_payload(payload)

        self.assertEqual(summary["missing_facts"], [])

    def test_check_summary_keeps_weakened_scopes_when_verdict_weakened(self) -> None:
        payload = {
            "mode": "check",
            "status": "ok",
            "workflow": "close-story",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "backend",
            "diagnostics": [],
            "outputs": {
                "can_execute": True,
                "guard_details": [],
                "stale_probe_scopes": ["gh.issue"],
                "verdict_basis_stale": True,
                "unevaluated_relevant_guards": [],
            },
        }

        summary = _summarize_check_payload(payload)

        self.assertEqual(summary["missing_facts"], ["fresh facts unavailable for gh.issue"])
