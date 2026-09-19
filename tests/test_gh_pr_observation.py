"""PR observation contracts. All external API responses are mocked."""

import copy
import json
import subprocess
import unittest
from unittest.mock import patch

from ordo.connectors.operations import evaluate_probe
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Guard, OperationRef, Workflow
from ordo.runtime.resolution import ResolvedOperation


HEAD = "a" * 40
BASE = "b" * 40
CANDIDATE = "c" * 40
OTHER = "d" * 40
PULL = {
    "number": 42, "state": "open", "draft": False, "merged": False, "merged_at": None,
    "head": {"ref": "feature", "sha": HEAD, "repo": {"full_name": "fork/repo"}},
    "base": {"ref": "main", "sha": BASE,
             "repo": {"full_name": "owner/repo", "owner": {"login": "owner"}, "name": "repo"}},
}


def commit_evidence(pull=PULL, *, candidate=None, merged_sha=None):
    return {"data": {"repository": {"nameWithOwner": "owner/repo", "pullRequest": {
        "number": pull["number"], "state": "MERGED" if pull["merged"] else pull["state"].upper(),
        "merged": pull["merged"], "headRefOid": pull["head"]["sha"], "baseRefOid": pull["base"]["sha"],
        "potentialMergeCommit": None if candidate is None else {"oid": candidate},
        "mergeCommit": None if merged_sha is None else {"oid": merged_sha},
    }}}}


def status_page(items=(), *, sha=HEAD, total=None):
    return {"sha": sha, "total_count": len(items) if total is None else total, "statuses": list(items)}


def run_page(items=(), *, total=None):
    return {"total_count": len(items) if total is None else total, "check_runs": list(items)}


def check_run(conclusion="success", *, status="completed", sha=HEAD, id=1):
    return {
        "id": id, "name": "unit", "status": status, "conclusion": conclusion,
        "head_sha": sha, "app": {"id": 15368, "slug": "github-actions"},
        "started_at": "2026-09-11T10:00:00Z", "completed_at": "2026-09-11T10:01:00Z",
        "html_url": "https://example.test/check/1",
    }


