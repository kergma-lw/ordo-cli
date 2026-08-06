"""Git family bootstrap contract."""

from pathlib import Path

from ordo.plugin_sdk import Diagnostic, bootstrap, bootstrap_fail, bootstrap_ok
from ordo.model.connector import ConnectorBootstrap

BOOTSTRAP = ConnectorBootstrap(
    prerequisites=("git binary available", "inside git repository"),
    context_fields=("repository_root",),
)


def info():
    return bootstrap(
        prerequisites=BOOTSTRAP.prerequisites,
        context_fields=BOOTSTRAP.context_fields,
        handler=run,
    )


def run(ctx):
    raw_input = ctx.family_input()
    command_cwd: str | None = None
    if raw_input:
        allowed_fields = {"directory"}
        unknown_fields = sorted(field for field in raw_input if field not in allowed_fields)
        if unknown_fields:
            return bootstrap_fail(
                code="unknown_context_field",
                summary="Git connector context contains unknown fields",
                diagnostics=(
                    Diagnostic(
                        code="bootstrap.git_unknown_context_field",
                        level="error",
                        message="Git connector context contains unknown fields",
                        details={"unknown_fields": unknown_fields, "allowed_fields": sorted(allowed_fields)},
                    ),
                ),
                raw={"connector_input": dict(raw_input), "unknown_fields": unknown_fields, "allowed_fields": sorted(allowed_fields)},
            )
        raw_directory = raw_input.get("directory")
        if raw_directory is not None:
            if not isinstance(raw_directory, str) or not raw_directory.strip():
                return bootstrap_fail(
                    code="directory_invalid",
                    summary="Git connector context field 'directory' must be a non-empty string",
                    diagnostics=(
                        Diagnostic(
                            code="bootstrap.git_directory_invalid",
                            level="error",
                            message="Git connector context field 'directory' must be a non-empty string",
                        ),
                    ),
                    raw={"connector_input": dict(raw_input)},
                )
            directory_path = Path(raw_directory).expanduser().resolve()
            if not directory_path.exists() or not directory_path.is_dir():
                return bootstrap_fail(
                    code="directory_invalid",
                    summary="Git connector context field 'directory' must resolve to an existing directory",
                    diagnostics=(
                        Diagnostic(
                            code="bootstrap.git_directory_missing",
                            level="error",
                            message="Git connector context field 'directory' must resolve to an existing directory",
                        ),
                    ),
                    raw={"connector_input": dict(raw_input), "directory": str(directory_path)},
                )
            command_cwd = str(directory_path)

    command = ctx.command(
        ["git", "rev-parse", "--show-toplevel"],
        failures={
            "os_error": "git_unavailable",
            "nonzero": "not_repository",
        },
        cwd=command_cwd,
    )

    repository_root = command.stdout.strip()
    if not repository_root:
        return bootstrap_fail(
            code="not_repository",
            summary="Repository root could not be determined",
            diagnostics=(
                Diagnostic(
                    code="bootstrap.repository_missing",
                    level="error",
                    message="Repository root could not be determined",
                ),
            ),
            raw=command.raw,
        )

    return bootstrap_ok(
        summary="Git bootstrap completed successfully",
        context={
            "repository_root": repository_root,
        },
        raw={**command.raw, "command_working_directory": repository_root, "connector_input": dict(raw_input)},
    )
