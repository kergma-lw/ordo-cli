"""Static profile context and launch/body provenance, without runtime effects."""

import yaml

from ordo.playbook import build_playbook_static_graph


def _project(tmp_path, workflows, *, bootstrap=False, profiles=None):
    profiles = profiles or {
        "alpha": {"repository": "org/alpha", "repo_dir": "/static/alpha", "selector": "profile-selector"},
        "beta": {"repository": "org/beta", "repo_dir": "/static/beta", "selector": "other-selector"},
    }
    catalog = {}
    for name, document in workflows.items():
        document = {"version": 0, "workflow": name, **document}
        (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        catalog[name] = {"file": f"./{name}.yaml", "state_bindings": {
            role: role for role in document.get("state_needs", {})}}
    for name, inputs in profiles.items():
        (tmp_path / f"{name}-profile.yaml").write_text(yaml.safe_dump({
            "name": name, "inputs": inputs, "working_directory": "${inputs.repo_dir}"}, sort_keys=False), encoding="utf-8")
    book = {"version": 1, "defaults": {"profile": "alpha"},
            "profiles": {name: {"file": f"./{name}-profile.yaml"} for name in profiles},
            "states": {"data": {"path": "state.json"}, "env": {"path": str(tmp_path / "env.json")}},
            "workflows": catalog}
    if bootstrap:
        (tmp_path / "bootstrap.yaml").write_text('''version: 0
workflow: bootstrap
inputs:
  selector: {default: selected}
state_needs:
  env: {}
let:
  chosen: state.env[inputs.selector]
blocks:
  - steps:
      - name: select
        profile_switch: ${chosen}
''', encoding="utf-8")
        book["pre_run"] = [{"file": "./bootstrap.yaml", "state_bindings": {"env": "env"}}]
    path = tmp_path / "ordo.yaml"
    path.write_text(yaml.safe_dump(book, sort_keys=False), encoding="utf-8")
    return path


def _writer(*steps, profile=None):
    return {**({"profile": profile} if profile else {}),
            "inputs": {"repository": {}, "selector": {"default": "selected"}, "target": {}, "operator": {}},
            "state_needs": {"data": {}, "env": {}}, "blocks": [{"steps": list(steps)}]}


def _set(path):
    return {"name": "write", "state_set": {path: True}}


def _read(path):
    return {"name": "read", "value": "${" + path + "}"}


def test_known_switch_preserves_defaults_overrides_and_bound_locations(tmp_path):
    path = _project(tmp_path, {"writer": _writer(
        {"name": "switch", "profile_switch": "${inputs.target}"},
        _set("state.data[inputs.repository].issue"), _set("state.env[inputs.selector]"),
        _set("state.data[inputs.operator].marker"))})
    payload = build_playbook_static_graph(playbook_path=path, profile_name="alpha",
                                          input_overrides={"target": "beta", "operator": "explicit"})
    assert [a["address"]["key"] for a in payload["accesses"]] == ["org/beta", "selected", "explicit"]
    assert payload["accesses"][0]["working_directory"] == "/static/beta"
    assert payload["accesses"][0]["address"]["store"] == "/static/alpha/state.json"
    assert not payload["workflows"][0]["boundaries"]


def test_fixed_workflow_profile_uses_declared_catalog_before_body(tmp_path):
    path = _project(tmp_path, {"writer": _writer(_set("state.data[inputs.repository].issue"), profile="beta")})
    payload = build_playbook_static_graph(playbook_path=path, profile_name="alpha")
    assert payload["accesses"][0]["profile"] == "beta"
    assert payload["accesses"][0]["address"]["key"] == "org/beta"
    assert payload["accesses"][0]["working_directory"] == "/static/beta"
    assert not payload["workflows"][0]["boundaries"]


def test_explicit_profile_is_authoritative_over_bootstrap_without_reading_state(tmp_path, monkeypatch):
    import ordo.runtime.state as state
    import ordo.runtime.local_expressions as expressions
    def forbidden(*args, **kwargs):
        raise AssertionError("static graph must not observe or evaluate runtime expressions")
    monkeypatch.setattr(state, "read_state_document", forbidden)
    monkeypatch.setattr(expressions, "evaluate_parsed_local_expression", forbidden)
    path = _project(tmp_path, {"writer": _writer(_set("state.data[inputs.repository].issue"))}, bootstrap=True)
    payload = build_playbook_static_graph(playbook_path=path, profile_name="beta")
    bootstrap, body = payload["accesses"]
    assert bootstrap["phase"] == "bootstrap" and bootstrap["address"]["key"] == "selected"
    assert body["phase"] == "body" and body["address"]["key"] == "org/beta"
    assert not payload["workflows"][0]["boundaries"]
    assert not (tmp_path / "env.json").exists()


def test_unknown_bootstrap_preserves_fixed_state_links_and_finite_context_candidates(tmp_path):
    path = _project(tmp_path, {
        "writer": _writer(_set('state.env["fixed"]')),
        "reader": _writer(_read('state.env["fixed"]')),
        "context-reader": _writer(_read("state.data[inputs.repository].issue")),
    }, bootstrap=True)
    payload = build_playbook_static_graph(playbook_path=path)
    link = next(link for link in payload["links"] if link["from_workflow"] == "writer" and link["to_workflow"] == "reader")
    assert link["address_identity"] == "proven"
    reader = next(user for c in payload["summary"]["contours"] for user in c["users"] if user["workflow"] == "reader")
    assert reader["placement"]["kind"] == "single_source"
    assert reader["placement"]["phase"] == "body"
    assert not reader["placement"]["incomplete_reader"]
    contextual = next(a for a in payload["accesses"] if a["workflow"] == "context-reader" and a["phase"] == "body")
    assert contextual["address"]["key_identity"] == "unresolved"
    assert set(contextual["address"]["key_candidates"]) == {"org/alpha", "org/beta"}


def test_known_profile_change_propagates_through_unbound_call(tmp_path):
    path = _project(tmp_path, {"parent": _writer(
        {"name": "call", "run": "./child.yaml"}, _set("state.data[inputs.repository].issue"))})
    (tmp_path / "child.yaml").write_text('''version: 0
workflow: child
blocks:
  - steps:
      - name: switch
        profile_switch: "beta"
''', encoding="utf-8")
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["accesses"][0]["address"]["key"] == "org/beta"
    assert payload["accesses"][0]["working_directory"] == "/static/beta"


def test_bound_callee_profile_does_not_leak_to_caller(tmp_path):
    path = _project(tmp_path, {"parent": _writer(
        {"name": "call", "run": "./child.yaml"}, _set("state.data[inputs.repository].issue"))})
    (tmp_path / "child.yaml").write_text('''version: 0
workflow: child
profile: beta
blocks: []
''', encoding="utf-8")
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["accesses"][0]["address"]["key"] == "org/alpha"


def test_symbolic_repeat_lookup_has_bounded_domain_without_unrolling(tmp_path):
    doc = _writer({"name": "each", "for_each": "${inputs.profiles}", "steps": [
        {"name": "switch", "profile_switch": "${item}"},
        _read("state.data[inputs.repositories | lookup(item)].issue")]})
    doc["inputs"].update({"profiles": {"default": ["alpha", "beta"]},
                          "repositories": {"default": {"alpha": "org/alpha", "beta": "org/beta"}}})
    path = _project(tmp_path, {"reader": doc})
    payload = build_playbook_static_graph(playbook_path=path)
    assert len(payload["accesses"]) == 1
    assert set(payload["accesses"][0]["address"]["key_candidates"]) == {"org/alpha", "org/beta"}
    assert len(payload["workflows"][0]["repeats"]) == 1


def test_bootstrap_selector_does_not_merge_independent_business_contours(tmp_path):
    path = _project(tmp_path, {
        "selector-writer": _writer(_set('state.env["selected"]')),
        "first-writer": _writer(_set('state.env["first"]')),
        "first-reader": _writer(_read('state.env["first"]')),
        "second-writer": _writer(_set('state.env["second"]')),
        "second-reader": _writer(_read('state.env["second"]')),
        "bootstrap-only": {"inputs": {"selector": {"default": "selected"}}, "blocks": []},
    }, bootstrap=True)
    payload = build_playbook_static_graph(playbook_path=path)
    assert len(payload["components"]) == 1
    assert [set(c["workflows"]) for c in payload["summary"]["contours"]] == [
        {"selector-writer"}, {"first-writer", "first-reader"}, {"second-writer", "second-reader"}]
    assert len(payload["summary"]["bootstrap"]["accesses"]) == 6
    assert payload["summary"]["bootstrap"]["only_workflows"] == ["bootstrap-only"]
    assert any(link["to_workflow"] == "bootstrap-only" for link in payload["links"])


def test_conditional_profile_switch_does_not_claim_one_concrete_context(tmp_path):
    path = _project(tmp_path, {"writer": _writer(
        {"name": "switch", "profile_switch": '${"beta"}', "if": "inputs.enabled"},
        _set("state.data[inputs.repository].issue"))})
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["accesses"][0]["address"]["key"] is None
    assert set(payload["accesses"][0]["address"]["key_candidates"]) == {"org/alpha", "org/beta"}


def test_unknown_directory_does_not_poison_fixed_absolute_state(tmp_path):
    path = _project(tmp_path, {"writer": _writer(_set('state.env["fixed"]')),
                               "reader": _writer(_read('state.env["fixed"]'))},
                    profiles={"alpha": {"repository": "org/alpha"}})
    payload = build_playbook_static_graph(playbook_path=path)
    assert any(b["reason"] == "working_directory_unresolved" and b["impact"] == "context" for b in payload["boundaries"])
    user = payload["summary"]["contours"][0]["users"][0]
    assert user["placement"]["kind"] == "single_source"


def test_profile_without_directory_uses_ambient_launch_directory(tmp_path):
    path = _project(tmp_path, {"writer": _writer(
        {"name": "beta", "profile_switch": '${"beta"}'},
        {"name": "gamma", "profile_switch": '${"gamma"}'}, _set("state.data[inputs.repository].issue"))},
        profiles={name: {"repository": "org/" + name, "repo_dir": "/static/" + name} for name in ("alpha", "beta", "gamma")})
    file = tmp_path / "gamma-profile.yaml"
    document = yaml.safe_load(file.read_text(encoding="utf-8"))
    document.pop("working_directory")
    file.write_text(yaml.safe_dump(document), encoding="utf-8")
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["accesses"][0]["profile"] == "gamma"
    assert payload["accesses"][0]["working_directory"] == "/static/alpha"


def test_finite_lookup_domain_excludes_disjoint_handoffs_and_is_bounded(tmp_path):
    reader = _writer({"name": "each", "for_each": "${inputs.profiles}", "steps": [
        _read("state.data[inputs.repositories | lookup(item)].issue")]})
    reader["inputs"].update({"profiles": {"default": ["a", "b"]},
                            "repositories": {"default": {"a": "one", "b": "two"}}})
    path = _project(tmp_path, {"reader": reader, "writer": _writer(_set('state.data["unrelated"].issue'))})
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["links"] == []
    assert set(payload["accesses"][0]["address"]["key_candidates"]) == {"one", "two"}
    reader["inputs"]["profiles"]["default"] = list(range(33))
    path = _project(tmp_path, {"reader": reader})
    payload = build_playbook_static_graph(playbook_path=path)
    assert len(payload["accesses"]) == 1
    assert "key_candidates" not in payload["accesses"][0]["address"]
    assert any(b["reason"] == "static_item_domain_limit" for b in payload["workflows"][0]["boundaries"])


def test_profile_bundle_verifies_actual_static_playbook_without_state_reads(monkeypatch):
    from ordo.model.help_snippets import GRAPH_PROFILE_EXAMPLE
    from ordo.runtime.help_snippet_runner import verify_help_snippet
    import ordo.runtime.state as state
    def forbidden(*args, **kwargs):
        raise AssertionError("no state contents in static snippet verification")
    monkeypatch.setattr(state, "read_state_document", forbidden)
    result = verify_help_snippet(snippet=GRAPH_PROFILE_EXAMPLE["yaml"], world="default",
                                 insertion_mode="graph_bundle", target="state")
    assert result.status == "ok"
    assert result.graph_result["summary"]["bootstrap"]["only_workflows"] == ["bootstrap-only"]
    assert len(result.graph_result["links"]) == 3


def test_known_let_switch_preserves_cli_and_entry_protected_keys(tmp_path):
    document = _writer({"name": "switch", "profile_switch": "${chosen}"},
                       _set("state.data[inputs.repository].issue"))
    document["let"] = {"chosen": "inputs.target"}
    path = _project(tmp_path, {"writer": document})
    book = yaml.safe_load(path.read_text(encoding="utf-8"))
    book["workflows"]["writer"]["with"] = {"target": "beta", "repository": "org/entry"}
    path.write_text(yaml.safe_dump(book, sort_keys=False), encoding="utf-8")
    entry = build_playbook_static_graph(playbook_path=path)
    assert entry["accesses"][0]["address"]["key"] == "org/entry"
    cli = build_playbook_static_graph(playbook_path=path, input_overrides={"repository": "org/cli"})
    assert cli["accesses"][0]["profile"] == "beta"
    assert cli["accesses"][0]["address"]["key"] == "org/cli"


def test_conditional_same_profile_call_does_not_invent_other_profile_candidates(tmp_path):
    path = _project(tmp_path, {"parent": _writer(
        {"name": "call", "run": "./child.yaml"}, _set("state.data[inputs.repository].issue"))})
    (tmp_path / "child.yaml").write_text('''version: 0
workflow: child
blocks:
  - steps:
      - name: switch
        if: inputs.enabled
        profile_switch: "alpha"
''', encoding="utf-8")
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["accesses"][0]["profile"] == "alpha"
    assert payload["accesses"][0]["address"]["key"] == "org/alpha"
    assert "key_candidates" not in payload["accesses"][0]["address"]


def test_explicit_launch_and_different_bound_profile_keep_bootstrap_scope_honest(tmp_path):
    path = _project(tmp_path, {"writer": _writer(_set("state.data[inputs.repository].issue"), profile="alpha")}, bootstrap=True)
    source = tmp_path / "bootstrap.yaml"
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    document["inputs"]["repository"] = {}
    document["blocks"][0]["steps"].append(_read("state.env[inputs.repository]"))
    source.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    payload = build_playbook_static_graph(playbook_path=path, profile_name="beta")
    bootstrap_read = next(a for a in payload["accesses"] if a["phase"] == "bootstrap" and a["address"]["key"] is None)
    assert set(bootstrap_read["address"]["key_candidates"]) == {"org/alpha", "org/beta"}
    body = next(a for a in payload["accesses"] if a["phase"] == "body")
    assert body["profile"] == "alpha" and body["address"]["key"] == "org/alpha"
    assert body["address"]["store"] == "/static/beta/state.json"


def test_unknown_callee_cannot_leave_a_false_concrete_profile_binding(tmp_path):
    path = _project(tmp_path, {"parent": _writer(
        {"name": "call", "run": "./child.yaml"}, _set("state.data[inputs.repository].issue"))})
    # A recursive boundary supplies an unknown final profile, not an implicit no-op.
    (tmp_path / "child.yaml").write_text('''version: 0
workflow: child
blocks:
  - steps:
      - name: recurse
        run: ./child.yaml
''', encoding="utf-8")
    payload = build_playbook_static_graph(playbook_path=path)
    assert set(payload["accesses"][0]["address"]["key_candidates"]) == {"org/alpha", "org/beta"}
    assert any(b["reason"] == "recursion" for b in payload["workflows"][0]["boundaries"])


def test_inline_call_profile_propagates_locally_but_not_into_bound_parent(tmp_path):
    path = _project(tmp_path, {"parent": _writer(
        {"name": "each", "for_each": '${["unit"]}', "steps": [
            {"name": "call", "run": "./child.yaml"}, _read("state.data[inputs.repository].issue")]},
        _set("state.data[inputs.repository].done"), profile="alpha")})
    (tmp_path / "child.yaml").write_text('''version: 0
workflow: child
blocks:
  - steps:
      - name: switch
        profile_switch: "beta"
''', encoding="utf-8")
    payload = build_playbook_static_graph(playbook_path=path)
    assert [a["address"]["key"] for a in payload["accesses"]] == ["org/beta", "org/alpha"]


def test_missing_literal_profile_does_not_invent_another_named_profile(tmp_path):
    path = _project(tmp_path, {"writer": _writer(
        {"name": "switch", "profile_switch": '${"absent"}'},
        _set("state.data[inputs.repository].issue"), _set("state.env[inputs.selector]"))})
    payload = build_playbook_static_graph(playbook_path=path)
    assert "key_candidates" not in payload["accesses"][0]["address"]
    assert payload["accesses"][1]["address"]["key"] == "selected"
    assert payload["workflows"][0]["boundaries"][0]["target"] == "absent"


def test_legacy_profile_action_has_static_context_parity_without_execution(tmp_path):
    # Compatibility coverage, not a recommended authoring pattern.
    path = _project(tmp_path, {"writer": _writer(
        {"name": "legacy", "uses": "runtime.profile.use", "with": {"profile": '${"beta"}'}},
        _set("state.data[inputs.repository].issue"))})
    payload = build_playbook_static_graph(playbook_path=path)
    assert payload["accesses"][0]["address"]["key"] == "org/beta"
    assert payload["accesses"][0]["profile"] == "beta"