class GitHubPullObservationTest(unittest.TestCase):
    def observe(self, reference, responses, **inputs):
        authored = {"repository": "owner/repo", "pull_number": 42, **inputs}
        workflow = Workflow(version=0, workflow="observation", guards=(Guard(OperationRef(reference, with_=authored)),), steps=())
        operation = get_public_connector_registry().get_operation(reference)
        resolved = ResolvedOperation(reference, "gh", operation, "public")
        completed = [subprocess.CompletedProcess([], 0, "authenticated\n", "")]
        for response in responses:
            completed.append(response if isinstance(response, (subprocess.CompletedProcess, BaseException)) else
                             subprocess.CompletedProcess([], 0, json.dumps(response), ""))
        with patch("subprocess.run", side_effect=completed) as command:
            result = evaluate_probe(resolved, workflow)
        self.assertEqual(command.call_count, len(completed))
        return result, [call.args[0] for call in command.call_args_list]

    def checks(self, *, pull=None, statuses=None, runs=None, **inputs):
        return self.observe("gh.pr.checks", [
            copy.deepcopy(PULL) if pull is None else pull,
            [status_page()] if statuses is None else statuses,
            [run_page()] if runs is None else runs,
        ], **inputs)

    def test_contract_exposes_binding_target_and_evidence(self):
        registry = get_public_connector_registry()
        pr = registry.get_operation("gh.pr")
        checks = registry.get_operation("gh.pr.checks")
        self.assertEqual(checks.inputs["expected_head_sha"], "string")
        self.assertEqual(checks.inputs["target"], "string")
        for field in ("head_repository", "base_repository", "base_sha", "merged", "merged_at",
                      "merge_commit_sha", "test_merge_sha", "test_merge_head_sha", "test_merge_base_sha", "test_merge_state",
                      "test_merge_reason", "stack_state", "stack"):
            self.assertIn(field, pr.outputs)
        for field in ("complete", "commit_sha", "neutral_count", "unknown_count", "test_merge_reason"):
            self.assertIn(field, checks.outputs)

    def test_metadata_distinguishes_merge_result_and_verified_candidate(self):
        pull = copy.deepcopy(PULL)
        commit = {"sha": CANDIDATE, "parents": [{"sha": BASE}, {"sha": HEAD}]}
        result, calls = self.observe("gh.pr", [pull, commit_evidence(candidate=CANDIDATE), commit])
        self.assertEqual(result.status, "ok")
        outputs = result.outputs
        self.assertEqual(outputs["head_repository"], "fork/repo")
        self.assertEqual(outputs["base_repository"], "owner/repo")
        self.assertEqual(outputs["base_sha"], BASE)
        self.assertFalse(outputs["merged"])
        self.assertIsNone(outputs["merge_commit_sha"])
        self.assertEqual(outputs["test_merge_sha"], CANDIDATE)
        self.assertEqual(outputs["test_merge_head_sha"], HEAD)
        self.assertEqual(outputs["test_merge_base_sha"], BASE)
        self.assertEqual(outputs["test_merge_state"], "verified")
        self.assertIsNone(outputs["test_merge_reason"])
        self.assertIn(f"repos/owner/repo/commits/{CANDIDATE}", calls[-1])

    def test_merged_metadata_never_relabels_result_as_candidate(self):
        pull = {**PULL, "state": "closed", "merged": True, "merged_at": "2026-09-11T12:00:00Z"}
        result, _ = self.observe("gh.pr", [pull, commit_evidence(pull, merged_sha=OTHER)])
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.outputs["merged"])
        self.assertEqual(result.outputs["merged_at"], pull["merged_at"])
        self.assertEqual(result.outputs["merge_commit_sha"], OTHER)
        self.assertEqual(result.outputs["test_merge_state"], "merged")
        for field in ("test_merge_sha", "test_merge_head_sha", "test_merge_base_sha"):
            self.assertIsNone(result.outputs[field])

    def test_missing_metadata_is_null_including_candidate_identity(self):
        result, _ = self.observe("gh.pr", [{"number": 42, "head": {"sha": HEAD}}])
        self.assertEqual(result.status, "ok")
        for field in ("head_repository", "base_repository", "base_sha", "merged", "merged_at",
                      "merge_commit_sha", "test_merge_sha", "test_merge_head_sha", "test_merge_base_sha"):
            self.assertIsNone(result.outputs[field])
        self.assertEqual(result.outputs["test_merge_state"], "unavailable")
        self.assertEqual(result.outputs["stack_state"], "unknown")
        self.assertIsNone(result.outputs["stack"])

    def test_valid_stack_is_preserved_with_valid_pr_identity(self):
        stack = {"base": {"ref": "main", "sha": BASE}, "size": 3, "position": 1}
        result, _ = self.observe("gh.pr", [{**PULL, "stack": stack}, commit_evidence()])
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["stack_state"], "stacked")
        self.assertEqual(result.outputs["stack"], stack)

    def test_absent_stack_is_standalone_only_for_a_valid_envelope(self):
        result, _ = self.observe("gh.pr", [PULL, commit_evidence()])
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["stack_state"], "standalone")
        self.assertIsNone(result.outputs["stack"])
        incomplete = copy.deepcopy(PULL)
        del incomplete["base"]["repo"]["owner"]
        for payload in (incomplete, {"number": 42, "head": {"sha": "abc123"}}):
            result, _ = self.observe("gh.pr", [payload])
            self.assertEqual(result.status, "ok")
            self.assertEqual(result.outputs["stack_state"], "unknown")
            self.assertIsNone(result.outputs["stack"])

    def test_null_and_malformed_stack_are_unknown_not_standalone(self):
        for stack in (None, {}, [], "unknown", {"base": {"ref": "main", "sha": "abc123"}},
                      {"base": {"ref": "main", "sha": BASE}, "size": "3"}):
            with self.subTest(stack=stack):
                result, _ = self.observe("gh.pr", [{**PULL, "stack": stack}, commit_evidence()])
                self.assertEqual(result.status, "ok")
                self.assertEqual(result.outputs["stack_state"], "unknown")
                self.assertIsNone(result.outputs["stack"])

    def test_stack_object_without_valid_pr_identity_is_unknown(self):
        payload = {"number": 42, "stack": {"base": {"ref": "main", "sha": BASE}}}
        result, _ = self.observe("gh.pr", [payload])
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["stack_state"], "unknown")
        self.assertIsNone(result.outputs["stack"])

    def test_response_identity_mismatch_fails_before_candidate_or_checks_api(self):
        wrong_repo = copy.deepcopy(PULL)
        wrong_repo["base"]["repo"]["full_name"] = "other/repo"
        wrong_owner = copy.deepcopy(PULL)
        wrong_owner["base"]["repo"]["owner"]["login"] = "other"
        for payload in ({**PULL, "number": 99}, {**PULL, "number": "42"}, wrong_repo, wrong_owner):
            for reference in ("gh.pr", "gh.pr.checks"):
                result, _ = self.observe(reference, [payload])
                self.assertEqual(result.status, "probe_failed")
                self.assertEqual(result.diagnostics[0].code, "probe.gh_pr.identity_mismatch")

    def test_merged_metadata_is_boolean_or_null(self):
        for merged in (True, False, None, 0, 1, "false", "true", [], {}):
            with self.subTest(merged=merged):
                responses = [{**PULL, "merged": merged}]
                if merged is False:
                    responses.append(commit_evidence())
                result, _ = self.observe("gh.pr", responses)
                self.assertEqual(result.status, "ok")
                if type(merged) is bool:
                    self.assertIs(result.outputs["merged"], merged)
                else:
                    self.assertIsNone(result.outputs["merged"])
                    self.assertEqual(result.outputs["stack_state"], "unknown")

    def test_checks_bind_expected_head_and_default_to_head_without_graphql(self):
        result, calls = self.checks(pull=PULL,
                                    runs=[run_page([check_run()])], expected_head_sha=HEAD.upper())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["overall_state"], "success")
        self.assertEqual(result.outputs["commit_sha"], HEAD)
        self.assertEqual(result.outputs["target"], "head")
        self.assertEqual(result.outputs["sha_evidence"], "api_attached_commit")
        self.assertEqual(result.outputs["expected_head_sha"], HEAD)
        self.assertIsNone(result.outputs["test_merge_sha"])
        self.assertEqual(result.outputs["test_merge_state"], "not_requested")
        self.assertFalse(any("graphql" in call for call in calls))
        for call in calls[-2:]:
            self.assertTrue(any(f"/commits/{HEAD}/" in part for part in call))
            self.assertIn("--paginate", call)
            self.assertIn("--slurp", call)

    def test_stale_head_binding_fails_before_reading_checks(self):
        result, _ = self.observe("gh.pr.checks", [PULL], expected_head_sha=OTHER)
        self.assertEqual(result.status, "checks_unavailable")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_pr_checks.head_mismatch")
        self.assertEqual(result.outputs["head_sha"], HEAD)
        self.assertIsNone(result.outputs["commit_sha"])

    def test_invalid_binding_or_target_fails_before_api_calls(self):
        for inputs in ({"expected_head_sha": "main"}, {"expected_head_sha": "abc123"}, {"target": "merge"}):
            with self.subTest(inputs=inputs):
                result, _ = self.observe("gh.pr.checks", [], **inputs)
                self.assertEqual(result.status, "checks_unavailable")

    def test_test_merge_checks_are_attached_to_verified_candidate(self):
        pull = copy.deepcopy(PULL)
        commit = {"sha": CANDIDATE, "parents": [{"sha": BASE}, {"sha": HEAD}]}
        result, calls = self.observe("gh.pr.checks", [pull, commit_evidence(candidate=CANDIDATE), commit, [status_page(sha=CANDIDATE)],
                                                     [run_page([check_run(sha=CANDIDATE)])]],
                                     target="test_merge", expected_head_sha=HEAD)
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["test_merge_state"], "verified")
        self.assertEqual(result.outputs["head_sha"], HEAD)
        self.assertEqual(result.outputs["base_sha"], BASE)
        self.assertEqual(result.outputs["commit_sha"], CANDIDATE)
        self.assertEqual(result.outputs["checks"][0]["sha"], CANDIDATE)
        self.assertTrue(any(f"/commits/{CANDIDATE}/check-runs" in part for part in calls[-1]))

    def test_changed_base_or_candidate_parent_mismatch_is_not_usable(self):
        cases = [
            ({**PULL, "base": {**PULL["base"], "sha": OTHER}}, [BASE, HEAD], CANDIDATE),
            (PULL, [BASE, OTHER], CANDIDATE),
            (PULL, [HEAD, BASE], CANDIDATE),
            (PULL, [BASE, HEAD, OTHER], CANDIDATE),
            (PULL, [BASE], CANDIDATE),
            (PULL, [BASE, HEAD], OTHER),
        ]
        for pull, parents, returned_sha in cases:
            with self.subTest(pull=pull, parents=parents, returned_sha=returned_sha):
                payload = copy.deepcopy(pull)
                commit = {"sha": returned_sha, "parents": [{"sha": sha} for sha in parents]}
                for reference in ("gh.pr", "gh.pr.checks"):
                    inputs = {"target": "test_merge", "expected_head_sha": HEAD} if reference.endswith("checks") else {}
                    result, _ = self.observe(reference, [payload, commit_evidence(pull, candidate=CANDIDATE), commit], **inputs)
                    self.assertEqual(result.status, "checks_unavailable" if inputs else "ok")
                    self.assertEqual(result.outputs["test_merge_state"], "identity_mismatch")
                    for field in ("test_merge_sha", "test_merge_head_sha", "test_merge_base_sha"):
                        self.assertIsNone(result.outputs[field])

    def test_missing_candidate_never_falls_back_to_head(self):
        result, _ = self.observe("gh.pr.checks", [PULL, commit_evidence()], target="test_merge")
        self.assertEqual(result.status, "checks_unavailable")
        self.assertIsNone(result.outputs["commit_sha"])
        self.assertIsNone(result.outputs["test_merge_sha"])

    def test_merged_result_cannot_be_selected_as_test_merge_target(self):
        pull = {**PULL, "merged": True, "state": "closed"}
        result, _ = self.observe("gh.pr.checks", [pull], target="test_merge")
        self.assertEqual(result.status, "checks_unavailable")
        self.assertEqual(result.outputs["test_merge_state"], "merged")
        self.assertIsNone(result.outputs["commit_sha"])

    def test_missing_head_is_not_an_empty_checks_observation(self):
        result, _ = self.observe("gh.pr.checks", [{"number": 42}])
        self.assertEqual(result.status, "checks_unavailable")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_pr_checks.missing_head_sha")

    def test_empty_checks_are_an_observation_not_generic_success(self):
        result, _ = self.checks()
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.outputs["complete"])
        self.assertEqual(result.outputs["overall_state"], "no_checks")
        self.assertEqual(result.outputs["total_count"], 0)

    def test_run_states_preserve_observation_and_do_not_apply_acceptance_policy(self):
        cases = [("completed", "failure", "failed"), ("in_progress", None, "pending"),
                 ("queued", None, "pending"), ("completed", "skipped", "skipped"),
                 ("completed", "neutral", "neutral"), ("completed", "new_conclusion", "unknown"),
                 ("new_status", None, "unknown"), ("completed", None, "unknown"),
                 ("in_progress", "success", "unknown")]
        for status, conclusion, category in cases:
            with self.subTest(status=status, conclusion=conclusion):
                result, _ = self.checks(runs=[run_page([check_run(conclusion, status=status)])])
                self.assertEqual(result.status, "ok")
                self.assertEqual(result.outputs["overall_state"], category)
                self.assertEqual(result.outputs[f"{category}_count"], 1)
                self.assertEqual(result.outputs["success_count"], 0)
                self.assertEqual(result.outputs["checks"][0]["status"], status)
                self.assertEqual(result.outputs["checks"][0]["conclusion"], conclusion)

    def test_success_plus_neutral_or_skipped_is_mixed(self):
        for conclusion in ("neutral", "skipped"):
            result, _ = self.checks(runs=[run_page([check_run(id=1), check_run(conclusion, id=2)])])
            self.assertEqual(result.outputs["overall_state"], "mixed")
            self.assertEqual(result.outputs["success_count"], 1)

    def test_legacy_error_is_not_rewritten_and_creator_is_not_app_identity(self):
        legacy = {"id": 17, "context": "external", "state": "error", "creator": {"id": 99, "login": "bot"},
                  "created_at": "2026-09-11T10:00:00Z", "updated_at": "2026-09-11T10:01:00Z"}
        result, _ = self.checks(statuses=[status_page([legacy])], runs=[run_page([check_run()])])
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["overall_state"], "failed")
        status, run = result.outputs["checks"]
        self.assertEqual(status["state"], "error")
        self.assertEqual(status["conclusion"], "error")
        self.assertEqual(status["sha"], HEAD)
        self.assertEqual(status["id"], 17)
        self.assertEqual(status["created_at"], legacy["created_at"])
        self.assertEqual(status["updated_at"], legacy["updated_at"])
        self.assertEqual(status["creator"], legacy["creator"])
        self.assertEqual(status["app_identity"], "unavailable")
        self.assertIsNone(status["app_id"])
        self.assertIsNone(status["app_slug"])
        self.assertEqual(run["app_identity"], "available")
        self.assertEqual(run["app_id"], 15368)
        self.assertEqual(run["app_slug"], "github-actions")
        self.assertEqual(run["started_at"], check_run()["started_at"])
        self.assertEqual(run["completed_at"], check_run()["completed_at"])

    def test_legacy_states_remain_distinct(self):
        for state, category in (("success", "success"), ("pending", "pending"), ("failure", "failed"), ("future", "unknown")):
            result, _ = self.checks(statuses=[status_page([{"id": 1, "context": "legacy", "state": state}])])
            self.assertEqual(result.outputs["overall_state"], category)
            self.assertEqual(result.outputs["checks"][0]["state"], state)

    def test_check_suite_metadata_preserves_aggregation_and_legacy_null(self):
        registry = get_public_connector_registry()
        self.assertEqual(registry.get_operation("gh.pr.checks").outputs["checks"][0]["check_suite_id"], "integer")
        legacy = {"id": 17, "context": "external", "state": "success", "check_suite": {"id": 999}}
        for suite, expected in ((None, None), ({}, None), ({"id": None}, None), ({"id": 71}, 71)):
            result, _ = self.checks(statuses=[status_page([legacy])],
                                    runs=[run_page([{**check_run(), "check_suite": suite}])])
            self.assertEqual(result.status, "ok")
            self.assertEqual(result.outputs["overall_state"], "success")
            self.assertEqual(result.outputs["success_count"], 2)
            self.assertIsNone(result.outputs["checks"][0]["check_suite_id"])
            self.assertEqual(result.outputs["checks"][1]["check_suite_id"], expected)
        result, _ = self.checks(runs=[run_page([check_run()])])
        self.assertIsNone(result.outputs["checks"][0]["check_suite_id"])

    def test_malformed_nonnull_check_suite_metadata_is_unavailable(self):
        for suite in (False, 1, "71", [], {"id": True}, {"id": False}, {"id": "71"},
                      {"id": 0}, {"id": -1}, {"id": []}, {"id": 1.5}):
            with self.subTest(suite=suite):
                result, _ = self.checks(runs=[run_page([{**check_run(), "check_suite": suite}])])
                self.assertEqual(result.status, "checks_unavailable")

    def test_missing_run_app_and_sha_are_explicitly_unavailable(self):
        run = check_run()
        del run["app"]
        del run["head_sha"]
        result, _ = self.checks(runs=[run_page([run])])
        self.assertEqual(result.outputs["overall_state"], "unknown")
        self.assertIsNone(result.outputs["checks"][0]["sha"])
        self.assertIsNone(result.outputs["checks"][0]["app_id"])
        self.assertEqual(result.outputs["checks"][0]["app_identity"], "unavailable")

    def test_checks_with_wrong_attached_sha_fail(self):
        result, _ = self.checks(runs=[run_page([check_run(sha=OTHER)])])
        self.assertEqual(result.status, "checks_unavailable")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_pr_checks.check_sha_mismatch")

    def test_status_response_sha_mismatch_fails_even_for_empty_results(self):
        result, _ = self.observe("gh.pr.checks", [PULL, [status_page(sha=OTHER)]])
        self.assertEqual(result.status, "checks_unavailable")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_pr_checks.status_sha_mismatch")

    def test_missing_status_sha_is_null_not_inferred_from_requested_head(self):
        page = status_page([{"id": 1, "context": "legacy", "state": "success"}])
        del page["sha"]
        result, _ = self.checks(statuses=[page])
        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.outputs["checks"][0]["sha"])
        self.assertEqual(result.outputs["overall_state"], "unknown")

    def test_partial_app_identity_preserves_available_field(self):
        run = {**check_run(), "app": {"id": 15368}}
        result, _ = self.checks(runs=[run_page([run])])
        self.assertEqual(result.outputs["checks"][0]["app_id"], 15368)
        self.assertIsNone(result.outputs["checks"][0]["app_slug"])
        self.assertEqual(result.outputs["checks"][0]["app_identity"], "unavailable")

    def test_all_pages_are_included_with_advertised_total(self):
        statuses = [{"id": i, "context": f"status-{i}", "state": "success"} for i in range(1, 102)]
        runs = [check_run(id=i) for i in range(1, 102)]
        result, _ = self.checks(
            statuses=[status_page(statuses[:100], total=101), status_page(statuses[100:], total=101)],
            runs=[run_page(runs[:100], total=101), run_page(runs[100:], total=101)],
        )
        self.assertTrue(result.outputs["complete"])
        self.assertEqual(result.outputs["total_count"], 202)
        self.assertEqual(result.outputs["success_count"], 202)

    def test_truncated_or_drifting_pagination_is_explicitly_incomplete(self):
        cases = [
            [run_page([check_run()], total=2)],
            [run_page([check_run()], total=2), run_page([check_run(id=2)], total=3)],
            [run_page([check_run()], total=2), run_page([check_run()], total=2)],
            [{"check_runs": [check_run()]}],
        ]
        for pages in cases:
            result, _ = self.checks(runs=pages)
            self.assertEqual(result.status, "ok")
            self.assertFalse(result.outputs["complete"])
            self.assertFalse(result.outputs["check_runs_complete"])
            self.assertEqual(result.outputs["overall_state"], "incomplete")
        result, _ = self.checks(statuses=[status_page([], total=1)])
        self.assertFalse(result.outputs["statuses_complete"])

    def test_api_failure_never_reports_success_even_after_partial_pages(self):
        failure = subprocess.CompletedProcess([], 1, json.dumps([status_page()]), "api rate limit exceeded")
        for responses, reference, inputs in (
            ([PULL, failure], "gh.pr.checks", {}),
            ([PULL, [status_page()], failure], "gh.pr.checks", {}),
            ([failure], "gh.pr", {}),
            ([PULL, failure], "gh.pr.checks", {"target": "test_merge"}),
        ):
            result, _ = self.observe(reference, responses, **inputs)
            self.assertNotEqual(result.status, "ok")

    def test_optional_candidate_api_failure_preserves_metadata_and_raw_but_blocks_candidate_checks(self):
        failure = subprocess.CompletedProcess([], 1, "", "api rate limit exceeded")
        payload = copy.deepcopy(PULL)
        for reference, inputs in (("gh.pr", {}), ("gh.pr.checks", {"target": "test_merge"})):
            result, _ = self.observe(reference, [payload, failure], **inputs)
            self.assertEqual(result.status, "ok" if reference == "gh.pr" else "checks_unavailable")
            self.assertEqual(result.outputs["head_sha"], HEAD)
            self.assertEqual(result.outputs["test_merge_state"], "unavailable")
            self.assertEqual(result.outputs["test_merge_reason"], "api_unavailable")
            self.assertEqual(result.raw["test_merge"]["graphql"]["returncode"], 1)
            self.assertEqual(result.raw["test_merge"]["graphql"]["stderr"], failure.stderr)
            for field in ("test_merge_sha", "test_merge_head_sha", "test_merge_base_sha"):
                self.assertIsNone(result.outputs[field])
            if reference == "gh.pr":
                self.assertFalse(result.outputs["merged"])
                self.assertEqual(result.outputs["stack_state"], "standalone")
            else:
                self.assertIsNone(result.outputs["commit_sha"])

    def test_invalid_candidate_sha_is_unavailable_without_path_interpolation(self):
        for sha in ("abc123", "../status", "main?per_page=1", "g" * 40, 123, ""):
            for reference, inputs in (("gh.pr", {}), ("gh.pr.checks", {"target": "test_merge"})):
                result, _ = self.observe(reference, [PULL, commit_evidence(candidate=sha)], **inputs)
                self.assertEqual(result.status, "ok" if reference == "gh.pr" else "checks_unavailable")
                self.assertEqual(result.outputs["test_merge_state"], "unavailable")
                self.assertEqual(result.outputs["test_merge_reason"], "invalid_candidate_sha")
                self.assertIsNone(result.outputs["test_merge_sha"])

    def test_candidate_requires_full_parent_identity_but_legacy_metadata_remains_usable(self):
        payload = {**PULL, "head": {"sha": "abc123"}}
        result, _ = self.observe("gh.pr", [payload])
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["head_sha"], "abc123")
        self.assertEqual(result.outputs["test_merge_reason"], "head_or_base_sha_unavailable")
        self.assertIsNone(result.outputs["test_merge_sha"])

    def test_candidate_full_hex_sha_is_canonicalized_before_api_path(self):
        payload = copy.deepcopy(PULL)
        payload["head"]["sha"] = HEAD.upper()
        payload["base"]["sha"] = BASE.upper()
        commit = {"sha": CANDIDATE.upper(), "parents": [{"sha": BASE.upper()}, {"sha": HEAD.upper()}]}
        result, calls = self.observe("gh.pr", [payload, commit_evidence(candidate=CANDIDATE.upper()), commit])
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["test_merge_sha"], CANDIDATE)
        self.assertIsNone(result.outputs["test_merge_reason"])
        self.assertIn(f"repos/owner/repo/commits/{CANDIDATE}", calls[-1])

    def test_invalid_api_shapes_do_not_look_like_empty_success(self):
        for invalid in ({"statuses": []}, [], [{}], [{"statuses": [None]}],
                        [{"statuses": [{"state": {}}]}]):
            result, _ = self.observe("gh.pr.checks", [PULL, invalid])
            self.assertEqual(result.status, "checks_unavailable")

    def test_graphql_snapshot_mismatch_never_fetches_commit_or_checks(self):
        for field, value in (("number", 43), ("state", "CLOSED"), ("state", "MERGED"),
                             ("merged", True), ("headRefOid", OTHER), ("baseRefOid", OTHER),
                             ("repository", "other/repo")):
            evidence = commit_evidence(candidate=CANDIDATE)
            repository = evidence["data"]["repository"]
            if field == "repository":
                repository["nameWithOwner"] = value
            else:
                repository["pullRequest"][field] = value
            for reference in ("gh.pr", "gh.pr.checks"):
                with self.subTest(field=field, value=value, reference=reference):
                    inputs = {"target": "test_merge"} if reference.endswith("checks") else {}
                    result, calls = self.observe(reference, [PULL, evidence], **inputs)
                    self.assertEqual(result.status, "checks_unavailable" if inputs else "ok")
                    self.assertEqual(result.outputs["test_merge_state"], "identity_mismatch")
                    self.assertEqual(result.outputs["test_merge_reason"], "graphql_snapshot_mismatch")
                    self.assertIsNone(result.outputs["test_merge_sha"])
                    self.assertEqual(calls[-1][2], "graphql")

    def test_graphql_malformed_envelopes_and_partial_errors_are_unavailable(self):
        cases = [None, [], {}, {"data": None}, {"data": []}, {"data": {}},
                 {"data": {"repository": None}}, {"data": {"repository": []}}]
        for field, values in {"nameWithOwner": (None, 42), "pullRequest": (None, [], {})}.items():
            for value in values:
                evidence = commit_evidence(candidate=CANDIDATE)
                evidence["data"]["repository"][field] = value
                cases.append(evidence)
        for errors in (None, {}, "error", [{"message": "partial"}]):
            cases.append({**commit_evidence(candidate=CANDIDATE), "errors": errors})
        for field, values in {
            "number": (None, True, "42"), "state": (None, [], "open"),
            "merged": (None, 1, "false"), "headRefOid": (None, "short", "g" * 40),
            "baseRefOid": (None, "short"), "potentialMergeCommit": ([], {}, {"oid": None}),
            "mergeCommit": ([], {}, {"oid": "short"}),
        }.items():
            for value in values:
                evidence = commit_evidence(candidate=CANDIDATE)
                evidence["data"]["repository"]["pullRequest"][field] = value
                cases.append(evidence)
            evidence = commit_evidence(candidate=CANDIDATE)
            del evidence["data"]["repository"]["pullRequest"][field]
            cases.append(evidence)
        for evidence in cases:
            with self.subTest(evidence=evidence):
                result, calls = self.observe("gh.pr.checks", [PULL, evidence], target="test_merge")
                self.assertEqual(result.status, "checks_unavailable")
                self.assertEqual(result.outputs["test_merge_state"], "unavailable")
                self.assertIsNone(result.outputs["commit_sha"])
                self.assertEqual(calls[-1][2], "graphql")

    def test_early_test_merge_head_pin_mismatch_never_reads_graphql(self):
        result, calls = self.observe("gh.pr.checks", [PULL], target="test_merge", expected_head_sha=OTHER)
        self.assertEqual(result.status, "checks_unavailable")
        self.assertEqual(result.diagnostics[0].code, "probe.gh_pr_checks.head_mismatch")
        self.assertFalse(any("graphql" in call for call in calls))

    def test_graphql_query_binds_requested_pr_and_accepts_empty_errors(self):
        evidence = commit_evidence(candidate=CANDIDATE)
        evidence["errors"] = []
        evidence["data"]["repository"]["nameWithOwner"] = "OWNER/REPO"
        commit = {"sha": CANDIDATE, "parents": [{"sha": BASE}, {"sha": HEAD}]}
        result, calls = self.observe("gh.pr", [PULL, evidence, commit])
        self.assertEqual(result.outputs["test_merge_state"], "verified")
        graphql = calls[-2]
        for argument in ("owner=owner", "repo=repo", "number=42"):
            self.assertIn(argument, graphql)
        query = next(argument for argument in graphql if argument.startswith("query="))
        for field in ("nameWithOwner", "headRefOid", "baseRefOid", "potentialMergeCommit", "mergeCommit"):
            self.assertIn(field, query)

    def test_invalid_optional_candidate_commit_response_preserves_metadata(self):
        for commit in (None, [], {}, {"sha": CANDIDATE, "parents": [None]},
                       {"sha": CANDIDATE, "parents": None},
                       {"sha": "short", "parents": [{"sha": BASE}, {"sha": HEAD}]},
                       {"sha": CANDIDATE, "parents": [{"sha": BASE}, {"sha": "short"}]}):
            for reference, inputs in (("gh.pr", {}), ("gh.pr.checks", {"target": "test_merge"})):
                result, _ = self.observe(reference, [PULL, commit_evidence(candidate=CANDIDATE), commit], **inputs)
                self.assertEqual(result.status, "ok" if reference == "gh.pr" else "checks_unavailable")
                self.assertEqual(result.outputs["head_sha"], HEAD)
                self.assertEqual(result.outputs["test_merge_state"], "unavailable")
                self.assertEqual(result.outputs["test_merge_reason"], "invalid_commit_response")

    def test_immutable_commit_failure_retains_both_reads_and_never_fetches_checks(self):
        failure = subprocess.CompletedProcess([], 1, "", "commit unavailable")
        result, calls = self.observe("gh.pr.checks", [PULL, commit_evidence(candidate=CANDIDATE), failure],
                                     target="test_merge")
        self.assertEqual(result.status, "checks_unavailable")
        self.assertEqual(result.outputs["test_merge_reason"], "api_unavailable")
        self.assertEqual(result.raw["test_merge"]["graphql"]["returncode"], 0)
        self.assertEqual(result.raw["test_merge"]["commit"]["returncode"], 1)
        self.assertIn(f"repos/owner/repo/commits/{CANDIDATE}", calls[-1])
        self.assertIsNone(result.outputs["commit_sha"])

    def test_graphql_transport_and_json_failures_never_fetch_checks(self):
        failures = (subprocess.TimeoutExpired("gh", 30), OSError("offline"),
                    UnicodeError("invalid output"), subprocess.CompletedProcess([], 0, "{broken", ""),
                    subprocess.CompletedProcess([], 1, json.dumps(commit_evidence(candidate=CANDIDATE)), "failed"))
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                result, calls = self.observe("gh.pr.checks", [PULL, failure], target="test_merge")
                self.assertEqual(result.status, "checks_unavailable")
                self.assertEqual(result.outputs["test_merge_state"], "unavailable")
                self.assertIsNone(result.outputs["commit_sha"])
                self.assertEqual(calls[-1][2], "graphql")

    def test_merged_metadata_evidence_failure_preserves_merge_fact_without_inventing_sha(self):
        pull = {**PULL, "state": "closed", "merged": True}
        mismatch = commit_evidence(pull, merged_sha=OTHER)
        mismatch["data"]["repository"]["pullRequest"]["headRefOid"] = OTHER
        for evidence in (commit_evidence(pull), mismatch,
                         {**commit_evidence(pull, merged_sha=OTHER), "errors": [{"message": "partial"}]},
                         subprocess.CompletedProcess([], 1, "", "unavailable")):
            result, calls = self.observe("gh.pr", [pull, evidence])
            self.assertEqual(result.status, "ok")
            self.assertTrue(result.outputs["merged"])
            self.assertIsNone(result.outputs["merge_commit_sha"])
            self.assertIsNone(result.outputs["test_merge_sha"])
            self.assertEqual(result.outputs["test_merge_state"], "merged")
            self.assertEqual(calls[-1][2], "graphql")


if __name__ == "__main__":
    unittest.main()
