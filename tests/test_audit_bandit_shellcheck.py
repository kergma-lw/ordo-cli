"""Adapter contracts using fake scanners and real temporary selected paths."""

from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / ".ordo/scripts"


@pytest.fixture(params=["bandit", "shellcheck"])
def adapter(request, monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("audit_scanner_common", SCRIPTS / "audit_scanner_common.py")
    c = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, c)
    spec.loader.exec_module(c)
    name = request.param
    spec = importlib.util.spec_from_file_location("audit_" + name, SCRIPTS / ("audit-" + name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source"
    source.mkdir()
    filename = "src/a.py" if name == "bandit" else "script.sh"
    path = source / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("pass\n" if name == "bandit" else "#!/bin/sh\ntrue\n")
    snap = c.Snapshot(tmp_path, source, [filename], [str(path)], {"selected_count": 1, "tracked_count": 3, "excluded_deleted": 1, "history": False, "untracked": False})
    snapshot = Mock(return_value=nullcontext(snap))
    monkeypatch.setattr(c, "snapshot", snapshot)
    monkeypatch.setattr(c, "python_tool", Mock(return_value=["python", "-m", "bandit"]))
    monkeypatch.setattr(c, "native_tool", Mock(return_value="/fake/shellcheck"))
    run = Mock()
    monkeypatch.setattr(c, "run", run)
    if name == "bandit":
        report = {"results": [], "errors": [], "metrics": {str(path): {}, "_totals": {}}}
        finding = {"test_id": "B602", "filename": str(path), "line_number": 1, "issue_severity": "MEDIUM", "issue_confidence": "HIGH", "issue_text": "SECRET", "code": "SECRET"}
    else:
        report = {"comments": []}
        finding = {"code": 2086, "file": str(path), "line": 1, "level": "info", "message": "SECRET", "fix": {"replacement": "SECRET"}}
    return module, c, snap, report, finding, run, snapshot


@pytest.mark.parametrize("count", [0, 1, 53])
def test_clean_findings_and_policy(adapter, capsys, count):
    module, c, snap, report, finding, run, snapshot = adapter
    bandit = "results" in report
    report["results" if bandit else "comments"] = [finding] * count
    run.return_value = subprocess.CompletedProcess([], int(bool(count)), json.dumps(report).encode(), b"SECRET")
    assert c.finish(module.audit) == int(bool(count))
    raw = capsys.readouterr().out
    payload = json.loads(raw)
    assert "SECRET" not in raw
    assert payload["finding_count"] == count
    assert len(payload["findings"]) == min(count, 50)
    assert payload["truncated_count"] == max(0, count - 50)
    assert payload["coverage"] == dict(snap.coverage, scan_files=1, **({"metric_files": 1} if bandit else {}))
    assert payload["version"] == c.PINS["bandit" if bandit else "shellcheck"]
    snapshot.assert_called_once_with("python" if bandit else "shell")
    expected = (["python", "-m", "bandit", "--quiet", "--format", "json", "--ignore-nosec", "--severity-level", "medium", "--confidence-level", "medium"] if bandit else ["/fake/shellcheck", "--norc", "--format=json1", "--"])
    run.assert_called_once_with(expected + snap.paths, cwd=snap.base)
    if count:
        assert set(payload["findings"][0]) == ({"code", "path", "line", "severity", "confidence"} if bandit else {"code", "path", "line", "level"})
        assert payload["findings"][0]["path"] == snap.files[0]
    assert payload["policy"]


def test_missing_tool_before_snapshot(adapter, capsys):
    module, c, _, report, _, run, snapshot = adapter
    tool = c.python_tool if "results" in report else c.native_tool
    tool.side_effect = c.Incomplete("tool_unavailable")
    assert c.finish(module.audit) == 2
    assert json.loads(capsys.readouterr().out)["code"] == "tool_unavailable"
    snapshot.assert_not_called()
    run.assert_not_called()


@pytest.mark.parametrize("raw", [b"SECRET", b"[]", b"{}", b'{"results":[],"errors":{},"metrics":{},"comments":{}}'])
def test_malformed_report(adapter, capsys, raw):
    module, c, _, _, _, run, _ = adapter
    run.return_value = subprocess.CompletedProcess([], 0, raw, b"SECRET")
    assert c.finish(module.audit) == 2
    assert json.loads(capsys.readouterr().out) == {"status": "incomplete", "code": "invalid_report"}


@pytest.mark.parametrize("exitcode,count", [(0, 1), (1, 0), (2, 1), (3, 0), (4, 0), (-9, 0)])
def test_exit_contradictions(adapter, capsys, exitcode, count):
    module, c, _, report, finding, run, _ = adapter
    report["results" if "results" in report else "comments"] = [finding] * count
    run.return_value = subprocess.CompletedProcess([], exitcode, json.dumps(report).encode())
    assert c.finish(module.audit) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "incomplete"
    assert payload["finding_count"] == count


@pytest.mark.parametrize("field,value", [("line", True), ("line", 0), ("path", "/outside/SECRET"), ("severity", "LOW"), ("confidence", "LOW"), ("code", "SECRET")])
def test_finding_bounds(adapter, capsys, field, value):
    module, c, _, report, finding, run, _ = adapter
    bandit = "results" in report
    fields = ({"line": "line_number", "path": "filename", "severity": "issue_severity", "confidence": "issue_confidence", "code": "test_id"} if bandit else {"line": "line", "path": "file", "severity": "level", "confidence": "level", "code": "code"})
    finding[fields[field]] = value
    report["results" if bandit else "comments"] = [finding]
    run.return_value = subprocess.CompletedProcess([], 1, json.dumps(report).encode())
    assert c.finish(module.audit) == 2
    assert json.loads(capsys.readouterr().out)["code"] == "invalid_report"


@pytest.mark.parametrize("case", ["errors", "missing_metrics", "bad_metrics_path", "bad_metrics_shape"])
@pytest.mark.parametrize("count", [0, 1])
@pytest.mark.parametrize("adapter", ["bandit"], indirect=True)
def test_bandit_partial_coverage(adapter, capsys, case, count):
    module, c, _, report, finding, run, _ = adapter
    report["results"] = [finding] * count
    if case == "errors":
        report["errors"] = [{"reason": "SECRET"}]
    elif case == "missing_metrics":
        report["metrics"] = {"_totals": {}}
    elif case == "bad_metrics_path":
        report["metrics"]["/outside/SECRET"] = {}
    else:
        report["metrics"] = []
    run.return_value = subprocess.CompletedProcess([], int(bool(count)), json.dumps(report).encode())
    assert c.finish(module.audit) == 2
    raw = capsys.readouterr().out
    assert "SECRET" not in raw
    payload = json.loads(raw)
    if case in ("errors", "missing_metrics"):
        assert payload["code"] == "bandit_scan_incomplete"
        assert payload["finding_count"] == count
    else:
        assert payload["code"] == "invalid_report"


@pytest.mark.parametrize("directive", ["# shellcheck external-sources=true", " \t#  shellcheck disable=SC1090 external-sources = true", "# shellcheck external-sources=false", "# shellcheck disable=SC2086"])
@pytest.mark.parametrize("adapter", ["shellcheck"], indirect=True)
def test_shell_external_directive(adapter, capsys, directive):
    module, c, snap, report, _, run, _ = adapter
    (snap.source / snap.files[0]).write_text("#!/bin/sh\n" + directive + "\n. /outside/SECRET\n")
    run.return_value = subprocess.CompletedProcess([], 0, json.dumps(report).encode())
    blocked = "external-sources" in directive
    assert c.finish(module.audit) == (2 if blocked else 0)
    payload = json.loads(capsys.readouterr().out)
    if blocked:
        assert payload["code"] == "unsupported_external_source_directive"
        run.assert_not_called()
    else:
        run.assert_called_once()
