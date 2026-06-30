"""shell.command action."""

from ordo.plugin_sdk import OperationContext, OperationOutcome, action, ok


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
    result = ctx.command(
        ["bash", "-lc", command],
        failures={
            "os_error": "action_failed",
            "nonzero": "command_failed",
        },
    )
    return ok(
        summary="Command completed successfully",
        outputs={"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
        raw=result.raw,
    )
