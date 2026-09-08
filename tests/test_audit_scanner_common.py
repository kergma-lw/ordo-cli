"""Shared audit mechanics, without executing scanners or Git."""

import importlib.metadata
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest


SPEC = importlib.util.spec_from_file_location(
    "audit_scanner_common_tested",
    Path(__file__).resolve().parents[1] / ".ordo/scripts/audit_scanner_common.py",
)
common = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = common
SPEC.loader.exec_module(common)


def test_safe_env(monkeypatch):
    for key in ("SEMGREP_TOKEN", "PIP_AUDIT_TEST", "BANDIT_CONFIG", "SHELLCHECK_OPTS", "PYTHONPATH", "PYTHONHOME", "GIT_DIR"):
        monkeypatch.setenv(key, "secret")
    env = common.safe_env()
    assert not any(value == "secret" for value in env.values())
    assert env["GIT_NO_LAZY_FETCH"] == "1"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_python_tool(monkeypatch):
    monkeypatch.setattr(sys, "executable", str(common.ROOT / ".venv/bin/python"))
    version = Mock(return_value="1.9.4")
    spec = Mock(return_value=object())
    monkeypatch.setattr(importlib.metadata, "version", version)
    monkeypatch.setattr(importlib.util, "find_spec", spec)
    assert common.python_tool("bandit", "bandit") == [sys.executable, "-m", "bandit"]
    monkeypatch.setattr(sys, "executable", str(common.ROOT / ".ordo/scripts/../../.venv/bin/python"))
    assert common.python_tool("bandit", "bandit") == [sys.executable, "-m", "bandit"]
    spec.return_value = None
    with pytest.raises(common.Incomplete, match="bandit_unavailable"):
        common.python_tool("bandit", "bandit")
    version.return_value = "1.9.3"
    with pytest.raises(common.Incomplete) as caught:
        common.python_tool("bandit", "bandit")
    assert caught.value.code == "bandit_version_mismatch"
    assert caught.value.details == {"expected": "1.9.4", "actual": "1.9.3"}
    version.side_effect = importlib.metadata.PackageNotFoundError("secret")
    with pytest.raises(common.Incomplete, match="bandit_unavailable"):
        common.python_tool("bandit", "bandit")


def test_semgrep_console_entrypoint(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    python = tmp_path / ".venv/bin/python"
    monkeypatch.setattr(sys, "executable", str(python))
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "1.176.1")
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    with pytest.raises(common.Incomplete, match="semgrep_unavailable"):
        common.python_tool("semgrep", "semgrep")
    entrypoint = python.with_name("semgrep")
    entrypoint.parent.mkdir(parents=True)
    entrypoint.touch()
    assert common.python_tool("semgrep", "semgrep") == [str(python), str(entrypoint)]


def test_native_and_run(monkeypatch, tmp_path):
    monkeypatch.setattr(common.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(common.shutil, "which", lambda name: "/usr/bin/shellcheck")
    execute = Mock(return_value=subprocess.CompletedProcess([], 0, b"ShellCheck\nversion: 0.11.0\n", b"secret"))
    monkeypatch.setattr(common.subprocess, "run", execute)
    assert common.native_tool("shellcheck") == "/usr/bin/shellcheck"
    assert execute.call_args.kwargs["cwd"].is_relative_to(tmp_path)
    assert execute.call_args.kwargs["capture_output"] is True
    execute.side_effect = subprocess.TimeoutExpired("secret", 1, output=b"secret")
    with pytest.raises(common.Incomplete, match="command_timeout"):
        common.run(["scanner"], tmp_path)
    execute.side_effect = OSError("secret")
    with pytest.raises(common.Incomplete, match="command_unavailable"):
        common.run(["scanner"], tmp_path)


def test_report_validation(tmp_path):
    name = "odd\n\udcff.py"
    (tmp_path / name).touch()
    assert common.report_path(name, tmp_path, [name]) == name
    assert common.report_path(str(tmp_path / name), tmp_path, [name]) == name
    (tmp_path / "link.py").symlink_to(tmp_path / name)
    for raw in ("../escape.py", "./" + name, "missing.py", "link.py", "/outside.py"):
        with pytest.raises(common.Incomplete, match="invalid_report"):
            common.report_path(raw, tmp_path, [name, "link.py"])
    assert common.json_output(subprocess.CompletedProcess([], 0, b'{"ok": true}')) == {"ok": True}
    for raw in (b"\xff", b"secret"):
        with pytest.raises(common.Incomplete, match="invalid_report"):
            common.json_output(subprocess.CompletedProcess([], 0, raw))


def test_snapshot_scopes(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common.tree, "ROOT", root)
    monkeypatch.setattr(common.tempfile, "gettempdir", lambda: str(tmp_path))
    contents = {
        "src/a.py": b"pass\n", "tests/test_a.py": b"pass\n",
        "root.py": b"pass\n", ".ordo/scripts/a.py": b"pass\n",
        "ordo-playbook": b"#!/usr/bin/env -S bash -eu\n",
        "script.sh": b"true\n", "doc": b"#!/usr/bin/env python\n",
    }
    for name, content in contents.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    index = b"".join(b"100644 " + b"a" * 40 + b" 0\t" + name.encode() + b"\0" for name in [*contents, "src/deleted.py"])
    execute = Mock(return_value=subprocess.CompletedProcess([], 0, index, b""))
    monkeypatch.setattr(common, "run", execute)
    with common.snapshot("python") as snap:
        assert snap.files == [".ordo/scripts/a.py", "src/a.py"]
        assert snap.coverage == {"selected_count": 2, "tracked_count": 8, "excluded_deleted": 1, "history": False, "untracked": False, "excluded_tests": True}
        assert (snap.source / "doc").exists()
        assert snap.paths == [str(snap.source / name) for name in snap.files]
        assert snap.base.stat().st_mode & 0o777 == 0o700
    assert not snap.base.exists()
    with common.snapshot("shell") as snap:
        assert snap.files == ["ordo-playbook", "script.sh"]
    execute.return_value.stdout = b""
    with pytest.raises(common.Incomplete, match="empty_scan_scope"):
        with common.snapshot("python"):
            pytest.fail("empty scope yielded")
    execute.return_value.stdout = b"malformed\0"
    with pytest.raises(common.Incomplete, match="invalid_index"):
        with common.snapshot("python"):
            pytest.fail("invalid index yielded")
    monkeypatch.setattr(common.tempfile, "gettempdir", lambda: str(root))
    with pytest.raises(common.Incomplete, match="unsafe_temp_directory"):
        with common.snapshot("python"):
            pytest.fail("unsafe temporary directory yielded")


def test_finish_sanitizes(capsys):
    def fail():
        raise common.Incomplete("bandit_version_mismatch", {"expected": "1.9.4", "actual": "secret\n", "stderr": "secret"})

    assert common.finish(fail) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"status": "incomplete", "code": "bandit_version_mismatch", "details": {"expected": "1.9.4"}}
    for exception in (ValueError("secret"), KeyboardInterrupt()):
        def unexpected():
            raise exception
        assert common.finish(unexpected) == 2
        assert json.loads(capsys.readouterr().out)["code"] == "unexpected_error"
    for status, expected in (("clean", 0), ("manual-review-needed", 0), ("findings", 1), ("incomplete", 2)):
        assert common.finish(lambda: {"status": status, "file": "\udcff"}) == expected
        output = capsys.readouterr().out
        assert output.isascii()
        assert len(output.splitlines()) == 1
