import errno
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from stat import S_IMODE
from unittest.mock import Mock

import pytest

from connectors.fs.probes import file as probe
from ordo.plugin_sdk import OperationContext


@pytest.fixture
def safe_open():
    if os.name != "posix" or any(
        type(getattr(os, name, None)) is not int or getattr(os, name) == 0
        for name in ("O_NOFOLLOW", "O_NONBLOCK")
    ):
        pytest.skip("Requires POSIX safe-open flags")


@pytest.fixture
def invoke():
    def run(path):
        ctx = Mock(spec=OperationContext)
        ctx.input.return_value = str(path)
        ctx.reference = "fs.file"
        return probe.run(ctx)

    return run


@pytest.mark.parametrize("kind", ["symlink", "fifo", "directory"])
def test_preopen_nonregular_swap(tmp_path, monkeypatch, invoke, safe_open, kind):
    if kind == "fifo" and not hasattr(os, "mkfifo"):
        pytest.skip("Requires mkfifo")
    path = tmp_path / "file.txt"
    path.write_text("original")
    target = tmp_path / "target.txt"
    target.write_text("must not read")
    real_open = os.open
    opened = []

    def swap(path_arg, flags):
        assert flags & os.O_NOFOLLOW
        assert flags & os.O_NONBLOCK
        path.unlink()
        if kind == "symlink":
            path.symlink_to(target)
        elif kind == "fifo":
            os.mkfifo(path)
        else:
            path.mkdir()
        fd = real_open(path_arg, flags)
        opened.append(fd)
        return fd

    monkeypatch.setattr(probe.os, "open", swap)
    monkeypatch.setattr(probe.os, "fdopen", Mock(side_effect=AssertionError("must not read")))
    result = invoke(path)
    expected = "content_unavailable" if kind == "symlink" else "not_a_file"
    assert result.status == expected
    assert result.diagnostics[0].code == f"probe.fs_file.{expected}"
    assert result.outputs == {}
    if kind == "symlink":
        assert result.diagnostics[0].details["reason"]
        assert "kind" not in result.diagnostics[0].details
    else:
        assert result.diagnostics[0].details["kind"] == kind
    for fd in opened:
        with pytest.raises(OSError, match="Bad file descriptor"):
            os.fstat(fd)


