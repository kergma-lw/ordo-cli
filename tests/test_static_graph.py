"""Engine topology tests: synthetic workflows, never project lifecycle execution."""

from dataclasses import replace
from pathlib import Path

from ordo.model.workflow import Step, Workflow
from ordo.model.json import AuthoredString
from ordo.runtime.graphing import build_static_graph


def workflow(name, *steps, **kwargs):
    def authored(value):
        if isinstance(value, str):
            return AuthoredString(value)
        if isinstance(value, dict):
            return {key: authored(item) for key, item in value.items()}
        return value
    def authored_step(step):
        return replace(step, value=authored(step.value), for_each=authored(step.for_each),
                       run_with=authored(step.run_with),
                       steps=tuple(authored_step(item) for item in step.steps) if step.steps is not None else None)
    steps = tuple(authored_step(step) for step in steps)
    return Workflow(version=0, workflow=name, steps=steps,
                    state_bindings={"s": "store"}, states={"store": "/absent/state.json"}, **kwargs)


def read(field="a", key="'repo'"):
    return Step(name="read", value=f"state.s[{key}].{field}")


def write(field="a", key="'repo'"):
    return Step(name="set", state_set={f"state.s[{key}].{field}": True})


def graph(*items):
    return build_static_graph([(w.workflow, w, "/") for w in items])


def test_empty_state_bridge_fields_and_two_independent_loops(monkeypatch):
    import ordo.runtime.state as state
    def forbidden(*args, **kwargs):
        raise AssertionError("static graph must not read state")
    monkeypatch.setattr(state, "read_state_document", forbidden)
    a = workflow("a", read("end"), write("start"))
    b = workflow("bridge", read("start"), write("middle"))
    c = workflow("c", read("middle"), write("end"))
    d = workflow("d", read("y"), write("x"))
    e = workflow("e", read("x"), write("y"))
    payload = graph(a, b, c, d, e)
    assert payload["possible_loop_components"] == [["a", "bridge", "c"], ["d", "e"]]
    assert payload["activity"] == {"status": "not_requested"}
    assert all(link["execution"] == "possible" for link in payload["links"])
    assert all(link["address_identity"] == "proven" for link in payload["links"])


def test_same_named_dynamic_inputs_are_not_proven_identical():
    payload = graph(workflow("a", write(key="inputs.key")), workflow("b", read(key="inputs.key")))
    assert payload["links"][0]["address_identity"] == "possible"
    assert payload["accesses"][0]["address"]["symbol_scope"] != payload["accesses"][1]["address"]["symbol_scope"]


def test_different_keys_and_stores_do_not_link_but_store_aliases_do():
    a = workflow("a", write())
    b = workflow("b", read(key="'other'"))
    c = replace(workflow("c", read()), states={"store": "/another/state.json"})
    d = replace(workflow("d", read()), state_bindings={"s": "alias"}, states={"alias": "/absent/./state.json"})
    assert [(link["from_workflow"], link["to_workflow"]) for link in graph(a, b, c, d)["links"]] == [("a", "d")]


def test_subtree_replacement_delete_and_empty_parent_prune():
    a = workflow("a", write("parent"), Step(name="delete", state_delete="state.s['repo'].parent.child"))
    b = workflow("b", read("parent.child"), read("parent"), read("sibling"))
    links = graph(a, b)["links"]
    assert any(link["kind"] == "handoff" and link["field_relation"] == "ancestor" for link in links)
    assert any(link["kind"] == "invalidation" and link["empty_parent_prune"] for link in links)
    assert not any(link["to"] == "b:2" for link in links)


def test_occurrences_used_let_and_registered_values():
    w = workflow("a", Step(name="materialize", value="used", register="saved"),
                 Step(name="reuse", value="step.saved.outputs.value"),
                 Step(name="again", value="used"),
                 let_bindings={"used": "state.s['repo'].a", "unused": "state.s['repo'].b"})
    payload = graph(w)
    assert len(payload["accesses"]) == 2
    assert [site["address"]["fields"] for site in payload["accesses"]] == [["a"], ["a"]]
    assert payload["order_edges"] == [{"from": "a:0", "to": "a:1", "kind": "authored_order"}]


