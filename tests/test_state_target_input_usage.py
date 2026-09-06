import pytest

from ordo.model.runtime import RuntimeStatus
from ordo.model.workflow import Step, Workflow
from ordo.runtime import check_workflow, explain_workflow, plan_workflow, review_workflow
from ordo.runtime.checking import _collect_input_names_from_expression_node
from ordo.runtime.local_expression_engine.core import parse_local_expression_tree

from tests.support import STANDARD_CONNECTOR_PROVIDER


@pytest.mark.parametrize("mode", [check_workflow, review_workflow, plan_workflow, explain_workflow])
@pytest.mark.parametrize("mutation", ["state_set", "state_delete"])
@pytest.mark.parametrize(
    "target,used",
    [
        ("state.shared_state[inputs.active_profile_key]", {"active_profile_key"}),
        ("state.shared_state[inputs.active_profile_key].profile", {"active_profile_key"}),
        ("state.shared_state[state.lookup[inputs.active_profile_key].key].profile", {"active_profile_key"}),
        ('state.shared_state[format("{}:{}", inputs.active_profile_key, inputs.suffix)]', {"active_profile_key", "suffix"}),
        ('state.shared_state["inputs.active_profile_key"]', set()),
        ('state.shared_state[format("inputs.active_profile_key:{}", inputs.suffix)]', {"suffix"}),
    ],
)
def test_state_target_input_usage(tmp_path, mode, mutation, target, used):
    state_path = tmp_path / "state.json"
    step = Step(name="mutate", **{mutation: {target: 1} if mutation == "state_set" else target})
    workflow = Workflow(
        version=0,
        workflow="state-target-inputs",
        declared_inputs={"active_profile_key": {}, "suffix": {}},
        state_needs={"shared_state": {}, "lookup": {}},
        state_bindings={"shared_state": "store", "lookup": "lookup_store"},
        states={"store": str(state_path), "lookup_store": str(tmp_path / "lookup.json")},
        steps=(step,),
    )

    result = mode(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

    assert result.status is RuntimeStatus.OK, result.diagnostics
    usages = {item["input"]: item for item in result.analysis_tree.input_usages}
    for name, usage in usages.items():
        assert usage["classification"] == ("control_input" if name in used else "unused_input")
        assert usage["evidence"] == ([{
            "site_kind": mutation,
            "path": ["blocks", "0", "steps", "0", mutation],
            "detail": "mutate",
        }] if name in used else [])
    if mode is review_workflow:
        unused = {
            item["path"][-1] for item in result.outputs["findings"]
            if item["code"] == "review.workflow.input_declared_but_unused"
        }
        assert unused == set(usages) - used
    assert not state_path.exists()
    assert not (tmp_path / "lookup.json").exists()


@pytest.mark.parametrize("rhs", ["${inputs.profile}", {"inputs.ordinary_key": "${inputs.profile}"}])
def test_state_set_preserves_rhs_usage_without_scanning_mapping_keys(tmp_path, rhs):
    workflow = Workflow(
        version=0,
        workflow="state-set-rhs-inputs",
        declared_inputs={"active_profile_key": {}, "profile": {}, "ordinary_key": {}},
        state_needs={"shared_state": {}},
        state_bindings={"shared_state": "store"},
        states={"store": str(tmp_path / "state.json")},
        steps=(Step(name="remember", state_set={
            "state.shared_state[inputs.active_profile_key]": rhs,
        }),),
    )

    result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

    assert result.status is RuntimeStatus.OK, result.diagnostics
    usages = {item["input"]: item for item in result.analysis_tree.input_usages}
    for name in ("active_profile_key", "profile"):
        assert usages[name]["classification"] == "control_input"
        assert usages[name]["evidence"] == [{
            "site_kind": "state_set",
            "path": ["blocks", "0", "steps", "0", "state_set"],
            "detail": "remember",
        }]
    assert usages["ordinary_key"]["classification"] == "unused_input"
    assert usages["ordinary_key"]["evidence"] == []
    unused = [item["path"] for item in result.outputs["findings"] if item["code"] == "review.workflow.input_declared_but_unused"]
    assert unused == [["inputs", "ordinary_key"]]
    assert not (tmp_path / "state.json").exists()


def test_input_ast_traversal_descends_into_nested_state_keys():
    expression = parse_local_expression_tree(
        'state.shared_state[state.lookup[format("inputs.literal:{}", inputs.key)].key].profile'
    )

    assert _collect_input_names_from_expression_node(expression.root) == {"key"}
