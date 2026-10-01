"""Reader-facing discovery regressions for issue #593."""

import json
import subprocess
from pathlib import Path

from ordo import help_cli
from tools.build_help_site_docs import render_human_topic, render_root_index, render_topic


ROOT = Path(__file__).resolve().parents[1]


def test_root_and_features_teach_the_focused_describe_path_in_text_and_site():
    root = help_cli.build_root_response()
    features = help_cli.build_features_response()

    for rendered in (
        help_cli.render_root_text(root),
        render_root_index(root, [], []),
        help_cli.render_features_text(features),
        render_human_topic(features),
    ):
        assert "ordo-help describe <handle>" in rendered


def test_search_finds_related_authoring_concepts_from_human_content():
    for query in (
        "include run profile switch",
        "playbook workflows defaults pre-run",
        "profile overrides launchers",
    ):
        result = help_cli.build_search_response(query)
        assert any(topic["name"] == "features" for topic in result["topics"]), query


def test_hyphenated_goal_query_finds_pr_creation_from_human_content():
    result = help_cli.build_search_response("pull-request-creation")

    assert any(item["name"] == "connector.gh.pr.create" for item in result["facts"])


def test_github_family_navigation_covers_each_public_work_area():
    rendered = help_cli._render_human(
        help_cli._focused_target_payload("connector.gh", context=help_cli._HelpResponseContext())
    )

    for handle in (
        "connector.gh.issue",
        "connector.gh.pr",
        "connector.gh.actions.run",
        "connector.gh.project",
        "connector.gh.repo",
    ):
        assert handle in rendered


def test_github_family_map_explains_pr_actions_and_async_merge_handoffs():
    rendered = help_cli._render_human(
        help_cli._focused_target_payload("connector.gh", context=help_cli._HelpResponseContext())
    ).lower()

    for phrase in (
        "pull-request decisions", "not an automatic selection", "exact open duplicate",
        "actions attempts", "run id and attempt", "same attempt",
        "async merge lifecycle", "save the returned request id", "not proof that the pull request has merged",
    ):
        assert phrase in rendered


def test_git_family_map_groups_and_links_every_public_operation():
    payload = help_cli._focused_target_payload("connector.git", context=help_cli._HelpResponseContext())
    rendered = help_cli._render_human(payload)
    git = next(connector for connector in help_cli.build_model_response()["connectors"] if connector["namespace"] == "git")

    for heading in ("Inspect local state", "Inspect history and labels", "Change branches and history", "Synchronize and integrate"):
        assert heading.lower() in rendered.lower()
    for operation in git["operations"]:
        assert f"connector.git.{operation['name']}" in rendered


def test_project_field_navigation_uses_only_concrete_published_handles():
    for handle in (
        "connector.gh.project.field",
        "connector.gh.project.issue",
        "connector.gh.project.issue.add",
    ):
        rendered = help_cli._render_human(
            help_cli._focused_target_payload(handle, context=help_cli._HelpResponseContext())
        )
        assert "field_*" not in rendered

    catalog = help_cli.render_operations_text(help_cli.build_operations_response())
    assert "shell.command (action) [legacy-only; do not use for new workflows]" in catalog


def test_launcher_example_explains_legacy_status_and_related_navigation():
    payload = help_cli.build_examples_response()
    catalog = help_cli.render_examples_text(payload)
    focused = help_cli._render_human(
        help_cli._focused_target_payload("examples.launcher-step", context=help_cli._HelpResponseContext())
    )

    assert "retained for compatibility with older workflows" in catalog
    assert "Legacy compatibility example" in focused
    assert "profile.launchers" in focused
    assert "workflow-rules.routine.*" in focused
    assert help_cli._focused_target_payload(
        "workflow-rules.routine.*", context=help_cli._HelpResponseContext(),
    ) is not None


def test_model_navigation_uses_a_supported_focused_workflow_handle():
    model = help_cli.build_model_response()
    rendered = help_cli.render_model_text(model)
    site = render_topic("topics/model.md", "model", model)

    assert "ordo-help describe workflow.workflow" in rendered
    assert "ordo-help describe playbook.workflows" in site
    assert "- workflow.workflow:" not in rendered
    assert help_cli._focused_target_payload("workflow.workflow", context=help_cli._HelpResponseContext())["name"] == "workflow.workflow"


def test_model_navigates_to_the_complete_routine_example_without_an_internal_identifier():
    model = help_cli.build_model_response()
    text = help_cli.render_model_text(model)
    site = render_topic("topics/model.md", "model", model)

    for rendered in (text, site):
        assert "routine_bundle_registry_and_implementation" not in rendered
        assert "ordo-help describe routine_contract" in rendered
        assert "ordo-help describe routine`" not in rendered
        assert "example below" not in rendered

    assert "- Run `ordo-help describe routine_contract`: Use a narrow local-automation fallback" in text
    assert "- `ordo-help describe routine_contract`: Use a narrow local-automation fallback" in site


def test_examples_site_links_repository_examples_and_explains_snippet_distinction():
    rendered = render_topic("topics/examples.md", "examples", help_cli.build_examples_response())

    assert "[examples/minimal.yaml](../examples/minimal.yaml)" in rendered
    assert "Repository examples are complete files verified in this repository" in rendered
    assert "snippet-backed example is a smaller excerpt" in rendered


def test_site_root_renders_recommended_first_calls_once():
    rendered = render_root_index(help_cli.build_root_response(), [], [])

    assert rendered.count("## Recommended first calls") == 1
    assert "## Reference index" not in rendered


