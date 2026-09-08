import io
import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ordo.model.workflow import Workflow
from ordo.runtime import routines


@pytest.fixture
def invocation(tmp_path, monkeypatch):
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    monkeypatch.setattr(routines.tempfile, "gettempdir", lambda: str(temp_root))
    entry = SimpleNamespace(kind="action", outputs={}, implementation=SimpleNamespace(argv=["routine-test"]))
    registry = SimpleNamespace(path=tmp_path / "routines.yaml")
    monkeypatch.setattr(routines, "resolve_routine_entry", lambda **kwargs: (registry, entry))
    step = SimpleNamespace(reference="routine.demo.test", declared_with={})
    workflow = Workflow(version=0, workflow="test", blocks=(), launch_dir=str(tmp_path))
    handles = []

    def execute(payload=b"original\r\nstdout\n", stderr=b"original stderr\n", returncode=0, error=None):
        def run(argv, **kwargs):
            assert argv == ["routine-test"]
            assert set(kwargs) == {"check", "text", "stdout", "stderr", "env"}
            assert kwargs["check"] is False
            assert kwargs["text"] is True
            assert kwargs["env"] == os.environ.copy()
            for name, content in (("stdout", payload), ("stderr", stderr)):
                handle = kwargs[name]
                assert not isinstance(handle, (str, bytes, Path))
                assert not handle.closed
                handles.append(handle)
                os.write(handle.fileno(), content)
            if error is not None:
                raise error
            return subprocess.CompletedProcess(argv, returncode)

        monkeypatch.setattr(routines.subprocess, "run", run)
        return routines.execute_routine_step(step, workflow)

    return SimpleNamespace(
        root=temp_root, entry=entry, handles=handles, execute=execute, step=step, workflow=workflow,
    )


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission and symlink assertions")
def test_existing_ordo_directory_or_symlink_is_untouched(invocation, tmp_path):
    existing = invocation.root / "ordo"
    target = tmp_path / "target"
    target.mkdir()
    sentinel = target / "sentinel"
    sentinel.write_bytes(b"untouched")
    for symlink in (False, True):
        if symlink:
            existing.rmdir()
            existing.symlink_to(target, target_is_directory=True)
        else:
            existing.mkdir(mode=0o755)
        before = existing.lstat()
        result = invocation.execute()
        log_dir = Path(result.outputs["log_path"]).parent
        assert log_dir.parent == invocation.root
        assert log_dir != existing
        assert stat.S_IMODE(log_dir.stat().st_mode) == 0o700
        assert existing.lstat().st_ino == before.st_ino
        assert existing.lstat().st_mode == before.st_mode
        assert list(target.iterdir()) == [sentinel]
        assert sentinel.read_bytes() == b"untouched"
        assert [path.name for path in existing.iterdir()] == (["sentinel"] if symlink else [])


@pytest.mark.parametrize(
    "kind,mode,returncode,payload,error,status,summary,diagnostic,extra",
    [
        ("action", None, 0, b"ok", None, "ok", "Routine 'demo.test' completed successfully", None, "tails_exit"),
        ("probe", "verify", 0, b"ok", None, "ok", "Routine probe 'demo.test' completed successfully", None, "tails_exit"),
        ("action", None, 3, b"failed", None, "routine_failed", "Routine 'demo.test' failed", None, "tails_exit"),
        ("probe", "data", 3, b"not JSON", None, "routine_failed", "Routine 'demo.test' failed", None, "tails_exit"),
        ("action", None, 0, b"written", OSError("spawn failed"), "execution_error", "Routine 'demo.test' could not be started", "runtime.routine.start_failed", "tails"),
        ("probe", "data", 0, b"not JSON", None, "execution_error", "Routine probe 'demo.test' returned invalid structured output", "runtime.routine.probe_output_invalid", "tails"),
        ("probe", "data", 0, b'{"ok": true}', None, "ok", "Routine probe 'demo.test' returned structured data", None, "data"),
    ],
)
def test_result_parity_closure_and_retained_logs(
    invocation, kind, mode, returncode, payload, error, status, summary, diagnostic, extra,
):
    invocation.entry.kind = kind
    invocation.entry.outputs = {"mode": mode}
    result = invocation.execute(payload=payload, error=error, returncode=returncode)
    assert result.status == status
    assert result.summary == summary
    assert [item.code for item in result.diagnostics] == ([diagnostic] if diagnostic else [])
    keys = {"routine_id", "log_path", "stdout_log_path", "stderr_log_path"}
    keys.update({"data"} if extra == "data" else {"stdout_tail", "stderr_tail"})
    if extra == "tails_exit":
        keys.add("exit_code")
        assert result.outputs["exit_code"] == returncode
    assert set(result.outputs) == keys
    assert result.outputs["routine_id"] == "demo.test"
    assert result.outputs["log_path"] == result.outputs["stdout_log_path"]
    assert result.raw == {
        "stdout_path": result.outputs["stdout_log_path"],
        "stderr_path": result.outputs["stderr_log_path"],
    }
    if extra == "data":
        assert result.outputs["data"] == {"ok": True}
    else:
        assert result.outputs["stdout_tail"] == ("" if error else payload.decode())
        assert result.outputs["stderr_tail"] == ("" if error else "original stderr")
    assert len(invocation.handles) == 2
    for handle, content, suffix in zip(
        invocation.handles, (payload, b"original stderr\n"), (".stdout.log", ".stderr.log"),
    ):
        assert handle.closed
        path = Path(handle.name)
        assert path.read_bytes() == content
        assert path.name.startswith("demo-test-")
        assert path.name.endswith(suffix)
        if os.name == "posix":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.skipif(os.name != "posix", reason="POSIX open-file pathname replacement")
