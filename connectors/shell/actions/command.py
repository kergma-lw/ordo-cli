"""shell.command action."""

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_external_command, ok


def info():
    return action(
        name="command",
        inputs={"command": "string"},
        effects=("execute shell command",),
        outputs={"exit_code": "integer", "stdout": "string", "stderr": "string"},
        failure_modes=("command_failed", "action_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    command = str(ctx.input("command"))
    try:
        result = ctx.command(
            ["bash", "-lc", command],
            failures={
                "os_error": "action_failed",
                "nonzero": "command_failed",
            },
        )
    except MappedOutcomeError as exc:
        return fail_external_command(
            code=exc.outcome.status,
            summary="Shell command execution failed",
            diagnostic_code="action.shell_command.command_failed",
            reference=ctx.reference,
            details={"command": command},
            raw=exc.outcome.raw,
            tool="bash",
        )
    return ok(
        summary="Command completed successfully",
        outputs={"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
        raw=result.raw,
    )
