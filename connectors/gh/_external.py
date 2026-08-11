"""Shared helpers for GitHub CLI external command failures."""

from __future__ import annotations

from collections.abc import Mapping

from ordo.model.json import JSONObject
from ordo.plugin_sdk import OperationContext, OperationOutcome, fail_external_command


def command_text(raw: Mapping[str, object]) -> str:
    return f"{raw.get('stderr', '')}\n{raw.get('stdout', '')}".lower()


def text_mentions_not_found(text: str, *phrases: str) -> bool:
    return any(phrase in text for phrase in (*phrases, "not found"))


def fail_github_command(
    ctx: OperationContext,
    *,
    code: str,
    summary: str,
    diagnostic_code: str,
    raw: Mapping[str, object],
    details: JSONObject,
    message: str | None = None,
    outputs: JSONObject | None = None,
) -> OperationOutcome:
    return fail_external_command(
        code=code,
        summary=summary,
        diagnostic_code=diagnostic_code,
        raw=raw,
        reference=ctx.reference,
        details=details,
        outputs=outputs,
        tool="gh",
        system="github",
        message=message,
    )
