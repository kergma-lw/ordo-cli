"""Reader-facing content for the public command-line surface."""

from __future__ import annotations

from .human import HumanDeclaration, declare_human


COMMAND_LINE_HUMAN = declare_human({
    "title": "Command-line reference",
    "goal": "Choose the public command that lets you inspect, validate, plan, or carry out workflow work.",
    "summary": "Start by listing workflows, then inspect the workflow and its trust boundary before invoking a mode that can run probes or commands.",
    "sections": [
        {
            "heading": "Main entrypoint",
            "body": "Use `ordo-playbook` to work with the workflows published by the current playbook.",
            "items": [
                "`ordo-playbook workflows list` lists the workflows available in this project.",
                "`ordo-playbook workflows show <workflow>` shows what a named workflow needs before you run it.",
                "`ordo-playbook next` suggests the most useful workflow to consider next in the current context. It evaluates candidate workflows with contextual readiness checks and can run their probes, but does not execute action steps.",
                "`ordo-playbook graph` shows how published workflows share persistent data. Run it to see which workflows write, read, or remove that data; the result shows relationships, not a required run order. No active task is required.",
                "`ordo-playbook agent-instructions` reviews the whole playbook, then shows the compact Ordo-managed section for repository agent instructions when it is clean. Add `--write` only when you want it to update the repository AGENTS.md file.",
            ],
        },
        {
            "heading": "Choose a mode",
            "items": [
                "`ordo-playbook check <workflow>` answers whether the workflow can run now. It evaluates relevant probes and read-only preflight steps, so it can invoke local tools and external services; it does not execute action steps.",
                "`ordo-playbook review` checks every declared workflow using authored playbook material only. It does not resolve caller inputs, read current state, or run probes. Missing input descriptions and missing input sources block dependent generation; style recommendations remain advisory. The report separately counts pipe-style recommendations so they remain visible.",
                "`ordo-playbook review <workflow>` reports workflow-quality issues for one activated workflow. It runs the same contextual checks as check, including probes; it does not execute action steps.",
                "`ordo-playbook plan <workflow>` shows the work the workflow would perform. It runs the same contextual checks as check, including probes; it does not execute action steps.",
                "`ordo-playbook run <workflow>` performs the workflow's real work and reports its result.",
                "`ordo-playbook explain <workflow>` shows a compact static outline of the assembled workflow, including symbolic guards and step controls. It does not run probes, read state, validate runtime inputs, or execute action steps.",
                "After adding or changing a workflow, run both `check` and `review`: readiness and workflow quality are separate questions.",
            ],
        },
        {
            "heading": "Repository instructions",
            "items": [
                "Run `ordo-playbook agent-instructions` to inspect the generated compact workflow guidance without changing files after a clean whole-playbook review.",
                "Run `ordo-playbook agent-instructions --write` to update only the managed section of the repository AGENTS.md file after that same clean review. Any finding reports the review and leaves the section unavailable and the file unchanged.",
                "The command does not choose workflows at runtime or replace repository guidance outside its marked section.",
            ],
        },
        {
            "heading": "Public flags",
            "items": [
                "`--file PATH` selects a playbook file for this command.",
                "`--profile NAME` selects a named profile for this command.",
                "`--input KEY=VALUE` supplies or replaces one input for this command; repeat it for more inputs.",
                "`--input-file KEY=PATH` supplies one input from a file; repeat it for more inputs.",
                "`--progress-steps` prints each step name as a run begins it.",
                "`--json` returns machine-readable output when another tool needs to consume the result.",
            ],
        },
        {
            "heading": "Input precedence",
            "items": [
                "For the same input key, the workflow's declared default is used first, then a selected profile fills the key only when it is still missing, then a concrete playbook workflow binding replaces it, and a command-line value replaces all of those for this run.",
                "If both `--input KEY=VALUE` and `--input-file KEY=PATH` name the same key, `--input-file` wins: Ordo reads the file's UTF-8 text as that input value.",
                "Within repeated uses of either one flag, the later value for the same key wins.",
            ],
        },
        {
            "heading": "Practical next steps",
            "items": [
                "Run `ordo-playbook workflows list` when you do not yet know the workflow name.",
                "Run `ordo-playbook review` to check the whole playbook, then `ordo-playbook check <workflow>` and `ordo-playbook review <workflow>` before relying on a changed workflow.",
                "Run `ordo-playbook plan <workflow>` to inspect intended work before `ordo-playbook run <workflow>` makes changes.",
                "Use `ordo-help command-line --json` when a tool needs the complete command contract.",
            ],
            "references": [
                {"handle": "workflow-rules", "summary": "Read the workflow authoring practices that make check and review complementary."},
                {"handle": "overview", "summary": "Find related public help surfaces."},
            ],
        },
    ],
})


def _focused_command_line_human(*, title: str, summary: str, use_when: list[str], do_not_use_for: list[str], nearest_surfaces: list[str]) -> HumanDeclaration:
    """Declare one focused command-line guide without exposing runtime metadata."""

    return declare_human({
        "title": title,
        "goal": "Choose the command-line option that fits this one invocation.",
        "summary": summary,
        "sections": [
            {"heading": "Use when", "items": use_when},
            {"heading": "Do not use for", "items": do_not_use_for},
            {"heading": "Related surfaces", "items": nearest_surfaces},
        ],
    })


