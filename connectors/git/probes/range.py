"""git.range probe."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git range',
 'goal': 'A workflow needs to compare two endpoints such as main and HEAD before deciding whether a branch is ahead, '
         'behind, or diverged.',
  'summary': 'Compare two Git revision endpoints and return their resolved object ids, merge '
            'base, and ahead/behind counts.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to compare two endpoints such as main and HEAD before deciding whether a '
                         'branch is ahead, behind, or diverged.',
                         'Later logic needs one merge-base-aware relationship summary instead of a readable commit '
                         'list or one exact ref lookup.']},
              {'heading': 'Do not use for',
               'items': ['Checking only whether one exact ref resolves; use connector.git.ref for the simpler '
                          'single-ref lookup.',
                         'Reading commit subjects or bodies across a revision slice; use connector.git.commits when '
                         'the workflow needs readable history rather than ahead/behind math.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.ref',
                                'summary': 'Resolve one exact ref instead of comparing two revision '
                                          'endpoints'},
                              {'handle': 'connector.git.commits',
                                'summary': 'Read a commit-history slice after the workflow chooses '
                                          'a revision scope'},
                              {'handle': 'connector.git.branch',
                                'summary': 'Read current checkout branch context before choosing base and '
                                          'head endpoints'},
                              {'handle': 'connector.git.upstream',
                                'summary': 'Read upstream-tracking context when the workflow first needs '
                                          'to choose a comparison target'}]},
              {'heading': 'Examples',
               'items': ['git.range with inputs {"base": "main", "head": "HEAD"}',
                         'git.range with inputs {"base": "origin/main", "head": "feature/demo"}']},
              {'heading': 'Inspect next',
               'items': ['connector.git.ref', 'connector.git.commits', 'connector.git.upstream']}]})

def info():
    return probe(
        name="range",
        human=git_human(HUMAN, provide="`base`: required; provide one revision endpoint. `head`: required; provide the other revision endpoint, such as main and HEAD.", result="Returns base, head, base_oid, head_oid, merge_base_oid when one exists, ahead_count, behind_count, and repository_root. Unresolvable endpoints have no comparison result; counts can become stale when history changes."),
        inputs={"base": "string", "head": "string"},
        outputs={
            "base": "string",
            "head": "string",
            "base_oid": "string",
            "head_oid": "string",
            "merge_base_oid": "string | null",
            "ahead_count": "integer",
            "behind_count": "integer",
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
            diagnostic_code="probe.git_range.repo_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    base = ctx.input("base")
    head = ctx.input("head")
    if not isinstance(base, str) or not base.strip() or not isinstance(head, str) or not head.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.range requires non-empty base and head inputs",
            diagnostic_code="probe.git_range.invalid_input",
            reference=ctx.reference,
            raw={"base": base, "head": head},
        )

    raw: dict[str, object] = {}

    base_oid = _resolve_oid(ctx, ref_name=base, label="base", raw=raw)
    if isinstance(base_oid, OperationOutcome):
        return base_oid
    head_oid = _resolve_oid(ctx, ref_name=head, label="head", raw=raw)
    if isinstance(head_oid, OperationOutcome):
        return head_oid

    merge_base_oid = _resolve_merge_base(ctx, base=base, head=head, raw=raw)
    if isinstance(merge_base_oid, OperationOutcome):
        return merge_base_oid

    counts = _resolve_counts(ctx, base=base, head=head, raw=raw)
    if isinstance(counts, OperationOutcome):
        return counts
    ahead_count, behind_count = counts

    return ok(
        summary="Git range facts inspected successfully",
        outputs={
            "base": base,
            "head": head,
            "base_oid": base_oid,
            "head_oid": head_oid,
            "merge_base_oid": merge_base_oid,
            "ahead_count": ahead_count,
            "behind_count": behind_count,
            "repository_root": repository_root,
        },
        raw=raw,
    )


def _resolve_oid(
    ctx: OperationContext,
    *,
    ref_name: str,
    label: str,
    raw: dict[str, object],
) -> str | OperationOutcome:
    try:
        command = ctx.command(
            ["git", "rev-parse", "--verify", "--end-of-options", f"{ref_name}^{{object}}"],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 128:
            return fail_with_diagnostic(
                code="probe_failed",
                summary=f"Git could not resolve {label} ref '{ref_name}'",
                diagnostic_code="probe.git_range.unresolved_ref",
                reference=ctx.reference,
                raw={**raw, label: dict(exc.outcome.raw), "ref": ref_name},
            )
        return exc.outcome
    raw[label] = dict(command.raw)
    oid = command.stdout.strip()
    if not oid:
        return fail_with_diagnostic(
            code="probe_failed",
            summary=f"Git returned an empty oid for {label} ref '{ref_name}'",
            diagnostic_code="probe.git_range.empty_oid",
            reference=ctx.reference,
            raw={**raw, "ref": ref_name},
        )
    return oid


def _resolve_merge_base(
    ctx: OperationContext,
    *,
    base: str,
    head: str,
    raw: dict[str, object],
) -> str | None | OperationOutcome:
    try:
        command = ctx.command(
            ["git", "merge-base", base, head],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        returncode = exc.outcome.raw.get("returncode")
        if returncode == 1:
            raw["merge_base"] = dict(exc.outcome.raw)
            return None
        return exc.outcome
    raw["merge_base"] = dict(command.raw)
    merge_base_oid = command.stdout.strip()
    if not merge_base_oid:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git merge-base returned empty output",
            diagnostic_code="probe.git_range.empty_merge_base",
            reference=ctx.reference,
            raw=raw,
        )
    return merge_base_oid


def _resolve_counts(
    ctx: OperationContext,
    *,
    base: str,
    head: str,
    raw: dict[str, object],
) -> tuple[int, int] | OperationOutcome:
    command = ctx.command(
        ["git", "rev-list", "--left-right", "--count", f"{base}...{head}"],
        failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
    )
    raw["counts"] = dict(command.raw)
    parts = command.stdout.strip().split()
    if len(parts) != 2:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git rev-list returned an unexpected ahead/behind count format",
            diagnostic_code="probe.git_range.invalid_counts",
            reference=ctx.reference,
            raw=raw,
        )
    try:
        behind_count = int(parts[0])
        ahead_count = int(parts[1])
    except ValueError:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git rev-list returned non-integer ahead/behind counts",
            diagnostic_code="probe.git_range.invalid_counts",
            reference=ctx.reference,
            raw=raw,
        )
    if behind_count < 0 or ahead_count < 0:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git rev-list returned negative ahead/behind counts",
            diagnostic_code="probe.git_range.invalid_counts",
            reference=ctx.reference,
            raw=raw,
        )
    return ahead_count, behind_count