@pytest.mark.parametrize("data_probe", [False, True])
def test_replaced_paths_cannot_redirect_capture_or_reads(invocation, tmp_path, monkeypatch, data_probe):
    invocation.entry.kind = "probe" if data_probe else "action"
    invocation.entry.outputs = {"mode": "data"} if data_probe else {}
    payload = json.dumps({"lines": list(range(60))}, indent=2).encode()
    sentinels = [tmp_path / "stdout-sentinel", tmp_path / "stderr-sentinel"]
    for sentinel in sentinels:
        sentinel.write_bytes(b'{"replacement": true}')

    def run(argv, **kwargs):
        for name, sentinel, content in zip(("stdout", "stderr"), sentinels, (payload, b"real stderr")):
            handle = kwargs[name]
            assert not handle.closed
            invocation.handles.append(handle)
            path = Path(handle.name)
            path.unlink()
            path.symlink_to(sentinel)
            os.write(handle.fileno(), content)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(routines.subprocess, "run", run)
    result = routines.execute_routine_step(invocation.step, invocation.workflow)
    assert result.status == "ok"
    if data_probe:
        assert result.outputs["data"] == {"lines": list(range(60))}
    else:
        assert result.outputs["stdout_tail"] == "\n".join(payload.decode().splitlines()[-20:])
        assert result.outputs["stderr_tail"] == "real stderr"
    for handle, sentinel in zip(invocation.handles, sentinels):
        assert handle.closed
        assert Path(handle.name).is_symlink()
        assert sentinel.read_bytes() == b'{"replacement": true}'


def test_invocations_have_unique_persistent_artifacts(invocation):
    first = invocation.execute()
    second = invocation.execute()
    paths = [Path(result.outputs[key]) for result in (first, second) for key in ("stdout_log_path", "stderr_log_path")]
    assert len(set(paths)) == 4
    assert paths[0].parent != paths[2].parent
    assert all(path.is_file() for path in paths)
    assert all(handle.closed for handle in invocation.handles)


def test_tail_decoding_and_line_limits_are_preserved(invocation):
    payload = b"\r\n".join(str(i).encode() for i in range(60)) + b"\rfinal\xff\n"
    result = invocation.execute(payload=payload, stderr=payload)
    with io.TextIOWrapper(io.BytesIO(payload), encoding="utf-8", errors="replace", newline=None) as text:
        lines = text.read().splitlines()
    assert result.outputs["stdout_tail"] == "\n".join(lines[-20:])
    assert result.outputs["stderr_tail"] == "\n".join(lines[-40:])


@pytest.mark.parametrize("failure", ["spawn_unexpected", "tail_oserror", "invalid_utf8"])
def test_unexpected_errors_propagate_and_close_handles(invocation, monkeypatch, failure):
    invocation.entry.kind = "probe"
    invocation.entry.outputs = {"mode": "data"}
    error = RuntimeError("unexpected") if failure == "spawn_unexpected" else None
    if failure == "tail_oserror":
        def fail_read(*args, **kwargs):
            raise OSError("tail read failed")
        monkeypatch.setattr(routines, "_read_log_tail", fail_read)
    expected = {"spawn_unexpected": RuntimeError, "tail_oserror": OSError, "invalid_utf8": UnicodeDecodeError}[failure]
    with pytest.raises(expected):
        invocation.execute(payload=b'"\xff"', error=error)
    assert len(invocation.handles) == 2
    assert all(handle.closed for handle in invocation.handles)
    assert all(Path(handle.name).is_file() for handle in invocation.handles)


def test_partial_allocation_failure_closes_and_removes_only_own_directory(invocation, monkeypatch):
    existing = invocation.root / "ordo"
    existing.mkdir()
    sentinel = existing / "sentinel"
    sentinel.write_bytes(b"untouched")
    allocate = routines.tempfile.NamedTemporaryFile
    failure = OSError("second allocation failed")

    def fail_second(**kwargs):
        if invocation.handles:
            raise failure
        handle = allocate(**kwargs)
        invocation.handles.append(handle)
        return handle

    monkeypatch.setattr(routines.tempfile, "NamedTemporaryFile", fail_second)
    with pytest.raises(OSError) as raised:
        invocation.execute()
    assert raised.value is failure
    assert len(invocation.handles) == 1
    assert invocation.handles[0].closed
    assert not Path(invocation.handles[0].name).parent.exists()
    assert list(invocation.root.iterdir()) == [existing]
    assert sentinel.read_bytes() == b"untouched"
