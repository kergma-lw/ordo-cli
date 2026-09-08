"""Mocked adapter tests; YAML checks do not validate Semgrep engine syntax."""

from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest
import yaml


SCRIPTS = Path(__file__).resolve().parents[1] / ".ordo/scripts"
COMMON_SPEC = importlib.util.spec_from_file_location(
    "audit_scanner_common", SCRIPTS / "audit_scanner_common.py",
)
common = importlib.util.module_from_spec(COMMON_SPEC)
sys.modules[COMMON_SPEC.name] = common
COMMON_SPEC.loader.exec_module(common)
SPEC = importlib.util.spec_from_file_location("audit_semgrep_tested", SCRIPTS / "audit-semgrep.py")
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


@pytest.fixture
def snap(tmp_path):
    source = tmp_path / "source"
    names = ["src/a.py", "connectors/b.py", "tools/c.py", ".ordo/scripts/d.py"]
    for name in names:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pass\n")
    return common.Snapshot(tmp_path, source, names, [str(source / n) for n in names], {
        "selected_count": 4, "tracked_count": 4, "excluded_deleted": 0,
        "history": False, "untracked": False, "excluded_tests": True,
    })


def report(snap, findings=False):
    return {
        "version": "1.176.1", "errors": [], "skipped_rules": [],
        "paths": {"scanned": snap.paths},
        "results": [{
            "check_id": "ordo-shell-execution", "path": snap.paths[0],
            "start": {"line": 2},
            "extra": {"severity": "WARNING", "message": "SECRET", "lines": "SECRET"},
        }] if findings else [],
    }


def result(data, code=0):
    return subprocess.CompletedProcess([], code, json.dumps(data).encode(), b"SECRET")


def test_local_rules_shape(monkeypatch, tmp_path):
    raw = adapter.read_rules()
    config = yaml.safe_load(raw)
    assert len(config["rules"]) == adapter.RULE_COUNT == 4
    assert {r["id"] for r in config["rules"]} == adapter.RULE_IDS
    assert [len(r["pattern-either"]) for r in config["rules"]] == [2, 2, 2, 4]
    path = tmp_path / ".ordo/security/semgrep.yml"
    path.parent.mkdir(parents=True)
    monkeypatch.setattr(common, "ROOT", tmp_path)
    bad_configs = []
    for key, value in (("validators", []), ("languages", ["javascript"]), ("message", "$CODE")):
        bad = copy.deepcopy(config)
        bad["rules"][0][key] = value
        bad_configs.append(bad)
    bad_configs.extend([{"rules": config["rules"][:3]}, {"rules": [config["rules"][0]] * 4}, {"include": "https://example.invalid"}])
    bad = copy.deepcopy(config)
    bad["rules"][0]["pattern-either"] = [{"pattern-regex": ".*"}]
    bad_configs.append(bad)
    for bad in bad_configs:
        path.write_text(yaml.safe_dump(bad))
        with pytest.raises(common.Incomplete, match="invalid_local_rules"):
            adapter.read_rules()
    path.unlink()
    target = tmp_path / "rules.yml"
    target.write_bytes(raw)
    path.symlink_to(target)
    with pytest.raises(common.Incomplete, match="invalid_local_rules"):
        adapter.read_rules()


def test_clean_findings_and_contradictions(snap):
    for found, code, status in ((False, 0, "clean"), (True, 1, "findings"),
                                (True, 0, "incomplete"), (False, 1, "incomplete"),
                                (True, 2, "incomplete"), (False, -9, "incomplete")):
        parsed = adapter.parse_report(result(report(snap, found), code), snap)
        assert parsed["status"] == status
        assert "SECRET" not in json.dumps(parsed)
        if found:
            assert parsed["findings"] == [{"RuleID": "ordo-shell-execution", "File": "src/a.py", "Line": 2, "Severity": "WARNING"}]


def test_incomplete_coverage_retains_findings(snap):
    for field, value in (("errors", [{"message": "SECRET"}]),
                         ("skipped_rules", ["SECRET"]), ("version", "0.0.0"),
                         ("paths", {"scanned": snap.paths[1:]})):
        data = report(snap, True)
        data[field] = value
        parsed = adapter.parse_report(result(data, 1), snap)
        assert parsed["status"] == "incomplete"
        assert parsed["finding_count"] == 1
        assert "SECRET" not in json.dumps(parsed)


def test_invalid_schema(snap):
    invalid = [[], {}, {**report(snap), "paths": {"scanned": ["../escape.py"]}}]
    for key in ("results", "errors", "paths", "skipped_rules"):
        data = report(snap)
        del data[key]
        invalid.append(data)
        invalid.append({**report(snap), key: None})
    for key, value in (("check_id", "unknown"), ("start", {"line": True}),
                       ("start", {"line": 0}), ("extra", {"severity": "SECRET"}),
                       ("path", "tests/test_a.py")):
        data = report(snap, True)
        data["results"][0][key] = value
        invalid.append(data)
    for data in invalid:
        with pytest.raises(common.Incomplete, match="invalid_report"):
            adapter.parse_report(result(data), snap)


def test_finding_limit_and_optional_version(snap):
    data = report(snap, True)
    del data["version"]
    data["results"] *= 51
    parsed = adapter.parse_report(result(data, 1), snap)
    assert parsed["status"] == "findings"
    assert parsed["finding_count"] == 51 and parsed["truncated"]
    assert len(parsed["findings"]) == 50


def test_audit_policy_and_failure(monkeypatch, snap, capsys):
    raw = adapter.read_rules()
    entrypoint = str(common.ROOT / ".venv/bin/semgrep")
    tool = Mock(return_value=["python", entrypoint])
    monkeypatch.setattr(common, "python_tool", tool)

    @contextmanager
    def snapshot(language):
        assert language == "python"
        yield snap

    monkeypatch.setattr(common, "snapshot", snapshot)
    execute = Mock(return_value=result(report(snap)))
    monkeypatch.setattr(common, "run", execute)
    assert common.finish(adapter.audit) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rules_sha256"] == hashlib.sha256(raw).hexdigest()
    assert payload["coverage"]["local_rules_only"]
    assert payload["coverage"]["untracked"] is False
    tool.assert_called_once_with("semgrep", "semgrep")
    config = snap.base / "semgrep.yml"
    assert config.read_bytes() == raw and not config.is_relative_to(snap.source)
    assert execute.call_args.args[0] == [
        "python", entrypoint, "scan", "--oss-only", "--config", str(config),
        "--metrics", "off", "--disable-version-check", "--disable-nosem", "--strict",
        "--no-git-ignore", "--error", "--json", "--no-rewrite-rule-ids",
        "--max-target-bytes", "0", *snap.paths,
    ]
    assert execute.call_args.kwargs == {"cwd": snap.base, "env": common.safe_env()}
    execute.side_effect = common.Incomplete("command_timeout")
    assert common.finish(adapter.audit) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "incomplete" and payload["code"] == "command_timeout"
    assert payload["rules_sha256"] == hashlib.sha256(raw).hexdigest()
