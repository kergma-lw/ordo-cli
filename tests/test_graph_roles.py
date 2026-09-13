"""Role projection contracts through static, non-executed playbooks."""

from copy import deepcopy

import pytest
import yaml

from ordo.playbook import build_playbook_static_graph
from ordo.runtime.graphing import render_static_graph


def project(tmp_path, workflows, states=("a", "b", "c")):
    entries = {}
    for name, steps in workflows.items():
        document = {"version": 0, "workflow": name,
                    "state_needs": {s: {} for s in states},
                    "blocks": [{"steps": [dict(name=f"step-{i}", **step) for i, step in enumerate(steps)]}]}
        (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(document, sort_keys=False))
        entries[name] = {"file": f"./{name}.yaml", "category": "flow",
                         "state_bindings": {s: s for s in states}}
    path = tmp_path / "ordo.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "states": {s: {"path": f"{s}.json"} for s in states},
                                   "workflows": entries}, sort_keys=False))
    return build_playbook_static_graph(playbook_path=path)


def put(path):
    return {"state_set": {path: True}}


def use(path):
    return {"value": path}


def delete(path):
    return {"state_delete": path}


def roles(payload):
    return [r for c in payload["summary"]["contours"] for r in c["role_view"]["roles"]]


@pytest.mark.parametrize("mixed", [0, 1, 2, 3])
def test_n_states_m_mixed_roles_not_keys_or_fields(tmp_path, mixed):
    steps = [put(f'state.{s}["{key}"].{field}') for s in ("a", "b", "c")
             for key in ("one", "two") for field in ("x", "y")]
    steps += [delete(f'state.{s}["one"]') for s in ("a", "b", "c")[:mixed]]
    payload = project(tmp_path, {"operation": steps})
    before = deepcopy(payload)
    projected = roles(payload)
    assert len(projected) == 3 + mixed
    assert {(r["state"]["name"], r["kind"]) for r in projected} == {
        *((s, "write") for s in ("a", "b", "c")),
        *((s, "delete") for s in ("a", "b", "c")[:mixed])}
    assert len(payload["workflows"]) == len(payload["summary"]["contours"]) == 1
    text = render_static_graph(payload)
    assert sum(line.startswith("operation (") for line in text.splitlines()) == 3 + mixed
    assert "Contour 1" not in text
    assert "↔ another role of the same workflow." in text
    assert payload == before


def test_partial_delete_terminal_keeps_writer_order_and_cross_context_anchor(tmp_path):
    payload = project(tmp_path, {
        "creator": [put('state.a["repo"].task.branch')],
        "task-reader": [use('state.a["repo"].task.branch')],
        "other": [put('state.a["repo"].story')],
        "cross-reader": [use('state.a["repo"].task.branch'), use('state.a["repo"].story')],
        "close": [use('state.a["repo"].task.branch'), delete('state.a["repo"].task')],
    })
    text = render_static_graph(payload)
    assert 'creator (+task.branch)\n├── task-reader\n├── cross-reader [also reads from: other]\n└── close (−task)\nother (+story)\n└── cross-reader ↔ (reference)' in text
    terminal = next(r for r in roles(payload) if r["kind"] == "delete")
    assert terminal["termination"]["cross_context_users"] == ["cross-reader"]
    assert len(terminal["termination"]["creator_roles"]) == 1
    assert len(payload["summary"]["contours"]) == 1


def test_mixed_operation_roles_nested_and_reader_not_duplicated(tmp_path):
    payload = project(tmp_path, {
        "creator": [put('state.a["repo"].x')],
        "reader": [use('state.a["repo"].x')],
        "other": [put('state.b["repo"].y')],
        "close": [use('state.a["repo"].x'), delete('state.a["repo"]'), put('state.b["repo"].z')],
        "join": [use('state.a["repo"].x'), use('state.b["repo"].z')],
    })
    text = render_static_graph(payload)
    assert text.index('close (+b["repo"].z)') < text.index('close (−a["repo"])')
    assert 'close (+b["repo"].z) ↔ b/write\n│   └── join [also reads from: creator]' in text
    assert sum("── join " in line for line in text.splitlines()) == 1
    assert len([node for node in payload["workflows"] if node["workflow"] == "close"]) == 1
    close_roles = [r for r in roles(payload) if r["workflow"] == "close"]
    assert [len(r["read_sites"]) for r in close_roles] == [1, 0]


def test_alternative_sources_remain_symbolic_and_deletion_uses_both(tmp_path):
    payload = project(tmp_path, {
        "reader": [use('state.a["repo"].x')],
        "first": [put('state.a["repo"].x')],
        "second": [put('state.a["repo"].x')],
        "close": [delete('state.a["repo"].x')],
    })
    contour = payload["summary"]["contours"][0]
    assert contour["users"][0]["placement"]["kind"] == "alternatives"
    assert contour["users"][0]["placement"]["after"] is None
    terminal = next(r for r in roles(payload) if r["kind"] == "delete")
    assert len(terminal["termination"]["creator_roles"]) == 2
    assert 'reader (data use; alternative sources) [read sources: first, second]\nfirst (+x)\nsecond (+x)\nclose (−x) [read sources: first, second]' in render_static_graph(payload)


