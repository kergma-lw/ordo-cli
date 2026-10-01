"""Inspect a configured Git remote using local Git configuration."""

from __future__ import annotations

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, fail_with_diagnostic, ok, probe
from ordo.model.human import declare_human
from connectors.git.human import git_human


HUMAN = declare_human({'title': 'Git remote',
  'goal': 'A workflow needs the recorded destinations for one named remote before deciding whether to synchronize or publish.',
  'summary': 'Observe one named remote, including whether it exists, its fetch and push destinations, and whether it mirrors.',
 'sections': [{'heading': 'Use when',
               'items': ['Use this before fetch or push when a workflow needs to select a local remote by name.',
                          'Later logic needs the recorded destination facts, not proof that a network operation will succeed.']},
               {'heading': 'Do not use for',
                'items': ['Destination safety or policy; decide whether an observed destination is acceptable.',
                           'Reachability, access, remote identity, or proof of a later push destination.',
                          'Repository-root facts, current-branch tracking, or publication itself; use '
                          'connector.git.repo, connector.git.upstream, or connector.git.sync.push respectively.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.git.repo',
                               'summary': 'Local repository-root, git-dir, and default-branch facts'},
                              {'handle': 'connector.git.upstream',
                               'summary': "Current branch's configured tracking remote and tracking ref"},
                              {'handle': 'connector.git.sync.push',
                               'summary': "Publish a branch to a configured remote after the caller's decision"}]},
              ]})

def info():
    return probe(
        name="remote",
        human=git_human(HUMAN, provide="`remote`: required; provide a recorded remote name, such as origin or team/origin. It identifies a saved destination rather than a destination to invent.", result="Returns name, exists, fetch_urls, push_urls, and mirror. A missing name is reported with exists=false; recorded destinations are descriptive only and may change, while invalid or unreadable information fails without partial facts."),
        summary=(
            "Inspect a configured remote's effective fetch and push URLs and mirror setting without network access. "
            "Git applies URL rewrites; returned URLs are preserved verbatim. "
            "An absent remote has exists=false, empty URL lists, and mirror=null."
        ),
        inputs={"remote": "string"},
        outputs={
            "name": "string",
            "exists": "boolean",
            "fetch_urls": ["string"],
            "push_urls": ["string"],
            "mirror": "boolean | null",
        },
        failure_modes=("probe_failed",),
        handler=run,
    )


def _valid_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith("-")
        and "\0" not in value
        and not any(char.isspace() for char in value)
    )


def _lines(value: str) -> list[str]:
    # Only LF delimits Git output records; do not trim URL whitespace or split
    # on other characters (such as CR or Unicode line separators).
    return value.removesuffix("\n").split("\n") if value else []


def run(ctx: OperationContext) -> OperationOutcome:
    name = ctx.input("remote")
    raw: dict[str, object] = {}

    def failure(diagnostic: str, summary: str) -> OperationOutcome:
        return fail_with_diagnostic(
            code="probe_failed",
            summary=summary,
            diagnostic_code=f"probe.git_remote.{diagnostic}",
            reference=ctx.reference,
            raw=raw,
        )

    if not _valid_name(name):
        return failure("invalid_input", "Remote must be a nonempty configured name without whitespace or a leading '-'")

    try:
        inventory = ctx.command(
            ["git", "remote"], failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        raw["inventory"] = dict(exc.outcome.raw)
        return failure("inventory_failed", "Could not read configured Git remote names")
    raw["inventory"] = dict(inventory.raw)
    names = _lines(inventory.stdout)
    if len(names) != len(set(names)) or any(not _valid_name(item) for item in names):
        return failure("invalid_inventory", "Git remote inventory returned malformed names")

    outputs = {"name": name, "exists": name in names, "fetch_urls": [], "push_urls": [], "mirror": None}
    if name not in names:
        return ok(summary="Git remote inspected successfully", outputs=outputs, raw=raw)

    for label, argv in (
        ("fetch_urls", ["git", "remote", "get-url", "--all", name]),
        ("push_urls", ["git", "remote", "get-url", "--push", "--all", name]),
    ):
        try:
            command = ctx.command(argv, failures={"os_error": "probe_failed", "nonzero": "probe_failed"})
        except MappedOutcomeError as exc:
            raw[label] = dict(exc.outcome.raw)
            return failure(f"{label}_failed", f"Could not read Git remote {label}")
        raw[label] = dict(command.raw)
        urls = _lines(command.stdout)
        if not urls or any(not url for url in urls):
            return failure(f"invalid_{label}", f"Git remote returned empty {label}")
        outputs[label] = urls

    try:
        command = ctx.command(
            ["git", "config", "--bool", "--get", f"remote.{name}.mirror"],
            failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
        )
    except MappedOutcomeError as exc:
        raw["mirror"] = dict(exc.outcome.raw)
        if exc.outcome.raw.get("returncode") != 1:
            return failure("mirror_failed", "Could not read Git remote mirror configuration")
        outputs["mirror"] = False
    else:
        raw["mirror"] = dict(command.raw)
        value = command.stdout.removesuffix("\n")
        if value not in ("true", "false"):
            return failure("invalid_mirror", "Git config returned an invalid mirror boolean")
        outputs["mirror"] = value == "true"

    return ok(summary="Git remote inspected successfully", outputs=outputs, raw=raw)
