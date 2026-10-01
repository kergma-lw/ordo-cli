"""Contracts for the canonical reader-facing basic help route."""

from copy import deepcopy
import json

import pytest

from ordo import help_cli
from ordo.model import discovery_catalog
from ordo.model.connector import OPERATIONS_HUMAN, operations_catalog_human
from ordo.model.human import validate_human_mapping
from tools.build_help_site_docs import CLI_ONLY_TOPICS, STATIC_TOPICS, render_human_topic, render_topic


@pytest.mark.parametrize(
    "builder",
    [
        help_cli.build_overview_response,
        help_cli.build_features_response,
        help_cli.build_model_response,
        help_cli.build_workflow_rules_response,
        help_cli.build_capabilities_response,
        help_cli.build_operations_response,
    ],
)
def test_basic_routes_publish_valid_human_contracts(builder):
    payload = builder()
    validate_human_mapping(payload["human"], owner=payload["document_kind"])
    help_cli._validate_human_references(payload)
    assert "filename" not in json.dumps(payload["human"])


def test_text_and_site_do_not_fall_back_to_contract_metadata():
    payload = help_cli.build_model_response()
    changed = deepcopy(payload)
    changed["workflow"]["document_kind"] = "technical-value-that-must-not-render"

    assert "technical-value-that-must-not-render" not in help_cli.render_model_text(changed)
    assert "technical-value-that-must-not-render" not in render_human_topic(changed)


def test_operations_text_and_site_do_not_fall_back_to_connector_contract_metadata():
    payload = help_cli.build_operations_response()
    changed = deepcopy(payload)
    changed["connectors"][0]["bootstrap"]["prerequisites"] = ["technical-value-that-must-not-render"]

    assert "technical-value-that-must-not-render" not in help_cli.render_operations_text(changed)
    assert "technical-value-that-must-not-render" not in render_human_topic(changed)


def test_operations_catalog_human_is_declared_with_connector_contract():
    declaration = operations_catalog_human(help_cli.describe_operations()["connectors"])

    assert declaration.filename == OPERATIONS_HUMAN.filename
    assert declaration.filename.endswith("src/ordo/model/connector.py")
    assert "Catalog by namespace" in [section["heading"] for section in declaration.content["sections"]]


def test_consumers_render_canonical_human_content_without_filtering():
    payload = help_cli.build_overview_response()
    payload["human"]["sections"][0]["items"] = ["ctx.call source sentinel"]

    assert "ctx.call source sentinel" in help_cli.render_overview_text(payload)
    assert "ctx.call source sentinel" in render_human_topic(payload)


def test_features_take_cluster_prose_from_domain_human_sources(monkeypatch):
    workflow = help_cli.describe_workflow_contract()
    workflow["human"]["feature_clusters"]["guards"]["summary"] = "Domain-owned guard sentinel."
    monkeypatch.setattr(help_cli, "describe_workflow_contract", lambda: deepcopy(workflow))

    page = render_human_topic(help_cli.build_features_response())
    assert "Domain-owned guard sentinel." in page
    assert not hasattr(discovery_catalog, "FEATURE_CLUSTER_CONTENT")


def test_features_publish_normalized_adapter_keyword_catalogue():
    keywords = {
        entry["name"]: entry["targets"]
        for entry in help_cli.build_features_response()["human"]["keywords"]
    }

    assert "markdown" in keywords
    assert "markdown.blocks" in keywords
    assert "field" in keywords
    assert {target["handle"] for target in keywords["set"]} == {
        "workflow.local_expression.adapter.json",
    }
    assert "[n]" not in keywords
    assert '["literal-key"]' not in keywords
    for targets in keywords.values():
        for target in targets:
            assert target["handle"] in help_cli.focused_describe_declarations()


def test_feature_map_renders_adapter_keywords_from_the_catalogue_not_syntax_samples():
    payload = help_cli.build_features_response()
    for page in (help_cli.render_features_text(payload), render_human_topic(payload)):
        assert "json: field, many, one, remove, set" in page
        assert "markdown: add, append, blocks, list, list_items, lists" in page
        for syntax_sample in ("[n]", '["literal-key"]', ".one(field=value)", 'find("literal")'):
            assert syntax_sample not in page


