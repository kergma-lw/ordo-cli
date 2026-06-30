"""shell.command action."""

from connectors._shared import require_input, run_command
from ordo.model.connector import OperationContract
from ordo.model.runtime import OperationResult

ORDER = 10

OPERATION = OperationContract(
    name="command",
    kind="action",
    inputs={"command": "string"},
    effects=("execute shell command",),
    outputs={"exit_code": "integer", "stdout": "string", "stderr": "string"},
    failure_modes=("shell_unavailable", "command_failed", "action_failed"),
)


def execute(resolved, workflow) -> OperationResult:
    command = require_input(workflow, resolved, "command")
    if isinstance(command, OperationResult):
        return command
    return run_command(["bash", "-lc", command], reference=resolved.reference)
