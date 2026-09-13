"""Structural parameter correspondence never substitutes for concrete identity."""

from copy import deepcopy

import yaml

from ordo.model.workflow import Step, Workflow
from ordo.playbook import build_playbook_static_graph
from ordo.runtime.graph_structure import structural_relation
from ordo.runtime.graphing import build_static_graph, render_static_graph, _relation
from test_graph_profiles import _project, _writer, _read, _set


def _user(payload, name="reader"):
    return next(u for c in payload["summary"]["contours"] for u in c["users"] if u["workflow"] == name)


def test_default_profile_family_links_without_selecting_or_reading_state(tmp_path, monkeypatch):
    import ordo.runtime.state as state
    def forbidden(*args, **kwargs):
        raise AssertionError("structural graph cannot read state")
    monkeypatch.setattr(state, "read_state_document", forbidden)
    path = _project(tmp_path, {
        "producer": _writer({"name": "switch", "profile_switch": "${inputs.target}"},
            _set("state.data[inputs.repository].issue"), _set("state.data[inputs.repository].branch")),
        "reader": _writer(_read("state.data[inputs.repository].issue"), _read("state.data[inputs.repository].branch")),
    }, bootstrap=True)
    payload = build_playbook_static_graph(playbook_path=path)
    user = _user(payload)
    assert user["placement"]["kind"] == "single_source" and user["placement"]["parametric"]
    body = [a for a in payload["accesses"] if a["phase"] == "body"]
    assert all(a["address"]["key"] is None for a in body)
    assert all(set(a["address"]["key_candidates"]) == {"org/alpha", "org/beta"} for a in body)
    assert all(a["address"]["selector"]["kind"] == "parameter" for a in body)
    links = [link for link in payload["structural_links"] if link["from"] == body[0]["id"] and link["to"] == body[2]["id"]]
    assert links[0]["selector_correspondence"] == "independent_parameters"
    assert links[0]["concrete_address_identity"] == "possible"
    assert links[0]["requirements"][0]["predicate"] == "selector_equal"
    assert "data[parameter]" in render_static_graph(payload)
    assert "producer (+issue, +branch)\n└── reader" in render_static_graph(payload)
    assert not (tmp_path / "env.json").exists()


def test_shared_selection_origin_is_correspondence_not_cross_run_value_equality(tmp_path):
    path = _project(tmp_path, {"producer": _writer(_set("state.data[inputs.repository].x")),
                               "reader": _writer(_read("state.data[inputs.repository].x"))}, bootstrap=True)
    payload = build_playbook_static_graph(playbook_path=path)
    link = next(link for link in payload["structural_links"] if link["from"] == "producer:1" and link["to"] == "reader:1")
    assert link["selector_correspondence"] == "shared_origin_parameter"
    assert any(r["predicate"] == "selector_equal" for r in link["requirements"])
    assert link["concrete_address_identity"] == "possible"


def test_unknown_input_spelling_never_proves_equality(tmp_path):
    producer = _writer(_set("state.data[inputs.key].x"))
    reader = _writer(_read("state.data[inputs.key].x"))
    producer["inputs"]["key"] = reader["inputs"]["key"] = {}
    payload = build_playbook_static_graph(playbook_path=_project(tmp_path, {"producer": producer, "reader": reader}))
    a, b = payload["accesses"]
    assert a["address"]["selector"]["origin"] != b["address"]["selector"]["origin"]
    assert payload["structural_links"][0]["selector_correspondence"] == "independent_parameters"
    assert payload["links"][0]["address_identity"] == "possible"


def test_fixed_indices_and_closed_domains_remain_disjoint(tmp_path):
    path = _project(tmp_path, {"producer": _writer(_set('state.data["one"].x')),
                               "reader": _writer(_read('state.data["two"].x'))})
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["links"] == payload["structural_links"] == []
    assert len(payload["summary"]["contours"]) == 2
    a, b = deepcopy(payload["accesses"])
    for site, domain in ((a, ["one", "extra"]), (b, ["two", "other"])):
        site["address"]["selector"] = {"kind": "parameter", "origin": {"scope": site["workflow"]}, "closed_domain": domain}
    assert structural_relation(a, b) is None


def test_profile_store_instances_share_family_but_not_physical_identity(tmp_path):
    path = _project(tmp_path, {"producer": _writer(_set('state.data["slot"].x')),
                               "reader": _writer(_read('state.data["slot"].x'))})
    alpha = build_playbook_static_graph(playbook_path=path, profile_name="alpha")
    beta = build_playbook_static_graph(playbook_path=path, profile_name="beta")
    a, b = alpha["accesses"][0], beta["accesses"][1]
    assert a["address"]["store"] != b["address"]["store"]
    assert _relation(a, b) is None
    link = structural_relation(a, b)
    assert link["concrete_address_identity"] == "disjoint"
    assert link["selector_correspondence"] == "fixed_equal"
    assert [r["predicate"] for r in link["requirements"]] == ["same_family_instance"]
    writer = Workflow(version=0, workflow="producer", state_bindings={"s": "data"}, states={"data": a["address"]["store"]},
                      steps=(Step(name="write", state_set={'state.s["slot"].x': True}),))
    reader = Workflow(version=0, workflow="reader", state_bindings={"s": "data"}, states={"data": b["address"]["store"]},
                      steps=(Step(name="read", value='${state.s["slot"].x}'),))
    combined = build_static_graph([("producer", writer, "/"), ("reader", reader, "/")], state_families={
        "producer": {"data": a["address"]["family"]}, "reader": {"data": b["address"]["family"]}})
    assert combined["links"] == []
    assert combined["structural_components"] == [["producer", "reader"]]
    assert _user(combined)["placement"]["parametric"]


