#!/usr/bin/env python3
"""Audit tracked worktree bytes, not index blobs or history. No installation.

Invoke with the project-local Python interpreter. Deleted tracked files are
excluded explicitly; successful coverage is still limited by Gitleaks itself.
The snapshot is not an atomic view of a concurrently modified worktree.
"""

from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
VERSION = "8.20.1"
MAX_FINDINGS = 50


class Incomplete(Exception):
    pass


def command(args: list[str], cwd: Path, env: dict[str, str], timeout: int):
    try:
        return subprocess.run(
            args, cwd=cwd, env=env, capture_output=True, timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise Incomplete("command_timeout") from None
    except OSError:
        raise Incomplete("command_unavailable") from None


def path_parts(name: str) -> list[str]:
    parts = name.split("/")
    if any(part in ("", ".", "..", ".git") for part in parts) or "\x00" in name:
        raise Incomplete("invalid_path")
    return parts


def snapshot(index: bytes, tree: Path) -> tuple[set[str], int]:
    if index and not index.endswith(b"\x00"):
        raise Incomplete("invalid_index")
    scanned: set[str] = set()
    seen: set[str] = set()
    deleted = 0
    for record in index.split(b"\x00")[:-1]:
        header, separator, raw_name = record.partition(b"\t")
        if not separator or not re.fullmatch(rb"[0-7]{6} (?:[0-9a-f]{40}|[0-9a-f]{64}) [0-3]", header):
            raise Incomplete("invalid_index")
        mode, _, stage = header.split(b" ")
        if stage != b"0":
            raise Incomplete("unresolved_index")
        if mode == b"160000":
            raise Incomplete("submodule")
        if mode == b"120000":
            raise Incomplete("symlink")
        if mode not in (b"100644", b"100755"):
            raise Incomplete("nonregular_file")
        name = os.fsdecode(raw_name)
        parts = path_parts(name)
        if name in seen:
            raise Incomplete("invalid_index")
        seen.add(name)
        with ExitStack() as stack:
            # Hold each directory open: path swaps cannot redirect subsequent opens.
            directory = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, directory)
            try:
                for part in parts[:-1]:
                    info = os.stat(part, dir_fd=directory, follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        raise Incomplete("symlink")
                    if not stat.S_ISDIR(info.st_mode):
                        raise Incomplete("nonregular_file")
                    directory = os.open(
                        part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=directory,
                    )
                    stack.callback(os.close, directory)
                info = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    raise Incomplete("symlink")
                if not stat.S_ISREG(info.st_mode):
                    raise Incomplete("nonregular_file")
                fd = os.open(
                    parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=directory,
                )
            except FileNotFoundError:
                deleted += 1
                continue
            source = stack.enter_context(os.fdopen(fd, "rb"))
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise Incomplete("nonregular_file")
            if (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino):
                raise Incomplete("worktree_changed")
            prefix = source.read(1024)
            if prefix.startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise Incomplete("lfs_pointer")
            destination = tree.joinpath(*parts)
            parent = tree
            for part in parts[:-1]:
                parent /= part
                parent.mkdir(mode=0o700, exist_ok=True)
            output_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(output_fd, "wb") as output:
                output.write(prefix)
                shutil.copyfileobj(source, output)
            after = os.fstat(source.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns,
            ):
                raise Incomplete("worktree_changed")
        scanned.add(name)
    return scanned, deleted


def audit() -> dict:
    executable = shutil.which("gitleaks")
    if executable is None:
        raise Incomplete("gitleaks_unavailable")
    executable = os.path.abspath(executable)
    env = {
        key: value for key, value in os.environ.items()
        if key not in ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML")
        and not key.startswith("GIT_")
    }
    with tempfile.TemporaryDirectory(prefix="ordo-gitleaks-") as temporary:
        base = Path(temporary).resolve()
        if base.is_relative_to(ROOT.resolve()):
            raise Incomplete("unsafe_temp_directory")
        version = command([executable, "version"], base, env, 15)
        if version.returncode != 0 or version.stdout.strip() != VERSION.encode("ascii"):
            raise Incomplete("gitleaks_version_mismatch")
        index = command(["git", "ls-files", "--stage", "-z"], ROOT, env, 30)
        if index.returncode != 0:
            raise Incomplete("git_failed")
        source = base / "source"
        source.mkdir(mode=0o700)
        # Gitleaks always checks source/.gitleaksignore, even with an explicit
        # ignore path. Keep tracked files one level below that implicit location.
        tree = source / "tree"
        tree.mkdir(mode=0o700)
        scanned, deleted = snapshot(index.stdout, tree)
        config = base / "config.toml"
        config.write_text("[extend]\nuseDefault = true\n", encoding="ascii")
        ignore = base / "empty.ignore"
        ignore.write_bytes(b"")
        report = base / "report.json"
        result = command([
            executable, "detect", "--no-git", "--source", str(source),
            "--redact", "--report-format", "json", "--report-path", str(report),
            "--exit-code", "10", "--no-banner", "--ignore-gitleaks-allow",
            "--config", str(config),
            "--gitleaks-ignore-path", str(ignore),
        ], base, env, 300)
        if result.returncode not in (0, 10):
            raise Incomplete("scanner_failed")
        try:
            findings = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise Incomplete("invalid_report") from None
        if not isinstance(findings, list):
            raise Incomplete("invalid_report")
        published = []
        for finding in findings:
            if not isinstance(finding, dict):
                raise Incomplete("invalid_report")
            rule, name, line = (finding.get(key) for key in ("RuleID", "File", "StartLine"))
            if (
                not isinstance(rule, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", rule)
                or not isinstance(name, str) or type(line) is not int or line < 1
            ):
                raise Incomplete("invalid_report")
            if name.startswith(str(tree) + "/"):
                name = name[len(str(tree)) + 1:]
            elif name.startswith("tree/"):
                name = name[len("tree/"):]
            else:
                path_parts(name)
                raise Incomplete("invalid_report")
            path_parts(name)
            if name not in scanned:
                raise Incomplete("invalid_report")
            if len(published) < MAX_FINDINGS:
                published.append({"RuleID": rule, "File": name, "StartLine": line})
        if (result.returncode == 10) != bool(findings):
            raise Incomplete("inconsistent_report")
        return {
            "status": "findings" if findings else "clean",
            "coverage": "tracked-worktree-scanner-limited",
            "gitleaks_version": VERSION,
            "scanned_files": len(scanned),
            "excluded_deleted": deleted,
            "findings_total": len(findings),
            "findings_truncated": len(findings) > MAX_FINDINGS,
            "findings": published,
        }


def main() -> int:
    try:
        payload = audit()
        code = 1 if payload["status"] == "findings" else 0
    except Incomplete as error:
        payload = {"status": "incomplete", "code": error.args[0]}
        code = 2
    except (Exception, KeyboardInterrupt):
        payload = {"status": "incomplete", "code": "unexpected_error"}
        code = 2
    print(json.dumps(payload, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