def test_conditional_symbolic_repeat_preserves_access_order():
    w = workflow("a", Step(name="loop", for_each="inputs.items", if_="inputs.enabled",
        steps=(read(), write("b"))))
    payload = graph(w)
    assert [site["kind"] for site in payload["accesses"]] == ["read", "set"]
    assert len(payload["workflows"][0]["repeats"]) == 1
    assert [c["kind"] for c in payload["accesses"][0]["conditions"]] == ["if", "iteration"]


def test_known_call_binds_static_argument_and_keeps_caller_condition(tmp_path):
    target = tmp_path / "child.yaml"
    target.write_text("args:\n  key: string\nblocks:\n- steps:\n  - name: read\n    value: state.s[args.key].a\n")
    w = workflow("caller", Step(name="invoke", run="child.yaml", resolved_run_path=str(target),
        run_with={"key": "inputs.repository"}, if_="inputs.enabled"), inputs={"repository": "repo"})
    payload = graph(w)
    assert payload["accesses"], payload["workflows"]
    assert payload["accesses"][0]["address"]["key"] == "repo"
    assert payload["accesses"][0]["conditions"] == [{"kind": "if", "expression": "inputs.enabled"}]


def test_recursion_and_unresolved_call_boundaries_are_explicit():
    w = workflow("caller", Step(name="recursive", run="self", resolved_run_path="/self.yaml"),
                 Step(name="unknown", run="unknown"), source_path="/self.yaml")
    assert [b["reason"] for b in graph(w)["workflows"][0]["boundaries"] if b["impact"] == "structure"] == ["recursion", "unresolved_call"]


def test_static_graph_never_evaluates_probe_keys_or_values(monkeypatch):
    import ordo.runtime.local_expressions as expressions
    def forbidden(*args, **kwargs):
        raise AssertionError("no expression evaluation")
    monkeypatch.setattr(expressions, "evaluate_parsed_local_expression", forbidden)
    payload = graph(workflow("a", write(key="gh.repo.name")), workflow("b", read()))
    assert payload["accesses"][0]["address"]["key_identity"] == "unresolved"
    assert payload["links"][0]["address_identity"] == "possible"


def test_project_graph_does_not_read_state_or_activate(monkeypatch):
    import ordo.playbook as playbook
    import ordo.runtime.state as state
    def forbidden(*args, **kwargs):
        raise AssertionError("graph cannot activate or read state")
    monkeypatch.setattr(playbook, "activate_playbook", forbidden)
    monkeypatch.setattr(state, "read_state_document", forbidden)
    payload = playbook.build_playbook_static_graph(playbook_path=Path(__file__).parents[1] / ".ordo/ordo.yaml")
    assert any({"set-active-task", "merge-task", "close-task"} <= set(c) for c in payload["components"])
    assert any(link["from_workflow"] == "set-active-task" and link["address_identity"] == "proven" for link in payload["links"])
    from ordo.runtime.graphing import render_static_graph
    text = render_static_graph(payload)
    for name in ("task-to-review", "current-task-context"):
        assert _summary_user(payload, name)["placement"]["kind"] == "single_source"
        assert text.index(name) < text.index("\nmerge-task (")
    cancel = _summary_user(payload, "cancel-task")
    assert cancel["placement"]["kind"] == "join"
    assert len(cancel["dependencies"]) == 5
    assert len(cancel["placement"]["conditional_sources"]) == 2
    assert text.index("\nmerge-task (") < text.index("└── cancel-task") < text.index("\nclose-task (")
    assert "set-active-task (+issue_number, +branch)\n├── task-to-review\n└── current-task-context" in text
    assert "merge-task (+pull_number?, +merge_attempted?, +merge_request_id?)" in text
    assert "close-task (−context)" in text


