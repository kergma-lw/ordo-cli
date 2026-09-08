#!/usr/bin/env python3
"""Scan raw local commit and reachable annotated tag objects, without fetching."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


spec = importlib.util.spec_from_file_location(
    "ordo_audit_history_helpers", Path(__file__).with_name("audit-gitleaks-history.py"),
)
history = importlib.util.module_from_spec(spec)
spec.loader.exec_module(history)
ROOT = history.ROOT
VERSION = history.VERSION
MAX_FINDINGS = history.MAX_FINDINGS
MAX_OBJECT_BYTES = 16 * 1024 * 1024
Incomplete = history.Incomplete
git = history.git
command = history.command


def read_objects(expected: dict[str, str], mirror: Path, env: dict) -> dict[str, bytes]:
    """Check sizes before requesting bodies; parse the byte-counted batch strictly."""
    if not expected:
        return {}
    request = "".join(oid + "\n" for oid in expected).encode("ascii")

    def batch(option):
        try:
            result = subprocess.run(
                ["git", "cat-file", option], input=request, cwd=mirror, env=env,
                capture_output=True, check=False, timeout=120,
            )
        except subprocess.TimeoutExpired:
            raise Incomplete("command_timeout") from None
        except OSError:
            raise Incomplete("command_unavailable") from None
        if result.returncode != 0:
            raise Incomplete("git_failed")
        return result.stdout

    for oid, kind in expected.items():
        if not re.fullmatch(history.OID.decode("ascii"), oid) or kind not in ("commit", "tag"):
            raise Incomplete("invalid_objects")
    headers = batch("--batch-check").splitlines()
    if len(headers) != len(expected):
        raise Incomplete("invalid_objects")
    sizes = []
    for (oid, kind), header in zip(expected.items(), headers):
        prefix = f"{oid} {kind} ".encode("ascii")
        if not header.startswith(prefix) or not re.fullmatch(rb"0|[1-9][0-9]{0,19}", header[len(prefix):]):
            raise Incomplete("invalid_objects")
        size = int(header[len(prefix):])
        if size > MAX_OBJECT_BYTES:
            raise Incomplete("metadata_too_large")
        sizes.append(size)
    raw = batch("--batch")
    offset, bodies = 0, {}
    for oid, header, size in zip(expected, headers, sizes):
        prefix = header + b"\n"
        if raw[offset:offset + len(prefix)] != prefix:
            raise Incomplete("invalid_objects")
        offset += len(prefix)
        body = raw[offset:offset + size]
        offset += size
        if len(body) != size or raw[offset:offset + 1] != b"\n":
            raise Incomplete("invalid_objects")
        offset += 1
        bodies[oid] = body
    if offset != len(raw):
        raise Incomplete("invalid_objects")
    return bodies


def gather(commits: set[str], records: list[bytes], mirror: Path, env: dict, source: Path):
    known = {}

    def store(oid, kind, body):
        name = f"{kind}-{oid}.txt"
        fd = os.open(source / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(body)
        known[name] = (kind, oid)

    for oid, body in read_objects(dict.fromkeys(sorted(commits), "commit"), mirror, env).items():
        store(oid, "commit", body)
    pending = {record.split(b" ")[0].decode("ascii") for record in records
               if record.split(b" ")[2] == b"tag"}
    edges = {}
    while pending:
        bodies = read_objects(dict.fromkeys(sorted(pending), "tag"), mirror, env)
        pending = set()
        for oid, body in bodies.items():
            # Mandatory tag headers precede the free-form identity and message.
            lines = body.split(b"\n", 2)
            if (len(lines) != 3 or not re.fullmatch(b"object " + history.OID, lines[0])
                    or lines[1] not in (b"type commit", b"type tag", b"type tree", b"type blob")):
                raise Incomplete("invalid_tag")
            target = lines[0][7:].decode("ascii")
            kind = lines[1][5:].decode("ascii")
            if len(target) != len(oid):
                raise Incomplete("invalid_tag")
            edges[oid] = target if kind == "tag" else None
            if kind == "tag":
                if target not in edges and target not in bodies:
                    pending.add(target)
            else:
                actual = git(["cat-file", "-t", target], mirror, env).stdout
                if actual != kind.encode("ascii") + b"\n":
                    raise Incomplete("invalid_tag")
                if kind == "commit" and target not in commits:
                    raise Incomplete("invalid_commits")
            store(oid, "tag", body)
    finished = set()
    for oid in edges:
        chain = set()
        while oid is not None and oid not in finished:
            if oid in chain:
                raise Incomplete("tag_cycle")
            chain.add(oid)
            oid = edges[oid]
        finished.update(chain)
    return known, len(edges)


def sanitize(report: Path, returncode: int, known: dict, source: Path) -> dict:
    if returncode not in (0, 10):
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
        if (not isinstance(rule, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", rule)
                or not isinstance(name, str) or type(line) is not int or line < 1):
            raise Incomplete("invalid_report")
        if name.startswith(str(source) + "/"):
            name = name[len(str(source)) + 1:]
        if name not in known:
            raise Incomplete("invalid_report")
        kind, oid = known[name]
        if len(published) < MAX_FINDINGS:
            published.append(dict(RuleID=rule, ObjectType=kind, ObjectID=oid, StartLine=line))
    if (returncode == 10) != bool(findings):
        raise Incomplete("inconsistent_report")
    return dict(status="findings" if findings else "clean", findings_total=len(findings),
                findings_truncated=len(findings) > MAX_FINDINGS, findings=published)


def audit() -> dict:
    executable = shutil.which("gitleaks")
    if executable is None:
        raise Incomplete("gitleaks_unavailable")
    executable = os.path.abspath(executable)
    env = history.safe_environment()
    temporary_parent = Path(tempfile.gettempdir()).resolve()
    if temporary_parent.is_relative_to(ROOT.resolve()):
        raise Incomplete("unsafe_temp_directory")
    with tempfile.TemporaryDirectory(prefix="ordo-gitleaks-metadata-", dir=temporary_parent) as temporary:
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
        before = history.state(env)
        try:
            mirror = base / "mirror"
            git(["clone", "--mirror", "--shared", "--local", "--quiet",
                 "--", str(ROOT), str(mirror)], base, env)
            if history.refs(mirror, env) != before[0]:
                raise Incomplete("refs_changed")
            head = before[4].strip() if before[3] == 0 else b""
            if head:
                names = {record.split(b" ")[1] for record in before[0]}
                name = b"refs/ordo-audit/head"
                while name in names:
                    name += b"-head"
                git(["update-ref", name.decode("ascii"), head.decode("ascii")], mirror, env)
            objects = git(["rev-list", "--objects", "--all", "--missing=print"], mirror, env).stdout
            if any(line.startswith(b"?") for line in objects.splitlines()):
                raise Incomplete("missing_objects")
            raw_commits = git(["rev-list", "--all"], mirror, env).stdout.splitlines()
            if any(not re.fullmatch(history.OID, oid) for oid in raw_commits):
                raise Incomplete("invalid_commits")
            commits = {oid.decode("ascii") for oid in raw_commits}
            if head and head.decode("ascii") not in commits:
                raise Incomplete("invalid_head")
            source = base / "source"
            source.mkdir(mode=0o700)
            known, tags = gather(commits, before[0], mirror, env, source)
            if not known:
                raise Incomplete("empty_metadata")
            config, ignore, report = (base / name for name in ("config.toml", "empty.ignore", "report.json"))
            config.write_text("[extend]\nuseDefault = true\n", encoding="ascii")
            ignore.write_bytes(b"")
            result = command([
                executable, "detect", "--no-git", "--source", str(source),
                "--ignore-gitleaks-allow", "--config", str(config),
                "--gitleaks-ignore-path", str(ignore), "--exit-code", "10",
                "--redact", "--no-banner", "--report-format", "json", "--report-path", str(report),
            ], base, env, 600)
            payload = sanitize(report, result.returncode, known, source)
            counts = dict(heads=0, tags=0, remote_tracking=0, other=0)
            for record in before[0]:
                name = record.split(b" ")[1]
                category = next((category for prefix, category in (
                    (b"refs/heads/", "heads"), (b"refs/tags/", "tags"),
                    (b"refs/remotes/", "remote_tracking"),
                ) if name.startswith(prefix)), "other")
                counts[category] += 1
            digest = hashlib.sha256(b"\n".join(before[0]) + b"\x00" + before[2] + b"\x00" + before[4])
            payload.update(
                coverage="local-reachable-commit-and-tag-metadata-scanner-limited",
                rules="gitleaks-default-rules-limited", gitleaks_version=VERSION,
                commit_count=len(commits), tag_object_count=tags, local_ref_counts=counts,
                coverage_snapshot_sha256=digest.hexdigest(), head_ref_added=bool(head),
                detached_head_included=bool(head) and before[1] == 1,
                replacement_graft_semantics=False, metadata_object_max_bytes=MAX_OBJECT_BYTES,
                privacy_acceptability_assessed=False,
                excluded=["remote-only-refs", "reflogs", "unreachable-objects", "worktree",
                          "blob-and-tree-content", "lfs-payloads", "submodule-repositories"],
            )
            return payload
        finally:
            if history.state(env) != before:
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
