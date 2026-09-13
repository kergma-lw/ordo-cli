"""Bounded data-use forests: roles are display vertices, never executions."""

from copy import deepcopy

import pytest

from test_graph_roles import project, put, use, delete
from ordo.runtime.graphing import render_static_graph


def forest(payload):
    nodes = {node["id"]: node for contour in payload["summary"]["contours"]
             for node in contour["role_view"]["forest"]["nodes"]}
    # Tests using this helper deliberately have one connected contour.
    assert len(payload["summary"]["contours"]) == 1
    roots = payload["summary"]["contours"][0]["role_view"]["forest"]["roots"]
    seen, todo = [], list(roots)
    while todo:
        ref = todo.pop()
        assert ref not in seen, "duplicate or cyclic forest vertex"
        seen.append(ref)
        todo.extend(nodes[ref]["children"])
    assert set(seen) == set(nodes)
    return nodes


def node_for(nodes, name, role=None):
    matches = [node for node in nodes.values() if node["workflow"] == name
               and (role is None or node.get("role") == role)]
    assert len(matches) == 1
    return matches[0]


def parent_name(nodes, node):
    parent = node["placement"]["parent"]
    return nodes[parent]["workflow"] if parent else None


@pytest.mark.parametrize("fallback", [False, True])
def test_writers_and_terminal_join_follow_chain_in_reverse_author_order(tmp_path, fallback):
    value = 'state.a["repo"].y'
    if fallback:
        value += ' | catch(["runtime.value.state_missing"], null)'
    payload = project(tmp_path, {
        "end": [use('state.a["repo"].x'), use(value), delete('state.a["repo"]')],
        "middle": [use('state.a["repo"].x'), put('state.a["repo"].y')],
        "start": [put('state.a["repo"].x')],
    })
    nodes = forest(payload)
    end, middle = node_for(nodes, "end"), node_for(nodes, "middle")
    assert parent_name(nodes, middle) == "start"
    assert parent_name(nodes, end) == "middle"
    assert end["placement"]["kind"] == "chain"
    assert bool(end["placement"]["conditional_sources"]) == fallback
    text = render_static_graph(payload)
    assert 'middle (+y)' in text and '+y?' not in text
    assert 'also reads from: start' in text
    assert ('reads from: middle?' in text) == fallback
    # Invalidation creates a detailed cycle but must not flatten the data chain.
    assert payload["possible_loop_components"]


@pytest.mark.parametrize("alternative", [False, True])
def test_incomparable_sources_use_common_parent_with_all_refs(tmp_path, alternative):
    payload = project(tmp_path, {
        "start": [put('state.a["repo"].base')],
        "left": [use('state.a["repo"].base'), put('state.a["repo"].x')],
        "right": [use('state.a["repo"].base'), put('state.a["repo"].x' if alternative else 'state.a["repo"].y')],
        "join": [use('state.a["repo"].x'), *([] if alternative else [use('state.a["repo"].y')]),
                 put('state.a["repo"].done')],
    })
    nodes = forest(payload)
    join = node_for(nodes, "join")
    assert parent_name(nodes, join) == "start"
    assert join["placement"]["kind"] == ("alternatives" if alternative else "join")
    text = render_static_graph(payload)
    if alternative:
        assert '[read sources: left, right]' in text
        assert '(reference)' not in text
    else:
        assert 'join (+done) [also reads from: right]' in text
        assert 'join ↔ (reference)' in text


def test_alternative_writers_in_a_chain_do_not_select_last_source(tmp_path):
    payload = project(tmp_path, {
        "first": [put('state.a["repo"].base'), put('state.a["repo"].x')],
        "second": [use('state.a["repo"].base'), put('state.a["repo"].x')],
        "reader": [use('state.a["repo"].x')],
    })
    nodes = forest(payload)
    assert parent_name(nodes, node_for(nodes, "second")) == "first"
    assert parent_name(nodes, node_for(nodes, "reader")) is None
    assert node_for(nodes, "reader")["placement"]["kind"] == "alternatives"


def test_handoff_scc_retains_vertices_and_downstream_unique_anchor(tmp_path):
    payload = project(tmp_path, {
        "one": [use('state.a["repo"].y'), put('state.a["repo"].x')],
        "two": [use('state.a["repo"].x'), put('state.a["repo"].y')],
        "reader": [use('state.a["repo"].x')],
    })
    nodes = forest(payload)
    for name in ("one", "two"):
        assert node_for(nodes, name)["placement"]["kind"] == "cycle"
        assert parent_name(nodes, node_for(nodes, name)) is None
    assert parent_name(nodes, node_for(nodes, "reader")) == "one"