def test_graph_cli_is_independent_of_next(monkeypatch, capsys):
    import ordo.cli as cli
    import ordo.playbook as playbook
    def forbidden(*args, **kwargs):
        raise AssertionError("graph must not call next")
    monkeypatch.setattr(cli, "_build_next_payload", forbidden)
    monkeypatch.setattr(playbook, "build_playbook_static_graph", lambda **kwargs: graph(workflow("a", read())))
    monkeypatch.setattr("sys.argv", ["ordo-playbook", "--json", "graph"])
    assert cli.main() == 0
    assert '"schema_version": 1' in capsys.readouterr().out


def test_unknown_call_argument_retains_body(tmp_path):
    target = tmp_path / "child.yaml"
    target.write_text("args:\n  key: string\nblocks:\n- steps:\n  - name: read\n    value: state.s[args.key].a\n")
    w = workflow("caller", Step(name="invoke", run="child.yaml", resolved_run_path=str(target),
        run_with={"key": "inputs.missing"}))
    payload = graph(w)
    assert payload["accesses"], payload["workflows"]
    assert payload["accesses"][0]["address"]["key_identity"] == "unresolved"


def test_graph_snippet_verifies_builder_and_rejects_false_expectations():
    import pytest
    from ordo.model.help_snippets import GRAPH_BUNDLE_EXAMPLE
    from ordo.runtime.help_snippet_runner import verify_help_snippet
    snippet = GRAPH_BUNDLE_EXAMPLE["yaml"]
    result = verify_help_snippet(snippet=snippet, world="default", insertion_mode="graph_bundle", target="state")
    assert result.verification_path == "static_graph"
    assert result.graph_result["schema_version"] == 1
    assert result.graph_result["activity"]["status"] == "not_requested"
    with pytest.raises(ValueError, match="link mismatch"):
        verify_help_snippet(snippet=snippet.replace("[open, bridge, handoff, proven]", "[open, reset, handoff, proven]"),
                            world="default", insertion_mode="graph_bundle", target="state")


def test_quoted_values_do_not_create_artificial_reads():
    from ordo.runtime.loading import load_workflow_text
    w = load_workflow_text('''version: 0
workflow: literals
state_needs:
  s: {}
blocks:
  - steps:
      - name: literal
        value: "state.s['repo'].a"
      - name: actual
        value: state.s['repo'].a
''')
    assert len(graph(w)["accesses"]) == 1


def test_graph_guidance_is_published_in_model_and_capabilities():
    from ordo.help_cli import build_capabilities_response, build_model_response
    for payload in (build_capabilities_response(), build_model_response()):
        assert "schema_version 1" in payload["graph_guidance"]
        assert "independently of next" in payload["graph_guidance"]
        assert "summary is additive" in payload["graph_presentation"]
        assert "Grouped writes are not atomic" in payload["graph_presentation"]
        assert "existing body read sites" in payload["graph_source_placement"]
        assert "may perform external effects" in payload["graph_source_placement"]
        assert "bootstrap/body" in payload["graph_context"]
        assert "up to 32 alternatives" in payload["graph_context"]
        assert "selector_equal" in payload["graph_parameters"]
        assert "without relabeling possible concrete identity as proven" in payload["graph_parameters"]


def test_profile_switch_does_not_prove_later_context_across_blocks():
    from ordo.model.workflow import StepBlock
    w = workflow("switch", inputs={"key": "repo"})
    w = replace(w, blocks=(StepBlock(steps=(Step(name="profile", profile_switch="other"),)),
                           StepBlock(steps=(write(key="inputs.key"),))))
    payload = graph(w)
    assert payload["accesses"][0]["address"]["key_identity"] == "unresolved"
    assert payload["workflows"][0]["boundaries"][0]["reason"] == "profile_context_unresolved"
    assert payload["workflows"][0]["boundaries"][0]["impact"] == "context"


