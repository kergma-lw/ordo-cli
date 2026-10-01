"""Canonical human-content checks for the command-line help surface."""

from copy import deepcopy

from ordo import help_cli
from ordo.model.command_line import COMMAND_LINE_HUMAN
from ordo.model.human import human_mapping
from tools.build_help_site_docs import render_human_topic


FORBIDDEN_HUMAN_TERMS = (
    "serialized envelope",
    "caller_slot",
    "source coverage",
    "diagnostic IDs",
    "graph-layout",
    "fixture",
    "harness",
    "backend",
    "raw JSON",
)


def test_command_line_human_preserves_the_public_baseline_purpose():
    text = help_cli.render_command_line_text(help_cli.build_command_line_response())

    for term in (
        "workflows list",
        "workflows show <workflow>",
        "check <workflow>",
        "review <workflow>",
        "plan <workflow>",
        "run <workflow>",
        "--file PATH",
        "--profile NAME",
        "--input KEY=VALUE",
        "--input-file KEY=PATH",
        "--progress-steps",
        "--json",
        "next",
        "graph",
    ):
        assert term in text
    assert "readiness and workflow quality are separate questions" in text


def test_command_line_human_makes_graph_discoverable_without_teaching_mechanics():
    rendered = (
        help_cli.render_command_line_text(help_cli.build_command_line_response()),
        render_human_topic(help_cli.build_command_line_response()),
    )

    for text in rendered:
        assert "`ordo-playbook graph`" in text
        assert "which workflows write, read, or remove that data" in text
        assert "relationships, not a required run order" in text
        assert "No active task is required" in text
        assert "+field" not in text
        assert "↔" not in text


def test_command_line_human_explains_same_key_input_precedence():
    text = help_cli.render_command_line_text(help_cli.build_command_line_response())

    assert "workflow's declared default is used first" in text
    assert "playbook workflow binding replaces it" in text
    assert "command-line value replaces all of those" in text
    assert "--input-file` wins" in text


def test_command_line_human_preserves_caller_and_readiness_boundaries():
    text = help_cli.render_command_line_text(help_cli.build_command_line_response())

    assert "workflows show <workflow>" in text
    assert "whether the workflow can run now" in text
    assert "readiness and workflow quality are separate questions" in text


def test_command_line_human_is_owned_outside_the_renderers():
    payload = help_cli.build_command_line_response()

    assert payload["human"] == human_mapping(COMMAND_LINE_HUMAN)
    assert help_cli.render_command_line_text(payload) == help_cli._render_human(payload)
    assert render_human_topic(payload).split("\n", 1)[0] == "# Command-line reference"


def test_command_line_consumers_do_not_fall_back_to_contract_metadata():
    payload = deepcopy(help_cli.build_command_line_response())
    payload["commands"][0]["purpose"] = "contract-only-sentinel"

    assert "contract-only-sentinel" not in help_cli.render_command_line_text(payload)
    assert "contract-only-sentinel" not in render_human_topic(payload)
    result = help_cli.build_search_response("contract-only-sentinel", human_surfaces={"command-line": payload})
    assert not any(topic["name"] == "command-line" for topic in result["topics"])


def test_command_line_human_text_and_site_avoid_implementation_jargon():
    payload = help_cli.build_command_line_response()
    reader_text = f"{help_cli.render_command_line_text(payload)}\n{render_human_topic(payload)}".lower()

    assert all(term not in reader_text for term in FORBIDDEN_HUMAN_TERMS)
