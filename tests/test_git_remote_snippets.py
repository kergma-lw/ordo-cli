"""Exact-source remote examples and bounded normalized fixture admission."""

from copy import deepcopy
from dataclasses import replace

import pytest

from ordo.model.help_snippets import _git_remote_workflow, describe_help_snippets
from ordo.model.help_snippet_worlds import describe_help_snippet_worlds
from ordo.runtime import load_workflow_text, validate_workflow_text
from ordo.runtime.help_snippet_runner import normalized_fixture_provider, verify_help_snippet
from ordo.runtime.help_snippet_scaffolds import build_workflow_fragment_scaffold, WORKFLOW_FRAGMENT_CONTRACT
from ordo.runtime.resolution import ResolvedOperation


@pytest.fixture(autouse=True)
def no_live_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Remote snippet attempted live execution")
    for name in ("subprocess.run", "subprocess.Popen", "socket.create_connection",
                 "ordo.connectors.operations.evaluate_probe", "ordo.connectors.operations.execute_operation",
                 "ordo.runtime.providers.get_default_connector_provider"):
        monkeypatch.setattr(name, forbidden)


def verify(case="exists", **kwargs):
    return verify_help_snippet(snippet=kwargs.pop("snippet", _git_remote_workflow()),
                               world="git-remote-" + case,
                               insertion_mode=kwargs.pop("insertion_mode", "workflow_fragment"),
                               target=kwargs.pop("target", "connector.git.remote"), **kwargs)


@pytest.mark.parametrize("case", ("exists", "missing"))
def test_published_source_executes_unchanged(case):
    example = next(item for item in describe_help_snippets()["connector.git.remote"]["canonical_examples"]
                   if item["name"] == "git_remote_" + case)
    source = example["yaml"]
    assert "connector.git.remote" in WORKFLOW_FRAGMENT_CONTRACT.supported_targets
    assert build_workflow_fragment_scaffold(target="connector.git.remote", snippet=source) == source
    assert validate_workflow_text(source).status.value == "ok"
    result = verify(case, snippet=source)
    assert result.workflow_text == source
    assert result.verification_path == "fixture_execution"
    assert result.status == example["verification"]["expected_status"]
    facts = result.effective_world["probes"]["git.remote"][0]["outputs"]
    assert result.calls and len(result.calls) <= 12
    assert all(call["reference"] == "git.remote" and call["inputs"] == {"remote": "origin"}
               for call in result.calls)
    if case == "missing":
        assert result.runtime_result.failed_step == "require-existing-remote"
        assert not result.runtime_result.published
        assert result.runtime_result.outputs["executed_steps"] == ["observe-remote"]
        assert result.runtime_result.outputs["skipped_steps"] == [
            "publish-remote-facts", "count-fetch-urls", "count-push-urls", "publish-url-counts",
        ]
        assert result.runtime_result.operation_results[-1].outputs == facts
    else:
        assert result.runtime_result.published[0] == facts
        assert result.runtime_result.published[1] == {"fetch_count": 1, "push_count": 1}


@pytest.mark.parametrize("urls", [[], [" ssh://example.com/Repo.git\r", "x\u2028y", "x\u2028y"],
                                  ["custom::literal-path", "file:///example/repo"]])
@pytest.mark.parametrize("mirror", [False, True, None])
def test_literal_urls_and_empty_lists_are_data_not_admission_policy(urls, mirror):
    world = describe_help_snippet_worlds()["git-remote-exists"]
    fixture = world["probes"]["git.remote"][0]
    fixture["outputs"].update(fetch_urls=urls, push_urls=list(reversed(urls)), mirror=mirror)
    result = verify(overrides={"probes": world["probes"]})
    assert result.status == "ok"
    assert result.runtime_result.published[0] == fixture["outputs"]
    assert result.runtime_result.published[1] == {"fetch_count": len(urls), "push_count": len(urls)}


@pytest.mark.parametrize("change", [{"snippet": _git_remote_workflow() + "\n"},
                                   {"target": "connector.git.repo"}, {"insertion_mode": "step_fragment"},
                                   {"overrides": {"inputs": {"other": True}}}])
def test_noncanonical_admission_is_rejected(change):
    with pytest.raises(ValueError):
        verify(**change)


@pytest.mark.parametrize("field,value", [("mirror", 1), ("mirror", "false"), ("exists", None),
                                        ("exists", 1), ("name", None), ("fetch_urls", [None]),
                                        ("push_urls", "url"), ("fetch_urls", [42])])
def test_output_fixture_types_are_strict(field, value):
    world = describe_help_snippet_worlds()["git-remote-exists"]
    world["probes"]["git.remote"][0]["outputs"][field] = value
    with pytest.raises(ValueError, match="Normalized fixture"):
        verify(overrides={"probes": world["probes"]})


@pytest.mark.parametrize("case", ["missing", "extra", "duplicate", "bad-input", "extra-output", "action"])
def test_fixture_shape_has_no_fallback(case):
    world = describe_help_snippet_worlds()["git-remote-exists"]
    fixture = world["probes"]["git.remote"][0]
    if case == "missing":
        world["probes"]["git.remote"] = []
    elif case == "extra":
        world["probes"]["git.repo"] = [{"with_": {}, "outputs": {"exists": True}}]
    elif case == "duplicate":
        world["probes"]["git.remote"].append(deepcopy(fixture))
    elif case == "bad-input":
        fixture["with_"]["remote"] = False
    elif case == "extra-output":
        fixture["outputs"]["safe"] = True
    else:
        world["actions"]["git.sync.push"] = {"status": "ok", "outputs": {}}
    with pytest.raises(ValueError):
        verify(overrides=world)


def test_resolved_input_mismatch_and_budget_fail_closed():
    world = describe_help_snippet_worlds()["git-remote-exists"]
    calls = []
    provider = normalized_fixture_provider(world, references={"git.remote"}, calls=calls,
                                           call_budget=1, strict_nulls=True)
    workflow = load_workflow_text(_git_remote_workflow())
    operation = ResolvedOperation(reference="git.remote", connector_namespace="git",
                                  operation=provider.registry.get_operation("git.remote"), source="public",
                                  declared_with={"remote": "origin"})
    provider.guard_probe(operation, workflow)
    with pytest.raises(ValueError, match="call budget"):
        provider.guard_probe(operation, workflow)
    assert len(calls) == 1
    calls.clear()
    wrong = replace(operation, declared_with={"remote": "elsewhere"})
    with pytest.raises(ValueError, match="Resolved fixture inputs differ"):
        provider.guard_probe(wrong, workflow)
    assert calls == []