def test_missing_profile_input_and_state_file_preserve_structure(tmp_path):
    from ordo.playbook import build_playbook_static_graph
    (tmp_path / "workflow.yaml").write_text('''version: 0
workflow: reader
inputs:
  key: {}
state_needs:
  s: {}
blocks:
  - steps:
      - name: read
        value: state.s[inputs.key].a
''')
    path = tmp_path / "ordo.yaml"
    path.write_text('''version: 1
defaults:
  profile: missing
profiles:
  missing:
    file: missing.yaml
states:
  memory:
    path: .ordo.json
workflows:
  reader:
    file: ./workflow.yaml
    state_bindings:
      s: memory
''')
    payload = build_playbook_static_graph(playbook_path=path)
    assert not (tmp_path / ".ordo.json").exists()
    assert len(payload["accesses"]) == 1
    assert payload["accesses"][0]["address"]["key_identity"] == "unresolved"
    assert any(boundary["reason"] == "profile_unavailable" for boundary in payload["boundaries"])


def test_structured_condition_reads_keep_short_circuit_context():
    w = workflow("conditions", Step(name="optional", value=True,
        if_={"all": ["state.s['repo'].a == true", "state.s['repo'].b == true"]}))
    accesses = graph(w)["accesses"]
    assert accesses[0]["conditions"] == []
    assert accesses[1]["conditions"][0]["operator"] == "all"
    assert accesses[1]["conditions"][0]["expressions"] == ["state.s['repo'].a == true"]


def test_compact_summary_common_reads_users_and_single_termination():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("writer", write("issue"), write("branch")),
                    workflow("review", read("issue"), read("branch"), read("branch")),
                    workflow("merge", read("issue"), read("branch")),
                    workflow("reset", read("branch"), Step(name="delete", state_delete="state.s['repo']")))
    text = render_static_graph(payload)
    assert "writer (+issue, +branch)\n├── review\n└── merge\nreset (−context)" in text
    assert text.splitlines().count("reset (−context)") == 1
    assert "Reads:" not in text and "writes:" not in text
    assert payload["summary"]["contours"][0]["changes"][0]["groups"][0]["fields"] == [["issue"], ["branch"]]
    assert "->" not in text
    assert "loop" not in text.lower()
    assert "review -> merge" not in text
    assert any(link["kind"] == "invalidation" for link in payload["links"])


def test_compact_summary_preserves_mutation_order_and_conditional_groups():
    from ordo.runtime.graphing import render_static_graph
    enabled = {"all": ["inputs.enabled", "inputs.ready"]}
    a = replace(write("first"), if_=enabled)
    b = replace(write("second"), if_=enabled)
    c = replace(write("third"), if_="not inputs.enabled")
    payload = graph(workflow("anything", a, b, c,
        Step(name="remove", state_delete="state.s['repo'].old"), write("last")))
    groups = payload["summary"]["contours"][0]["changes"][0]["groups"]
    assert [g["kind"] for g in groups] == ["change", "change", "removal", "change"]
    assert groups[0]["fields"] == [["first"], ["second"]]
    assert groups[0]["conditions"] == [{"kind": "if", "expression": enabled}]
    text = render_static_graph(payload)
    assert "inputs.enabled" not in text
    assert text.splitlines().count("anything (+first?, +second?, +third?, −old, +last)") == 1
    assert [g["fields"] for g in groups] == [[["first"], ["second"]], [["third"]], [["old"]], [["last"]]]


def test_summary_is_additive_and_rendering_legacy_v1_data_is_supported():
    from copy import deepcopy
    from ordo.runtime.graph_summary import summarize_static_graph
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("a", read(), write("b")), workflow("b", read("b"), write()))
    legacy = deepcopy(payload)
    legacy.pop("summary")
    before = deepcopy(legacy)
    assert summarize_static_graph(legacy) == payload["summary"]
    assert legacy == before
    assert render_static_graph(legacy) == render_static_graph(payload)
    assert {key: value for key, value in payload.items() if key != "summary"} == before
    assert payload["possible_loop_components"] == [["a", "b"]]
    assert "loop" not in render_static_graph(payload).lower()


def test_summary_independent_contours_and_overlapping_context_usage():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("a", write("a", "'first'")),
                    workflow("bridge", read("a", "'first'"), write("b", "'second'")),
                    workflow("reader", read("b", "'second'")),
                    workflow("other-writer", write("x", "'third'")),
                    workflow("other-reader", read("x", "'third'")),
                    workflow("unused"))
    contours = payload["summary"]["contours"]
    assert len(contours) == 2
    assert len(contours[0]["contexts"]) == 2
    assert contours[0]["changes"][1]["reads"] == ["C1"]
    assert 'Contour 1 · store["first"]; store["second"]' in render_static_graph(payload)
    assert 'bridge (+store["second"].b)\n└── reader' in render_static_graph(payload)
    assert payload["summary"]["without_state_access"] == ["unused"]


