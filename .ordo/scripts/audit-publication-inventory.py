#!/usr/bin/env python3
"""Manual publication review inventory, never a privacy clearance or leak verdict.

History inspection enumerates tree path names only, not historical contents or
metadata privacy. Per-commit ls-tree avoids log framing ambiguity for odd names.
The shared snapshot copies tracked regular files before text inspection limits
apply. Neither the worktree snapshot nor separate audit routines are atomic.
Report paths can themselves carry private context; keep the report private.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile


def load_helper(name):
    spec = importlib.util.spec_from_file_location(
        "ordo_publication_" + name, Path(__file__).with_name(f"audit-gitleaks-{name}.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


history = load_helper("history")
tree = load_helper("tree")
ROOT = Path(__file__).resolve().parents[2]
Incomplete = history.Incomplete
git = history.git
MAX_CANDIDATES = 40
MAX_PATH = 240
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
SCOPES = ("tracked", "history", "untracked")
NAME_PATTERNS = {
    "archives": r"\.(?:zip|tar|tgz|gz|bz2|xz|7z|rar|zst)$",
    "database_or_dump": r"\.(?:db|sqlite\d*|sql|dump|bson)(?:\.|$)|(?:^|[/_.-])dumps?(?:[/_.-]|$)",
    "logs": r"(?:^|[/_.-])logs?(?:[/_.-]|$)",
    "backup": r"(?:^|[/_.-])(?:backups?|bak|old|orig)(?:[/_.-]|$)|~$",
    "credentials_or_environment": r"(?:^|[/_.-])(?:env|credentials?|secrets?|tokens?|passwords?|id_rsa|id_ed25519)(?:[/_.-]|$)|\.(?:pem|key|p12|pfx)$",
    "fixture_or_sample_data": r"(?:^|[/_.-])(?:fixtures?|samples?|examples?|testdata|test_data|seed)(?:[/_.-]|$)",
    "repository_local_configuration": r"(?:^|/)(?:\.ordo|\.opencode|\.vscode|\.idea|\.github)(?:/|$)|(?:^|/)(?:\.gitconfig|\.gitmodules|\.npmrc|\.pypirc|\.netrc|config\.local(?:\.[^/]*)?|[^/]+\.local\.[^/]+)$",
}
CONTENT_PATTERNS = {
    "local_absolute_path": r"/(?:home|Users)/[^\s/]+|\b[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]|\b[A-Za-z]:\\[^\s\\]+",
    "email_identifier": r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",
    "private_network_reference": r"\blocalhost\b|\b(?:10(?:\.\d{1,3}){3}|127(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b|\b[A-Za-z0-9-]+\.(?:internal|local)\b|(?<![\w:])::1(?![\w:])|\b(?:f[cd][0-9a-f]{2}|fe[89ab][0-9a-f]):[0-9a-f:]+",
}
NAME_RULES = {key: re.compile(value, re.I) for key, value in NAME_PATTERNS.items()}
CONTENT_RULES = {key: re.compile(value, re.I) for key, value in CONTENT_PATTERNS.items()}
# Conservative suppression, not a credential detector. Even benign long IDs are
# withheld rather than echoing a possible credential embedded in a filename.
PATH_TOKEN = re.compile(r"[A-Za-z0-9_+=%-]{32,}")
CATEGORIES = tuple(NAME_RULES) + tuple(CONTENT_RULES)
SAMPLING_CATEGORIES = tuple(CONTENT_RULES) + tuple(NAME_RULES)
ERROR_CODES = frozenset({
    "command_timeout", "command_unavailable", "git_failed", "invalid_refs",
    "invalid_head", "unsafe_temp_directory", "shallow_repository",
    "invalid_repository", "partial_clone", "refs_changed", "missing_objects",
    "invalid_commits", "empty_history", "invalid_paths", "invalid_path",
    "invalid_index", "unresolved_index", "submodule", "symlink",
    "nonregular_file", "worktree_changed", "lfs_pointer", "unexpected_error",
})


def paths(raw: bytes) -> set[str]:
    """Parse only NUL-terminated ls-files / ls-tree --name-only records."""
    if raw and not raw.endswith(b"\0"):
        raise Incomplete("invalid_paths")
    result = set()
    for item in raw.split(b"\0")[:-1]:
        name = os.fsdecode(item)
        tree.path_parts(name)
        result.add(name)
    return result


def classify(value: str, rules: dict) -> set[str]:
    return {category for category, pattern in rules.items() if pattern.search(value)}


def inventory(names: dict[str, set[str]], scanned: set[str], source: Path) -> dict:
    counts = {scope: dict.fromkeys(CATEGORIES, 0) for scope in SCOPES}
    skipped = dict(binary=0, large=0, budget=0)
    total = used = inspected = 0
    buckets = {(scope, category): []
               for category in SAMPLING_CATEGORIES for scope in SCOPES}
    # Retain only a bounded, sanitized prefix per group, with paths sorted below.
    for scope in SCOPES:
        for name in sorted(names[scope]):
            categories = classify(name, NAME_RULES)
            if scope == "tracked" and name in scanned:
                path = source.joinpath(*tree.path_parts(name))
                size = path.stat().st_size
                if size > MAX_FILE_BYTES:
                    skipped["large"] += 1
                elif used + size > MAX_TOTAL_BYTES:
                    skipped["budget"] += 1
                else:
                    data = path.read_bytes()
                    used += len(data)
                    try:
                        if b"\0" in data:
                            raise UnicodeError()
                        text = data.decode("utf-8")
                    except UnicodeError:
                        skipped["binary"] += 1
                    else:
                        inspected += 1
                        categories.update(classify(text, CONTENT_RULES))
            for category in sorted(categories):
                counts[scope][category] += 1
                total += 1
                bucket = buckets[scope, category]
                if len(bucket) < MAX_CANDIDATES:
                    entry = dict(File=name[:MAX_PATH], Category=category, Scope=scope)
                    withheld = bool(PATH_TOKEN.search(name))
                    if withheld:
                        entry.update(File="[withheld]", path_withheld=True)
                    elif len(name) > MAX_PATH:
                        entry["path_truncated"] = True
                    if withheld or len(name) > MAX_PATH:
                        entry["location_id"] = hashlib.sha256(os.fsencode(name)).hexdigest()
                    bucket.append(entry)
    published = []
    for index in range(MAX_CANDIDATES):
        for bucket in buckets.values():
            if index < len(bucket):
                published.append(bucket[index])
                if len(published) == MAX_CANDIDATES:
                    break
        if len(published) == MAX_CANDIDATES:
            break
    return dict(
        status="manual-review-needed", privacy_acceptability_assessed=False,
        report_private_context_possible=True, candidate_total=total,
        candidates=published, truncated=total > len(published),
        sampling="round-robin-scope-category",
        omitted_count=total - len(published), category_counts=counts,
        path_counts={scope: len(names[scope]) for scope in SCOPES},
        text_files_inspected=inspected, content_bytes_inspected=used,
        content_skip_counts=skipped, file_max_bytes=MAX_FILE_BYTES,
        content_budget_bytes=MAX_TOTAL_BYTES, candidate_limit=MAX_CANDIDATES,
        printed_path_max_chars=MAX_PATH, text_encoding="utf-8-no-nul",
        historical_contents_reviewed=False, untracked_contents_reviewed=False,
        allowlist_applied=False, atomic_snapshot=False,
        coverage="heuristic-manual-review-inventory-not-proven-leaks",
        excluded=["ignored-files", "untracked-contents", "historical-contents",
                  "historical-metadata-privacy", "commit-messages", "tag-annotations",
                  "reflogs", "unreachable-objects", "remote-only-refs",
                  "noncommit-ref-trees-and-blobs", "archive-members", "lfs-payloads",
                  "submodule-repositories", "deleted-tracked-contents",
                  "binary-or-non-utf8-contents", "large-file-contents",
                  "over-budget-contents"],
    )


def audit() -> dict:
    env = history.safe_environment()
    temporary_parent = Path(tempfile.gettempdir()).resolve()
    if temporary_parent.is_relative_to(ROOT.resolve()):
        raise Incomplete("unsafe_temp_directory")
    with tempfile.TemporaryDirectory(prefix="ordo-publication-", dir=temporary_parent) as temporary:
        base = Path(temporary).resolve()
        if base.is_relative_to(ROOT.resolve()):
            raise Incomplete("unsafe_temp_directory")
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
                ref_names = {record.split(b" ")[1] for record in before[0]}
                name = b"refs/ordo-audit/head"
                while name in ref_names:
                    name += b"-head"
                git(["update-ref", name.decode("ascii"), head.decode("ascii")], mirror, env)
            objects = git(["rev-list", "--objects", "--all", "--missing=print"], mirror, env).stdout
            if any(line.startswith(b"?") for line in objects.splitlines()):
                raise Incomplete("missing_objects")
            commits = set(git(["rev-list", "--all"], mirror, env).stdout.splitlines())
            if any(not re.fullmatch(history.OID, commit) for commit in commits):
                raise Incomplete("invalid_commits")
            if not commits:
                raise Incomplete("empty_history")
            if head and head not in commits:
                raise Incomplete("invalid_head")
            historical = set()
            for commit in sorted(commits):
                historical.update(paths(git([
                    "ls-tree", "-r", "--name-only", "-z", commit.decode("ascii"),
                ], mirror, env).stdout))
            index = git(["ls-files", "--stage", "-z"], ROOT, env).stdout
            source = base / "tree"
            source.mkdir(mode=0o700)
            scanned, deleted = tree.snapshot(index, source)
            # snapshot validates every index record, including deleted paths.
            tracked = paths(b"".join(record.partition(b"\t")[2] + b"\0"
                                     for record in index.split(b"\0")[:-1]))
            untracked = paths(git([
                "ls-files", "--others", "--exclude-standard", "-z",
            ], ROOT, env).stdout)
            payload = inventory(dict(tracked=tracked, history=historical, untracked=untracked),
                                scanned, source)
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
                    peeled = git(["rev-parse", "--verify", "--quiet",
                                  oid.decode("ascii") + "^{commit}"], mirror, env, (0, 1))
                    if peeled.returncode:
                        noncommit += 1
                    elif peeled.stdout.strip() not in commits:
                        raise Incomplete("invalid_commits")
            digest = hashlib.sha256(b"\n".join(before[0]) + b"\0" + before[2] + b"\0" + before[4])
            payload.update(commit_count=len(commits), local_ref_counts=counts,
                           excluded_noncommit_refs=noncommit, excluded_deleted=deleted,
                           head_ref_added=bool(head), detached_head_included=bool(head) and before[1] == 1,
                           coverage_snapshot_sha256=digest.hexdigest(),
                           replacement_graft_semantics=False)
            return payload
        finally:
            if history.state(env) != before:
                raise Incomplete("refs_changed")


def main() -> int:
    try:
        payload = audit()
        code = 0
    except (Incomplete, tree.Incomplete) as error:
        reason = error.args[0] if error.args and isinstance(error.args[0], str) else "unexpected_error"
        payload = dict(status="incomplete", code=reason if reason in ERROR_CODES else "unexpected_error")
        code = 2
    except (Exception, KeyboardInterrupt):
        payload = dict(status="incomplete", code="unexpected_error")
        code = 2
    print(json.dumps(payload, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
