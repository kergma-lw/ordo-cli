"""git.worktree probe."""

from __future__ import annotations

from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git worktree',
 'goal': 'A workflow needs the exact dirty-path list or needs to distinguish staged, unstaged, and untracked changes '
         'before a later Git action.',
  'summary': 'Read current Git worktree cleanliness and changed paths, separating untracked, staged, and '
            'unstaged changes without mixing in branch or stash summary fields.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs the exact dirty-path list or needs to distinguish staged, unstaged, and '
                         'untracked changes before a later Git action.',
                         'Later logic is about worktree cleanliness itself rather than about the current branch name '
                         'or stash inventory.']},
              {'heading': 'Do not use for',
               'items': ['One coarse repository-status snapshot that also includes current-branch and stash facts; use '
                           'connector.git.state for that combined summary.',
                          'Mutating the index by staging everything; use connector.git.index.add_all for the all-in '
                          'staging action.']},
              {'heading': 'What to provide',
               'items': ['No operation inputs are required; run it from the repository context whose worktree facts '
                         'the workflow needs.']},
              {'heading': 'Result and boundary',
               'items': ['Reports whether the current worktree is clean or dirty, and identifies whether the dirty '
                         'state includes staged, unstaged, or untracked changes.',
                         'Reports the repository root for the inspected checkout, so later steps can distinguish the '
                         'repository context from the caller\'s starting directory.',
                         'Includes changed paths when a workflow needs file-level follow-up, but cleanliness and change '
                         'categories remain usable without inspecting that list.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.state',
                                'summary': 'Read one broader repository-status snapshot that includes '
                                          'branch and stash context'},
                               {'handle': 'connector.git.index.add_all',
                                'summary': 'Stage the current worktree batch after reviewing it'},
                              {'handle': 'connector.git.branch.switch',
                               'summary': 'Sibling action for checkout movement when local cleanliness may decide '
                                          'whether switching is safe'},
                              {'handle': 'connector.git.commit.create',
                               'summary': 'Sibling action for committing once staged and unstaged worktree state has '
                                          'been reviewed'}]},
              {'heading': 'Examples', 'items': ['git.worktree with inputs {}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.index.add_all', 'connector.git.state', 'connector.git.commit.create']}]})

def info():
    return probe(
        name="worktree",
        human=git_human(HUMAN, provide="No operation inputs are required; use the checkout whose worktree facts matter.", result="Returns clean, dirty_paths, has_untracked, has_staged_changes, has_unstaged_changes, and repository_root; unreadable state has no partial result and paths can change after observation."),
        outputs={
            "clean": "boolean",
            "dirty_paths": ["string"],
            "has_untracked": "boolean",
            "has_staged_changes": "boolean",
            "has_unstaged_changes": "boolean",
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
            diagnostic_code="probe.git_worktree.repo_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    command = ctx.command(
        ["git", "--no-optional-locks", "status", "--porcelain"],
        failures={
            "os_error": "probe_failed",
            "nonzero": "probe_failed",
        },
    )

    dirty_paths: list[str] = []
    has_untracked = False
    has_staged_changes = False
    has_unstaged_changes = False

    for line in command.stdout.splitlines():
        if not line:
            continue
        if len(line) < 4:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git status porcelain returned a line that is too short to parse",
                diagnostic_code="probe.git_worktree.invalid_status_line",
                reference=ctx.reference,
                raw={"status": dict(command.raw), "line": line},
            )

        x = line[0]
        y = line[1]
        separator = line[2]
        path = line[3:]

        if separator != " ":
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git status porcelain returned an unexpected separator",
                diagnostic_code="probe.git_worktree.invalid_status_line",
                reference=ctx.reference,
                raw={"status": dict(command.raw), "line": line},
            )
        if not path:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="Git status porcelain returned an entry without a path",
                diagnostic_code="probe.git_worktree.empty_path",
                reference=ctx.reference,
                raw={"status": dict(command.raw), "line": line},
            )

        if x == "?" and y == "?":
            has_untracked = True
            dirty_paths.append(path)
            continue
        if x == "!" and y == "!":
            continue
        if x != " ":
            has_staged_changes = True
        if y != " ":
            has_unstaged_changes = True
        if x != " " or y != " ":
            dirty_paths.append(path)

    return ok(
        summary="Git worktree inspected successfully",
        outputs={
            "clean": not dirty_paths,
            "dirty_paths": dirty_paths,
            "has_untracked": has_untracked,
            "has_staged_changes": has_staged_changes,
            "has_unstaged_changes": has_unstaged_changes,
            "repository_root": repository_root,
        },
        raw=command.raw,
    )
