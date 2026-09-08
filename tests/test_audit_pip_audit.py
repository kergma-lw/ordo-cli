"""Runtime-only audit contract; all scanner calls and distribution lookups are fake."""

from contextlib import contextmanager
from email.message import Message
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / ".ordo/scripts"
SPEC = importlib.util.spec_from_file_location("audit_scanner_common_pip_test", SCRIPTS / "audit_scanner_common.py")
common = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = common
SPEC.loader.exec_module(common)
SPEC = importlib.util.spec_from_file_location("audit_pip_audit_test", SCRIPTS / "audit-pip-audit.py")
adapter = importlib.util.module_from_spec(SPEC)
with patch.dict(sys.modules, {"audit_scanner_common": common}):
    SPEC.loader.exec_module(adapter)


@pytest.fixture
def world(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    project = root / "pyproject.toml"
    project.write_text('[project]\ndependencies = ["PyYAML>=6,<7"]\n[build-system]\nrequires = ["build-secret"]\n', encoding="ascii")
    monkeypatch.setattr(common, "ROOT", root)
    tool = Mock(return_value=["python", "-m", "pip_audit"])
    monkeypatch.setattr(common, "python_tool", tool)

    def dist(name, version="6.0.2", requires=None, extras=(), direct=None):
        metadata = Message()
        metadata["Name"] = name
        metadata["Version"] = version
        for extra in extras:
            metadata["Provides-Extra"] = extra
        return SimpleNamespace(metadata=metadata, version=version, requires=requires,
                               read_text=lambda filename: "Wheel-Version: 1.0\n" if filename == "WHEEL" else direct)

    distributions = {"pyyaml": dist("PyYAML")}
    lookup = Mock(side_effect=lambda name: distributions[name])
    monkeypatch.setattr(adapter.importlib.metadata, "distribution", lookup)
    state = SimpleNamespace(project=project, dist=dist, distributions=distributions, lookup=lookup, tool=tool,
                            rows=[{"name": "pyyaml", "version": "6.0.2", "vulns": []}], exit=0, raw=None, pins=None)

    @contextmanager
    def temporary():
        base = tmp_path / "private"
        base.mkdir(exist_ok=True)
        yield base

    monkeypatch.setattr(common, "_temporary", temporary)

    def run(argv, cwd, timeout):
        assert not cwd.is_relative_to(root)
        assert timeout == 300
        requirement = cwd / "runtime-requirements.txt"
        assert argv == ["python", "-m", "pip_audit", "--requirement", str(requirement), "--no-deps", "--disable-pip",
                        "--format", "json", "--progress-spinner", "off", "--strict", "--vulnerability-service", "pypi"]
        assert requirement.stat().st_mode & 0o777 == 0o600
        state.pins = requirement.read_text(encoding="ascii")
        data = json.dumps({"dependencies": state.rows, "fixes": []}).encode() if state.raw is None else state.raw
        return subprocess.CompletedProcess(argv, state.exit, data, b"credential-secret")

    state.run = Mock(side_effect=run)
    monkeypatch.setattr(common, "run", state.run)
    return state


def test_permission_and_unavailable_never_install(world, capsys):
    for args, code in [([], "network_not_authorized"), (["FaLsE"], "network_not_authorized"),
                       (["yes"], "invalid_network_permission"), (["true", "false"], "invalid_network_permission")]:
        assert adapter.main(args) == 2
        assert json.loads(capsys.readouterr().out)["code"] == code
    world.run.assert_not_called()
    world.tool.assert_not_called()
    world.lookup.assert_not_called()
    world.tool.side_effect = common.Incomplete("pip_audit_unavailable")
    assert adapter.main(["TrUe"]) == 2
    assert json.loads(capsys.readouterr().out)["code"] == "pip_audit_unavailable"
    world.tool.assert_called_once_with("pip-audit", "pip_audit")
    world.run.assert_not_called()
    world.lookup.assert_not_called()


def test_exact_runtime_closure_extras_and_cycles(world):
    world.project.write_text('[project]\ndependencies = ["addon", "PyYAML>=6,<7"]\n', encoding="ascii")
    world.distributions.update({
        "pyyaml": world.dist("PyYAML", requires=['child>=1; extra == "fast"', 'ignored; python_version < "1"'], extras=["fast"]),
        "addon": world.dist("addon", "1", ["PyYAML[fast]>=6"]),
        "child": world.dist("child", "1.2", ["PyYAML>=6"]),
    })
    world.rows = [{"name": name, "version": version, "vulns": []} for name, version in
                  [("addon", "1"), ("child", "1.2"), ("pyyaml", "6.0.2")]]
    result = adapter.audit(True)
    assert result["status"] == "clean"
    assert result["runtimepackages_count"] == 3
    assert result["coverage"]["runtimeOnly"] is True
    assert result["network_service"] == "pypi"
    assert world.pins == "addon==1\nchild==1.2\npyyaml==6.0.2\n"
    assert {call.args[0] for call in world.lookup.call_args_list} == {"pyyaml", "addon", "child"}
    assert world.lookup.call_count == 3


@pytest.mark.parametrize("case", ["missing", "constraint", "transitive", "name", "version", "ambiguous", "url", "local", "editable", "legacy", "extra", "marker"])
def test_runtime_failures_stop_before_scanner(world, case):
    if case == "missing":
        world.lookup.side_effect = adapter.importlib.metadata.PackageNotFoundError("credential-secret")
    elif case == "constraint":
        world.distributions["pyyaml"] = world.dist("PyYAML", "7.0")
    elif case == "transitive":
        world.distributions["pyyaml"].requires = ["child>=2"]
        world.distributions["child"] = world.dist("child", "1")
    elif case == "name":
        world.distributions["pyyaml"] = world.dist("wrong-secret")
    elif case == "version":
        world.distributions["pyyaml"] = world.dist("PyYAML", "6.0\ncredential-secret")
    elif case == "ambiguous":
        world.distributions["pyyaml"].metadata["Version"] = "6.1"
    elif case in ("url", "local"):
        world.distributions["pyyaml"].requires = ["child @ " + ("https://credential-secret@example.org/a.whl" if case == "url" else "file:///credential-secret")]
    elif case == "editable":
        world.distributions["pyyaml"] = world.dist("PyYAML", direct='{"url":"file:///credential-secret","dir_info":{"editable":true}}')
    elif case == "legacy":
        world.distributions["pyyaml"].read_text = lambda filename: None
    elif case == "extra":
        world.distributions["pyyaml"].requires = ["PyYAML[unknown]"]
    else:
        world.distributions["pyyaml"].requires = ['child; unknown_marker == "credential-secret"']
    result = adapter.audit(True)
    assert result["status"] == "incomplete"
    assert "secret" not in json.dumps(result)
    world.run.assert_not_called()


@pytest.mark.parametrize("exit_code,vulnerable,status", [(0, False, 0), (1, True, 1), (1, False, 2), (0, True, 2), (2, False, 2), (-9, True, 2)])
def test_report_exit_status_and_redaction(world, capsys, exit_code, vulnerable, status):
    world.exit = exit_code
    if vulnerable:
        world.rows[0]["vulns"] = [{"id": "PYSEC-2026-1", "fix_versions": ["6.0.3"],
                                   "description": "credential-secret", "aliases": ["credential-secret"]}]
    assert adapter.main(["true"]) == status
    output = capsys.readouterr().out
    assert "credential-secret" not in output
    result = json.loads(output)
    assert result["findings_total"] == int(vulnerable)
    if vulnerable:
        assert result["findings"] == [{"name": "pyyaml", "version": "6.0.2", "id": "PYSEC-2026-1", "fix_versions": ["6.0.3"]}]


@pytest.mark.parametrize("case", ["array", "invalid_json", "fixes", "missing", "duplicate", "wrong_version", "unknown", "skipped", "bad_id", "bad_fix"])
def test_report_incompleteness_preserves_valid_findings(world, case):
    world.exit = 1
    world.rows[0]["vulns"] = [{"id": "GHSA-abcd-1234", "fix_versions": []}]
    if case == "array":
        world.raw = json.dumps(world.rows).encode()
    elif case == "invalid_json":
        world.raw = b"credential-secret"
    elif case == "fixes":
        world.raw = json.dumps({"dependencies": world.rows, "fixes": "credential-secret"}).encode()
    elif case == "missing":
        world.distributions["pyyaml"].requires = ["child"]
        world.distributions["child"] = world.dist("child", "1")
    elif case == "duplicate":
        world.rows.append(dict(world.rows[0]))
    elif case == "wrong_version":
        world.rows[0]["version"] = "6.0.1"
    elif case == "unknown":
        world.rows.append({"name": "unknown", "version": "1", "vulns": []})
    elif case == "skipped":
        world.rows.append({"name": "child", "skip_reason": "credential-secret"})
    else:
        world.rows[0]["vulns"].append({"id": "credential-secret\n" if case == "bad_id" else "CVE-2026-2",
                                        "fix_versions": ["https://credential-secret"] if case == "bad_fix" else []})
    result = adapter.audit(True)
    assert result["status"] == "incomplete"
    assert "credential-secret" not in json.dumps(result)
    if case not in ("array", "invalid_json", "wrong_version"):
        assert result["findings"][0]["id"] == "GHSA-abcd-1234"


def test_findings_limit_and_equivalent_report_identity(world):
    world.rows[0].update(name="PyYAML", version="6.0.2.0", vulns=[{"id": f"CVE-2026-{i}", "fix_versions": []} for i in range(60)])
    world.exit = 1
    result = adapter.audit(True)
    assert result["status"] == "findings"
    assert len(result["findings"]) == 50
    assert result["findings_total"] == 60


def test_scanner_exception_is_sanitized(world):
    world.run.side_effect = common.Incomplete("command_timeout")
    assert adapter.audit(True)["code"] == "command_timeout"
    world.run.side_effect = RuntimeError("credential-secret")
    result = adapter.audit(True)
    assert result["status"] == "incomplete"
    assert "credential-secret" not in json.dumps(result)
