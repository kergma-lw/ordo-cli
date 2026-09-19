"""Regression contracts for response-local help catalog and lookup reuse."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from ordo import help_cli
from ordo.model import help_snippets


LOOKUP_BUILDERS = (
    "_build_capability_lookup",
    "_build_model_node_lookup",
    "_build_command_line_node_lookup",
    "_build_workflow_rules_node_lookup",
    "_build_examples_node_lookup",
)


class _NoReuseHelpResponseContext(help_cli._HelpResponseContext):
    """Reference response assembly using fresh lookups and snippet catalogs.

    Inherit the original class before monkeypatching its public module binding;
    builders receive this instance explicitly, so construction cannot recurse.
    Excerpt reads within each catalog still use the current implementation:
    this reference isolates response reuse, not historical file-read behavior.
    """

    def lookup(self, topic):
        if topic == "workflow-rules":
            return help_cli._build_workflow_rules_node_lookup()
        builder = {
            "examples": help_cli._build_examples_node_lookup,
            "model": help_cli._build_model_node_lookup,
            "command-line": help_cli._build_command_line_node_lookup,
            "capabilities": help_cli._build_capability_lookup,
        }[topic]
        return builder(context=self)

    def snippet_surface(self, handle):
        return help_cli._snippet_surface_for_handle(handle)


@pytest.fixture
def small_registry(monkeypatch):
    # Keep the real validator and excerpt renderer, without walking the large
    # published registry or executing any snippet/workflow.
    example = {
        "name": "first",
        "kind": "positive",
        "form": "field_fragment",
        "summary": "Synthetic excerpt",
        "source_excerpt": {"path": "first.yaml", "start_line": 1, "end_line": 2},
        "verification": {"kind": "excerpt_verified", "example": "synthetic"},
    }
    entry = {"snippet_coverage": "excerpt_verified", "canonical_examples": [example]}
    registry = {name: deepcopy(entry) for name in ("state", "connector.fs.file", "examples.minimal")}
    second = deepcopy(example)
    second.update(name="second", source_excerpt={"path": "first.yaml", "start_line": 2, "end_line": 3})
    third = deepcopy(example)
    third.update(name="third", source_excerpt={"path": "second.yaml", "start_line": 1, "end_line": 1})
    registry["state"]["canonical_examples"].extend([second, third])
    monkeypatch.setattr(help_snippets, "HELP_SNIPPET_REGISTRY", registry)
    sources = {"first.yaml": "alpha\nbeta\ngamma\n", "second.yaml": "delta\n"}
    reads = Counter()
    original_read = Path.read_text

    def read_text(path, *args, **kwargs):
        if path.parent == help_snippets._REPO_ROOT and path.name in sources:
            assert kwargs == {"encoding": "utf-8"}
            reads[path.name] += 1
            return sources[path.name]
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    return registry, sources, reads


@pytest.mark.parametrize("arguments, status", [
    (["features"], 0),
    (["search", "state"], 0),
    (["snippet-coverage"], 0),
    (["describe", "state"], 0),
    (["describe", "operation.fs.file"], 0),
    (["describe", "operation.nonexistent"], 1),
])
def test_each_response_builds_one_catalog_and_reuses_lookups(
    monkeypatch, capsys, small_registry, arguments, status,
):
    catalog = Mock(wraps=help_cli.describe_help_snippets)
    monkeypatch.setattr(help_cli, "describe_help_snippets", catalog)
    builders = {}
    for name in LOOKUP_BUILDERS:
        builders[name] = Mock(wraps=getattr(help_cli, name))
        monkeypatch.setattr(help_cli, name, builders[name])

    for response_number in (1, 2):
        before = {name: builder.call_count for name, builder in builders.items()}
        assert help_cli.main([*arguments, "--json"]) == status
        payload = json.loads(capsys.readouterr().out)
        assert payload["document_kind"]
        assert catalog.call_count == response_number
        assert small_registry[2] == {"first.yaml": response_number, "second.yaml": response_number}
        for name, builder in builders.items():
            assert builder.call_count - before[name] <= 1, name
        if arguments == ["features"]:
            assert all(builder.call_count == response_number for builder in builders.values())
            assert payload["clusters"]
        if status == 1:
            assert payload["status"] == "unknown_topic"
            assert payload["suggestions"][0]["command"] == "ordo-help operation nonexistent --json"


def test_catalog_reads_each_source_once_and_refreshes_between_calls(small_registry):
    registry, sources, reads = small_registry
    original = deepcopy(registry)
    first = help_snippets.describe_help_snippets()
    assert [example["yaml"] for example in first["state"]["canonical_examples"]] == [
        "alpha\nbeta", "beta\ngamma", "delta",
    ]
    assert reads == {"first.yaml": 1, "second.yaml": 1}
    assert registry == original

    sources["first.yaml"] = "changed\nsource\ntext\n"
    registry["state"]["canonical_examples"][0]["summary"] = "New registry metadata"
    registry["new.handle"] = deepcopy(registry["state"])
    second = help_snippets.describe_help_snippets()
    assert reads == {"first.yaml": 2, "second.yaml": 2}
    assert second["new.handle"]["canonical_examples"][0]["yaml"] == "changed\nsource"
    assert second["state"]["canonical_examples"][0]["summary"] == "New registry metadata"
    assert first["state"]["canonical_examples"][0]["yaml"] == "alpha\nbeta"
    assert "new.handle" not in first


@pytest.mark.parametrize("arguments, expected_status", [
    (["features"], 0),
    (["search", "state"], 0),
    (["snippet-coverage"], 0),
    (["describe", "state"], 0),
    (["describe", "operation.fs.file"], 0),
    (["describe", "operation.nonexistent"], 1),
])
@pytest.mark.parametrize("as_json", [False, True], ids=["text", "json"])
def test_response_matches_no_reuse_reference(
    monkeypatch, capsys, small_registry, arguments, expected_status, as_json,
):
    # A fixed six-response matrix and three-entry registry bound the reference
    # work while keeping the complete actual builders, payloads and renderers.
    argv = [*arguments, *(["--json"] if as_json else [])]
    optimized_status = help_cli.main(argv)
    optimized = capsys.readouterr()

    monkeypatch.setattr(help_cli, "_HelpResponseContext", _NoReuseHelpResponseContext)
    reference_status = help_cli.main(argv)
    reference = capsys.readouterr()

    assert optimized_status == reference_status == expected_status
    assert optimized.out == reference.out
    assert optimized.err == reference.err
    if as_json:
        assert json.loads(optimized.out) == json.loads(reference.out)
        assert optimized.err == ""
    elif expected_status:
        assert optimized.out == ""
        assert "Unsupported public topic" in optimized.err
    else:
        assert optimized.out.strip()
        assert optimized.err == ""


def test_describe_refreshes_source_and_registry_between_requests(small_registry, capsys):
    registry, sources, _ = small_registry
    assert help_cli.main(["describe", "state", "--json"]) == 0
    first = json.loads(capsys.readouterr().out)
    sources["first.yaml"] = "fresh\ntext\n"
    registry["state"]["canonical_examples"][0]["verification"]["example"] = "replacement"
    assert help_cli.main(["describe", "state", "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["canonical_examples"][0]["yaml"] == "alpha\nbeta"
    assert second["canonical_examples"][0]["yaml"] == "fresh\ntext"
    assert second["canonical_examples"][0]["verification"]["example"] == "replacement"


def test_nested_examples_are_isolated_between_sibling_projections_and_calls(small_registry):
    registry, _, _ = small_registry
    context = help_cli._HelpResponseContext()
    first = context.snippet_surface("state")
    sibling = context.snippet_surface("state")
    expected = deepcopy(sibling)
    example = first["canonical_examples"][0]
    example["verification"]["example"] = "mutated"
    example["source_excerpt"]["start_line"] = 99
    first["canonical_examples"].append({"name": "injected"})

    assert sibling == expected
    assert context.snippet_surface("state") == expected
    assert help_cli._HelpResponseContext().snippet_surface("state") == expected
    assert registry["state"]["canonical_examples"][0]["verification"]["example"] == "synthetic"
    assert help_cli._snippet_surface_for_handle("missing", snippets={}) == {
        "snippet_coverage": "none", "canonical_examples": [],
    }


def test_public_reference_earlier_match_still_propagates_later_builder_failure(monkeypatch):
    calls = []
    failure = RuntimeError("later capability builder failed")
    for name in LOOKUP_BUILDERS:
        def build(*, context=None, name=name):
            calls.append(name)
            if name == "_build_capability_lookup":
                raise failure
            return {"early": {"node_kind": "rule", "summary": "Earlier match"}}
        monkeypatch.setattr(help_cli, name, build)

    with pytest.raises(RuntimeError) as caught:
        help_cli._build_public_handle_reference("early")
    assert caught.value is failure
    assert calls == [
        "_build_workflow_rules_node_lookup", "_build_examples_node_lookup",
        "_build_model_node_lookup", "_build_command_line_node_lookup", "_build_capability_lookup",
    ]


@pytest.mark.parametrize("handle", ["state", "missing"])
def test_unrelated_malformed_entry_is_validated_even_for_known_or_missing_handle(small_registry, handle):
    small_registry[0]["unrelated"] = {"snippet_coverage": "invalid", "canonical_examples": []}
    with pytest.raises(ValueError, match="Unsupported snippet coverage for unrelated"):
        help_cli._HelpResponseContext().snippet_surface(handle)


def test_failed_catalog_is_not_cached_and_can_be_retried(small_registry):
    registry, _, _ = small_registry
    registry["unrelated"] = {"snippet_coverage": "invalid"}
    context = help_cli._HelpResponseContext()
    with pytest.raises(ValueError, match="unrelated"):
        context.snippet_surface("state")
    del registry["unrelated"]
    assert context.snippet_surface("state")["canonical_examples"][0]["yaml"] == "alpha\nbeta"


def test_model_failure_precedes_catalog_validation(monkeypatch, small_registry):
    small_registry[0]["unrelated"] = {"snippet_coverage": "invalid"}
    failure = RuntimeError("model construction failed first")
    monkeypatch.setattr(help_cli, "build_model_response", Mock(side_effect=failure))
    catalog = Mock(wraps=help_cli.describe_help_snippets)
    monkeypatch.setattr(help_cli, "describe_help_snippets", catalog)
    with pytest.raises(RuntimeError) as caught:
        help_cli._build_model_node_lookup()
    assert caught.value is failure
    catalog.assert_not_called()


def test_excerpt_failure_precedes_registry_validation(monkeypatch, small_registry):
    registry, _, _ = small_registry
    registry["state"]["snippet_coverage"] = "invalid"
    failure = OSError("excerpt source unavailable")
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=failure))
    with pytest.raises(OSError) as caught:
        help_snippets.describe_help_snippets()
    assert caught.value is failure


def test_failed_lookup_is_retried_in_same_context(monkeypatch):
    failure = RuntimeError("incomplete lookup")
    completed = {"example": {"summary": "Complete"}}
    builder = Mock(side_effect=[failure, completed])
    monkeypatch.setattr(help_cli, "_build_examples_node_lookup", builder)
    context = help_cli._HelpResponseContext()
    with pytest.raises(RuntimeError) as caught:
        context.lookup("examples")
    assert caught.value is failure
    assert context.lookup("examples") == completed
    assert context.lookup("examples") == completed
    assert builder.call_count == 2