def test_fixed_entry_directories_do_not_become_profile_store_aliases(tmp_path):
    path = _project(tmp_path, {"producer": _writer(_set('state.data["slot"].x')),
                               "reader": _writer(_read('state.data["slot"].x'))})
    book = yaml.safe_load(path.read_text())
    book["workflows"]["producer"]["working_directory"] = "/fixed/one"
    book["workflows"]["reader"]["working_directory"] = "/fixed/two"
    path.write_text(yaml.safe_dump(book, sort_keys=False))
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["links"] == payload["structural_links"] == []


def test_unrelated_declared_states_do_not_match_by_role_or_filename(tmp_path):
    producer = _writer(_set("state.data[inputs.key].x"))
    reader = _writer(_read("state.env[inputs.key].x"))
    producer["inputs"]["key"] = reader["inputs"]["key"] = {}
    path = _project(tmp_path, {"producer": producer, "reader": reader})
    book = yaml.safe_load(path.read_text())
    book["states"]["env"]["path"] = "/static/alpha/state.json"
    path.write_text(yaml.safe_dump(book, sort_keys=False))
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["links"][0]["address_identity"] == "possible"
    assert payload["structural_links"] == []
    assert _user(payload)["placement"]["kind"] == "unresolved"


def test_family_ids_are_scoped_to_the_declaring_playbook(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    a = build_playbook_static_graph(playbook_path=_project(first, {"a": _writer(_set("state.data[inputs.target].x"))}))["accesses"][0]
    b = build_playbook_static_graph(playbook_path=_project(second, {"b": _writer(_read("state.data[inputs.target].x"))}))["accesses"][0]
    assert a["address"]["binding"] == b["address"]["binding"]
    assert a["address"]["family"]["id"] != b["address"]["family"]["id"]
    assert structural_relation(a, b) is None


def test_used_let_and_forwarded_argument_preserve_origin_across_call_scope(tmp_path):
    parent = _writer(_read("state.data[alias].x"),
                     {"name": "call", "run": "./child.yaml", "with": {"slot": "${inputs.target}"}})
    parent["let"] = {"alias": "inputs.target"}
    path = _project(tmp_path, {"parent": parent})
    (tmp_path / "child.yaml").write_text('''args: {slot: string}
blocks:
  - steps:
      - name: write
        state_set:
          state.data[args.slot].x: true
''')
    payload = build_playbook_static_graph(playbook_path=path)
    a, b = payload["accesses"]
    assert a["address"]["selector"]["origin"] == b["address"]["selector"]["origin"]
    assert a["address"]["family"]["id"] == b["address"]["family"]["id"]


def test_nested_state_override_does_not_borrow_parent_family(tmp_path):
    child = tmp_path / "child.yaml"
    child.write_text('''blocks:
  - steps:
      - name: read
        value: ${state.s[inputs.key].x}
''')
    parent = Workflow(version=0, workflow="parent", declared_inputs={"key": {}},
        states={"store": "/root/state.json"}, state_bindings={"s": "store"},
        steps=(Step(name="write", state_set={"state.s[inputs.key].x": True}),
               Step(name="call", run="child.yaml", resolved_run_path=str(child),
                    run_states={"store": "/private/state.json"})))
    payload = build_static_graph([("parent", parent, "/")], state_families={"parent": {
        "store": {"id": "root-declaration", "name": "store", "instance_kind": "fixed"}}})
    a, b = payload["accesses"]
    assert a["address"]["family"]["id"] != b["address"]["family"]["id"]
    assert structural_relation(a, b) is None


def test_shape_bridges_and_parent_deletes_keep_structural_requirements(tmp_path):
    path = _project(tmp_path, {
        "producer": _writer(_set("state.data[inputs.target].parent")),
        "bridge": _writer(_read("state.data[inputs.target].parent.child"), _set("state.data[inputs.target].done")),
        "reset": _writer(_read("state.data[inputs.target].done"), {"name": "delete", "state_delete": "state.data[inputs.target].parent.child"}),
    })
    payload = build_playbook_static_graph(playbook_path=path)
    handoff = next(s for s in payload["structural_links"] if s["from_workflow"] == "producer" and s["to_workflow"] == "bridge")
    assert handoff["field_relation"] == "ancestor"
    assert {r["predicate"] for r in handoff["requirements"]} == {"selector_equal", "read_shape_available"}
    invalidation = next(s for s in payload["structural_links"] if s["kind"] == "invalidation")
    assert invalidation["execution"] == "possible"
    assert ["bridge", "reset"] in payload["structural_loop_components"]
    assert "→" not in render_static_graph(payload)


def test_shared_family_does_not_hide_a_second_unsourced_selector(tmp_path):
    reader = _writer({"name": "first", "for_each": '${["only", "first-other"]}',
                      "steps": [_read("state.data[item].x")]},
                     {"name": "second", "for_each": '${["outside", "second-other"]}',
                      "steps": [_read("state.data[item].x")]})
    path = _project(tmp_path, {"producer": _writer(_set('state.data["only"].x')), "reader": reader})
    payload = build_playbook_static_graph(playbook_path=path)
    assert _user(payload)["placement"]["kind"] == "unresolved"
    assert _user(payload)["placement"]["unresolved_dependencies"]


def test_different_unknown_selector_names_require_equality(tmp_path):
    producer = _writer(_set("state.data[inputs.left].x"))
    reader = _writer(_read("state.data[inputs.right].x"))
    producer["inputs"]["left"] = {}
    reader["inputs"]["right"] = {}
    payload = build_playbook_static_graph(playbook_path=_project(tmp_path, {"producer": producer, "reader": reader}))
    assert _user(payload)["placement"]["parametric"]
    assert payload["structural_links"][0]["selector_correspondence"] == "independent_parameters"
    assert payload["structural_links"][0]["requirements"][0]["predicate"] == "selector_equal"


def test_fixed_default_input_indices_are_not_generic_parameters(tmp_path):
    producer = _writer(_set("state.data[inputs.target].x"))
    reader = _writer(_read("state.data[inputs.target].x"))
    producer["inputs"]["target"] = {"default": "one"}
    reader["inputs"]["target"] = {"default": "two"}
    payload = build_playbook_static_graph(playbook_path=_project(tmp_path, {"producer": producer, "reader": reader}))
    assert payload["structural_links"] == []
    assert all(a["address"]["selector"]["kind"] == "fixed" for a in payload["accesses"])


def test_role_aliases_require_an_explicit_shared_store_binding(tmp_path):
    producer = _writer(_set("state.data[inputs.target].x"))
    reader = _writer(_read("state.alias[inputs.target].x"))
    reader["state_needs"] = {"alias": {}}
    path = _project(tmp_path, {"producer": producer, "reader": reader})
    book = yaml.safe_load(path.read_text())
    book["workflows"]["reader"]["state_bindings"] = {"alias": "data"}
    path.write_text(yaml.safe_dump(book, sort_keys=False))
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["structural_links"]
    assert payload["accesses"][0]["address"]["family"]["id"] == payload["accesses"][1]["address"]["family"]["id"]


def test_recursive_selector_let_keeps_an_explicit_boundary_not_recursive_json():
    import json
    w = Workflow(version=0, workflow="recursive", states={"store": "/state.json"}, state_bindings={"s": "store"},
                 let_bindings={"loop": "state.s[loop]"},
                 steps=(Step(name="write", state_set={"state.s[loop].x": True}),))
    payload = build_static_graph([("recursive", w, "/")])
    assert any(b["reason"] == "recursive_let" for b in payload["workflows"][0]["boundaries"])
    assert json.dumps(payload)


def test_verified_parameter_example_checks_equality_evidence_and_concrete_proof():
    import pytest
    from ordo.model.help_snippets import GRAPH_PARAMETER_EXAMPLE
    from ordo.runtime.help_snippet_runner import verify_help_snippet
    snippet = GRAPH_PARAMETER_EXAMPLE["yaml"]
    result = verify_help_snippet(snippet=snippet, world="default", insertion_mode="graph_bundle", target="state")
    assert result.status == "ok"
    assert all(link["address_identity"] == "possible" for link in result.graph_result["links"])
    with pytest.raises(ValueError, match="structural link mismatch"):
        verify_help_snippet(snippet=snippet.replace("requires: [selector_equal]", "requires: []"),
                            world="default", insertion_mode="graph_bundle", target="state")


def test_independent_parametric_lifecycle_shapes_do_not_merge_by_family_alone(tmp_path):
    path = _project(tmp_path, {
        "a": _writer(_read("state.data[inputs.target].done_a"), _set("state.data[inputs.target].start_a")),
        "b": _writer(_read("state.data[inputs.target].start_a"), _set("state.data[inputs.target].done_a")),
        "c": _writer(_read("state.data[inputs.target].done_b"), _set("state.data[inputs.target].start_b")),
        "d": _writer(_read("state.data[inputs.target].start_b"), _set("state.data[inputs.target].done_b")),
    })
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["structural_loop_components"] == [["a", "b"], ["c", "d"]]
    assert [c["workflows"] for c in payload["summary"]["contours"]] == [["a", "b"], ["c", "d"]]