def test_summary_does_not_guess_workflow_roles_from_names():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("close-task", write()), workflow("create-task", read()))
    text = render_static_graph(payload)
    assert "close-task (+a)\n└── create-task" in text
    assert "end context" not in text


def test_summary_unknown_indices_form_a_parameter_family_without_identity_claim():
    payload = graph(workflow("a", write(key="inputs.key")), workflow("b", read(key="inputs.key")))
    contexts = payload["summary"]["contours"][0]["contexts"]
    assert len(contexts) == 1 and contexts[0]["parameter_family"]
    assert contexts[0]["address"]["key_identity"] == "unresolved"
    assert payload["structural_links"][0]["selector_correspondence"] == "independent_parameters"
    assert payload["links"][0]["address_identity"] == "possible"


def test_summary_does_not_merge_across_reads_or_changed_gate_context():
    w = workflow("ordered", write(), read("b"), write(),
                 Step(name="checkpoint", gate="inputs.admit"), write())
    payload = graph(w)
    groups = payload["summary"]["contours"][0]["changes"][0]["groups"]
    assert len(groups) == 3
    assert groups[-1]["conditions"] != groups[-2]["conditions"]
    assert [site for group in groups for site in group["sites"]] == ["ordered:0", "ordered:2", "ordered:3"]


def test_graph_snippet_verifies_compact_presentation_and_accepts_legacy_bundles():
    import pytest
    import yaml
    from ordo.model.help_snippets import GRAPH_BUNDLE_EXAMPLE
    from ordo.runtime.help_snippet_runner import verify_help_snippet
    snippet = GRAPH_BUNDLE_EXAMPLE["yaml"]
    with pytest.raises(ValueError, match="compact text mismatch"):
        verify_help_snippet(snippet=snippet.replace("└── observer", "Transition: observer"),
                            world="default", insertion_mode="graph_bundle", target="state")
    legacy = yaml.safe_load(snippet)
    legacy.pop("expected_text")
    result = verify_help_snippet(snippet=yaml.safe_dump(legacy), world="default",
                                 insertion_mode="graph_bundle", target="state")
    assert result.status == "ok"


def test_summary_overlapping_processes_keep_shared_workflow_once():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("one", read("done_one"), write("start_one")),
                    workflow("two", read("done_two"), write("start_two")),
                    workflow("shared", read("start_one"), read("start_two"),
                             replace(write("done_one"), if_="inputs.one"),
                             replace(write("done_two"), if_="inputs.two")))
    assert len(payload["summary"]["contours"]) == 1
    text = render_static_graph(payload)
    assert text.splitlines().count("shared (+done_one?, +done_two?)") == 1
    groups = payload["summary"]["contours"][0]["changes"][-1]["groups"]
    assert [g["conditions"][-1]["expression"] for g in groups] == ["inputs.one", "inputs.two"]
    assert "inputs.one" not in text and "inputs.two" not in text
    assert "->" not in text
    assert "loop" not in text.lower()


def _summary_user(payload, name="consumer"):
    return next(user for contour in payload["summary"]["contours"]
                for user in contour["users"] if user["workflow"] == name)


def test_user_placement_single_covering_source_ignores_irrelevant_writes():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", write("x"), write("y"), write("extra"),
                             replace(write("later"), if_="inputs.enabled")),
                    workflow("consumer", read("x"), read("y")))
    user = _summary_user(payload)
    assert user["placement"]["kind"] == "single_source"
    assert user["placement"]["sources"] == ["S1"]
    text = render_static_graph(payload)
    assert "producer (+x, +y, +extra, +later?)\n└── consumer" in text
    assert text.count("└── consumer") == 1
    assert "inputs.enabled" not in text


