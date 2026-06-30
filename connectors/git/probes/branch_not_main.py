"""git.branch_not_main probe."""

from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, fail, ok, probe


def info():
    return probe(
        name="branch_not_main",
        outputs={"allowed": "boolean", "current_branch": "string"},
        failure_modes=("probe_failed",),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    branch_outcome = ctx.call("branch")
    branch = str(branch_outcome.outputs.get("value", ""))
    if branch != "main":
        return ok(
            summary="Current branch inspected successfully",
            outputs={"allowed": True, "current_branch": branch},
            raw=branch_outcome.raw,
        )

    return fail(
        code="guard_failed",
        summary="Current branch inspected successfully",
        outputs={"allowed": False, "current_branch": branch},
        diagnostics=(
            Diagnostic(
                code="guard.branch_main",
                level="error",
                message="Current branch is main",
                details={"reference": ctx.reference, "current_branch": branch},
            ),
        ),
        raw=branch_outcome.raw,
    )