def test_reader_facing_cleanup_keeps_paths_shell_fallbacks_and_examples_clear():
    file_probe = help_cli._render_human(
        help_cli._focused_target_payload("connector.fs.file", context=help_cli._HelpResponseContext())
    )
    shell = help_cli._render_human(
        help_cli._focused_target_payload("connector.shell.command", context=help_cli._HelpResponseContext())
    )
    coverage = help_cli.render_snippet_coverage_text(help_cli.build_snippet_coverage_response())

    assert "textual Path projections" not in file_probe
    assert "registered content" not in file_probe
    assert "path text you supplied" in file_probe
    assert "typed domain semantics" not in shell
    assert "defined inputs, results, and safety boundaries" in shell
    assert "intentionally conceptual" in coverage
    assert "not a request to create an example" in coverage
    assert "workflow.run_contract" in coverage


def test_search_finds_run_contract_for_repeated_work_from_human_content():
    result = help_cli.build_search_response("repeat workflow work for each selected item")

    assert any(item["name"] == "workflow.run_contract" for item in result["facts"])


def test_compose_start_explains_success_separately_from_readiness():
    rendered = help_cli._render_human(
        help_cli._focused_target_payload("connector.compose.start", context=help_cli._HelpResponseContext())
    )

    assert "Neither result proves application-level readiness for a later step." in rendered
    assert "It can still succeed when that observation finds `running`, `starting`, or `degraded`" in rendered
    assert "For readiness beyond this action, inspect connector.compose.project or connector.compose.service again" in rendered
    assert "connector.compose.service" in rendered


def test_capabilities_keep_authoring_boundaries_without_internal_mvp_framing():
    rendered = help_cli.render_capabilities_text(help_cli.build_capabilities_response())

    assert "MVP" not in rendered
    assert "synthetic" not in rendered
    assert "cross-iteration" not in rendered
    assert "A skipped optional step has no result to name for later reads" in rendered
    assert "Checking one child workflow does not establish safety across separate calls or repeated work" in rendered


def test_capabilities_reconcile_supported_step_forms_and_include_caller_bindings():
    rendered = help_cli.render_capabilities_text(help_cli.build_capabilities_response())

    for phrase in (
        "Use `run` to invoke a named reusable target",
        "pair `for_each` with inline `steps`",
        "Use `profile_switch` to select another declared profile",
        "Use `result` for one ordered result value and `publish` for a named caller-facing payload",
        "to a `uses` operation or `run` target",
        "An include binding is evaluated in the caller context",
        "earlier registered step output",
        "receives only values declared as `args.name`",
    ):
        assert phrase in rendered


def test_profile_overrides_explain_the_no_implicit_change_boundary_without_opaque_ownership_terms():
    rendered = help_cli._render_human(
        help_cli._focused_target_payload("profile.overrides.with", context=help_cli._HelpResponseContext())
    )

    assert "consumer-owned" not in rendered
    assert "opaque payload" not in rendered
    assert "does not treat its keys as built-in workflow behavior" in rendered


def test_focused_representation_adapter_rule_renders_stop_when_once():
    rendered = help_cli._render_human(
        help_cli._focused_target_payload("workflow-rules.representation_adapters", context=help_cli._HelpResponseContext())
    )

    assert rendered.count("stop when:") == 1


def test_workflow_rules_topic_uses_reader_facing_headings_without_internal_identifiers():
    rendered = help_cli.render_workflow_rules_text(help_cli.build_workflow_rules_response())
    focused = help_cli._render_human(
        help_cli._focused_target_payload("workflow-rules.early_guards", context=help_cli._HelpResponseContext())
    )

    assert "declare applicability early:" in rendered
    assert "early_guards:" not in rendered
    assert "technical identifier:" not in rendered
    assert "`workflow-rules.early_guards`" in focused
    assert focused.splitlines()[0] == "Declare applicability early"


def test_capabilities_topic_uses_reader_facing_headings_without_internal_identifiers():
    rendered = help_cli.render_capabilities_text(help_cli.build_capabilities_response())

    assert "workflow branching:" in rendered
    assert "workflow.branching:" not in rendered
    assert "optional steps cannot register results:" in rendered
    assert "workflow_step.if_conflicts_with_register:" not in rendered
    assert "technical identifier:" not in rendered


def test_operations_topic_gives_actionable_routine_fallback_guidance_with_a_resolved_reference():
    payload = help_cli.build_operations_response()
    focused = help_cli._focused_target_payload("workflow-rules.routine.*", context=help_cli._HelpResponseContext())

    text = help_cli.render_operations_text(payload)
    site = render_human_topic(payload)
    for rendered in (text, site):
        assert "name the remaining gap" in rendered
        assert "mechanical or intentionally project-local task" in rendered
        assert "semantic, clarify it with the user" in rendered
        assert "workflow-rules.routine.*" in rendered
    assert "Run `ordo-help describe workflow-rules.routine.*`" in text
    assert focused is not None


def test_public_human_references_must_resolve_through_describe():
    payload = {
        "document_kind": "test",
        "human": {
            "title": "Title", "goal": "Goal", "summary": "Summary",
            "sections": [{"heading": "Links", "references": [{"handle": "playbook", "summary": "Not describable"}]}],
        },
    }

    try:
        help_cli._validate_human_references(payload)
    except ValueError as error:
        assert "unpublished handle playbook" in str(error)
    else:
        raise AssertionError("non-describable model nodes must not be rendered as navigation")


def test_all_published_focused_help_is_readiness_reviewed():
    result = subprocess.run(
        ["ordo-playbook", "run", "not-ready-describe-handles"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["published"][0]["count"] == 0


def test_describe_readiness_omits_unpublished_routine_handle():
    readiness = json.loads((ROOT / ".ordo" / "describe-readiness.json").read_text(encoding="utf-8"))["handles"]

    assert "routine" not in help_cli.focused_describe_declarations()
    assert "routine" not in readiness
