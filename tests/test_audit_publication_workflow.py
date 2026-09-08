"""Project-local publication audit composition, not an engine behavior test."""

from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from ordo.model.runtime import OperationResult, RuntimeStatus
from ordo.runtime import execute_workflow, load_workflow_file
from tests.support import STANDARD_CONNECTOR_PROVIDER


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".ordo/workflows/audit-publication.yml"
SCANNERS = (
    "gitleaks-tree", "gitleaks-history", "gitleaks-metadata", "bandit",
    "semgrep", "pip-audit", "shellcheck", "inventory",
)
ROUTINES = tuple(
    f"routine.audit.{name if name != 'inventory' else 'publication-inventory'}"
    for name in SCANNERS
)
PROBES = {"bandit", "semgrep", "pip-audit", "shellcheck"}


def test_publication_workflow_replaces_history_catalog_entry():
    catalog = yaml.safe_load((ROOT / ".ordo/ordo.yaml").read_text())
    workflows = catalog["workflows"]
    assert "audit-secrets-history" not in workflows
    assert workflows["audit-publication"]["file"] == "workflows/audit-publication.yml"
    assert "audit-secrets-tree" in workflows
    assert not (ROOT / ".ordo/workflows/audit-secrets-history.yml").exists()
    assert {name for name in workflows if name.startswith("audit-")} == {
        "audit-publication", "audit-secrets-tree",
    }


def test_publication_sequence_retains_manual_review_requirement():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    assert workflow["workflow"] == "audit-publication"
    assert workflow["inputs"]["scanner"]["default"] == "all"
    assert workflow["inputs"]["allow_dependency_lookup"]["default"] is False
    guards = workflow["blocks"][0]["guards"]
    assert "git.repo.exists" in guards
    assert "inputs.allow_dependency_lookup | is_boolean" in guards
    assert guards[0].startswith("inputs.scanner | in(")
    assert json.loads(guards[0].removeprefix("inputs.scanner | in(").removesuffix(")")) == [
        "all", *SCANNERS,
    ]
    steps = workflow["blocks"][1]["steps"]
    calls = [step for step in steps if "uses" in step]
    assert [step["uses"] for step in calls] == list(ROUTINES)
    reports = [step for step in steps[:-1] if "publish" in step]
    assert len(reports) == len(SCANNERS)
    routines = yaml.safe_load((ROOT / ".ordo/routines.yaml").read_text())["routines"]
    for scanner, call, report in zip(SCANNERS, calls, reports, strict=True):
        condition = f'inputs.scanner == "all" or inputs.scanner == "{scanner}"'
        assert call["if"] == report["if"] == condition
        assert steps.index(call) < steps.index(report)
        output = "data" if scanner in PROBES else "stdout_tail | json"
        assert report["publish"] == {
            scanner.replace("-", "_"): f'step.{call["register"]}.outputs.{output}',
        }
        routine = routines[call["uses"].removeprefix("routine.")]
        assert routine["kind"] == ("probe" if scanner in PROBES else "action")
        script = "publication-inventory" if scanner == "inventory" else scanner
        assert routine["implementation"]["argv"] == [
            f".ordo/scripts/audit-{script}.sh",
            *(["{allow_network}"] if scanner == "pip-audit" else []),
        ]
        if scanner in PROBES:
            assert routine["outputs"] == {"mode": "data", "format": "json"}
        else:
            assert "outputs" not in routine
            assert routine["failure_modes"] == (
                ["inventory_incomplete", "runtime_unavailable"] if scanner == "inventory"
                else ["secrets_found", "scan_incomplete", "runtime_unavailable"]
            )
    gates = [step for step in steps if "gate" in step]
    assert len(gates) == 1
    gate = gates[0]
    pip = calls[SCANNERS.index("pip-audit")]
    assert gate["gate"] == "inputs.allow_dependency_lookup"
    assert gate["if"] == pip["if"]
    assert steps.index(gate) < steps.index(pip)
    assert pip["with"]["args"]["allow_network"] is True
    assert routines["audit.pip-audit"]["args"]["allow_network"] == {
        "type": "boolean", "required": True,
    }
    publication = steps[-1]["publish"]
    assert publication["publication_status"] == "manual-review-needed"
    assert publication["audit_scope"] == "inputs.scanner"
    assert "manual publication review remains required" in publication["summary"]
    assert "Not publication clearance" in publication["recommendation"]
    assert "if" not in steps[-1]
    assert all("on_failure" not in step for step in steps)