# These handles are the source-owned reader guides for focused command-line help.
COMMAND_LINE_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "command-line.ordo-playbook": COMMAND_LINE_HUMAN,
    "command-line.ordo-playbook.flag.file": _focused_command_line_human(
        title="command-line.ordo-playbook.flag.file",
        summary="Use one explicit playbook file for this invocation instead of the default playbook discovery path.",
        use_when=["You need to point this run at a different playbook file without changing repository defaults."],
        do_not_use_for=[
            "Selecting a workflow profile; use --profile for that.",
            "Passing workflow input values; use --input or --input-file for those values.",
        ],
        nearest_surfaces=[
            "command-line.ordo-playbook: Parent command surface for ordo-playbook",
            "playbook.workflows.file: Playbook field that binds a published workflow name to a workflow file inside a playbook",
        ],
    ),
    "command-line.ordo-playbook.flag.profile": _focused_command_line_human(
        title="command-line.ordo-playbook.flag.profile",
        summary="Select one named execution profile for this run.",
        use_when=[
            "You need one project-local profile override for this invocation.",
            "This explicit launch choice should win over playbook defaults and remembered-profile switching attempted inside playbook-owned pre_run setup.",
        ],
        do_not_use_for=[
            "Passing workflow input values; use --input or --input-file for those.",
            "Changing the playbook file itself; use --file for that.",
        ],
        nearest_surfaces=[
            "command-line.ordo-playbook: Parent command surface for ordo-playbook",
            "workflow.profile: Workflow-declared fixed profile binding inside authored workflow source",
            "profile.inputs: Profile-owned input defaults that may supply declared workflow inputs",
        ],
    ),
    "command-line.ordo-playbook.flag.input": _focused_command_line_human(
        title="command-line.ordo-playbook.flag.input",
        summary="Set one top-level workflow input from inline command-line text for this run.",
        use_when=["You need a quick one-run workflow input override that fits naturally on the command line."],
        do_not_use_for=[
            "Large text bodies or file-backed content; use --input-file when the value already lives in a file.",
            "Selecting a profile or playbook file; use --profile or --file for those launch concerns.",
        ],
        nearest_surfaces=[
            "command-line.ordo-playbook: Parent command surface for ordo-playbook",
            "command-line.ordo-playbook.flag.input_file: Sibling flag for loading one workflow input value from a file",
            "workflow.inputs_contract: Workflow contract that defines which activation inputs are allowed and required",
        ],
    ),
    "command-line.ordo-playbook.flag.input_file": _focused_command_line_human(
        title="command-line.ordo-playbook.flag.input_file",
        summary="Set one top-level workflow input by reading its raw UTF-8 value from a file for this run.",
        use_when=["You need to pass longer text or file-backed content into one workflow input without shell quoting it inline."],
        do_not_use_for=[
            "Short inline values that are clearer directly on the command line; use --input for those.",
            "Selecting a profile or playbook file; use --profile or --file for those launch concerns.",
        ],
        nearest_surfaces=[
            "command-line.ordo-playbook: Parent command surface for ordo-playbook",
            "command-line.ordo-playbook.flag.input: Sibling flag for setting one workflow input inline on the command line",
            "workflow.inputs_contract: Workflow contract that defines which activation inputs are allowed and required",
        ],
    ),
    "command-line.ordo-playbook.flag.json": _focused_command_line_human(
        title="command-line.ordo-playbook.flag.json",
        summary="Emit machine-readable JSON for this invocation instead of the default text rendering.",
        use_when=["You need stable machine-readable output for automation, tooling, or precise inspection."],
        do_not_use_for=["Changing workflow behavior; this flag changes output format, not execution semantics."],
        nearest_surfaces=[
            "command-line.ordo-playbook: Parent command surface for ordo-playbook",
            "overview: Public discovery overview that teaches the main JSON-capable help surfaces",
        ],
    ),
    "command-line.ordo-playbook.flag.progress_steps": _focused_command_line_human(
        title="command-line.ordo-playbook.flag.progress_steps",
        summary="During run, emit each step name to standard error right before execution.",
        use_when=[
            "You need immediate human-visible progress while run mode is executing real workflow steps.",
            "You want progress lines without corrupting JSON or summary data written to standard output.",
        ],
        do_not_use_for=[
            "Non-run modes; this flag is only supported with run.",
            "Machine-readable progress parsing from standard output; progress is emitted on standard error instead.",
        ],
        nearest_surfaces=[
            "command-line.ordo-playbook: Parent command surface for ordo-playbook",
            "command-line.ordo-playbook.flag.json: Companion output-format flag that keeps standard output machine-readable while progress goes to standard error",
        ],
    ),
}


def command_line_focused_describe_human(handle: str) -> HumanDeclaration | None:
    """Return the reader guide for one focused command-line handle."""

    return COMMAND_LINE_FOCUSED_DESCRIBE_HUMAN.get(handle)
