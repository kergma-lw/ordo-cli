"""Reader-facing completeness and vocabulary checks for every Git operation."""

from ordo import help_cli
from ordo.help_cli import build_model_response, build_operation_response, render_operation_text


def _git_operations():
    git = next(connector for connector in build_model_response()["connectors"] if connector["namespace"] == "git")
    return git["operations"]


def test_all_git_operations_name_inputs_results_and_material_boundaries():
    operations = _git_operations()
    assert len(operations) == 28
    for operation in operations:
        sections = {section["heading"]: " ".join(section.get("items", ())) for section in operation["human"]["sections"]}
        assert {"Use when", "What to provide", "Result and boundary", "Do not use for"} <= set(sections), operation["name"]
        provide, result = sections["What to provide"], sections["Result and boundary"]
        assert len(provide) > 60 and len(result) > 100, operation["name"]
        if operation["inputs"]:
            assert all(name in provide for name in operation["inputs"]), operation["name"]
        else:
            assert "no " in provide.lower() and "input" in provide.lower(), operation["name"]
        assert all(name in result for name in operation["outputs"]), operation["name"]
        assert any(word in result.lower() for word in ("fail", "block", "missing", "invalid", "conflict", "change", "stale", "unreadable", "unavailable")), operation["name"]


def test_git_operation_guidance_avoids_raw_inline_input_schemas():
    for operation in _git_operations():
        payload = build_operation_response(f"git.{operation['name']}")
        assert payload is not None
        assert "with inputs {" not in render_operation_text(payload).lower(), operation["name"]


def test_git_operation_guidance_uses_reader_facing_actions():
    for operation in _git_operations():
        human = operation["human"]
        text = " ".join(
            [human["title"], human["goal"], human["summary"]]
            + [item for section in human["sections"] for item in section.get("items", ())]
            + [reference["summary"] for section in human["sections"] for reference in section.get("references", ())]
        ).lower()
        assert "probe" not in text, operation["name"]
        assert "surface" not in text, operation["name"]
        assert "authored" not in text, operation["name"]


def test_remote_upstream_and_commits_guides_exclude_implementation_vocabulary():
    forbidden = ("command", "configuration", "exit code", "diagnostic", "fixture", "live i/o", "runtime")
    for name in ("remote", "upstream", "commits"):
        payload = build_operation_response(f"git.{name}")
        assert payload is not None
        text = render_operation_text(payload).lower()
        assert all(term not in text for term in forbidden), name


def test_git_family_guide_requires_one_safe_integration_choice():
    payload = help_cli._focused_target_payload("connector.git", context=help_cli._HelpResponseContext())
    text = help_cli._render_human(payload).lower()

    assert "choose exactly one operation" in text
    assert "merge to record an integration commit" in text
    assert "fast-forward only" in text
    assert "cherry-pick to copy one commit" in text
    assert "rebase onto to rewrite a topic branch" in text
    assert "running several integration strategies one after another" in text