def test_human_keyword_catalogue_rejects_duplicate_or_unroutable_entries():
    human = {
        "title": "Example",
        "goal": "Check keyword validation.",
        "summary": "Example reader-facing help.",
        "sections": [],
        "keywords": [
            {"name": "set", "targets": [{"handle": "example.set", "summary": "Example."}]},
            {"name": "set", "targets": [{"handle": "example.other", "summary": "Example."}]},
        ],
    }

    with pytest.raises(ValueError, match="declared more than once"):
        validate_human_mapping(human, owner="example")
    with pytest.raises(ValueError, match="unpublished focused help"):
        help_cli._validate_feature_keyword_targets([
            {"name": "set", "targets": [{"handle": "example.set", "summary": "Example."}]},
        ])


def test_describe_resolves_family_exact_keyword_and_short_keyword_dispatcher(capsys):
    assert help_cli.main(["describe", "markdown"]) == 0
    family = capsys.readouterr().out
    assert family.startswith("markdown\n")
    assert "Markdown sections" in family

    assert help_cli.main(["describe", "markdown.blocks", "--json"]) == 0
    exact = json.loads(capsys.readouterr().out)
    assert exact["document_kind"] == "keyword_guide"
    assert exact["keyword"] == "markdown.blocks"
    assert exact["guide_handle"] == "workflow.local_expression.adapter.markdown"
    assert exact["human"]["summary"] == "Use `blocks` with the markdown adapter."

    assert help_cli.main(["describe", "field"]) == 0
    dispatcher = capsys.readouterr().out
    assert "ordo-help describe json.field" in dispatcher
    assert "ordo-help describe yaml.field" in dispatcher


def test_every_published_keyword_resolves_to_a_guide_or_dispatcher():
    context = help_cli._HelpResponseContext()
    keywords = help_cli.build_features_response(context)["human"]["keywords"]

    for keyword in keywords:
        name = keyword["name"]
        resolved = help_cli._resolve_public_topic(name, context=context)
        assert resolved is not None, name
        payload, renderer = resolved
        assert renderer is help_cli._render_human
        if len(keyword["targets"]) == 1:
            assert payload["document_kind"] == "keyword_guide", name
            assert payload["keyword"] == name
        else:
            assert payload["document_kind"] == "keyword_dispatcher", name
            assert [target["handle"] for target in payload["targets"]] == [
                target["handle"] for target in keyword["targets"]
            ]


def test_feature_page_keeps_cluster_navigation_compact():
    page = render_human_topic(help_cli.build_features_response())

    for phrase in (
        "## Playbook", "### Public names", "Admission control for a path",
        "A limited project-local helper path",
    ):
        assert phrase in page
    for heading in ("### Use when", "### Avoid when", "### Inspect next", "### Related rules", "### Published examples"):
        assert heading not in page


def test_basic_pages_preserve_domain_guidance_not_just_titles():
    model = render_human_topic(help_cli.build_model_response())
    rules = render_human_topic(help_cli.build_workflow_rules_response())
    capabilities = render_human_topic(help_cli.build_capabilities_response())

    assert "Keep state safe" in model
    assert "### Why" in rules and "### Prefer" in rules and "### Avoid" in rules
    assert "### Do not infer" in capabilities and "### Why" in capabilities


@pytest.mark.parametrize(
    "builder,renderer",
    [
        (help_cli.build_overview_response, help_cli.render_overview_text),
        (help_cli.build_features_response, help_cli.render_features_text),
        (help_cli.build_model_response, help_cli.render_model_text),
        (help_cli.build_workflow_rules_response, help_cli.render_workflow_rules_text),
        (help_cli.build_capabilities_response, help_cli.render_capabilities_text),
    ],
)
def test_basic_human_text_and_site_withhold_implementation_terms(builder, renderer):
    payload = builder()
    rendered = "\n".join((renderer(payload), render_human_topic(payload), str(payload["human"]))).lower()

    for term in (
        "ctx.call", "caller_slot", "state_deferral", "validation.workflow", "↔", "reads from:",
        "graphql", "head_repository_key", "json-shaped", "serialized envelope", "diagnostic",
    ):
        assert term not in rendered


def test_workflow_rule_reader_guides_omit_internal_classifications():
    text = help_cli.render_workflow_rules_text(help_cli.build_workflow_rules_response())
    focused = help_cli._render_human(help_cli._focused_target_payload("workflow-rules.routine.*", context=help_cli._HelpResponseContext()))

    for rendered in (text, focused):
        assert "Priority" not in rendered
        assert "Guidance level" not in rendered
        assert "opaque local-automation" not in rendered
    assert "published operations and clear compositions" in focused


