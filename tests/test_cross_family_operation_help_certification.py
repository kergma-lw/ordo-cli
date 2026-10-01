"""Final reader-help certification across non-GitHub operation families."""

import re
from pathlib import Path

from ordo.help_cli import build_model_response, build_operation_response


def _operation(reference):
    payload = build_operation_response(reference)
    assert payload is not None
    return payload["operation"], {
        section["heading"]: " ".join(section.get("items", ()))
        for section in payload["human"]["sections"]
    }


def test_non_github_input_guides_label_every_reader_input():
    model = build_model_response()
    git = next(connector for connector in model["connectors"] if connector["namespace"] == "git")
    references = [f"git.{operation['name']}" for operation in git["operations"] if operation["inputs"]]
    references += [
        "runtime.profile.use",
        "compose.project",
        "compose.service",
        "compose.start",
        "compose.stop",
        "compose.remove",
        "shell.command",
        "fs.file",
    ]

    # The stated families name 18 Git operations and eight other operations.
    assert len(references) == 26
    for reference in references:
        operation, sections = _operation(reference)
        provide = sections["What to provide"]
        for name in operation["inputs"]:
            assert re.search(
                rf"`{re.escape(name)}`\s*:\s*(?:required|optional|conditional|context-defaulted)",
                provide,
            ), (reference, name, provide)


def test_compose_shell_and_file_guides_name_every_result_for_later_steps():
    for reference in (
        "compose.project",
        "compose.service",
        "compose.start",
        "compose.stop",
        "compose.remove",
        "shell.command",
        "fs.file",
    ):
        operation, sections = _operation(reference)
        result = sections["Result and boundary"]
        assert all(f"`{name}`" in result for name in operation["outputs"]), reference


def test_compose_shell_and_file_help_matches_the_published_runtime_boundaries():
    start, start_sections = _operation("compose.start")
    stop, stop_sections = _operation("compose.stop")
    shell, shell_sections = _operation("shell.command")
    _, file_sections = _operation("fs.file")

    assert "changed_services" not in start["outputs"]
    assert "changed_services" not in stop["outputs"]
    assert "one delayed recovery observation" in start_sections["Result and boundary"]
    assert "does not keep waiting or repeatedly recheck" in start_sections["Result and boundary"]
    assert "bash -lc <command>" in shell_sections["What to provide"]
    assert "trusted author-controlled code" in shell_sections["What to provide"]
    file_text = " ".join(file_sections.values())
    assert "connector.shell.command" not in file_text
    assert "operations" in file_text


def test_pr_outcome_prose_hides_transport_status_and_examples_hide_bootstrap():
    for reference in ("gh.pr.create", "gh.pr.merge", "gh.pr.merge.request"):
        _, sections = _operation(reference)
        text = " ".join(sections.values()).lower()
        assert "http_status" not in text

    payload = build_operation_response("gh.pr.create")
    assert payload is not None
    example = payload["canonical_examples"][0]
    assert "bootstrap" not in example["yaml"].lower()


def test_published_shell_example_never_executes_workflow_controlled_text():
    source = Path(__file__).resolve().parents[1] / "examples" / "shell-command-legacy-compatibility.yaml"
    text = source.read_text(encoding="utf-8")

    assert "command: \"printf 'legacy check'\"" in text
    assert "command: inputs." not in text
    assert "command: ${" not in text
