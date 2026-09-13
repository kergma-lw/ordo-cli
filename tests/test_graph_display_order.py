"""Display tie-breaking through real, synthetic playbook entries (no execution)."""

from copy import deepcopy

import yaml

from ordo.playbook import build_playbook_static_graph, list_playbook_workflows
from ordo.runtime.graphing import render_static_graph


def _write_playbook(tmp_path, entries):
    catalog = {}
    for name, category, reads, writes in entries:
        steps = [{"name": f"read-{field}", "value": f'state.s["repo"].{field}'} for field in reads]
        steps.extend({"name": f"write-{field}", "state_set": {f'state.s["repo"].{field}': True}}
                     for field in writes)
        document = {"version": 0, "workflow": name, "state_needs": {"s": {}},
                    "blocks": [{"steps": steps}]}
        (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        catalog[name] = {"file": f"./{name}.yaml", "category": category, "state_bindings": {"s": "memory"}}
    path = tmp_path / "ordo.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "states": {"memory": {"path": "memory.json"}},
                                    "workflows": catalog}, sort_keys=False), encoding="utf-8")
    return path


def test_same_category_producer_tie_uses_authored_not_alphabetical_order(tmp_path):
    entries = [("z-reader", "flow", ["x", "y"], []),
               ("z-producer", "flow", [], ["x"]), ("a-producer", "flow", [], ["y"])]
    path = _write_playbook(tmp_path, entries)
    catalog = list_playbook_workflows(playbook_path=path)
    assert [entry.workflow_name for entry in catalog] == [entry[0] for entry in entries]
    assert {entry.workflow_category for entry in catalog} == {"flow"}
    payload = build_playbook_static_graph(playbook_path=path)
    contour = payload["summary"]["contours"][0]
    assert [change["workflow"] for change in contour["changes"]] == ["z-producer", "a-producer"]
    assert contour["users"][0]["placement"]["kind"] == "join"
    assert "z-producer (+x)\na-producer (+y)\n└── z-reader" in render_static_graph(payload)
    # The early reader entry still follows its source anchor. No producer-to-
    # producer relation is invented by their shared category or authored order.
    assert {(link["from_workflow"], link["to_workflow"], link["kind"]) for link in payload["links"]} == {
        ("z-producer", "z-reader", "handoff"), ("a-producer", "z-reader", "handoff")}


def test_tied_readers_follow_entry_order_without_cross_category_grouping(tmp_path):
    entries = [("z-reader", "flow", ["x"], []), ("producer", "flow", [], ["x"]),
               ("middle-reader", "inspect", ["x"], []), ("a-reader", "flow", ["x"], [])]
    path = _write_playbook(tmp_path, entries)
    before = build_playbook_static_graph(playbook_path=path)
    assert "producer (+x)\n├── z-reader\n├── middle-reader\n└── a-reader" in render_static_graph(before)
    # Relabel categories while keeping entry order and source documents identical.
    # The complete graph, placement, IDs and display remain unchanged.
    _write_playbook(tmp_path, [(name, "other", reads, writes) for name, _, reads, writes in entries])
    after = build_playbook_static_graph(playbook_path=path)
    # Category is now carried as display metadata, never as relation evidence.
    for graph in (after, before):
        for node in graph["workflows"]:
            node.pop("category", None)
    assert after == before


def test_distinct_source_anchors_take_precedence_over_same_category_entry_order(tmp_path):
    path = _write_playbook(tmp_path, [("z-later-reader", "flow", ["y"], []),
        ("a-earlier-reader", "flow", ["x"], []), ("producer", "flow", [], ["x", "y"])])
    source = tmp_path / "producer.yaml"
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    document["inputs"] = {"enabled": {"default": True}}
    document["blocks"][0]["steps"][1]["if"] = "inputs.enabled"
    source.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    payload = build_playbook_static_graph(playbook_path=path)
    users = payload["summary"]["contours"][0]["users"]
    assert [user["workflow"] for user in users] == ["z-later-reader", "a-earlier-reader"]
    assert [user["placement"]["after"] for user in users] == ["S2", "S1"]
    assert "producer (+x, +y?)\n├── a-earlier-reader\n└── z-later-reader" in render_static_graph(payload)


def test_category_does_not_create_links_or_merge_independent_contours(tmp_path):
    path = _write_playbook(tmp_path, [("z-work", "flow", [], ["x"]), ("a-work", "flow", [], ["y"])])
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["links"] == []
    assert len(payload["summary"]["contours"]) == 2
    text = render_static_graph(payload)
    assert text.index("z-work (+x)") < text.index("a-work (+y)")
    assert "Ties within a category follow playbook order." in text


def test_alternatives_use_category_order_before_an_anchored_successor_block(tmp_path):
    path = _write_playbook(tmp_path, [
        ("producer", "context", [], ["choice", "story"]),
        ("alternate", "context", [], ["choice"]),
        ("ready", "lifecycle", ["choice"], []),
        ("review", "lifecycle", ["story"], []),
        ("done", "lifecycle", ["story"], ["done"]),
    ])
    payload = build_playbook_static_graph(playbook_path=path)
    before = deepcopy(payload)
    text = render_static_graph(payload)
    assert "ready\nproducer (+choice, +story)\n└── review\nalternate (+choice)\ndone (+done)" in text
    users = {u["workflow"]: u for c in payload["summary"]["contours"] for u in c["users"]}
    assert users["ready"]["placement"]["kind"] == "alternatives"
    assert users["ready"]["placement"]["after"] is None
    assert len(users["ready"]["dependencies"][0]["sources"]) == 2
    assert users["review"]["placement"]["kind"] == "single_source"
    assert users["review"]["placement"]["after"] == "S1"
    assert text.splitlines().count("ready") == 1
    assert payload == before


def test_category_tie_cannot_split_an_established_source_reader_block(tmp_path):
    path = _write_playbook(tmp_path, [
        ("producer", "flow", [], ["choice", "story"]),
        ("alternate", "flow", [], ["choice"]),
        ("ready", "flow", ["choice"], []),
        ("review", "flow", ["story"], []),
    ])
    text = render_static_graph(build_playbook_static_graph(playbook_path=path))
    # Same-category predecessors and successor share an indivisible anchored
    # block. Keep the anchor and fall back to authored standalone-row order.
    assert "producer (+choice, +story)\n└── review\nalternate (+choice)\nready" in text
    assert "└── ready" not in text


def test_alternatives_declared_first_do_not_wait_for_all_producers(tmp_path):
    path = _write_playbook(tmp_path, [("reader", "flow", ["x"], []),
        ("producer-one", "flow", [], ["x"]), ("producer-two", "flow", [], ["x"])])
    payload = build_playbook_static_graph(playbook_path=path)
    assert "reader\nproducer-one (+x)\nproducer-two (+x)" in render_static_graph(payload)
    assert payload["summary"]["contours"][0]["users"][0]["placement"]["kind"] == "alternatives"


def test_verified_alternatives_example_retains_sources_without_a_parent():
    from ordo.model.help_snippets import GRAPH_ALTERNATIVES_EXAMPLE
    from ordo.runtime.help_snippet_runner import verify_help_snippet
    result = verify_help_snippet(snippet=GRAPH_ALTERNATIVES_EXAMPLE["yaml"], world="default",
                                 insertion_mode="graph_bundle", target="state")
    ready = next(u for c in result.graph_result["summary"]["contours"] for u in c["users"] if u["workflow"] == "ready")
    assert ready["placement"]["kind"] == "alternatives"
    assert ready["placement"]["after"] is None
    assert ready["placement"]["sources"] == ["S1", "S2"]