def test_human_reference_integrity_rejects_unknown_handles():
    payload = help_cli.build_overview_response()
    payload["human"]["sections"][0]["references"][0]["handle"] = "not-published"

    with pytest.raises(ValueError, match="unpublished handle"):
        help_cli._validate_human_references(payload)


def test_search_uses_capability_human_content_only(monkeypatch):
    payload = help_cli.describe_capabilities()
    capability = payload["capabilities"][0]
    capability.update(name="technical-name", scope="technical-scope", status="technical-status")
    capability["human"] = {
        "title": "Readable capability",
        "goal": "Find the readable boundary.",
        "summary": "A reader-facing summary.",
        "sections": [{"heading": "Use", "items": ["Use this for readable work."]}],
    }
    monkeypatch.setattr(help_cli, "describe_capabilities", lambda: payload)

    technical = help_cli.build_search_response("technical-scope")["facts"]
    readable = help_cli.build_search_response("readable boundary")["facts"]
    assert not any(item["kind"] == "capability" and item["name"] == "technical-name" for item in technical)
    assert not any(item["kind"] == "capability" and item["name"] == "technical-name" for item in readable)


def test_basic_topic_search_uses_canonical_human_content_only():
    payload = help_cli.build_overview_response()
    payload["human"]["sections"][0].setdefault("items", []).append("human-only topic search phrase")
    payload["purpose"] = "technical sibling search phrase"

    readable = help_cli.build_search_response(
        "human-only topic search phrase", human_surfaces={"overview": payload},
    )
    technical = help_cli.build_search_response(
        "technical sibling search phrase", human_surfaces={"overview": payload},
    )

    assert any(item["name"] == "overview" for item in readable["topics"])
    assert not any(item["name"] == "overview" for item in technical["topics"])


def test_examples_text_site_and_search_use_its_canonical_human_catalog():
    payload = help_cli.build_examples_response()
    payload["examples"][0]["definition"] = "contract-only example sentinel"

    text = help_cli.render_examples_text(payload)
    site = render_topic("topics/examples.md", "examples", payload)
    search = help_cli.build_search_response("working repository example")

    assert "Minimal workflow example" in text and "Minimal workflow example" in site
    assert "contract-only example sentinel" not in text and "contract-only example sentinel" not in site
    assert any(item["name"] == "examples" for item in search["topics"])
    assert "examples" in STATIC_TOPICS


def test_snippet_coverage_text_and_search_use_canonical_human_content_and_stays_cli_only():
    payload = help_cli.build_snippet_coverage_response()
    payload["purpose"] = "contract-only coverage sentinel"

    text = help_cli.render_snippet_coverage_text(payload)
    search = help_cli.build_search_response("checked examples")

    assert "Coverage reports whether" in text
    assert "contract-only coverage sentinel" not in text
    assert any(item["name"] == "snippet-coverage" for item in search["topics"])
    assert "snippet-coverage" in CLI_ONLY_TOPICS and "snippet-coverage" not in STATIC_TOPICS


def test_focused_describe_renders_target_human_guidance_without_metadata_fallback():
    context = help_cli._HelpResponseContext()
    node = deepcopy(context.lookup("model")["workflow.profile"])
    declaration = help_cli.focused_describe_declarations()["workflow.profile"]
    node["human"] = deepcopy(declaration.content)
    node["human"]["summary"] = "Target-owned reader guidance sentinel."
    node["metadata"]["contract_only"] = "contract-only focused sentinel"
    focused = help_cli._focused_describe_payload(node, declaration)
    focused["metadata"]["contract_only"] = "changed contract metadata sentinel"

    text = help_cli._render_human(focused)

    assert declaration.content["summary"] in text
    assert "Target-owned reader guidance sentinel." not in text
    assert "changed contract metadata sentinel" not in text


def test_search_page_text_and_index_use_canonical_human_content_and_stays_cli_only():
    payload = help_cli.build_search_response("reader-facing help")

    text = help_cli.render_search_text(payload)
    search = help_cli.build_search_response("Find a public help topic")

    assert "Search matches only published reader-facing help" in text
    assert "model_field" not in text
    assert any(item["name"] == "search" for item in search["topics"])
    assert "search" in CLI_ONLY_TOPICS and "search" not in STATIC_TOPICS