def test_user_placement_join_requires_all_read_addresses():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("p1", write("x")), workflow("p2", write("y")),
                    workflow("consumer", read("x"), read("x"), read("y")))
    user = _summary_user(payload)
    assert user["placement"]["kind"] == "join"
    assert user["placement"]["sources"] == ["S1", "S2"]
    assert user["placement"]["after"] == "S2"
    assert sum(len(d["reads"]) for d in user["dependencies"]) == 3
    assert "p1 (+x)\np2 (+y)\n└── consumer" in render_static_graph(payload)


def test_user_placement_alternatives_do_not_choose_latest_conditional_writer():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("p1", write("x")),
                    workflow("p2", replace(write("x"), if_="inputs.enabled")),
                    workflow("consumer", read("x")))
    user = _summary_user(payload)
    assert user["placement"]["kind"] == "alternatives"
    assert user["placement"]["sources"] == ["S1", "S2"]
    assert user["placement"]["conditional_sources"] == ["S2"]
    assert user["placement"]["after"] is None
    assert user["dependencies"][0]["sources"][1]["conditions"] == [{"kind": "if", "expression": "inputs.enabled"}]
    text = render_static_graph(payload)
    assert "p1 (+x)\np2 (+x?)\nconsumer" in text
    assert "Unresolved placement" not in text
    assert text.count("? conditional") == 1
    assert "from S2" not in text


def test_user_placement_join_with_alternatives_preserves_per_field_options():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("p1", write("x")), workflow("p2", write("x")),
                    workflow("p3", write("y")), workflow("consumer", read("x"), read("y")))
    assert _summary_user(payload)["placement"]["kind"] == "join_with_alternatives"
    assert _summary_user(payload)["placement"]["after"] == "S3"
    assert "p1 (+x)\np2 (+x)\np3 (+y)\n└── consumer" in render_static_graph(payload)


def test_user_placement_unique_conditional_source_is_not_permission():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", replace(write("x"), if_="false")), workflow("consumer", read("x")))
    user = _summary_user(payload)
    assert user["placement"]["kind"] == "single_source"
    assert user["placement"]["availability"] == "symbolic"
    assert user["placement"]["conditional_sources"] == ["S1"]
    text = render_static_graph(payload)
    assert "not execution order" in text
    assert "producer (+x?)\n└── consumer" in text


def test_user_placement_missing_and_possible_coverage_stays_unresolved():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", write("x")), workflow("consumer", read("x"), read("missing")))
    user = _summary_user(payload)
    assert user["placement"]["kind"] == "unresolved"
    assert user["placement"]["unresolved_dependencies"] == [1]
    assert "producer (+x)\nUnresolved placement\n└── consumer" in render_static_graph(payload)
    no_sources = graph(workflow("consumer", read("x")))
    assert _summary_user(no_sources)["placement"]["after"] is None
    partial = graph(workflow("producer", write("parent")), workflow("consumer", read("parent.child")))
    assert _summary_user(partial)["placement"]["parametric"]
    assert "producer (+parent)\n└── consumer" in render_static_graph(partial)
    assert any(r["predicate"] == "read_shape_available" for r in partial["structural_links"][0]["requirements"])
    uncertain = graph(workflow("producer", write(key="inputs.key")), workflow("consumer", read(key="inputs.key")))
    assert _summary_user(uncertain)["placement"]["kind"] == "single_source"
    assert _summary_user(uncertain)["placement"]["parametric"]


def test_user_placement_catch_reads_and_external_effects_are_not_dropped():
    from ordo.model.workflow import OperationRef
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", write("x")),
                    workflow("optional-source", replace(write("y"), if_="inputs.ship")),
                    workflow("consumer", read("x"),
                        Step(name="optional", value='state.s[\'repo\'].y | catch(["runtime.value.state_missing"], null)'),
                        Step(name="external", operation=OperationRef(uses="gh.issue.close"))))
    user = _summary_user(payload)
    assert user["placement"]["kind"] == "join"
    assert user["placement"]["conditional_sources"] == ["S2"]
    assert "catch" in user["dependencies"][1]["reads"][0]["expression"]
    assert "producer (+x)\noptional-source (+y?)\n└── consumer" in render_static_graph(payload)


