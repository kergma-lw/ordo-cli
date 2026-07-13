"""runtime.profile.use action."""

from __future__ import annotations

from ordo.plugin_sdk import action, ok


def info():
    return action(
        name="profile.use",
        summary="Legacy compatibility action for switching runtime execution to another declared profile",
        inputs={"profile": "string"},
        effects=("switch runtime profile for later execution in the current run",),
        outputs={"profile": "string"},
        failure_modes=("input_error", "execution_error"),
        deprecated=True,
        replaced_by=("workflow.step.profile_switch",),
        handler=run,
    )


def run(ctx):
    return ok(summary="Profile switch requested", outputs={"profile": str(ctx.input("profile"))})