def _execute(monkeypatch, inputs, *, fail=None):
    subprocess_run = Mock(side_effect=AssertionError("No external commands in workflow tests"))
    monkeypatch.setattr("subprocess.run", subprocess_run)
    workflow = load_workflow_file(WORKFLOW, launch_dir=ROOT)
    workflow = replace(workflow, inputs={**workflow.inputs, **inputs})
    calls = []
    reports = []

    def executor(resolved, _workflow):
        assert resolved.reference in ROUTINES
        scanner = SCANNERS[ROUTINES.index(resolved.reference)]
        calls.append((resolved.reference, resolved.resolved_inputs))
        if scanner == fail:
            return OperationResult(status="execution_error", summary="Synthetic scanner failure")
        report = {"scanner": scanner, "status": "clean", "findings": []}
        reports.append({scanner.replace("-", "_"): report})
        outputs = {"data": report} if scanner in PROBES else {"stdout_tail": json.dumps(report)}
        return OperationResult(status="ok", outputs=outputs)

    guard_probe = Mock(return_value=OperationResult(status="ok", outputs={"exists": True}))
    result = execute_workflow(
        workflow, guard_probe=guard_probe, step_executor=executor,
        connector_provider=STANDARD_CONNECTOR_PROVIDER,
    )
    assert all(call.args[0].reference == "git.repo" for call in guard_probe.call_args_list)
    subprocess_run.assert_not_called()
    return result, calls, reports


@pytest.mark.parametrize("inputs,selected,scope", [
    ({"allow_dependency_lookup": True}, SCANNERS, "all"),
    ({"scanner": "bandit"}, ("bandit",), "bandit"),
    ({"scanner": "pip-audit", "allow_dependency_lookup": True}, ("pip-audit",), "pip-audit"),
])
def test_selected_scanners_publish_parsed_reports(monkeypatch, inputs, selected, scope):
    result, calls, reports = _execute(monkeypatch, inputs)
    assert result.status == RuntimeStatus.OK, result.to_contract()
    assert result.outputs["can_execute"] is True
    assert [reference for reference, _ in calls] == [
        ROUTINES[SCANNERS.index(scanner)] for scanner in selected
    ]
    for reference, arguments in calls:
        assert arguments == ({"args": {"allow_network": True}} if reference.endswith("pip-audit") else {})
    published = result.to_contract()["published"]
    assert published[:-1] == reports
    assert published[-1]["audit_scope"] == scope
    assert published[-1]["publication_status"] == "manual-review-needed"
    assert "Not publication clearance" in published[-1]["recommendation"]


@pytest.mark.parametrize("scanner", ["pip-audit", "unknown-scanner"])
def test_rejected_selection_never_calls_scanners(monkeypatch, scanner):
    result, calls, reports = _execute(monkeypatch, {"scanner": scanner})
    assert calls == reports == []
    assert result.outputs["can_execute"] is False
    assert result.to_contract()["published"] == []
    if scanner == "pip-audit":
        assert result.status == RuntimeStatus.EXECUTION_ERROR, result.to_contract()
        assert result.failed_step == "Require permission for dependency vulnerability lookup"
        assert "runtime.step.gate.failed" in {item.code for item in result.diagnostics}
    else:
        assert result.status == RuntimeStatus.GUARD_FAILED, result.to_contract()
        assert result.failed_guard == yaml.safe_load(WORKFLOW.read_text())["blocks"][0]["guards"][0]


def test_scanner_failure_stops_sequence_without_publication_clearance(monkeypatch):
    result, calls, reports = _execute(monkeypatch, {"allow_dependency_lookup": True}, fail="bandit")
    assert result.status == RuntimeStatus.EXECUTION_ERROR, result.to_contract()
    assert result.outputs["can_execute"] is False
    assert result.failed_step == "Audit production Python with Bandit"
    assert [reference for reference, _ in calls] == list(ROUTINES[:4])
    # Failure envelopes retain report operations, not top-level publications.
    assert result.to_contract()["published"] == []
    assert [
        operation.outputs["value"] for operation in result.operation_results
        if operation.raw.get("step_detail", {}).get("reference") == "publish"
    ] == reports
    assert len(reports) == 3
    assert all("publication_status" not in report for report in result.published)