def test_user_placement_cycles_do_not_duplicate_or_topologically_order_users():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("p1", read("y"), write("x")), workflow("p2", read("x"), write("y")),
                    workflow("consumer", read("x"), read("y")))
    assert payload["possible_loop_components"] == [["p1", "p2"]]
    assert _summary_user(payload)["placement"]["kind"] == "join"
    text = render_static_graph(payload)
    assert text.count("└── consumer") == 1
    assert "loop" not in text.lower()
    assert "->" not in text


def test_user_placement_incomplete_reader_and_old_summaries_are_honest():
    from copy import deepcopy
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", write("x")),
                    workflow("consumer", read("x"), Step(name="unknown", run="unknown")))
    assert _summary_user(payload)["placement"]["kind"] == "unresolved"
    text = render_static_graph(payload)
    assert "Unresolved placement\n└── consumer" in text
    assert _summary_user(payload)["placement"]["incomplete_reader"] is True
    old = deepcopy(payload)
    old["summary"].pop("placement_version")
    for contour in old["summary"]["contours"]:
        for user in contour["users"]:
            user.pop("placement")
    assert render_static_graph(old) == text


def test_human_labels_leave_json_ids_and_evidence_unchanged():
    from copy import deepcopy
    import re
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", write("x")), workflow("reader", read("x")))
    before = deepcopy(payload)
    text = render_static_graph(payload)
    assert payload == before
    assert payload["summary"]["contours"][0]["changes"][0]["groups"][0]["id"] == "S1"
    assert 'store["repo"]' in text
    assert "producer (+x)\n└── reader" in text
    assert "Context user" not in text
    assert not re.search(r"\b[CS]\d+\b", text)
    assert "/absent/" not in text


def test_human_store_names_disambiguate_actual_paths_across_contours():
    from ordo.runtime.graphing import render_static_graph
    first = replace(workflow("first", write()), states={"store": "/one/state.json"})
    second = replace(workflow("second", write()), states={"store": "/two/state.json"})
    text = render_static_graph(graph(first, second))
    assert 'store (one/state.json)["repo"]' in text
    assert 'store (two/state.json)["repo"]' in text
    assert "/one/state.json" not in text  # The unique suffix suffices.


def test_human_source_names_disambiguate_same_fields_at_different_keys():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", write("x", "'one'"), write("x", "'two'")),
                    workflow("reader", read("x", "'one'"), read("x", "'two'")))
    text = render_static_graph(payload)
    assert 'store["one"]; store["two"]' in text
    assert 'producer (+store["one"].x, +store["two"].x)\n└── reader' in text
    assert text.count("└── reader") == 1


def test_human_alternative_labels_preserve_distinct_write_occurrences():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", write("x"), read("barrier"), write("x")),
                    workflow("reader", read("x")))
    text = render_static_graph(payload)
    assert "producer (+x)\nreader" in text
    assert _summary_user(payload, "reader")["placement"]["sources"] == ["S1", "S2"]
    assert _summary_user(payload, "reader")["placement"]["kind"] == "alternatives"
    assert "Context user" not in text


def test_old_alternatives_anchor_is_not_rendered_as_a_parent_or_mutated():
    from copy import deepcopy
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("first", write("x")), workflow("last", write("x")), workflow("reader", read("x")))
    user = _summary_user(payload, "reader")
    user["placement"]["after"] = "S2"  # Previously serialized placement.
    before = deepcopy(payload)
    text = render_static_graph(payload)
    assert "first (+x)\nlast (+x)\nreader" in text
    assert "└── reader" not in text and "Unresolved placement" not in text
    assert payload == before