def test_cross_state_mixed_roles_share_workflow_reads_without_extra_edges(tmp_path):
    payload = project(tmp_path, {
        "start": [put('state.a["repo"].x')],
        "mixed": [use('state.a["repo"].x'), delete('state.a["repo"]'), put('state.b["repo"].y')],
        "reader": [use('state.b["repo"].y')],
    })
    before = deepcopy(payload)
    nodes = forest(payload)
    mixed = [node for node in nodes.values() if node["workflow"] == "mixed"]
    assert len(mixed) == 2
    assert all(parent_name(nodes, node) == "start" for node in mixed)
    assert mixed[0]["placement"]["read_sites"] == mixed[1]["placement"]["read_sites"]
    assert len([w for w in payload["workflows"] if w["workflow"] == "mixed"]) == 1
    text = render_static_graph(payload)
    assert text.index('mixed (+b["repo"].y)') < text.index('mixed (−a["repo"])')
    assert payload == before


def test_unknown_read_does_not_erase_known_source_or_gain_question_mark(tmp_path):
    payload = project(tmp_path, {
        "start": [put('state.a["repo"].x')],
        "writer": [use('state.a["repo"].x'), use('state.b[inputs.key].unknown'), put('state.a["repo"].y')],
    })
    nodes = forest(payload)
    writer = node_for(nodes, "writer")
    assert parent_name(nodes, writer) == "start"
    assert writer["placement"]["unknown_reads"]
    assert not writer["placement"]["conditional_sources"]
    assert 'writer (+a["repo"].y) [other sources unknown]' in render_static_graph(payload)


def test_conditional_read_annotation_is_independent_of_effect_annotation(tmp_path):
    payload = project(tmp_path, {
        "start": [put('state.a["repo"].x')],
        "writer": [dict(use('state.a["repo"].x'), **{"if": "inputs.enabled"}), put('state.a["repo"].y')],
    })
    nodes = forest(payload)
    assert parent_name(nodes, node_for(nodes, "writer")) == "start"
    assert 'writer (+y) [reads from: start?]' in render_static_graph(payload)


def test_complex_expression_unknown_optionality_keeps_known_data_use(tmp_path):
    payload = project(tmp_path, {
        "start": [put('state.a["repo"].x')],
        "writer": [use('state.a["repo"].x | default(0)'), put('state.a["repo"].y')],
    })
    nodes = forest(payload)
    writer = node_for(nodes, "writer")
    assert parent_name(nodes, writer) == "start"
    assert not writer["placement"]["conditional_sources"]


def test_two_terminal_siblings_follow_users_in_author_order(tmp_path):
    payload = project(tmp_path, {
        "start": [put('state.a["repo"].x')],
        "end-z": [delete('state.a["repo"].x')],
        "reader": [use('state.a["repo"].x')],
        "end-a": [delete('state.a["repo"].x')],
    })
    nodes = forest(payload)
    start = node_for(nodes, "start")
    assert [nodes[ref]["workflow"] for ref in start["children"]] == ["reader", "end-z", "end-a"]


def test_root_terminal_ties_follow_related_sections_without_reversing(tmp_path):
    payload = project(tmp_path, {
        "left": [put('state.a["repo"].x')],
        "end-z": [delete('state.a["repo"].x')],
        "right": [put('state.a["repo"].x')],
        "end-a": [delete('state.a["repo"].x')],
        "reader": [use('state.a["repo"].x')],
    })
    nodes = forest(payload)
    roots = payload["summary"]["contours"][0]["role_view"]["forest"]["roots"]
    assert [nodes[ref]["workflow"] for ref in roots] == ["left", "right", "reader", "end-z", "end-a"]


def test_role_projection_only_adds_forest_and_leaves_analyzer_payload_intact(tmp_path, monkeypatch):
    import ordo.runtime.graph_roles as role_module

    workflows = {"start": [put('state.a["repo"].x')],
                 "middle": [use('state.a["repo"].x'), put('state.a["repo"].y')],
                 "end": [use('state.a["repo"].y'), delete('state.a["repo"]')]}
    actual = project(tmp_path, workflows)
    monkeypatch.setattr(role_module, "_source_forest", lambda *args: None)
    legacy = project(tmp_path, workflows)
    for payload in (actual, legacy):
        for contour in payload["summary"]["contours"]:
            del contour["role_view"]["forest"]
    assert actual == legacy
