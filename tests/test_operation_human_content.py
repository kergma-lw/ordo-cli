"""Reader-facing operation-help content checks."""

import pytest

from ordo.connectors import get_public_connector_registry
from ordo.help_cli import build_operation_response, render_operation_text


def _published_references():
    registry = get_public_connector_registry()
    return sorted(
        f"{connector.namespace}.{operation.name}"
        for connector in registry.connectors
        for operation in connector.operations
    )


@pytest.mark.parametrize("reference", _published_references())
def test_every_published_operation_has_operation_specific_reader_content(reference):
    payload = build_operation_response(reference)
    assert payload is not None
    text = render_operation_text(payload).lower()
    human = payload["human"]

    assert len(text.splitlines()) >= 8
    assert "focused reference" not in text
    assert "connector_contexts." not in text
    assert "_" not in human["title"]
    assert human["summary"].lower() in text
    assert human["goal"].lower() in text
    assert "use when" in {section["heading"].lower() for section in human["sections"]}
    assert "do not use for" in {section["heading"].lower() for section in human["sections"]}

    use_when = next(section for section in human["sections"] if section["heading"] == "Use when")
    assert human["goal"] not in use_when.get("items", [])


@pytest.mark.parametrize(("reference", "required_phrases"), [
    ("gh.issue.create", ("non-empty issue title", "repository-qualified reference")),
    ("gh.project.issue.field_single_select.set", ("visible option label", "whether the value actually changed")),
    ("compose.start", ("declared service name", "whether the request targeted a project or service")),
    ("compose.project", ("declared services", "observation, not a lock")),
    ("compose.service", ("declared compose service name", "`declared` is true", "`state` is the observed service state", "`healthy` is true", "point-in-time observation")),
    ("shell.command", ("standard output", "partial changes")),
    ("runtime.profile.use", ("already declared", "later work in the current run")),
    ("git.sync.push", ("local branch to publish", "rejected non-fast-forward push", "remote branch unchanged")),
    ("git.integrate.rebase_onto", ("branch to rewrite", "upstream boundary", "checks out (switches to) `branch`", "newly rebased head revision")),
    ("git.tags", ("latest", "null when no tag matches")),
    ("git.worktree", ("clean or dirty", "staged, unstaged, or untracked", "repository root")),
    ("git.commit.create", ("staged changes become one new commit", "nothing to commit", "history is unchanged")),
    ("git.sync.push", ("current branch", "configured upstream remote", "rejected non-fast-forward push")),
])
def test_remediated_operations_publish_inputs_results_and_material_boundaries(reference, required_phrases):
    payload = build_operation_response(reference)
    assert payload is not None

    headings = {section["heading"] for section in payload["human"]["sections"]}
    assert {"What to provide", "Result and boundary"} <= headings
    text = render_operation_text(payload).lower()
    assert all(phrase in text for phrase in required_phrases)


def test_context_defaulted_inputs_explain_omission_source_and_override():
    references = ["compose.project"]
    for reference in _published_references():
        payload = build_operation_response(reference)
        assert payload is not None
        if reference.startswith("gh.") and "repository" in payload["operation"]["inputs"]:
            references.append(reference)
    for reference in references:
        payload = build_operation_response(reference)
        assert payload is not None
        text = render_operation_text(payload).lower()
        assert "context-defaulted" in text
        assert "when omitted" in text or "accepts no operation-local target" in text
        assert "playbook or profile settings" in text
        assert "override" in text


def test_compose_operation_examples_are_verified_workflows_with_decision_boundaries():
    for reference in ("compose.project", "compose.service", "compose.start", "compose.stop", "compose.remove"):
        payload = build_operation_response(reference)
        assert payload is not None
        example, = payload["canonical_examples"]
        assert example["form"] == "workflow_fragment"
        assert f"uses: {reference}" in example["yaml"]
        assert "register:" in example["yaml"]
        assert "gate:" in example["yaml"]


@pytest.mark.parametrize("reference", [reference for reference in _published_references() if reference.startswith("git.")])
def test_every_git_operation_names_its_inputs_results_and_boundaries(reference):
    payload = build_operation_response(reference)
    assert payload is not None
    operation = payload["operation"]
    sections = {section["heading"]: " ".join(section.get("items", ())) for section in payload["human"]["sections"]}

    provide = sections["What to provide"].lower()
    result = sections["Result and boundary"].lower()
    assert len(provide) > 60, reference
    assert len(result) > 100, reference
    if operation["inputs"]:
        assert all(name in provide for name in operation["inputs"]), reference
    else:
        assert "no " in provide and "input" in provide, reference
    assert all(name in result for name in operation["outputs"]), reference
    assert any(word in result for word in ("fail", "block", "missing", "invalid", "conflict", "change", "stale", "unreadable", "unavailable")), reference
    assert not any(term in result for term in ("diagnostic", "exit code", "runtime", "fixture", "command")), reference
