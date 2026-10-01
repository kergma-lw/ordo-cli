"""Completeness coverage for every published GitHub operation guide."""

import re

from ordo.help_cli import build_model_response, build_operation_response


def test_all_github_operations_name_inputs_results_and_material_boundaries():
    gh = next(connector for connector in build_model_response()["connectors"] if connector["namespace"] == "gh")
    assert len(gh["operations"]) == 34
    for operation in gh["operations"]:
        sections = {section["heading"]: " ".join(section.get("items", ())) for section in operation["human"]["sections"]}
        assert {"Use when", "What to provide", "Result and boundary", "Do not use for"} <= set(sections), operation["name"]
        provide, result = sections["What to provide"], sections["Result and boundary"]
        assert "relevant values" not in provide + result
        assert "appropriate result" not in provide + result
        assert all(re.search(rf"`{re.escape(name)}`:\s*(?:required|optional|conditional|context-defaulted)", provide)
                   for name in operation["inputs"]), operation["name"]
        reader_outputs = (name for name in operation["outputs"] if name != "http_status")
        assert all(name in result for name in reader_outputs), operation["name"]
        assert "Material constraint:" in result, operation["name"]


def test_actions_and_merge_request_reader_content_excludes_implementation_terms():
    gh = next(connector for connector in build_model_response()["connectors"] if connector["namespace"] == "gh")
    forbidden = re.compile(r"\b(?:api|transport|diagnostic|fixture|handler|sdk)\b", re.IGNORECASE)
    for operation in gh["operations"]:
        if operation["name"] not in {"actions.run", "actions.run.jobs", "pr.merge.request"}:
            continue
        text = " ".join(
            item
            for section in operation["human"]["sections"]
            for item in section.get("items", ())
        )
        assert not forbidden.search(text), operation["name"]
        response = build_operation_response(f"gh.{operation['name']}")
        assert response is not None
        example_text = " ".join(example["summary"] for example in response["canonical_examples"])
        assert not forbidden.search(example_text), operation["name"]


def test_actions_run_appends_only_its_missing_canonical_input_statuses():
    response = build_operation_response("gh.actions.run")
    assert response is not None
    sections = {section["heading"]: " ".join(section.get("items", ()))
                for section in response["human"]["sections"]}
    provide = sections["What to provide"]

    statuses = {
        "repository": "context-defaulted",
        "run_id": "conditional",
        "check_suite_id": "conditional",
        "attempt": "optional",
    }
    assert set(response["operation"]["inputs"]) == set(statuses)
    for name, status in statuses.items():
        assert f"`{name}`: {status}" in provide
    assert "Input status:" not in provide


def test_pr_create_publishes_each_canonical_input_status_once():
    response = build_operation_response("gh.pr.create")
    assert response is not None
    sections = {section["heading"]: " ".join(section.get("items", ()))
                for section in response["human"]["sections"]}
    provide = sections["What to provide"]

    statuses = {
        "repository": "context-defaulted",
        "head": "required",
        "base": "required",
        "title": "required",
        "body": "optional",
        "draft": "required",
        "head_repository": "conditional",
        "head_owner": "conditional",
    }
    assert set(response["operation"]["inputs"]) == set(statuses)
    for name, status in statuses.items():
        assert provide.count(f"`{name}`: {status}") == 1
    assert "`head_owner`: optional" not in provide


def test_pr_merge_request_publishes_each_required_input_status_once():
    response = build_operation_response("gh.pr.merge.request")
    assert response is not None
    sections = {section["heading"]: " ".join(section.get("items", ()))
                for section in response["human"]["sections"]}
    provide = sections["What to provide"]

    for name in ("pull_number", "request_id"):
        assert provide.count(f"`{name}`: required") == 1
