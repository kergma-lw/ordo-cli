"""Compose family bootstrap contract."""

from __future__ import annotations

from pathlib import Path

from ordo.model.connector import ConnectorBootstrap
from ordo.plugin_sdk import Diagnostic, bootstrap, bootstrap_fail, bootstrap_ok

BOOTSTRAP = ConnectorBootstrap(
    prerequisites=("docker compose available",),
    context_fields=("project_directory", "compose_file", "project_name"),
)


def info():
    return bootstrap(
        prerequisites=BOOTSTRAP.prerequisites,
        context_fields=BOOTSTRAP.context_fields,
        handler=run,
    )


def run(ctx):
    raw_input = ctx.family_input()
    project_directory: str | None = None
    compose_file: str | None = None
    project_name: str | None = None

    if raw_input:
        allowed_fields = {"directory", "file", "project_name"}
        unknown_fields = sorted(field for field in raw_input if field not in allowed_fields)
        if unknown_fields:
            return bootstrap_fail(
                code="unknown_context_field",
                summary="Compose connector context contains unknown fields",
                diagnostics=(
                    Diagnostic(
                        code="bootstrap.compose_unknown_context_field",
                        level="error",
                        message="Compose connector context contains unknown fields",
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
                    summary="Compose connector context field 'directory' must be a non-empty string",
                    diagnostics=(
                        Diagnostic(
                            code="bootstrap.compose_directory_invalid",
                            level="error",
                            message="Compose connector context field 'directory' must be a non-empty string",
                        ),
                    ),
                    raw={"connector_input": dict(raw_input)},
                )
            directory_path = Path(raw_directory).expanduser().resolve()
            if not directory_path.exists() or not directory_path.is_dir():
                return bootstrap_fail(
                    code="directory_invalid",
                    summary="Compose connector context field 'directory' must resolve to an existing directory",
                    diagnostics=(
                        Diagnostic(
                            code="bootstrap.compose_directory_missing",
                            level="error",
                            message="Compose connector context field 'directory' must resolve to an existing directory",
                        ),
                    ),
                    raw={"connector_input": dict(raw_input), "directory": str(directory_path)},
                )
            project_directory = str(directory_path)

        raw_file = raw_input.get("file")
        if raw_file is not None:
            if not isinstance(raw_file, str) or not raw_file.strip():
                return bootstrap_fail(
                    code="file_invalid",
                    summary="Compose connector context field 'file' must be a non-empty string",
                    diagnostics=(
                        Diagnostic(
                            code="bootstrap.compose_file_invalid",
                            level="error",
                            message="Compose connector context field 'file' must be a non-empty string",
                        ),
                    ),
                    raw={"connector_input": dict(raw_input)},
                )
            base_path = Path(project_directory) if project_directory is not None else Path.cwd()
            file_path = (base_path / raw_file).expanduser().resolve() if not Path(raw_file).is_absolute() else Path(raw_file).expanduser().resolve()
            if not file_path.exists() or not file_path.is_file():
                return bootstrap_fail(
                    code="file_invalid",
                    summary="Compose connector context field 'file' must resolve to an existing file",
                    diagnostics=(
                        Diagnostic(
                            code="bootstrap.compose_file_missing",
                            level="error",
                            message="Compose connector context field 'file' must resolve to an existing file",
                        ),
                    ),
                    raw={"connector_input": dict(raw_input), "file": str(file_path)},
                )
            compose_file = str(file_path)

        raw_project_name = raw_input.get("project_name")
        if raw_project_name is not None:
            if not isinstance(raw_project_name, str) or not raw_project_name.strip():
                return bootstrap_fail(
                    code="project_name_invalid",
                    summary="Compose connector context field 'project_name' must be a non-empty string",
                    diagnostics=(
                        Diagnostic(
                            code="bootstrap.compose_project_name_invalid",
                            level="error",
                            message="Compose connector context field 'project_name' must be a non-empty string",
                        ),
                    ),
                    raw={"connector_input": dict(raw_input)},
                )
            project_name = raw_project_name.strip()

    command = ctx.command(
        ["docker", "compose", "version"],
        failures={
            "os_error": "orchestrator_unavailable",
            "nonzero": "orchestrator_unavailable",
        },
        cwd=project_directory,
    )

    return bootstrap_ok(
        summary="Compose bootstrap completed successfully",
        context={
            "project_directory": project_directory,
            "compose_file": compose_file,
            "project_name": project_name,
        },
        raw={**command.raw, "command_working_directory": project_directory, "connector_input": dict(raw_input)},
    )
