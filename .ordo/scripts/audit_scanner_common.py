"""Mechanical audit helpers; adapters own scanner policy and report allowlists.

Snapshots copy every present tracked file before selecting a language scope,
without size thresholds. Keep scanner reports and configuration in base, not
source. Launch Python adapters with the project-local .venv interpreter.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
PINS = {"bandit": "1.9.4", "semgrep": "1.176.1", "pip-audit": "2.10.1", "shellcheck": "0.11.0"}
MAX_FINDINGS = 50
_VERSION = r"[0-9]+(?:\.[0-9]+){1,3}(?:(?:a|b|rc|\.post|\.dev)[0-9]+)?"


def _load(filename):
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_"), Path(__file__).with_name(filename + ".py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tree = _load("audit-gitleaks-tree")
history = _load("audit-gitleaks-history")


class Incomplete(Exception):
    """Codes are adapter-owned constants, never scanner or exception text.

    Only validated expected/actual version strings may be published as details.
    """

    def __init__(self, code: str, details: dict | None = None):
        self.code = code if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", code) else "unexpected_error"
        self.details = {
            key: value for key, value in (details or {}).items()
            if key in ("expected", "actual") and isinstance(value, str)
            and len(value) <= 64 and re.fullmatch(_VERSION, value)
        }
        super().__init__(self.code)


def safe_env() -> dict[str, str]:
    return {
        key: value for key, value in history.safe_environment().items()
        if not key.startswith(("SEMGREP_", "PIP_AUDIT_", "BANDIT_"))
        and key not in ("SHELLCHECK_OPTS", "PYTHONPATH", "PYTHONHOME")
    }


def python_tool(distribution: str, module: str) -> list[str]:
    if distribution not in ("bandit", "semgrep", "pip-audit"):
        raise Incomplete("unsupported_tool")
    code = distribution.replace("-", "_")
    if Path(os.path.abspath(sys.executable)).parent != ROOT / ".venv" / "bin":
        raise Incomplete(code + "_unavailable")
    try:
        actual = importlib.metadata.version(distribution)
    except Exception:
        raise Incomplete(code + "_unavailable") from None
    if actual != PINS[distribution]:
        raise Incomplete(code + "_version_mismatch", {"expected": PINS[distribution], "actual": actual})
    # A top-level spec lookup does not import the tool (dotted lookups can).
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module):
        raise Incomplete(code + "_unavailable")
    try:
        available = importlib.util.find_spec(module) is not None
    except Exception:
        raise Incomplete(code + "_unavailable") from None
    if not available:
        raise Incomplete(code + "_unavailable")
    if distribution == "semgrep":
        # Semgrep 1.176.1's __main__ only emits a deprecation error and exits 2.
        entrypoint = ROOT / ".venv/bin/semgrep"
        if not entrypoint.is_file():
            raise Incomplete("semgrep_unavailable")
        return [sys.executable, str(entrypoint)]
    return [sys.executable, "-m", module]


def run(argv, cwd, timeout=300, env=None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            argv, cwd=cwd, timeout=timeout, env=safe_env() if env is None else env,
            capture_output=True, check=False,
        )
    except subprocess.TimeoutExpired:
        raise Incomplete("command_timeout") from None
    except OSError:
        raise Incomplete("command_unavailable") from None


@contextmanager
def _temporary():
    parent = Path(tempfile.gettempdir()).resolve()
    if parent.is_relative_to(ROOT.resolve()):
        raise Incomplete("unsafe_temp_directory")
    with tempfile.TemporaryDirectory(prefix="ordo-audit-", dir=parent) as temporary:
        base = Path(temporary).resolve()
        if base.is_relative_to(ROOT.resolve()):
            raise Incomplete("unsafe_temp_directory")
        base.chmod(0o700)
        yield base


def native_tool(name: str) -> str:
    if name != "shellcheck":
        raise Incomplete("unsupported_tool")
    executable = shutil.which(name)
    if executable is None:
        raise Incomplete("shellcheck_unavailable")
    executable = os.path.abspath(executable)
    with _temporary() as base:
        result = run([executable, "--version"], base, timeout=15)
    matches = re.findall(rb"^version: ([^\r\n]+)\r?$", result.stdout, re.MULTILINE)
    actual = matches[0].decode("ascii", errors="replace") if len(matches) == 1 else ""
    if result.returncode != 0 or actual != PINS[name]:
        raise Incomplete("shellcheck_version_mismatch", {"expected": PINS[name], "actual": actual})
    return executable


def json_output(result):
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, ValueError, AttributeError):
        raise Incomplete("invalid_report") from None


def report_path(raw, source, selected) -> str:
    if not isinstance(raw, (str, bytes)):
        raise Incomplete("invalid_report")
    name = os.fsdecode(raw)
    source = Path(source).absolute()
    if name.startswith(str(source) + "/"):
        name = name[len(str(source)) + 1:]
    try:
        parts = tree.path_parts(name)
        if name not in selected:
            raise Incomplete("invalid_report")
        current = source
        if source.is_symlink() or source.resolve() != source:
            raise Incomplete("invalid_report")
        for i, part in enumerate(parts):
            current /= part
            mode = current.lstat().st_mode
            if not (stat.S_ISREG(mode) if i == len(parts) - 1 else stat.S_ISDIR(mode)):
                raise Incomplete("invalid_report")
    except (tree.Incomplete, OSError, ValueError):
        raise Incomplete("invalid_report") from None
    return name


@dataclass
class Snapshot:
    base: Path
    source: Path
    files: list[str]
    paths: list[str]
    coverage: dict


@contextmanager
def snapshot(language):
    if language not in ("python", "shell"):
        raise Incomplete("unsupported_language")
    with _temporary() as base:
        result = run(["git", "ls-files", "--stage", "-z"], ROOT, timeout=30)
        if result.returncode != 0:
            raise Incomplete("git_failed")
        source = base / "source"
        source.mkdir(mode=0o700)
        try:
            tracked, deleted = tree.snapshot(result.stdout, source)
        except tree.Incomplete as error:
            known = {
                "invalid_index", "unresolved_index", "submodule", "symlink",
                "nonregular_file", "invalid_path", "worktree_changed", "lfs_pointer",
            }
            code = error.args[0] if error.args else None
            raise Incomplete(code if code in known else "snapshot_failed") from None
        except (OSError, AttributeError, NotImplementedError):
            raise Incomplete("snapshot_failed") from None
        files = []
        for name in sorted(tracked):
            if language == "python":
                include = name.endswith(".py") and name.startswith(("src/", "connectors/", "tools/", ".ordo/scripts/"))
            else:
                include = name.endswith((".sh", ".bash"))
                if not include:
                    with (source / name).open("rb") as stream:
                        first = stream.readline()
                    if first.startswith(b"#!"):
                        try:
                            words = shlex.split(first[2:].decode("utf-8").strip())
                        except (UnicodeError, ValueError):
                            words = []
                        include = bool(words) and words[0] in ("/bin/sh", "/bin/bash")
                        if words and words[0] == "/usr/bin/env":
                            args = words[1:]
                            if args[:1] == ["-S"]:
                                args = args[1:]
                            include = bool(args) and args[0] in ("sh", "bash")
            if include:
                files.append(name)
        if not files:
            raise Incomplete("empty_scan_scope")
        coverage = {
            "selected_count": len(files), "tracked_count": len(tracked) + deleted,
            "excluded_deleted": deleted, "history": False, "untracked": False,
        }
        if language == "python":
            coverage["excluded_tests"] = True
        yield Snapshot(base, source, files, [str(source / name) for name in files], coverage)


def finish(audit_fn) -> int:
    """Publish only adapter-allowlisted payloads, never raw scanner output."""
    try:
        payload = audit_fn()
        code = {"clean": 0, "manual-review-needed": 0, "findings": 1, "incomplete": 2}[payload["status"]]
        output = json.dumps(payload, ensure_ascii=True, allow_nan=False)
    except Incomplete as error:
        payload = {"status": "incomplete", "code": error.code}
        if error.details:
            payload["details"] = error.details
        output = json.dumps(payload, ensure_ascii=True)
        code = 2
    except (Exception, KeyboardInterrupt):
        output = '{"status": "incomplete", "code": "unexpected_error"}'
        code = 2
    print(output)
    return code
