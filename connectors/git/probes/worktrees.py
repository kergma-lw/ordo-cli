"""git.worktrees probe."""

from __future__ import annotations

from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git worktrees',
 'goal': 'A workflow needs to reason about multiple checkouts of the same repository, such as locating the current '
         'worktree, finding detached sibling worktrees, or checking whether another branch is already checked out '
         'elsewhere.',
  'summary': "List the repository's Git worktrees and return every attached path together with its "
            'HEAD, branch or detached status, bare flag, and which path is current.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to reason about multiple checkouts of the same repository, such as locating '
                         'the current worktree, finding detached sibling worktrees, or checking whether another branch '
                         'is already checked out elsewhere.',
                         'Later logic needs the explicit multi-worktree topology itself rather than only the current '
                         'checkout branch or current worktree cleanliness.']},
              {'heading': 'Do not use for',
               'items': ["Inspecting only the current checkout's dirty files or staging state; use "
                         'connector.git.worktree for live path-level cleanliness details in one worktree.',
                         'Reading only one repository snapshot for the current checkout; use connector.git.state or '
                         'connector.git.branch when the workflow does not need sibling worktree inventory.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.worktree',
                                'summary': 'Read current dirty-path details inside one worktree instead of '
                                          'the repository-wide worktree inventory'},
                              {'handle': 'connector.git.branch',
                                'summary': 'Read current checkout branch identity when the workflow does '
                                          'not need multi-worktree topology'},
                              {'handle': 'connector.git.repo',
                                'summary': 'Read repository root and default-branch context before or '
                                          'alongside multi-worktree inspection'},
                              {'handle': 'connector.git.state',
                                'summary': 'Read one broader current-checkout summary instead of listing '
                                          'every attached worktree'}]},
              {'heading': 'Examples', 'items': ['git.worktrees with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.worktree', 'connector.git.branch', 'connector.git.repo']}]})

def info():
    return probe(
        name="worktrees",
        human=git_human(HUMAN, provide="No inputs are required; run from the repository whose attached checkouts must be considered.", result="Returns count, current_path, items with path, head, branch, bare, current, and detached, plus repository_root. An unreadable inventory has no partial result, and worktrees may be added, removed, or switched after this point-in-time inventory."),
        outputs={
            "count": "integer",
            "current_path": "string | null",
            "items": [
                {
                    "path": "string",
                    "head": "string",
                    "branch": "string | null",
                    "bare": "boolean",
                    "current": "boolean",
                    "detached": "boolean",
                }
            ],
            "repository_root": "string",
        },
        failure_modes=("probe_failed",),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    repository_root = ctx.bootstrap().context.get("repository_root")
    if not isinstance(repository_root, str) or not repository_root.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git bootstrap did not provide a usable repository root",
            diagnostic_code="probe.git_worktrees.repo_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    command = ctx.command(
        ["git", "worktree", "list", "--porcelain"],
        failures={
            "os_error": "probe_failed",
            "nonzero": "probe_failed",
        },
    )

    parsed = _parse_worktrees_output(ctx, command.stdout, dict(command.raw), repository_root)
    if isinstance(parsed, OperationOutcome):
        return parsed

    items = parsed
    current_path = next((item["path"] for item in items if item["current"]), None)
    return ok(
        summary="Git worktree list inspected successfully",
        outputs={
            "count": len(items),
            "current_path": current_path,
            "items": items,
            "repository_root": repository_root,
        },
        raw=command.raw,
    )


