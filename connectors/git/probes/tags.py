"""git.tags probe."""

from __future__ import annotations

import fnmatch
import re

from ordo.model.json import JSONValue
from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_external_command, fail_with_diagnostic, ok, probe
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value


def info():
    return probe(
        name="tags",
        summary=(
            "Inspect Git tags sorted by descending version refname. Each returned `oid` is the peeled target object id; "
            "for annotated tags this means the referenced object oid rather than the tag object oid. "
            "The `latest` output is the first matching item in that version-sorted order, not the newest tag by creation date."
        ),
        inputs={"match": "string | null", "match_kind": "'glob' | 'regex' | null"},
        outputs={
            "count": "integer",
            "items": [
                {
                    "name": "string",
                    "ref": "string",
                    "oid": "string",
                    "annotated": "boolean",
                }
            ],
            "latest": {
                "name": "string",
                "ref": "string",
                "oid": "string",
                "annotated": "boolean",
            },
            "repository_root": "string",
        },
        failure_modes=("probe_failed",),
        examples=(
            {"reference": "git.tags", "inputs": {"match": "v*", "match_kind": "glob"}},
            {"reference": "git.tags", "inputs": {"match": r"^v?[0-9]+\.[0-9]+\.[0-9]+$", "match_kind": "regex"}},
        ),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    repository_root = ctx.bootstrap().context.get("repository_root")
    if not isinstance(repository_root, str) or not repository_root.strip():
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git bootstrap did not provide a usable repository root",
            diagnostic_code="probe.git_tags.repo_root_missing",
            reference=ctx.reference,
            raw={"bootstrap": dict(ctx.bootstrap().context)},
        )

    match_value = _optional_input(ctx, "match")
    if isinstance(match_value, OperationOutcome):
        return match_value
    if match_value is not None and not isinstance(match_value, str):
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.tags match must be a string when provided",
            diagnostic_code="probe.git_tags.invalid_match",
            reference=ctx.reference,
            raw={"match": match_value},
        )
    match_kind = _optional_input(ctx, "match_kind")
    if isinstance(match_kind, OperationOutcome):
        return match_kind
    if match_kind in (None, ""):
        match_kind = "glob"
    if match_kind not in {"glob", "regex"}:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="git.tags match_kind must be 'glob' or 'regex' when provided",
            diagnostic_code="probe.git_tags.invalid_match_kind",
            reference=ctx.reference,
            raw={"match_kind": match_kind},
        )

    regex: re.Pattern[str] | None = None
    if match_value is not None and match_kind == "regex":
        try:
            regex = re.compile(match_value)
        except re.error:
            return fail_with_diagnostic(
                code="probe_failed",
                summary="git.tags received an invalid regex match pattern",
                diagnostic_code="probe.git_tags.invalid_match",
                reference=ctx.reference,
                raw={"match": match_value, "match_kind": match_kind},
            )

    try:
        command = ctx.command(
            [
                "git",
                "for-each-ref",
                "--sort=-version:refname",
                "--format=%(refname)\t%(refname:short)\t%(objecttype)\t%(objectname)\t%(*objectname)",
                "refs/tags",
            ],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        return fail_external_command(
            code="probe_failed",
            summary="Git tag inventory inspection failed",
            diagnostic_code="probe.git_tags.command_failed",
            reference=ctx.reference,
            raw=exc.outcome.raw,
            tool="git",
        )

    items: list[dict[str, object]] = []
    for line in command.stdout.splitlines():
        if not line:
            continue
        parsed = _parse_line(ctx, line=line, raw=dict(command.raw))
        if isinstance(parsed, OperationOutcome):
            return parsed
        if _matches(parsed["name"], match_value=match_value, match_kind=match_kind, regex=regex):
            items.append(parsed)

    return ok(
        summary="Git tag inventory inspected successfully",
        outputs={
            "count": len(items),
            "items": items,
            "latest": items[0] if items else None,
            "repository_root": repository_root,
        },
        raw=command.raw,
    )


def _parse_line(ctx: OperationContext, *, line: str, raw: dict[str, object]) -> dict[str, object] | OperationOutcome:
    parts = line.split("\t")
    if len(parts) != 5:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git tag inventory returned an unexpected line format",
            diagnostic_code="probe.git_tags.invalid_line",
            reference=ctx.reference,
            raw={"tags": raw, "line": line},
        )

    ref, short_name, object_type, object_oid, peeled_oid = parts
    if not ref.startswith("refs/tags/") or not short_name or not object_oid:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git tag inventory returned an incomplete tag entry",
            diagnostic_code="probe.git_tags.invalid_line",
            reference=ctx.reference,
            raw={"tags": raw, "line": line},
        )
    if object_type not in {"tag", "commit"}:
        return fail_with_diagnostic(
            code="probe_failed",
            summary="Git tag inventory returned an unsupported object type",
            diagnostic_code="probe.git_tags.invalid_object_type",
            reference=ctx.reference,
            raw={"tags": raw, "line": line},
        )

    return {
        "name": short_name,
        "ref": ref,
        "oid": peeled_oid if object_type == "tag" and peeled_oid else object_oid,
        "annotated": object_type == "tag",
    }


def _matches(name: object, *, match_value: str | None, match_kind: str, regex: re.Pattern[str] | None) -> bool:
    if not isinstance(name, str):
        return False
    if match_value is None:
        return True
    if match_kind == "regex":
        assert regex is not None
        return regex.search(name) is not None
    return fnmatch.fnmatchcase(name, match_value)


def _optional_input(ctx: OperationContext, key: str) -> JSONValue | None | OperationOutcome:
    resolved = getattr(ctx, "_resolved")
    workflow = getattr(ctx, "_workflow")

    resolved_inputs = getattr(resolved, "resolved_inputs", None)
    if isinstance(resolved_inputs, dict) and key in resolved_inputs:
        return resolved_inputs[key]

    candidate_inputs = getattr(resolved, "declared_with", None)
    if isinstance(candidate_inputs, dict) and key in candidate_inputs:
        candidate = candidate_inputs[key]
        if candidate is None:
            return None
        try:
            return resolve_runtime_value(candidate, workflow)
        except ValueResolutionError as exc:
            return OperationOutcome(status="input_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))

    for guard in workflow.guards:
        if guard.operation is not None and guard.operation.uses == resolved.reference and key in guard.operation.with_:
            candidate = guard.operation.with_[key]
            if candidate is None:
                return None
            try:
                return resolve_runtime_value(candidate, workflow)
            except ValueResolutionError as exc:
                return OperationOutcome(status="input_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))

    for step in workflow.steps:
        if step.operation is not None and step.operation.uses == resolved.reference and key in step.operation.with_:
            candidate = step.operation.with_[key]
            if candidate is None:
                return None
            try:
                return resolve_runtime_value(candidate, workflow)
            except ValueResolutionError as exc:
                return OperationOutcome(status="input_error", summary=exc.message, diagnostics=(exc.to_diagnostic(),))

    return None
