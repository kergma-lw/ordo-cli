"""gh.pr.diff probe."""

from __future__ import annotations

import re

from connectors.gh._external import command_text, fail_github_command, text_mentions_not_found
from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr._shared import fetch_json_list, resolve_limit
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, ok, probe
from ordo.model.human import declare_human

_PATCH_CHAR_LIMIT = 4000
_DIFF_HEADER_RE = re.compile(r'^diff --git a/(?P<old>.+) b/(?P<new>.+)$')


HUMAN = declare_human({'title': 'GitHub pr diff',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and the workflow needs '
         'changed-file detail there for one PR number.',
 'summary': 'Probe one GitHub pull request diff as normalized changed-file summaries with patch excerpts, rename '
            'metadata, and binary/truncation signals. Prefer connector_contexts.gh.repository as the normal repository '
            'target and use an explicit repository argument only as a one-off override.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and the workflow '
                         'needs changed-file detail there for one PR number.',
                         'The workflow needs to reason about which files changed or inspect bounded patch content '
                         'without parsing raw git output itself.']},
              {'heading': 'Do not use for',
               'items': ['Overall PR headline facts such as title, branch refs, or review decision; use '
                         'connector.gh.pr for that metadata snapshot.',
                         'Conversation or review decision surfaces; use comments, review_comments, or reviews when the '
                         'workflow is about discussion rather than code changes.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.pr',
                               'summary': 'Parent PR snapshot probe that reports change totals but not per-file diff '
                                          'content'},
                              {'handle': 'connector.gh.pr.review_comments',
                               'summary': 'Sibling probe for line-level reviewer feedback that may reference files '
                                          'from this diff'},
                              {'handle': 'connector.git.range',
                               'summary': 'Repository-local git diff surface when the workflow needs local git ranges '
                                          'instead of remote PR normalization'}]},
              {'heading': 'Examples', 'items': ['gh.pr.diff with inputs {"limit": 20, "pull_number": 42}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.pr.review_comments', 'connector.git.range', 'connector.gh.pr']}]})

def info():
    return probe(
        name="pr.diff",
        human=HUMAN,
        summary="Read normalized change content from a GitHub pull request.",
        inputs={**PULL_IDENTITY_INPUTS, "limit": "integer"},
        outputs={"pull_ref": "string", "total_files": "integer", "files": ["object"]},
        failure_modes=("pull_not_found", "limit_invalid", "probe_failed"),
        handler=run,
        examples=(
            {
                "reference": "gh.pr.diff",
                "inputs": {"pull_number": 42},
            },
        ),
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr_diff")
    if isinstance(identity, OperationOutcome):
        return identity
    limit = resolve_limit(
        ctx,
        pull_ref=identity.pull_ref,
        diagnostic_prefix="probe.gh_pr_diff",
        summary_subject="GitHub pull request diff",
        default=100,
    )
    if isinstance(limit, OperationOutcome):
        return limit
    fetched = fetch_json_list(
        ctx,
        argv=["gh", "api", f"repos/{identity.owner}/{identity.repo}/pulls/{identity.pull_number}/files?per_page={limit}"],
        diagnostic_prefix="probe.gh_pr_diff",
        pull_ref=identity.pull_ref,
        failed_summary="GitHub pull request diff probe failed",
    )
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, files_raw = fetched
    fetched_diff = _fetch_diff_text(ctx, owner=identity.owner, repo=identity.repo, pull_number=identity.pull_number, pull_ref=identity.pull_ref)
    if isinstance(fetched_diff, OperationOutcome):
        return fetched_diff
    diff_text, diff_raw = fetched_diff
    parsed_sections = _parse_diff_sections(diff_text)
    files = [_normalize_file(item, parsed_sections=parsed_sections) for item in payload if isinstance(item, dict)]
    return ok(
        summary="GitHub pull request diff retrieved successfully",
        outputs={"pull_ref": identity.pull_ref, "total_files": len(files), "files": files},
        raw={"files": files_raw, "diff": diff_raw},
    )


def _normalize_file(item: dict[str, object], *, parsed_sections: dict[str, dict[str, object]]) -> dict[str, object]:
    path = item.get("filename")
    previous_path = item.get("previous_filename")
    status = item.get("status")
    section = parsed_sections.get(str(path)) if path is not None else None
    patch_text = item.get("patch") if isinstance(item.get("patch"), str) else None
    binary = False
    truncated = False

    if isinstance(section, dict):
        patch_text = _first_text(patch_text, section.get("patch"))
        binary = bool(section.get("binary"))

    if patch_text is not None:
        patch_text, truncated = _bound_patch(patch_text)
    elif binary:
        truncated = False
    else:
        truncated = bool(status in {"modified", "added", "removed", "renamed", "copied", "changed"})

    return {
        "path": path,
        "previous_path": previous_path,
        "status": status,
        "additions": item.get("additions"),
        "deletions": item.get("deletions"),
        "changes": item.get("changes"),
        "patch": patch_text,
        "truncated": truncated,
        "binary": binary,
    }


def _fetch_diff_text(
    ctx: OperationContext,
    *,
    owner: str,
    repo: str,
    pull_number: int,
    pull_ref: str,
) -> tuple[str, dict[str, object]] | OperationOutcome:
    try:
        command = ctx.command(
            [
                "gh",
                "api",
                f"repos/{owner}/{repo}/pulls/{pull_number}",
                "-H",
                "Accept: application/vnd.github.v3.diff",
            ],
            failures={"os_error": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        text = command_text(exc.outcome.raw)
        if exc.outcome.status == "execution_error" and text_mentions_not_found(text, "could not resolve to a pull request"):
            return fail(
                code="pull_not_found",
                summary="GitHub pull request was not found",
                diagnostics=(
                    Diagnostic(
                        code="probe.gh_pr_diff.not_found",
                        level="error",
                        message="GitHub pull request was not found",
                        details={"reference": ctx.reference, "pull_ref": pull_ref},
                    ),
                ),
                raw=exc.outcome.raw,
            )
        return fail_github_command(
            ctx,
            code="probe_failed",
            summary="GitHub pull request diff probe failed",
            raw=exc.outcome.raw,
            diagnostic_code="probe.gh_pr_diff.command_failed",
            details={"pull_ref": pull_ref},
            message="GitHub pull request diff probe failed",
        )
    return command.stdout or "", command.raw


def _parse_diff_sections(diff_text: str) -> dict[str, dict[str, object]]:
    lines = diff_text.splitlines()
    sections: dict[str, dict[str, object]] = {}
    current: list[str] = []
    for line in lines:
        if line.startswith("diff --git "):
            _store_section(current, sections)
            current = [line]
        elif current:
            current.append(line)
    _store_section(current, sections)
    return sections


def _store_section(lines: list[str], sections: dict[str, dict[str, object]]) -> None:
    if not lines:
        return
    match = _DIFF_HEADER_RE.match(lines[0])
    if match is None:
        return
    path = match.group("new")
    binary = any(line.startswith("Binary files ") or line == "GIT binary patch" for line in lines[1:])
    hunk_start = next((index for index, line in enumerate(lines) if line.startswith("@@")), None)
    patch = "\n".join(lines[hunk_start:]) if hunk_start is not None else None
    sections[path] = {"patch": patch, "binary": binary}


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _bound_patch(value: str) -> tuple[str, bool]:
    if len(value) <= _PATCH_CHAR_LIMIT:
        return value, False
    return value[:_PATCH_CHAR_LIMIT], True