def test_conditional_delete_rewrite_preserves_order_conditions_and_cycles(tmp_path):
    payload = project(tmp_path, {
        "reset": [use('state.a["repo"].x'), dict(delete('state.a["repo"].x'), **{"if": "inputs.enabled"}),
                  put('state.a["repo"].x')],
        "peer": [use('state.a["repo"].x'), put('state.a["repo"].x')],
    })
    terminal = next(r for r in roles(payload) if r["kind"] == "delete")
    assert terminal["termination"]["rewrites_after_delete"]
    assert terminal["termination"]["cyclic"]
    assert terminal["groups"][0]["conditions"] == [{"kind": "if", "expression": "inputs.enabled"}]
    assert "reset (−x?) ↔ a/delete" in render_static_graph(payload)
    assert [s["kind"] for s in payload["accesses"] if s["workflow"] == "reset"] == ["read", "delete", "set"]


def test_unknown_alias_does_not_claim_a_terminal_anchor():
    from dataclasses import replace
    from test_static_graph import graph, workflow, read, write
    from ordo.model.workflow import Step

    producer = workflow("producer", write())
    reader = workflow("reader", read())
    unknown = replace(workflow("unknown", Step(name="delete", state_delete="state.s['repo']")),
                      states={})
    payload = graph(producer, reader, unknown)
    terminal = next(r for r in roles(payload) if r["kind"] == "delete")
    assert terminal["placement"]["kind"] == "unresolved"
    assert not terminal["termination"]["creator_roles"]
    assert "[placement unresolved]" in render_static_graph(payload)


def test_unmatched_pure_delete_is_isolated_not_a_global_terminal(tmp_path):
    payload = project(tmp_path, {"forget": [delete('state.a["absent"]')],
                                 "creator": [put('state.b["repo"].x')]})
    terminal = next(r for r in roles(payload) if r["kind"] == "delete")
    assert terminal["placement"]["kind"] == "isolated"
    assert render_static_graph(payload).index("forget (−context)") < render_static_graph(payload).index("creator (+x)")


def test_verified_role_example_keeps_mutating_user_and_exact_output():
    from ordo.model.help_snippets import GRAPH_ROLES_EXAMPLE
    from ordo.runtime.help_snippet_runner import verify_help_snippet

    result = verify_help_snippet(snippet=GRAPH_ROLES_EXAMPLE["yaml"], world="default",
                                 insertion_mode="graph_bundle", target="state")
    assert len([r for r in roles(result.graph_result) if r["workflow"] == "finish"]) == 2


def test_parametric_deletion_retains_selector_requirements(tmp_path):
    payload = project(tmp_path, {
        "creator": [put('state.a[inputs.key].x')],
        "reader": [use('state.a[inputs.key].x')],
        "forget": [delete('state.a[inputs.key].x')],
    })
    terminal = next(r for r in roles(payload) if r["kind"] == "delete")
    assert terminal["placement"]["kind"] == "terminal"
    assert terminal["termination"]["conditional"]
    assert all(m["concrete"]["address_identity"] == "possible"
               for m in terminal["termination"]["evidence"])
    assert all(any(r["predicate"] == "selector_equal" for r in m["structural"]["requirements"])
               for m in terminal["termination"]["evidence"])
    assert 'creator (+x)\n├── reader\n└── forget (−x)' in render_static_graph(payload)


def test_declared_aliases_share_one_state_role(tmp_path):
    project(tmp_path, {"operation": [put('state.a["one"].x'), put('state.b["two"].y'),
                                     delete('state.b["three"]')]})
    path = tmp_path / "ordo.yaml"
    document = yaml.safe_load(path.read_text())
    document["workflows"]["operation"]["state_bindings"]["b"] = "a"
    path.write_text(yaml.safe_dump(document, sort_keys=False))
    payload = build_playbook_static_graph(playbook_path=path)
    assert [(r["state"]["name"], r["kind"]) for r in roles(payload)] == [("a", "write"), ("a", "delete")]
    assert len(roles(payload)[0]["sites"]) == 2


def test_role_derivation_is_additive_deterministic_and_renders_old_summaries(tmp_path):
    from ordo.runtime.graph_roles import build_role_view
    from ordo.runtime.graph_summary import _standalone_alternatives

    payload = project(tmp_path, {"creator": [put('state.a["repo"].x')],
                                 "reader": [use('state.a["repo"].x')],
                                 "close": [delete('state.a["repo"]'), put('state.b["repo"].y')]})
    before = deepcopy(payload)
    contour = payload["summary"]["contours"][0]
    assert build_role_view(payload, contour, _standalone_alternatives) == contour["role_view"]
    assert payload == before
    expected_text = render_static_graph(payload)
    for item in payload["summary"]["contours"]:
        del item["role_view"]["forest"]
    old_roles = deepcopy(payload)
    assert render_static_graph(payload) == expected_text
    assert payload == old_roles
    for item in payload["summary"]["contours"]:
        del item["role_view"]
    legacy = deepcopy(payload)
    assert render_static_graph(payload) == expected_text
    assert payload == legacy
