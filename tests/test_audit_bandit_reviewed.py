"""Reviewed Bandit exceptions bind to exact locations and snapshot bytes."""

from contextlib import nullcontext
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]
POLICY = ".ordo/security/bandit-reviewed.json"
SOURCE = "src/ordo/runtime/loading.py"


@pytest.fixture
def adapter(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("audit_scanner_common", ROOT / ".ordo/scripts/audit_scanner_common.py")
    c = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, c)
    spec.loader.exec_module(c)
    spec = importlib.util.spec_from_file_location("audit_bandit_reviewed", ROOT / ".ordo/scripts/audit-bandit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "snapshot"
    path = source / SOURCE
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic snapshot bytes\n")
    policy = json.loads((ROOT / POLICY).read_text())
    policy["findings"][0]["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    policy["findings"][0]["reason"] = "SECRET review rationale"
    config = tmp_path / POLICY
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(policy))
    monkeypatch.setattr(c, "ROOT", tmp_path)
    snap = c.Snapshot(tmp_path, source, [SOURCE], [str(path)], {})
    monkeypatch.setattr(c, "snapshot", lambda language: nullcontext(snap))
    monkeypatch.setattr(c, "python_tool", lambda *args: ["fake-bandit"])
    finding = {"test_id": "B506", "filename": str(path), "line_number": 175,
               "issue_severity": "MEDIUM", "issue_confidence": "HIGH", "code": "SECRET excerpt"}
    report = {"results": [finding], "errors": [], "metrics": {str(path): {}}}
    run = Mock(side_effect=lambda *args, **kwargs: subprocess.CompletedProcess([], 1, json.dumps(report).encode()))
    monkeypatch.setattr(c, "run", run)
    return module, c, snap, report, config, run


@pytest.mark.parametrize("count", [1, 53])
def test_exact_match_and_counts(adapter, capsys, count):
    module, c, _, report, _, _ = adapter
    report["results"] *= count
    assert c.finish(module.audit) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert "SECRET" not in output
    assert payload["status"] == "clean"
    assert payload["raw_finding_count"] == payload["accepted_count"] == count
    assert payload["finding_count"] == 0 and payload["findings"] == []
    assert payload["accepted_findings"] == [{"code": "B506", "path": SOURCE, "line": 175,
                                               "exception_id": "authored-style-safe-loader"}] * min(count, 50)
    assert payload["accepted_truncated_count"] == max(0, count - 50)
    assert payload["policy"]["reviewed_exceptions"] == POLICY
    assert "SHA-256" in payload["policy"]["exception_binding"]


@pytest.mark.parametrize("case", ["hash", "path", "rule", "line", "absent", "inactive"])
def test_nonmatches_stay_unresolved(adapter, case):
    module, _, snap, _, _, _ = adapter
    finding = {"code": "B506", "path": SOURCE, "line": 175}
    if case == "hash":
        (snap.source / SOURCE).write_bytes(b"changed class or constructor\n")
    elif case == "path":
        finding["path"] = "src/other.py"
    elif case == "rule":
        finding["code"] = "B103"
    elif case == "line":
        finding["line"] += 1
    elif case == "inactive":
        (snap.source / SOURCE).unlink()
        snap.files.clear()
    findings = [] if case in ("absent", "inactive") else [finding]
    assert module.apply_reviewed(findings, snap.source, snap.files) == (findings, [])


def test_mixed_findings_stay_blocked(adapter, capsys):
    module, c, _, report, _, _ = adapter
    report["results"].append(dict(report["results"][0], line_number=176))
    assert c.finish(module.audit) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "findings"
    assert payload["raw_finding_count"] == 2
    assert payload["accepted_count"] == payload["finding_count"] == 1
    assert payload["findings"][0]["line"] == 176


@pytest.mark.parametrize("case", ["missing", "json", "version", "extra", "hash", "line", "reason", "entries", "duplicate", "symlink"])
def test_invalid_policy_fails_closed(adapter, capsys, case):
    module, c, _, report, config, run = adapter
    policy = json.loads(config.read_text())
    if case == "missing":
        config.unlink()
    elif case == "symlink":
        target = config.with_suffix(".target")
        config.rename(target)
        config.symlink_to(target)
    elif case == "json":
        config.write_text("SECRET")
    elif case == "duplicate":
        config.write_text(json.dumps(policy).replace('"version": 1', '"version": 1, "version": 1'))
    else:
        if case == "version":
            policy["version"] = True
        elif case == "extra":
            policy["extra"] = None
        elif case == "entries":
            policy["findings"] *= 2
        else:
            policy["findings"][0][{"hash": "source_sha256", "line": "line", "reason": "reason"}[case]] = {"hash": "not-a-hash", "line": True, "reason": " "}[case]
        config.write_text(json.dumps(policy))
    report["results"] = []
    run.side_effect = lambda *args, **kwargs: subprocess.CompletedProcess([], 0, json.dumps(report).encode())
    assert c.finish(module.audit) == 2
    assert json.loads(capsys.readouterr().out) == {"status": "incomplete", "code": "bandit_reviewed_policy_invalid"}


@pytest.mark.parametrize("case", ["errors", "metrics", "exit_zero", "exit_two"])
def test_scan_incomplete_not_swallowed(adapter, capsys, case):
    module, c, _, report, _, run = adapter
    if case == "errors":
        report["errors"] = [{"reason": "SECRET"}]
    elif case == "metrics":
        report["metrics"] = {}
    else:
        run.side_effect = lambda *args, **kwargs: subprocess.CompletedProcess([], 0 if case == "exit_zero" else 2, json.dumps(report).encode())
    assert c.finish(module.audit) == 2
    output = capsys.readouterr().out
    assert "SECRET" not in output
    payload = json.loads(output)
    assert payload["code"] == "bandit_scan_incomplete"
    assert payload["raw_finding_count"] == payload["accepted_count"] == 1
    assert payload["finding_count"] == 0


def test_real_manifest_fingerprint_requires_review():
    policy = json.loads((ROOT / POLICY).read_text())
    assert policy["version"] == 1 and len(policy["findings"]) == 1
    entry = policy["findings"][0]
    assert (entry["id"], entry["code"], entry["path"], entry["line"]) == (
        "authored-style-safe-loader", "B506", SOURCE, 175)
    source = (ROOT / SOURCE).read_bytes()
    assert hashlib.sha256(source).hexdigest() == entry["source_sha256"], "Source changed: review required; never auto-refresh the fingerprint"
    lines = source.decode().splitlines()
    assert lines[53] == "class _AuthoredStyleSafeLoader(yaml.SafeLoader):"
    assert lines[174].strip() == "loaded = yaml.load(text, Loader=_AuthoredStyleSafeLoader)"
    assert "tests/test_loading.py" in entry["reason"]
