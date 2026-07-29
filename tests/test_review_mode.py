import unittest

from ordo.model.profile import Profile
from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Guard, GuardBlock, OperationRef, Step, StepBlock, Workflow
from ordo.runtime import review_workflow
from ordo.runtime.reviewing import _review_input_classification

from tests.support import STANDARD_CONNECTOR_PROVIDER


class ReviewModeTest(unittest.TestCase):
    def test_review_reports_missing_input_validation(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string", "unused": "string"},
            steps=(Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["review_status"], "needs_attention")
        self.assertTrue(any(item["code"] == "review.workflow.input_validation_missing" for item in result.outputs["findings"]))
        validation = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.input_validation_missing")
        self.assertEqual(validation["evidence"]["classification"], "effect_target_input")

    def test_review_reports_unused_declared_input_separately(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string", "unused": "string"},
            steps=(Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        unused = next(item for item in result.outputs["findings"] if item["code"] == "review.workflow.input_declared_but_unused")
        self.assertEqual(unused["path"], ["inputs", "unused"])
        self.assertEqual(unused["evidence"]["classification"], "unused_input")

    def test_review_reports_missing_recommended_observations(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            inputs={"repository": "acme/repo", "issue_number": 7, "project_id": "PVT_demo"},
            blocks=(
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "${inputs.repository}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "Status",
                                    "option": "In review",
                                },
                            ),
                        ),
                    )
                ),
                GuardBlock(guards=(Guard(OperationRef("git.worktree")),)),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertTrue(any(item["code"] == "review.workflow.missing_recommended_observations" for item in result.outputs["findings"]))

    def test_review_recognizes_recommended_observations_from_let_bound_guard_probes(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="close-story",
            declared_inputs={"repository": {}, "issue_number": {}, "project_id": {}},
            let_bindings={
                "story_project_issue": "gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number, project_id=inputs.project_id)"
            },
            blocks=(
                GuardBlock(
                    guards=(
                        Guard(expr="story_project_issue.exists"),
                        Guard(expr='gh.project.field(project_id=inputs.project_id, field="Status").exists'),
                        Guard(expr='gh.project.field.option(project_id=inputs.project_id, field="Status", option="Done").exists'),
                    )
                ),
                StepBlock(
                    steps=(
                        Step(
                            name="set-status",
                            operation=OperationRef(
                                "gh.project.issue.field_single_select.set",
                                with_={
                                    "repository": "${inputs.repository}",
                                    "issue_number": "${inputs.issue_number}",
                                    "project_id": "${inputs.project_id}",
                                    "field": "Status",
                                    "option": "Done",
                                },
                            ),
                        ),
                    )
                ),
            ),
            inputs={"repository": "acme/repo", "issue_number": 7, "project_id": "PVT_demo"},
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertFalse(any(item["code"] == "review.workflow.missing_recommended_observations" for item in result.outputs["findings"]))

    def test_review_reports_clean_when_no_findings_exist(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string"},
            blocks=(
                GuardBlock(guards=(Guard(expr="inputs.repository | is_string"),)),
                StepBlock(
                    steps=(
                        Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),
                    )
                ),
            ),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        self.assertEqual(result.outputs["review_status"], "clean")
        self.assertEqual(result.outputs["finding_count"], 0)
        self.assertEqual(result.outputs["findings"], [])

    def test_review_ignores_profile_carried_ambient_context_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="set-active-profile",
            declared_inputs={
                "active_profile_key": {},
                "profile": {},
                "repo_kind": {},
                "repo_dir": {},
                "repository": {},
                "project_id": {},
            },
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.profile == "frontend" or inputs.profile == "backend" or inputs.profile == "meta"'),)),
                StepBlock(
                    steps=(
                        Step(name="Switch runtime profile", profile_switch="${inputs.profile}"),
                        Step(name="Remember active profile", state_set={"state.shared[inputs.active_profile_key]": "${inputs.profile}"}),
                    )
                ),
            ),
        )
        profile = Profile(
            name="backend",
            inputs={
                "repo_kind": "backend",
                "repo_dir": "/tmp/backend",
                "repository": "acme/backend",
                "project_id": "PVT_demo",
            },
        )

        result = review_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertEqual(result.status, RuntimeStatus.OK)
        messages = [item["message"] for item in result.outputs["findings"]]
        self.assertTrue(any("active_profile_key" in message for message in messages))
        self.assertFalse(any("repo_kind" in message for message in messages))
        self.assertFalse(any("repo_dir" in message for message in messages))
        self.assertFalse(any("repository" in message for message in messages))
        self.assertFalse(any("project_id" in message for message in messages))

    def test_review_classifies_profile_provided_consumed_inputs_as_trusted(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="issue-view",
            declared_inputs={"profile": {}, "number": {}, "repository": {}, "project_id": {}},
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.profile == "backend"'), Guard(expr="inputs.number | is_integer"))),
                StepBlock(
                    steps=(
                        Step(name="load issue", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": "${inputs.number}"})),
                        Step(name="publish", publish={"repository": "${inputs.repository}", "project_id": "${inputs.project_id}"}),
                    )
                ),
            ),
        )
        profile = Profile(
            name="backend",
            inputs={
                "repository": "acme/backend",
                "project_id": "PVT_demo",
            },
        )

        result = review_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        all_classifications = {
            item["input"]: item["classification"]
            for item in result.analysis_tree.input_usages
        }
        self.assertEqual(all_classifications["repository"], "contract_input")
        repository_usage = next(item for item in result.analysis_tree.input_usages if item["input"] == "repository")
        project_usage = next(item for item in result.analysis_tree.input_usages if item["input"] == "project_id")
        self.assertEqual(_review_input_classification(repository_usage, profile=profile), "trusted_profile_input")
        self.assertEqual(_review_input_classification(project_usage, profile=profile), "trusted_profile_input")
        self.assertEqual(result.status, RuntimeStatus.OK)

    def test_review_does_not_warn_for_trusted_profile_provided_consumed_inputs(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="issue-view",
            declared_inputs={"profile": {}, "number": {}, "repository": {}, "project_id": {}},
            blocks=(
                GuardBlock(guards=(Guard(expr='inputs.profile == "backend"'), Guard(expr="inputs.number | is_integer"))),
                StepBlock(
                    steps=(
                        Step(name="load issue", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": "${inputs.number}"})),
                        Step(name="publish", publish={"repository": "${inputs.repository}", "project_id": "${inputs.project_id}"}),
                    )
                ),
            ),
        )
        profile = Profile(name="backend", inputs={"repository": "acme/backend", "project_id": "PVT_demo"})

        result = review_workflow(workflow, profile=profile, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertFalse(any(item["code"] == "review.workflow.input_validation_missing" for item in result.outputs["findings"]))

    def test_review_keeps_missing_validation_for_user_driven_effect_target_input(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="open-task",
            declared_inputs={"repository": "string"},
            steps=(Step(name="inspect", operation=OperationRef("gh.issue", with_={"repository": "${inputs.repository}", "issue_number": 7})),),
        )

        result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

        self.assertTrue(any(item["code"] == "review.workflow.input_validation_missing" for item in result.outputs["findings"]))
