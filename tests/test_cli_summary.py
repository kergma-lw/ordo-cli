import unittest

from ordo.cli import (
    _summarize_activation_error_payload,
    _compact_value,
    _limit_items,
    _summarize_check_payload,
    _summarize_explain_payload,
    _summarize_review_payload,
    _summarize_run_payload,
)


class CliSummaryTest(unittest.TestCase):
    def test_review_summaries_preserve_all_findings(self) -> None:
        findings = [
            {
                "code": "review.workflow.input_description_missing",
                "category": "input_authoring",
                "message": f"Input input_{index} needs a description",
                "suggested_fix": "add_input_description",
            }
            for index in range(13)
        ]
        for review_status, summarize in (
            ("needs_attention", _summarize_review_payload),
            ("unavailable", _summarize_activation_error_payload),
        ):
            with self.subTest(review_status=review_status):
                summary = summarize({
                    "mode": "review",
                    "status": "ok" if review_status == "needs_attention" else "validation_error",
                    "diagnostics": [],
                    "outputs": {
                        "review_status": review_status,
                        "finding_count": len(findings),
                        "findings": findings,
                    },
                })
                self.assertEqual(summary["finding_count"], 13)
                self.assertEqual(len(summary["top_findings"]), 13)
                self.assertEqual(
                    [item["message"] for item in summary["top_findings"]],
                    [item["message"] for item in findings],
                )

    def test_limit_items_uses_ascii_ellipsis_marker(self) -> None:
        self.assertEqual(_limit_items([str(index) for index in range(10)], limit=3), ["0", "1", "2", "... and 7 more"])

    def test_compact_value_uses_ascii_ellipsis_marker(self) -> None:
        rendered = _compact_value("x" * 20, limit=10)
        self.assertTrue(rendered.endswith("..."))
        self.assertNotIn("…", rendered)

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

    def test_check_summary_preserves_active_profile_source(self) -> None:
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
                "stale_probe_scopes": [],
                "verdict_basis_stale": False,
                "unevaluated_relevant_guards": [],
                "active_profile_source": "workflow",
            },
        }

        summary = _summarize_check_payload(payload)

        self.assertEqual(summary["active_profile_source"], "workflow")

    def test_check_summary_surfaces_gate_blockers(self) -> None:
        payload = {
            "mode": "check",
            "status": "ok",
            "workflow": "story-to-ready",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "meta",
            "diagnostics": [],
            "outputs": {
                "can_execute": False,
                "guard_details": [],
                "gate_blockers": ["Set story status to Ready"],
                "preflight_step_items": [
                    {
                        "name": "Set story status to Ready",
                        "status": "gate_blocked",
                        "gate_report": {
                            "verdict": "failed",
                            "failed": [{"expression": "step.ready | eq(true)"}],
                        },
                    }
                ],
                "unevaluated_relevant_guards": [],
            },
        }

        summary = _summarize_check_payload(payload)

        self.assertEqual(summary["blockers"], ["Set story status to Ready"])
        self.assertEqual(summary["failed_step"], "Set story status to Ready")
        self.assertEqual(summary["message"], "Step gate blocked execution for 'Set story status to Ready': step.ready | eq(true)")

    def test_check_summary_surfaces_nested_gate_failure_like_run(self) -> None:
        payload = {
            "mode": "check",
            "status": "ok",
            "workflow": "story-to-ready",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "meta",
            "diagnostics": [],
            "outputs": {
                "can_execute": False,
                "guard_details": [],
                "gate_blockers": ["Validate linked task readiness"],
                "nested_gate_blockers": [
                    {
                        "expanded_from_step": "Validate linked task readiness",
                        "expanded_item": "kergma-lw/checklist-mobile#1",
                        "gate_blockers": ["Gate task readiness"],
                        "gate_reports": [
                            {
                                "verdict": "failed",
                                "failed": [
                                    {
                                        "expression": 'step.project_issue.outputs.status | eq("Ready")',
                                    }
                                ],
                                "on_fail_context": {
                                    "profile": "mobile",
                                    "issue_number": "1",
                                },
                            }
                        ],
                    }
                ],
                "unevaluated_relevant_guards": [],
            },
        }

        summary = _summarize_check_payload(payload)

        self.assertEqual(summary["failed_step"], "Gate task readiness")
        self.assertEqual(summary["item"], "kergma-lw/checklist-mobile#1")
        self.assertEqual(summary["on_fail_context"], {"profile": "mobile", "issue_number": "1"})
        self.assertEqual(
            summary["message"],
            'Item \'kergma-lw/checklist-mobile#1\' failed gate \'Gate task readiness\': step.project_issue.outputs.status | eq("Ready")',
        )

    def test_check_summary_surfaces_read_only_preflight_failure(self) -> None:
        payload = {
            "mode": "check",
            "status": "ok",
            "workflow": "story-to-ready",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "meta",
            "diagnostics": [],
            "outputs": {
                "can_execute": False,
                "guard_details": [],
                "preflight_halts": [
                    {
                        "reason": "read_only_step_failed",
                        "step_name": "Load story task item details in batch",
                    }
                ],
                "unevaluated_relevant_guards": [],
            },
        }

        summary = _summarize_check_payload(payload)

        self.assertEqual(summary["blockers"], ["Load story task item details in batch"])
        self.assertIn("read-only observation", summary["message"])

    def test_check_summary_surfaces_frontier_ready_step(self) -> None:
        payload = {
            "mode": "check",
            "status": "ok",
            "workflow": "story-to-ready",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "meta",
            "diagnostics": [],
            "outputs": {
                "can_execute": True,
                "guard_details": [],
                "frontier_ready_step": "Set story status to Ready",
                "unevaluated_relevant_guards": [],
            },
        }

        summary = _summarize_check_payload(payload)

        self.assertIn("workflow can run now", summary["message"])

    def test_check_summary_surfaces_context_only_preflight_facts(self) -> None:
        payload = {
            "mode": "check",
            "status": "ok",
            "workflow": "profile-switch-inline-probe",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "meta",
            "diagnostics": [],
            "outputs": {
                "can_execute": True,
                "guard_details": [],
                "preflight_step_items": [
                    {
                        "status": "interpreted",
                        "preflight_classification": "context_only",
                        "expanded_item": "mobile",
                        "active_profile": "mobile",
                    }
                ],
                "unevaluated_relevant_guards": [],
            },
        }

        summary = _summarize_check_payload(payload)

        self.assertIn("fan_out item = mobile", summary["observed_facts"])
        self.assertIn("active_profile = mobile", summary["observed_facts"])

    def test_explain_summary_surfaces_nested_gate_item_and_failed_conditions(self) -> None:
        payload = {
            "mode": "explain",
            "status": "ok",
            "workflow": "story-to-ready",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "meta",
            "failed_guard": None,
            "diagnostics": [],
            "outputs": {
                "explanation": {
                    "allowed": False,
                    "category": "gate",
                    "why": "Nested gate failed for fan-out item 'kergma-lw/checklist-mobile#1': step.linked_project_issue.outputs.status | eq(\"Ready\")",
                    "blockers": ["Validate linked task readiness"],
                    "nested_gate_blockers": [
                        {
                            "expanded_item": "kergma-lw/checklist-mobile#1",
                            "gate_reports": [
                                {
                                    "failed": [
                                        {
                                            "expression": 'step.linked_project_issue.outputs.status | eq("Ready")'
                                        }
                                    ]
                                }
                            ],
                        }
                    ],
                }
            },
        }

        summary = _summarize_explain_payload(payload)

        self.assertEqual(summary["item"], "kergma-lw/checklist-mobile#1")
        self.assertEqual(summary["failed_conditions"], ['step.linked_project_issue.outputs.status | eq("Ready")'])

    def test_explain_summary_prefers_structural_failed_causes(self) -> None:
        payload = {
            "mode": "explain",
            "status": "ok",
            "workflow": "story-to-ready",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "meta",
            "failed_guard": None,
            "diagnostics": [],
            "outputs": {
                "explanation": {
                    "allowed": False,
                    "category": "gate",
                    "why": "Nested gate failed",
                    "blockers": ["Validate linked task readiness"],
                    "nested_gate_blockers": [
                        {
                            "expanded_item": "kergma-lw/checklist-mobile#1",
                            "gate_reports": [
                                {
                                    "failed_causes": [
                                        {
                                            "rendered": 'any(step.linked_project_issue.outputs.type | eq("Task"), step.linked_project_issue.outputs.type | eq("Bug"))'
                                        }
                                    ],
                                    "failed": [
                                        {
                                            "expression": 'step.linked_project_issue.outputs.type | eq("Bug")'
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            },
        }

        summary = _summarize_explain_payload(payload)

        self.assertEqual(
            summary["failed_conditions"],
            ['any(step.linked_project_issue.outputs.type | eq("Task"), step.linked_project_issue.outputs.type | eq("Bug"))'],
        )

    def test_run_summary_surfaces_on_fail_context_from_diagnostic_details(self) -> None:
        payload = {
            "mode": "run",
            "status": "execution_error",
            "workflow": "story-to-ready",
            "profile": "meta",
            "diagnostics": [
                {
                    "message": "Item 'kergma-lw/checklist-mobile#1' failed gate 'Gate linked task readiness': step.linked_project_issue.outputs.status | eq(\"Ready\")",
                    "details": {
                        "fan_out_item": "kergma-lw/checklist-mobile#1",
                        "on_fail_context": {
                            "profile": "mobile",
                            "issue_number": "1",
                        },
                    },
                }
            ],
        }

        summary = _summarize_run_payload(payload)

        self.assertEqual(summary["item"], "kergma-lw/checklist-mobile#1")
        self.assertEqual(summary["on_fail_context"], {"profile": "mobile", "issue_number": "1"})
        self.assertNotIn("next context:", summary["message"])

    def test_run_summary_rebuilds_gate_message_from_diagnostic_details(self) -> None:
        payload = {
            "mode": "run",
            "status": "execution_error",
            "workflow": "story-to-ready",
            "profile": "meta",
            "failed_step": "Publish selected story task",
            "diagnostics": [
                {
                    "code": "runtime.step.gate.failed",
                    "message": "Step gate blocked execution for 'Publish selected story task'",
                    "details": {
                        "step": "Publish selected story task",
                        "failed_conditions": ["git.worktree.clean"],
                        "unknown_conditions": [],
                    },
                }
            ],
        }

        summary = _summarize_run_payload(payload)

        self.assertEqual(summary["message"], "Step gate blocked execution for 'Publish selected story task': git.worktree.clean")

    def test_run_summary_surfaces_guard_failure_without_diagnostics(self) -> None:
        payload = {
            "mode": "run",
            "status": "guard_failed",
            "workflow": "story-to-ready",
            "profile": "meta",
            "failed_guard": "git.worktree.clean",
            "diagnostics": [],
        }

        summary = _summarize_run_payload(payload)

        self.assertEqual(summary["message"], "Guard blocked execution for 'git.worktree.clean'")

    def test_run_summary_surfaces_failed_guard_detail(self) -> None:
        payload = {
            "mode": "run",
            "status": "guard_failed",
            "workflow": "story-tasks-show",
            "profile": "meta",
            "active_profile": "meta",
            "working_directory": "/tmp/meta",
            "failed_guard": 'story_project_issue.exists',
            "guard_detail": {
                "reference": "story_project_issue.exists",
                "failed_subcondition": "story_project_issue.exists",
                "failure_kind": "guard_failed",
                "affected_inputs": ["inputs.repository", "inputs.issue_number", "inputs.project_id"],
                "affected_lets": ["story_project_issue"],
                "trace": [
                    {
                        "expr": "story_project_issue",
                        "kind": "let",
                        "status": "ok",
                        "binding_name": "story_project_issue",
                        "expanded_expr": "gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id).exists",
                        "value": None,
                    }
                ],
            },
            "diagnostics": [
                {
                    "message": "GitHub issue was not found",
                }
            ],
        }

        summary = _summarize_run_payload(payload)

        self.assertEqual(summary["message"], "Guard blocked execution for 'story_project_issue.exists'")
        self.assertEqual(summary["guard_detail"]["affected_lets"], ["story_project_issue"])
        self.assertEqual(
            summary["guard_detail"]["affected_inputs"],
            ["inputs.repository", "inputs.issue_number", "inputs.project_id"],
        )

    def test_check_summary_surfaces_guard_failure_message(self) -> None:
        payload = {
            "mode": "check",
            "status": "guard_failed",
            "workflow": "story-to-ready",
            "playbook": "/tmp/.ordo/ordo.yaml",
            "profile": "meta",
            "active_profile": "mobile",
            "working_directory": "/tmp/mobile",
            "failed_guard": "git.worktree.clean",
            "diagnostics": [],
            "outputs": {
                "can_execute": False,
                "guard_details": [
                    {
                        "reference": "git.worktree.clean",
                        "failed_subcondition": "git.worktree.clean",
                    }
                ],
                "unevaluated_relevant_guards": [],
            },
        }

        summary = _summarize_check_payload(payload)

        self.assertEqual(summary["message"], "Guard blocked execution for 'git.worktree.clean'")
        self.assertEqual(summary["active_profile"], "mobile")
        self.assertEqual(summary["working_directory"], "/tmp/mobile")

    def test_run_summary_surfaces_runtime_context_fields(self) -> None:
        payload = {
            "mode": "run",
            "status": "execution_error",
            "active_profile": "mobile",
            "working_directory": "/tmp/mobile",
            "failed_guard": "git.worktree.clean",
            "diagnostics": [],
        }

        summary = _summarize_run_payload(payload)

        self.assertEqual(summary["active_profile"], "mobile")
        self.assertEqual(summary["working_directory"], "/tmp/mobile")

    def test_run_summary_surfaces_failed_step_detail(self) -> None:
        payload = {
            "mode": "run",
            "status": "execution_error",
            "workflow": "story-tasks-show",
            "active_profile": "meta",
            "working_directory": "/tmp/meta",
            "failed_step": "Load story task item details in batch",
            "step_detail": {
                "step": "Load story task item details in batch",
                "reference": "gh.project.items",
                "resolved_inputs": {"content_refs": ["owner/repo#1"]},
            },
            "diagnostics": [
                {
                    "message": "GitHub project item content_refs must be a list of OWNER/REPO#NUMBER strings",
                }
            ],
        }

        summary = _summarize_run_payload(payload)

        self.assertEqual(summary["failed_step"], "Load story task item details in batch")
        self.assertEqual(summary["step_detail"]["reference"], "gh.project.items")
        self.assertEqual(summary["step_detail"]["resolved_inputs"], {"content_refs": ["owner/repo#1"]})

    def test_run_summary_omits_null_mode_profile_workflow(self) -> None:
        payload = {
            "mode": None,
            "status": "execution_error",
            "workflow": None,
            "profile": None,
            "failed_step": "Gate task readiness",
            "diagnostics": [
                {
                    "message": "Item 'kergma-lw/checklist-mobile#1' failed gate 'Gate task readiness'",
                    "details": {
                        "fan_out_item": "kergma-lw/checklist-mobile#1",
                        "on_fail_context": {"profile": "mobile"},
                    },
                }
            ],
        }

        summary = _summarize_run_payload(payload)

        self.assertEqual(summary["status"], "execution_error")
        self.assertNotIn("mode", summary)
        self.assertNotIn("workflow", summary)
        self.assertNotIn("profile", summary)

    def test_review_summary_surfaces_structured_condition_rewrite_hints(self) -> None:
        payload = {
            "mode": "review",
            "status": "ok",
            "workflow": "story-to-ready",
            "profile": "meta",
            "diagnostics": [],
            "outputs": {
                "review_status": "needs_attention",
                "finding_count": 1,
                "findings": [
                    {
                        "code": "review.workflow.step_condition.structured_form_preferred",
                        "category": "condition_authoring",
                        "message": "Long or mixed string step conditions should be rewritten as structured all/any/not form",
                        "evidence": {
                            "suggested_rewrite": ["a", "b", "c", "d"],
                        },
                    }
                ],
            },
        }

        summary = _summarize_review_payload(payload)

        self.assertEqual(summary["top_findings"][0]["suggested_rewrite"], ["a", "b", "c", "d"])

    def test_review_summary_surfaces_other_constructive_hints(self) -> None:
        payload = {
            "mode": "review",
            "status": "ok",
            "workflow": "story-to-ready",
            "profile": "meta",
            "diagnostics": [],
            "outputs": {
                "review_status": "needs_attention",
                "finding_count": 2,
                "findings": [
                    {
                        "code": "review.workflow.adapter_pipe_style_preferred",
                        "category": "value_authoring",
                        "message": "Use pipe-style adapter binding instead of with{root: ...} when an equivalent pipe form exists",
                        "evidence": {
                            "suggested_expression": 'inputs.body | markdown["Tasks"]',
                            "suggested_rewrite": 'inputs.body | markdown["Tasks"]',
                        },
                    },
                    {
                        "code": "review.workflow.literal_string_maybe_unquoted",
                        "category": "value_authoring",
                        "message": "This bare profile_switch value may be an intended literal profile name.",
                        "evidence": {
                            "suggested_fix": "quote_literal_string",
                            "suggested_rewrite": '"meta"',
                        },
                    },
                    {
                        "code": "review.workflow.input_validation_missing",
                        "category": "input_validation",
                        "message": "Input 'repository' is not validated in early guards",
                        "evidence": {
                            "suggested_fix": "add_early_guard_validation",
                            "suggested_rewrite": {"guards": ["inputs.repository"]},
                        },
                    },
                ],
            },
        }

        summary = _summarize_review_payload(payload)

        self.assertEqual(summary["top_findings"][0]["suggested_expression"], 'inputs.body | markdown["Tasks"]')
        self.assertEqual(summary["top_findings"][0]["suggested_rewrite"], 'inputs.body | markdown["Tasks"]')
        self.assertEqual(summary["top_findings"][1]["suggested_fix"], "quote_literal_string")
        self.assertEqual(summary["top_findings"][1]["suggested_rewrite"], '"meta"')
        self.assertEqual(summary["top_findings"][2]["suggested_fix"], "add_early_guard_validation")
        self.assertEqual(summary["top_findings"][2]["suggested_rewrite"], {"guards": ["inputs.repository"]})