def _parse_worktrees_output(
    ctx: OperationContext,
    stdout: str,
    raw: dict[str, object],
    repository_root: str,
) -> list[dict[str, object]] | OperationOutcome:
    items: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in stdout.splitlines():
        if not line:
            if current is None:
                continue
            validated = _finalize_entry(ctx, current, raw, repository_root)
            if isinstance(validated, OperationOutcome):
                return validated
            items.append(validated)
            current = None
            continue

        if line in {"bare", "detached", "locked", "prunable"}:
            if current is None:
                return fail_with_diagnostic(
                    code="probe_failed",
                    summary="Git worktree porcelain returned fields before a worktree header",
                    diagnostic_code="probe.git_worktrees.invalid_line",
                    reference=ctx.reference,
                    raw={"worktrees": raw, "line": line},
                )
            if line == "bare":
                current["bare"] = True
            elif line == "detached":
                current["detached"] = True
            continue

        field, separator, value = line.partition(" ")
        if not separator:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git worktree porcelain returned an invalid line",
                diagnostic_code="probe.git_worktrees.invalid_line",
                reference=ctx.reference,
                raw={"worktrees": raw, "line": line},
            )

        if field == "worktree":
            if current is not None:
                validated = _finalize_entry(ctx, current, raw, repository_root)
                if isinstance(validated, OperationOutcome):
                    return validated
                items.append(validated)
            current = {"path": value, "bare": False, "detached": False}
            continue

        if current is None:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git worktree porcelain returned fields before a worktree header",
                diagnostic_code="probe.git_worktrees.invalid_line",
                reference=ctx.reference,
                raw={"worktrees": raw, "line": line},
            )

        if field == "HEAD":
            current["head"] = value
        elif field == "branch":
            prefix = "refs/heads/"
            if not value.startswith(prefix):
                return fail_with_diagnostic(
                    code="probe_failed",
                    summary="Git worktree porcelain returned an unsupported branch ref format",
                    diagnostic_code="probe.git_worktrees.invalid_branch_ref",
                    reference=ctx.reference,
                    raw={"worktrees": raw, "line": line},
                )
            current["branch"] = value[len(prefix) :]
        elif field == "bare":
            current["bare"] = True
        elif field == "detached":
            current["detached"] = True
        elif field in {"locked", "prunable"}:
            continue
        else:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git worktree porcelain returned an unexpected field",
                diagnostic_code="probe.git_worktrees.invalid_line",
                reference=ctx.reference,
                raw={"worktrees": raw, "line": line},
            )

    if current is not None:
        validated = _finalize_entry(ctx, current, raw, repository_root)
        if isinstance(validated, OperationOutcome):
            return validated
        items.append(validated)

    return items


def _finalize_entry(
    ctx: OperationContext,
    entry: dict[str, object],
    raw: dict[str, object],
    repository_root: str,
) -> dict[str, object] | OperationOutcome:
    path = entry.get("path")
    head = entry.get("head")
    branch = entry.get("branch")
    bare = bool(entry.get("bare", False))
    detached = bool(entry.get("detached", False))

    if not isinstance(path, str) or not path:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git worktree porcelain omitted the worktree path",
            diagnostic_code="probe.git_worktrees.missing_path",
            reference=ctx.reference,
            raw={"worktrees": raw, "entry": dict(entry)},
        )
    if not isinstance(head, str) or not head:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git worktree porcelain omitted the worktree head",
            diagnostic_code="probe.git_worktrees.missing_head",
            reference=ctx.reference,
            raw={"worktrees": raw, "entry": dict(entry)},
        )
    if branch is not None and (not isinstance(branch, str) or not branch):
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git worktree porcelain returned an empty branch value",
            diagnostic_code="probe.git_worktrees.invalid_branch_ref",
            reference=ctx.reference,
            raw={"worktrees": raw, "entry": dict(entry)},
        )
    if detached and branch is not None:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git worktree porcelain returned both detached and branch state",
            diagnostic_code="probe.git_worktrees.inconsistent_entry",
            reference=ctx.reference,
            raw={"worktrees": raw, "entry": dict(entry)},
        )

    return {
        "path": path,
        "head": head,
        "branch": branch if isinstance(branch, str) else None,
        "bare": bare,
        "current": path == repository_root,
        "detached": detached,
    }