@pytest.mark.parametrize("replace_after_open", [False, True])
def test_content_and_all_metadata_use_opened_object(tmp_path, monkeypatch, invoke, safe_open, replace_after_open):
    path = tmp_path / "authored.txt"
    replacement = tmp_path / "other.txt"
    path.write_bytes(b"original\r\n")
    replacement.write_bytes(b"replacement with different size\r\n")
    path.chmod(0o640)
    replacement.chmod(0o600)
    os.utime(path, (1600000000, 1600000000))
    os.utime(replacement, (1700000000, 1700000000))
    selected = path if replace_after_open else replacement
    expected_stat = selected.stat()
    expected_content = selected.read_text(encoding="utf-8")
    real_open = os.open
    opened = []

    def swap(path_arg, flags):
        assert flags & os.O_NOFOLLOW
        assert flags & os.O_NONBLOCK
        if not replace_after_open:
            replacement.replace(path)
        fd = real_open(path_arg, flags)
        opened.append(fd)
        if replace_after_open:
            replacement.replace(path)
        return fd

    monkeypatch.setattr(probe.os, "open", swap)
    result = invoke(path)
    assert result.status == "ok"
    assert result.outputs == {
        "path": str(path),
        "basename": "authored.txt",
        "filename_without_extension": "authored",
        "extension": "txt",
        "exists": True,
        "kind": "file",
        "content": expected_content,
        "size": expected_stat.st_size,
        "owner": probe._owner_name(expected_stat.st_uid),
        "group": probe._group_name(expected_stat.st_gid),
        "permissions": f"{S_IMODE(expected_stat.st_mode):04o}",
        "modified_at": datetime.fromtimestamp(expected_stat.st_mtime, tz=UTC).isoformat().replace("+00:00", "Z"),
        "line_count": len(expected_content.splitlines()),
    }
    assert result.raw == {"path": str(path), "encoding": "utf-8"}
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_unavailable_flags_fail_without_open(tmp_path, monkeypatch, invoke):
    path = tmp_path / "file"
    path.write_text("text")
    forbidden = Mock(side_effect=AssertionError("unsafe fallback"))
    monkeypatch.setattr(probe.os, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    for name in ("O_NOFOLLOW", "O_NONBLOCK"):
        for value in (None, 0, "invalid", True):
            with monkeypatch.context() as patch:
                if value is None:
                    patch.delattr(probe.os, name, raising=False)
                else:
                    patch.setattr(probe.os, name, value, raising=False)
                result = invoke(path)
                assert result.status == "content_unavailable"
                assert result.summary == "Filesystem file probe requires unavailable safe-open flags"
                diagnostic = result.diagnostics[0]
                assert diagnostic.code == "probe.fs_file.secure_open_unavailable"
                assert name in diagnostic.details["flags"]
                assert diagnostic.details["platform"] == sys.platform
                assert result.outputs == {}
    forbidden.assert_not_called()


@pytest.mark.parametrize("stage", ["fstat", "fdopen", "read", "decode"])
def test_descriptor_closes_on_failure(tmp_path, monkeypatch, invoke, safe_open, stage):
    path = tmp_path / "file"
    path.write_bytes(b"\xff" if stage == "decode" else b"text")
    real_open, real_fstat, real_fdopen = os.open, os.fstat, os.fdopen
    opened = []

    def capture(path_arg, flags):
        fd = real_open(path_arg, flags)
        opened.append(fd)
        return fd

    def failed_read(fd, **kwargs):
        stream = real_fdopen(fd, **kwargs)
        stream.read = Mock(side_effect=OSError("read failed"))
        return stream

    monkeypatch.setattr(probe.os, "open", capture)
    if stage == "fstat":
        monkeypatch.setattr(probe.os, "fstat", Mock(side_effect=OSError("stat failed")))
    elif stage == "fdopen":
        monkeypatch.setattr(probe.os, "fdopen", Mock(side_effect=OSError("fdopen failed")))
    elif stage == "read":
        monkeypatch.setattr(probe.os, "fdopen", failed_read)
    result = invoke(path)
    assert result.status == ("probe_failed" if stage == "fstat" else "content_unavailable")
    assert result.diagnostics[0].code == (
        "probe.fs_file.stat_failed" if stage == "fstat" else "probe.fs_file.content_unavailable"
    )
    assert result.outputs == {}
    assert len(opened) == 1
    with pytest.raises(OSError) as error:
        real_fstat(opened[0])
    assert error.value.errno == errno.EBADF


def test_initial_stat_failures_and_static_symlink_do_not_open(tmp_path, monkeypatch, invoke):
    path = tmp_path / "file"
    forbidden = Mock(side_effect=AssertionError("must not open"))
    monkeypatch.setattr(probe.os, "open", forbidden)
    result = invoke(path)
    assert result.status == "path_not_found"
    assert result.diagnostics[0].code == "probe.fs_file.path_not_found"
    assert result.outputs == {}
    with monkeypatch.context() as patch:
        patch.setattr(Path, "stat", Mock(side_effect=PermissionError("stat denied")))
        result = invoke(path)
        assert result.status == "probe_failed"
        assert result.diagnostics[0].code == "probe.fs_file.stat_failed"
        assert result.outputs == {}
    if os.name == "posix":
        path.symlink_to(tmp_path / "missing-target")
        result = invoke(path)
        assert result.status == "not_a_file"
        assert result.diagnostics[0].details["kind"] == "symlink"
        assert result.outputs == {}
    forbidden.assert_not_called()


@pytest.mark.parametrize("failure", [FileNotFoundError, PermissionError])
def test_poststat_open_failure_is_content_unavailable(tmp_path, monkeypatch, invoke, safe_open, failure):
    path = tmp_path / "file"
    path.write_text("text")
    monkeypatch.setattr(probe.os, "open", Mock(side_effect=failure("open failed")))
    result = invoke(path)
    assert result.status == "content_unavailable"
    assert result.diagnostics[0].code == "probe.fs_file.content_unavailable"
    assert result.diagnostics[0].details["reason"] == "open failed"
    assert result.outputs == {}


@pytest.mark.parametrize("alias", ["parent_symlink", "hardlink"])
def test_aliases_outside_cwd_remain_allowed(tmp_path, monkeypatch, invoke, safe_open, alias):
    outside = tmp_path / "outside"
    outside.mkdir()
    source = outside / "source.txt"
    source.write_text("allowed")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    if alias == "parent_symlink":
        (workspace / "alias").symlink_to(outside, target_is_directory=True)
        path = Path("alias/source.txt")
    else:
        path = Path("alias.txt")
        os.link(source, path)
    for raw_path in (f"./{path}", str(workspace / path)):
        result = invoke(raw_path)
        assert result.status == "ok"
        assert result.outputs["content"] == "allowed"
        assert result.outputs["path"] == str(Path(raw_path))
        assert result.outputs["basename"] == path.name


def test_utf8_universal_newlines_preserve_disk_size(tmp_path, invoke, safe_open):
    path = tmp_path / "file.txt"
    data = b"caf\xc3\xa9\r\nsecond\rthird\n"
    path.write_bytes(data)
    result = invoke(path)
    assert result.status == "ok"
    assert result.outputs["content"] == "caf\u00e9\nsecond\nthird\n"
    assert result.outputs["size"] == len(data)
    assert result.outputs["line_count"] == 3
