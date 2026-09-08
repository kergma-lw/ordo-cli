#!/usr/bin/env python3
"""Audit local reachable commit patches with pinned Gitleaks; never install/fetch.

The shared mirror is not an atomic snapshot: ref/HEAD checks detect endpoint
changes, not changes subsequently reverted or concurrent object pruning.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
VERSION = "8.20.1"
MAX_FINDINGS = 50
OID = rb"(?:[0-9a-f]{40}|[0-9a-f]{64})"


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


def git(args: list[str], cwd: Path, env: dict[str, str], allowed=(0,)):
    result = command(["git", *args], cwd, env, 120)
    if result.returncode not in allowed:
        raise Incomplete("git_failed")
    return result


def refs(cwd: Path, env: dict[str, str]) -> list[bytes]:
    records = git([
        "for-each-ref", "--format=%(objectname) %(refname) %(objecttype)",
    ], cwd, env).stdout.splitlines()
    for record in records:
        if not re.fullmatch(OID + rb" refs/[^\x00-\x20\x7f]+ (commit|tag|tree|blob)", record):
            raise Incomplete("invalid_refs")
    if len({record.split(b" ")[1] for record in records}) != len(records):
        raise Incomplete("invalid_refs")
    return sorted(records)


def state(env: dict[str, str]):
    records = refs(ROOT, env)
    symbolic = git(["symbolic-ref", "--quiet", "HEAD"], ROOT, env, (0, 1))
    head = git(["rev-parse", "--verify", "--quiet", "HEAD"], ROOT, env, (0, 1))
    if head.returncode == 0:
        if not re.fullmatch(OID, head.stdout.strip()):
            raise Incomplete("invalid_head")
    elif symbolic.returncode != 0:
        raise Incomplete("invalid_head")
    return records, symbolic.returncode, symbolic.stdout, head.returncode, head.stdout


def safe_environment() -> dict[str, str]:
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("GIT_", "GITLEAKS_CONFIG"))
    }
    env.update({
        "GIT_NO_LAZY_FETCH": "1", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0",
        # Also inherited by the Git process launched internally by Gitleaks.
        "GIT_CONFIG_COUNT": "4",
        "GIT_CONFIG_KEY_0": "core.hooksPath", "GIT_CONFIG_VALUE_0": os.devnull,
        "GIT_CONFIG_KEY_1": "init.templateDir", "GIT_CONFIG_VALUE_1": "",
        "GIT_CONFIG_KEY_2": "protocol.allow", "GIT_CONFIG_VALUE_2": "never",
        "GIT_CONFIG_KEY_3": "protocol.file.allow", "GIT_CONFIG_VALUE_3": "always",
    })
    return env


def audit() -> dict:
    executable = shutil.which("gitleaks")
    if executable is None:
        raise Incomplete("gitleaks_unavailable")
    executable = os.path.abspath(executable)
    env = safe_environment()
    temporary_parent = Path(tempfile.gettempdir()).resolve()
    if temporary_parent.is_relative_to(ROOT.resolve()):
        raise Incomplete("unsafe_temp_directory")
    with tempfile.TemporaryDirectory(
        prefix="ordo-gitleaks-history-", dir=temporary_parent,
    ) as temporary:
        base = Path(temporary).resolve()
        if base.is_relative_to(ROOT.resolve()):
            raise Incomplete("unsafe_temp_directory")
        version = command([executable, "version"], base, env, 15)
        if version.returncode != 0 or version.stdout.strip() != VERSION.encode("ascii"):
            raise Incomplete("gitleaks_version_mismatch")
        shallow = git(["rev-parse", "--is-shallow-repository"], ROOT, env).stdout.strip()
        if shallow == b"true":
            raise Incomplete("shallow_repository")
        if shallow != b"false":
            raise Incomplete("invalid_repository")
        partial = git([
            "config", "--local", "--no-includes", "--get-regexp",
            r"^(extensions\.partialclone|remote\..*\.(promisor|partialclonefilter))$",
        ], ROOT, env, (0, 1))
        if partial.returncode == 0:
            raise Incomplete("partial_clone")
        before = state(env)
        try:
            mirror = base / "mirror"
            git([
                "clone", "--mirror", "--shared", "--local", "--quiet",
                "--", str(ROOT), str(mirror),
            ], base, env)
            if refs(mirror, env) != before[0]:
                raise Incomplete("refs_changed")
            head = before[4].strip() if before[3] == 0 else b""
            head_added = False
            if head:
                # Use a free private ref rather than overwriting an original ref.
                names = {record.split(b" ")[1] for record in before[0]}
                name = b"refs/ordo-audit/head"
                while name in names:
                    name += b"-head"
                git(["update-ref", name.decode("ascii"), head.decode("ascii")], mirror, env)
                head_added = True
            objects = git([
                "rev-list", "--objects", "--all", "--missing=print",
            ], mirror, env).stdout
            # Object paths may contain arbitrary bytes; never publish this stream.
            if any(line.startswith(b"?") for line in objects.splitlines()):
                raise Incomplete("missing_objects")
            raw_commits = git(["rev-list", "--all"], mirror, env).stdout.splitlines()
            if any(not re.fullmatch(OID, commit) for commit in raw_commits):
                raise Incomplete("invalid_commits")
            commits = {commit.decode("ascii") for commit in raw_commits}
            if not commits:
                raise Incomplete("empty_history")
            if head and head.decode("ascii") not in commits:
                raise Incomplete("invalid_head")
            counts = dict(heads=0, tags=0, remote_tracking=0, other=0)
            noncommit = 0
            for record in before[0]:
                oid, name, kind = record.split(b" ")
                category = next((category for prefix, category in (
                    (b"refs/heads/", "heads"), (b"refs/tags/", "tags"),
                    (b"refs/remotes/", "remote_tracking"),
                ) if name.startswith(prefix)), "other")
                counts[category] += 1
                if kind != b"commit":
                    peeled = git([
                        "rev-parse", "--verify", "--quiet", oid.decode("ascii") + "^{commit}",
                    ], mirror, env, (0, 1))
                    if peeled.returncode:
                        noncommit += 1
                    elif peeled.stdout.strip().decode("ascii") not in commits:
                        raise Incomplete("invalid_commits")
            config, ignore, report = (base / name for name in (
                "config.toml", "empty.ignore", "report.json",
            ))
            config.write_text("[extend]\nuseDefault = true\n", encoding="ascii")
            ignore.write_bytes(b"")
            # The bare mirror has no source/.gitleaksignore or worktree config.
            result = command([
                executable, "detect", "--source", str(mirror),
                "--log-opts", "--all --full-history --root -m --no-ext-diff --no-textconv --no-renames",
                "--redact", "--ignore-gitleaks-allow", "--config", str(config),
                "--gitleaks-ignore-path", str(ignore), "--exit-code", "10",
                "--report-format", "json", "--report-path", str(report), "--no-banner",
            ], base, env, 600)
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
                rule, name, line, commit = (finding.get(key) for key in (
                    "RuleID", "File", "StartLine", "Commit",
                ))
                if (
                    not isinstance(rule, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", rule)
                    or not isinstance(name, str) or type(line) is not int or line < 1
                    or not isinstance(commit, str)
                    or not re.fullmatch(OID.decode("ascii"), commit) or commit not in commits
                ):
                    raise Incomplete("invalid_report")
                if (
                    any(part in ("", ".", "..", ".git") for part in name.split("/"))
                    or "\x00" in name or "\\" in name or re.match(r"^[A-Za-z]:", name)
                ):
                    raise Incomplete("invalid_path")
                if len(published) < MAX_FINDINGS:
                    published.append(dict(RuleID=rule, File=name, StartLine=line, Commit=commit))
            if (result.returncode == 10) != bool(findings):
                raise Incomplete("inconsistent_report")
            digest = hashlib.sha256(b"\n".join(before[0]) + b"\x00" + before[2] + b"\x00" + before[4])
            return {
                "status": "findings" if findings else "clean",
                "coverage": "local-reachable-commit-patches-scanner-limited",
                "rules": "gitleaks-default-rules-limited", "gitleaks_version": VERSION,
                "commit_count": len(commits), "local_ref_counts": counts,
                "excluded_noncommit_refs": noncommit,
                "head_ref_added": head_added,
                "detached_head_included": bool(head) and before[1] == 1,
                "coverage_snapshot_sha256": digest.hexdigest(),
                "replacement_graft_semantics": False,
                "excluded": ["reflogs", "unreachable-objects", "remote-only-refs",
                             "tag-annotations", "commit-messages", "metadata",
                             "lfs-payloads", "submodule-repositories"],
                "findings_total": len(findings),
                "findings_truncated": len(findings) > MAX_FINDINGS, "findings": published,
            }
        finally:
            if state(env) != before:
                raise Incomplete("refs_changed")


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
