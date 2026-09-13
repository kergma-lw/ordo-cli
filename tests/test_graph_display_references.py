"""Multi-source sightings preserve one operation and one full subtree."""

from copy import deepcopy

import pytest

from test_graph_roles import project, put, use, delete
from ordo.runtime.graphing import render_static_graph


def display(payload):
    view = payload["summary"]["contours"][0]["role_view"]
    nodes = {node["id"]: node for node in view["forest"]["nodes"]}
    rows = view["forest"]["display_rows"]
    assert len([row for row in rows if not row["reference"]]) == len(nodes)
    assert len({(row["node"], row["parent"]) for row in rows}) == len(rows)
    full = {row["node"]: row for row in rows if not row["reference"]}
    for ref in full:
        seen = set()
        while ref is not None:
            assert ref not in seen
            seen.add(ref)
            ref = full[ref]["parent"]
    return nodes, rows


def sightings(nodes, rows, name):
    return [(nodes[row["parent"]]["workflow"] if row["parent"] else None, row["reference"])
            for row in rows if nodes[row["node"]]["workflow"] == name]


@pytest.mark.parametrize("fallback", [False, True])
def test_distinct_source_join_has_one_full_and_one_reference_leaf(tmp_path, fallback):
    right_read = 'state.a["repo"].y'
    if fallback:
        right_read += ' | catch(["runtime.value.state_missing"], null)'
    payload = project(tmp_path, {
        "left": [put('state.a["repo"].x')],
        "right": [put('state.a["repo"].y')],
        "consumer": [use('state.a["repo"].x'), use(right_read), use(right_read)],
    })
    before = deepcopy(payload)
    nodes, rows = display(payload)
    assert sightings(nodes, rows, "consumer") == [("left", False), ("right", True)]
    assert len([node for node in nodes.values() if node["workflow"] == "consumer"]) == 1
    reference = next(row for row in rows if row["reference"])
    assert reference["conditional"] == fallback
    text = render_static_graph(payload)
    assert "left (+x)\n└── consumer [also reads from: right" in text
    assert "right (+y)\n└── consumer ↔ (reference)" in text
    assert payload == before


def test_mutating_consumer_subtree_is_not_copied_under_reference(tmp_path):
    payload = project(tmp_path, {
        "left": [put('state.a["repo"].x')],
        "right": [put('state.a["repo"].y')],
        "consumer": [use('state.a["repo"].x'), use('state.a["repo"].y'), put('state.a["repo"].z')],
        "child": [use('state.a["repo"].z')],
    })
    nodes, rows = display(payload)
    assert sightings(nodes, rows, "consumer") == [("left", False), ("right", True)]
    assert sightings(nodes, rows, "child") == [("consumer", False)]
    text = render_static_graph(payload)
    assert "└── consumer (+z) [also reads from: right]\n    └── child" in text
    assert "right (+y)\n└── consumer ↔ (reference)\n\nDetails" in text
    assert text.count("── child") == 1


@pytest.mark.parametrize("mixed", [False, True])
def test_same_data_alternatives_and_mixed_joins_never_expand(tmp_path, mixed):
    payload = project(tmp_path, {
        "one": [put('state.a["repo"].x'), put('state.a["repo"].y')],
        "two": [put('state.a["repo"].x')],
        "consumer": [use('state.a["repo"].x'), *([use('state.a["repo"].y')] if mixed else [])],
    })
    nodes, rows = display(payload)
    assert sightings(nodes, rows, "consumer") == [(None, False)]
    assert not any(row["reference"] for row in rows)
    assert "consumer (data use; alternative sources)" in render_static_graph(payload)


def test_multiple_roles_are_unambiguous_and_keep_single_identities(tmp_path):
    payload = project(tmp_path, {
        "left": [put('state.a["repo"].x')],
        "right": [put('state.a["repo"].y')],
        "mixed": [use('state.a["repo"].x'), use('state.a["repo"].y'),
                  put('state.b["repo"].z'), delete('state.a["repo"]')],
    })
    nodes, rows = display(payload)
    assert len([node for node in nodes.values() if node["workflow"] == "mixed"]) == 2
    assert len([row for row in rows if row["reference"]]) == 2
    assert len([node for node in payload["workflows"] if node["workflow"] == "mixed"]) == 1
    text = render_static_graph(payload)
    assert "mixed ↔ b/write (reference)" in text
    assert "mixed ↔ a/delete (reference)" in text


@pytest.mark.parametrize("reverse", [False, True])
def test_canonical_occurrence_uses_source_layout_not_alphabetical_order(tmp_path, reverse):
    producers = [("z-source", [put('state.a["repo"].x')]),
                 ("a-source", [put('state.a["repo"].y')])]
    if reverse:
        producers.reverse()
    payload = project(tmp_path, {"consumer": [use('state.a["repo"].x'), use('state.a["repo"].y')], **dict(producers)})
    nodes, rows = display(payload)
    assert sightings(nodes, rows, "consumer")[0] == (producers[0][0], False)


def test_cycles_remain_finite_and_do_not_expand_sources(tmp_path):
    payload = project(tmp_path, {
        "left": [use('state.a["repo"].z'), put('state.a["repo"].x')],
        "right": [put('state.a["repo"].y')],
        "consumer": [use('state.a["repo"].x'), use('state.a["repo"].y'), put('state.a["repo"].z')],
        "child": [use('state.a["repo"].z')],
    })
    nodes, rows = display(payload)
    assert not any(row["reference"] for row in rows)
    assert sightings(nodes, rows, "consumer") == [(None, False)]
    assert render_static_graph(payload).count("── child") == 1


def test_display_rows_do_not_change_established_source_parents(tmp_path, monkeypatch):
    import ordo.runtime.graph_roles as roles

    workflows = {"left": [put('state.a["repo"].x')], "right": [put('state.a["repo"].y')],
                 "consumer": [use('state.a["repo"].x'), use('state.a["repo"].y')]}
    actual = project(tmp_path, workflows)
    monkeypatch.setattr(roles, "_display_references", lambda *args: [])
    original = project(tmp_path, workflows)
    for payload in (actual, original):
        for contour in payload["summary"]["contours"]:
            del contour["role_view"]["forest"]["display_rows"]
    assert actual == original


def test_reference_expansion_is_bounded_by_source_vertices_not_fields(tmp_path):
    payload = project(tmp_path, {
        **{f"source-{i}": [put(f'state.a["repo"].field{i}'), put(f'state.a["repo"].extra{i}')]
           for i in range(4)},
        "consumer": [use(f'state.a["repo"].{field}{i}') for i in range(4)
                     for field in ("field", "extra", "field")],
    })
    nodes, rows = display(payload)
    assert len(sightings(nodes, rows, "consumer")) == 4
    assert sum(row["reference"] for row in rows) == 3
    expected = render_static_graph(payload)
    del payload["summary"]["contours"][0]["role_view"]["forest"]["display_rows"]
    before = deepcopy(payload)
    assert render_static_graph(payload) == expected
    assert payload == before


def test_incomplete_source_set_retains_uncertainty_without_reference_fan(tmp_path):
    payload = project(tmp_path, {
        "left": [put('state.a["repo"].x')],
        "right": [put('state.a["repo"].y')],
        "consumer": [use('state.a["repo"].x'), use('state.a["repo"].y'), use('state.a["repo"].unknown')],
    })
    nodes, rows = display(payload)
    assert sightings(nodes, rows, "consumer") == [(None, False)]
    assert "other sources unknown" in render_static_graph(payload)