def test_default_tree_is_exact_and_keeps_all_evidence_in_json():
    from copy import deepcopy
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", replace(write("internal_field"), if_="inputs.internal_flag")),
                    workflow("first-reader", read("internal_field")),
                    workflow("second-reader", read("internal_field")),
                    workflow("terminator", Step(name="delete", state_delete="state.s['repo']")))
    before = deepcopy(payload)
    assert render_static_graph(payload) == '''+ writes, − deletes, ? conditional; branches show data use, not execution order.
Ties within a category follow playbook order.

Context · store["repo"]

producer (+internal_field?)
├── first-reader
└── second-reader
terminator (−context)

Details: --json.'''
    assert payload == before
    group = payload["summary"]["contours"][0]["changes"][0]["groups"][0]
    assert group["fields"] == [["internal_field"]]
    assert group["conditions"] == [{"kind": "if", "expression": "inputs.internal_flag"}]
    assert payload["links"]


def test_parametric_tree_placement_keeps_unknown_selector_conditions_in_json():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("producer", write(key="inputs.private_key")),
                    workflow("consumer", read(key="inputs.private_key")))
    text = render_static_graph(payload)
    assert "inputs.private_key" not in text
    assert "[parameter]" in text
    assert "producer (+a)\n└── consumer" in text
    assert "Parametric links require matching selectors" in text
    assert text.count("consumer") == 1


def test_effect_suffix_deduplicates_in_first_seen_order_without_mutating_json():
    from copy import deepcopy
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("mutator", write("b"), read("barrier"), write("b"), write("a"),
        Step(name="delete", state_delete="state.s['repo'].b"),
        Step(name="delete-again", state_delete="state.s['repo'].b")))
    before = deepcopy(payload)
    text = render_static_graph(payload)
    assert "mutator (+b, +a, −b)" in text
    assert text.count("+b") == text.count("−b") == 1
    assert payload == before
    assert len(payload["summary"]["contours"][0]["changes"][0]["groups"]) == 3


def test_effect_suffix_does_not_infer_unconditional_branch_coverage():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("mutator", replace(write("x"), if_="inputs.enabled"),
        replace(write("x"), if_="not inputs.enabled"), write("x")))
    text = render_static_graph(payload)
    assert "mutator (+x?)" in text
    assert text.count("+x?") == 1
    assert "inputs.enabled" not in text


def test_effect_suffix_preserves_uncertainty_across_guard_contexts():
    from ordo.model.workflow import Guard, GuardBlock, StepBlock
    from ordo.runtime.graphing import render_static_graph
    w = workflow("guarded")
    w = replace(w, blocks=(GuardBlock(guards=(Guard(expr="inputs.first"),)),
        StepBlock(steps=(write("x"),)), GuardBlock(guards=(Guard(expr="inputs.second"),)),
        StepBlock(steps=(write("x"),))))
    assert "guarded (+x?)" in render_static_graph(graph(w))
    single_guard = replace(w, blocks=w.blocks[:2])
    assert "guarded (+x)" in render_static_graph(graph(single_guard))


def test_effect_suffix_handles_conditional_partial_and_whole_deletion():
    from ordo.runtime.graphing import render_static_graph
    w = workflow("cleanup",
        Step(name="partial", state_delete="state.s['repo'].parent.child", if_="inputs.partial"),
        Step(name="whole", state_delete="state.s['repo']", if_="not inputs.partial"))
    text = render_static_graph(graph(w))
    assert "cleanup (−parent.child?, −context?)" in text
    assert text.startswith("+ writes, − deletes, ? conditional; branches show data use, not execution order.\n")
    assert text.count("? conditional") == 1


def test_effect_suffix_qualifies_multiple_contexts_and_marks_symbolic_repeat():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("mutator", write("x", "'one'"),
        Step(name="repeat", for_each="inputs.items", steps=(write("x", "'two'"),)),
        Step(name="delete", state_delete="state.s['two']")))
    text = render_static_graph(payload)
    assert 'mutator (+store["one"].x, +store["two"].x?, −store["two"])' in text


def test_effect_suffix_distinguishes_a_field_named_context_from_root_deletion():
    from ordo.runtime.graphing import render_static_graph
    payload = graph(workflow("cleanup", Step(name="field", state_delete="state.s['repo'].context"),
                             Step(name="root", state_delete="state.s['repo']")))
    assert 'cleanup (−store["repo"].context, −context)' in render_static_graph(payload)
