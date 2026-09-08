"""Pinned installed CLIs scan fixed synthetic sources, never repository sources."""

from contextlib import nullcontext
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / ".ordo/scripts"


@pytest.mark.parametrize("scanner", ["bandit", "semgrep", "shellcheck"])
def test_installed_scanner(scanner, monkeypatch, tmp_path, capsys):
    if scanner == "shellcheck":
        monkeypatch.setenv("PATH", os.environ.get("PATH", "") + os.pathsep + str(Path.home() / ".bin"))
        if shutil.which(scanner) is None:
            pytest.skip("ShellCheck is not installed")
    else:
        try:
            importlib.metadata.version(scanner)
        except importlib.metadata.PackageNotFoundError:
            pytest.skip(f"{scanner} is not installed")

    spec = importlib.util.spec_from_file_location("audit_scanner_common", SCRIPTS / "audit_scanner_common.py")
    c = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, c)
    spec.loader.exec_module(c)
    spec = importlib.util.spec_from_file_location("audit_integration_" + scanner, SCRIPTS / f"audit-{scanner}.py")
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)

    base = tmp_path.resolve()
    base.chmod(0o700)
    source = base / "source"
    (source / "src").mkdir(parents=True)
    shell = scanner == "shellcheck"
    suffix = "sh" if shell else "py"
    files = [f"src/clean.{suffix}", f"src/risky.{suffix}"]
    contents = (["#!/bin/sh\nprintf '%s\\n' clean\n", "#!/bin/sh\nprintf '%s\\n' $value\n"]
                if shell else ["value=1\n", "import pickle\nresult=pickle.loads(value)\n"])
    if scanner == "bandit":
        # Bandit enables progress output above 50 files, even with JSON output.
        files.extend(f"src/clean_{index}.py" for index in range(49))
        contents.extend(["value=1\n"] * 49)
    for name, content in zip(files, contents):
        (source / name).write_text(content)
    snap = c.Snapshot(base, source, files, [str(source / name) for name in files], {
        "selected_count": len(files), "tracked_count": len(files), "excluded_deleted": 0,
        "history": False, "untracked": False,
    })
    monkeypatch.setattr(c, "snapshot", lambda language: nullcontext(snap))

    # Both clean and risky files go through one real CLI invocation. Tool/version
    # guards, offline flags, subprocess execution and report parsing stay real.
    exitcode = c.finish(adapter.audit)
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert exitcode == 1, output
    assert payload["status"] == "findings"
    assert payload["coverage"]["selected_count"] == len(files)
    assert payload["coverage"]["tracked_count"] == len(files)
    assert payload["coverage"]["history"] is False
    assert payload["coverage"]["untracked"] is False
    assert str(base) not in output
    for content in contents:
        assert content.strip() not in output
    assert "pickle.loads" not in output and "$value" not in output
    if scanner == "semgrep":
        assert payload["scanned_count"] == 2
        assert payload["expected_version"] == c.PINS[scanner]
        assert payload["coverage"]["local_rules_only"] is True
        assert payload["findings"] == [{
            "RuleID": "ordo-pickle-deserialization", "File": files[1],
            "Line": 2, "Severity": "WARNING",
        }]
    else:
        assert payload["version"] == c.PINS[scanner]
        assert payload["coverage"]["scan_files"] == len(files)
        if not shell:
            assert payload["coverage"]["metric_files"] == len(files)
        expected = [{
            "code": "SC2086" if shell else "B301", "path": files[1], "line": 2,
            **({"level": "info"} if shell else {"severity": "MEDIUM", "confidence": "HIGH"}),
        }]
        if shell:
            expected.insert(0, {"code": "SC2154", "path": files[1], "line": 2, "level": "warning"})
        assert payload["findings"] == expected
    assert payload["finding_count"] == (2 if shell else 1)
