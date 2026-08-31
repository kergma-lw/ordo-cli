"""GitHub family bootstrap contract."""

from __future__ import annotations

from connectors.gh._repository import normalize_repository_value
from ordo.plugin_sdk import Diagnostic, bootstrap, bootstrap_fail, bootstrap_ok
from ordo.model.connector import ConnectorBootstrap

BOOTSTRAP = ConnectorBootstrap(
    prerequisites=("gh binary available", "GitHub auth available"),
    context_fields=("host", "viewer", "scopes", "repository"),
)


def info():
    return bootstrap(
        prerequisites=BOOTSTRAP.prerequisites,
        context_fields=BOOTSTRAP.context_fields,
        handler=run,
    )


def run(ctx):
    raw_input = ctx.family_input()
    allowed_fields = {"repository"}
    unknown_fields = sorted(field for field in raw_input if field not in allowed_fields)
    if unknown_fields:
        return bootstrap_fail(
            code="unknown_context_field",
            summary="GitHub connector context contains unknown fields",
            diagnostics=(
                Diagnostic(
                    code="bootstrap.gh_unknown_context_field",
                    level="error",
                    message="GitHub connector context contains unknown fields",
                    details={"unknown_fields": unknown_fields, "allowed_fields": sorted(allowed_fields)},
                ),
            ),
            raw={"connector_input": dict(raw_input), "unknown_fields": unknown_fields, "allowed_fields": sorted(allowed_fields)},
        )

    repository = None
    if "repository" in raw_input:
        repository = normalize_repository_value(raw_input.get("repository"))
        if repository is None:
            return bootstrap_fail(
                code="repository_invalid",
                summary="GitHub connector context field 'repository' must use OWNER/REPO format",
                diagnostics=(
                    Diagnostic(
                        code="bootstrap.gh_repository_invalid",
                        level="error",
                        message="GitHub connector context field 'repository' must use OWNER/REPO format",
                    ),
                ),
                raw={"connector_input": dict(raw_input)},
            )

    command = ctx.command(
        ["gh", "auth", "status"],
        failures={
            "os_error": "gh_unavailable",
            "nonzero": "auth_missing",
        },
    )
    return bootstrap_ok(
        summary="GitHub bootstrap completed successfully",
        context={"host": "github.com", "viewer": None, "scopes": [], "repository": repository},
        raw={**command.raw, "connector_input": dict(raw_input)},
    )
