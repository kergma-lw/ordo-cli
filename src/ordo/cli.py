"""Command-line entrypoint for playbook-based workflow activation."""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys

import yaml

from ordo import check_workflow, clear_default_connector_provider, configure_standard_runtime, execute_workflow, explain_workflow, get_default_connector_provider, plan_workflow, set_default_connector_provider
from ordo.model.runtime import RuntimeResult
from ordo.playbook import PlaybookError, activate_playbook, activated_working_directory, inspect_playbook_workflow, list_playbook_workflows


WORKFLOWS_HELP = """usage: ordo-playbook workflows <list|show>

Inspect workflow entries declared in the project playbook.

Examples:
  ordo-playbook workflows list
  ordo-playbook workflows show inspect-issue
  ordo-playbook workflows show inspect-issue --json
"""


EXPLAIN_MODE_HELP = """usage: ordo-playbook [options] explain WORKFLOW

Explain why the selected workflow can or cannot be run right now.

Default output is intended to be concise:
  - overall status
  - whether execution is allowed
  - active blockers

Examples:
  ordo-playbook explain open-task
  ordo-playbook --profile backend --input issue_number=42 explain open-task
  ordo-playbook explain close-task --json
"""

PLAN_MODE_HELP = """usage: ordo-playbook [options] plan WORKFLOW

Show what the selected workflow would do without making changes.

Default output is intended to be concise:
  - if planning succeeds: guard checks and planned steps
  - if planning is blocked: a short note to use explain for details

Examples:
  ordo-playbook plan open-task
  ordo-playbook --profile backend --input issue_number=42 plan open-task
  ordo-playbook plan close-task --json
"""

CHECK_MODE_HELP = """usage: ordo-playbook [options] check WORKFLOW

Check whether the selected workflow can be run right now.

Default output is intended to be concise:
  - overall status
  - whether execution is allowed
  - observed facts
  - missing facts

Examples:
  ordo-playbook check open-task
  ordo-playbook --profile backend --input issue_number=42 check open-task
  ordo-playbook check close-task --json
"""


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] in {"check", "plan", "explain"} and sys.argv[2] in {"-h", "--help"}:
        if sys.argv[1] == "check":
            print(CHECK_MODE_HELP)
        elif sys.argv[1] == "plan":
            print(PLAN_MODE_HELP)
        else:
            print(EXPLAIN_MODE_HELP)
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] in {"-h", "--help"} and sys.argv[2] == "explain":
        print(EXPLAIN_MODE_HELP)
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] in {"-h", "--help"} and sys.argv[2] == "plan":
        print(PLAN_MODE_HELP)
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] in {"-h", "--help"} and sys.argv[2] == "check":
        print(CHECK_MODE_HELP)
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] == "workflows" and sys.argv[2] in {"-h", "--help"}:
        print(WORKFLOWS_HELP)
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] in {"-h", "--help"} and sys.argv[2] == "workflows":
        print(WORKFLOWS_HELP)
        return 0

    parser = argparse.ArgumentParser(
        prog="ordo-playbook",
        usage="%(prog)s [options] <command>",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "command help:\n"
            "  run `ordo-playbook <command> --help` to see command-specific guidance\n\n"
            "discovery:\n"
            "  workflows  list workflow entries or show one workflow contract summary\n\n"
            "execution:\n"
            "  check    check whether the workflow can be run now, without making changes\n"
            "  plan     show what the workflow would do, without making changes\n"
            "  explain  explain why the workflow can or cannot be run right now\n"
            "  run      run the workflow and do the real work\n"
            "  next     suggest the next workflow step to run now"
        ),
    )
    parser.add_argument("--file", dest="playbook_file", help="explicit playbook file path")
    parser.add_argument("--workflow", help="workflow name declared in the playbook; deprecated when used instead of positional workflow selection")
    parser.add_argument("--profile", help="active profile name for this run")
    parser.add_argument(
        "--input",
        dest="input_overrides",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override one workflow input for this run; repeatable; VALUE is parsed as YAML",
    )
    parser.add_argument(
        "--input-file",
        dest="input_files",
        action="append",
        default=[],
        metavar="KEY=PATH",
        help="load one workflow input value from a file as a raw string; repeatable",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON without extra decoration")
    parser.add_argument("command", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()
    command = list(args.command)
    if not command:
        parser.error("missing command")
    if command[0] == "workflows":
        return _run_workflow_discovery_args(args, command[1:], parser=parser)
    if command[0] not in {"check", "plan", "explain", "run", "next"}:
        parser.error(f"unknown command: {command[0]}")
    args.mode = command[0]
    args.workflow = _resolve_execution_workflow_name(args, parser=parser)
    input_overrides = _parse_input_overrides(args.input_overrides, parser=parser)
    input_overrides.update(_parse_input_file_overrides(args.input_files, parser=parser))

    had_previous_provider = True
    try:
        previous_provider = get_default_connector_provider()
    except RuntimeError:
        had_previous_provider = False
        previous_provider = None

    configure_standard_runtime()
    try:
        try:
            activated = activate_playbook(
                workflow_name=args.workflow,
                profile_name=args.profile,
                input_overrides=input_overrides,
                playbook_path=args.playbook_file,
            )
        except PlaybookError as exc:
            return _emit_error(exc, as_json=args.json)

        context_manager = activated_working_directory(activated)
        if args.mode == "run":
            context_manager = contextlib.nullcontext()

        with context_manager:
            if args.mode == "run":
                return _emit_refusal(
                    workflow=args.workflow,
                    playbook=str(activated.playbook_path),
                    profile=None if activated.profile is None else activated.profile.name,
                    as_json=args.json,
                )

            result = _run_mode(
                args.mode,
                activated.workflow,
                activated.profile,
                getattr(activated, "available_profiles", None),
                getattr(activated, "profile_working_directories", None),
            )
        if args.mode == "next":
            payload = {
                "mode": "next",
                "status": result.status.value,
                "diagnostics": [diagnostic.to_contract() for diagnostic in result.diagnostics],
                "workflow": activated.workflow_name,
                "playbook": str(activated.playbook_path),
                "profile": None if activated.profile is None else activated.profile.name,
                "next_actions": result.outputs.get("next_actions", []),
                "reason_category": result.outputs.get("reason_category"),
                "explanation": result.outputs.get("explanation"),
            }
        else:
            payload = result.to_contract()
            activation_diagnostics = getattr(activated, "diagnostics", ())
            if activation_diagnostics:
                payload["diagnostics"] = [
                    *payload.get("diagnostics", []),
                    *[diagnostic.to_contract() for diagnostic in activation_diagnostics],
                ]
            payload.update(
                {
                    "workflow": activated.workflow_name,
                    "playbook": str(activated.playbook_path),
                    "profile": None if activated.profile is None else activated.profile.name,
                }
            )

        if args.mode == "explain" and not args.json:
            payload = _summarize_explain_payload(payload)
        if args.mode == "plan" and not args.json:
            payload = _summarize_plan_payload(payload)
        if args.mode == "check" and not args.json:
            payload = _summarize_check_payload(payload)

        if args.json:
            json.dump(payload, sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if result.status.value == "ok" else 1
    finally:
        if had_previous_provider and previous_provider is not None:
            set_default_connector_provider(previous_provider)
        else:
            clear_default_connector_provider()


def _run_mode(mode: str, workflow, profile, available_profiles=None, profile_working_directories=None) -> RuntimeResult:
    if mode == "check":
        return check_workflow(workflow, profile=profile, available_profiles=available_profiles)
    if mode == "plan":
        return plan_workflow(workflow, profile=profile, available_profiles=available_profiles)
    if mode == "run":
        return execute_workflow(
            workflow,
            profile=profile,
            available_profiles=available_profiles,
            profile_working_directories=profile_working_directories,
        )
    explained = explain_workflow(workflow, profile=profile, available_profiles=available_profiles)
    return explained


def _resolve_execution_workflow_name(args, *, parser: argparse.ArgumentParser) -> str:
    command = list(args.command)
    if len(command) > 2:
        parser.error(f"{command[0]} accepts exactly one workflow name")
    if len(command) == 2:
        if args.workflow is not None:
            parser.error("do not combine a positional workflow name with --workflow")
        return command[1]
    if args.workflow is None:
        parser.error(f"{command[0]} requires a workflow name")
    print("warning: --workflow is deprecated; prefer `ordo-playbook <mode> <workflow>`", file=sys.stderr)
    return args.workflow


def _run_workflow_discovery_args(args, argv: list[str], *, parser: argparse.ArgumentParser) -> int:
    if not argv:
        parser.error("workflows requires a subcommand")
    if argv[0] not in {"list", "show"}:
        parser.error(f"unknown workflows subcommand: {argv[0]}")
    if argv[0] == "list" and len(argv) != 1:
        parser.error("workflows list does not accept a workflow name")
    if argv[0] == "show" and len(argv) != 2:
        parser.error("workflows show requires a workflow name")

    try:
        if argv[0] == "list":
            entries = list_playbook_workflows(playbook_path=args.playbook_file)
            payload = {
                "mode": "workflows.list",
                "status": "ok",
                "playbook": str(entries[0].playbook_path) if entries else str(args.playbook_file) if args.playbook_file else None,
                "workflows": [
                    {
                        "workflow": entry.workflow_name,
                        "description": entry.workflow_description,
                        "file": str(entry.workflow_path),
                    }
                    for entry in entries
                ],
            }
        else:
            entry = inspect_playbook_workflow(argv[1], playbook_path=args.playbook_file)
            payload = {
                "mode": "workflows.show",
                "status": "ok",
                "playbook": str(entry.playbook_path),
                "workflow": entry.workflow_name,
                "description": entry.workflow_description,
                "file": str(entry.workflow_path),
                "working_directory": entry.working_directory,
                "inputs": [
                    {
                        "name": item.name,
                        "description": item.description,
                    }
                    for item in entry.inputs
                ],
            }
    except PlaybookError as exc:
        return _emit_error(exc, as_json=args.json)

    if args.json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _parse_input_overrides(raw_items: list[str], *, parser: argparse.ArgumentParser) -> dict[str, object]:
    overrides: dict[str, object] = {}
    for item in raw_items:
        if "=" not in item:
            parser.error(f"--input expects KEY=VALUE, got: {item}")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            parser.error("--input key must not be empty")
        try:
            overrides[key] = "" if raw_value == "" else yaml.safe_load(raw_value)
        except yaml.YAMLError as exc:
            parser.error(f"invalid YAML value for --input {key}: {exc}")
    return overrides


def _parse_input_file_overrides(raw_items: list[str], *, parser: argparse.ArgumentParser) -> dict[str, object]:
    overrides: dict[str, object] = {}
    for item in raw_items:
        if "=" not in item:
            parser.error(f"--input-file expects KEY=PATH, got: {item}")
        key, raw_path = item.split("=", 1)
        key = key.strip()
        path = raw_path.strip()
        if not key:
            parser.error("--input-file key must not be empty")
        if not path:
            parser.error(f"--input-file path must not be empty for key {key}")
        try:
            with open(path, encoding="utf-8") as handle:
                overrides[key] = handle.read()
        except OSError as exc:
            parser.error(f"failed to read --input-file {key} from {path}: {exc}")
    return overrides


def _emit_refusal(*, workflow: str, playbook: str, profile: str | None, as_json: bool) -> int:
    payload = {
        "mode": "run",
        "status": "execution_error",
        "workflow": workflow,
        "playbook": playbook,
        "profile": profile,
        "diagnostics": [
            {
                "code": "playbook.run.disabled",
                "level": "error",
                "message": "Playbook run mode is temporarily disabled",
                "path": [],
                "details": {
                    "reason": "Run mode is intentionally blocked until the playbook execution surface is hardened",
                },
            }
        ],
    }
    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 1


def _emit_error(exc: PlaybookError, *, as_json: bool) -> int:
    payload = {
        "mode": "activation",
        "status": "resolution_error",
        "diagnostics": [diagnostic.to_contract() for diagnostic in exc.diagnostics],
    }
    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 1


def _summarize_explain_payload(payload: dict[str, object]) -> dict[str, object]:
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        outputs = {}
    explanation = outputs.get("explanation")
    if not isinstance(explanation, dict):
        explanation = {}

    return {
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "workflow": payload.get("workflow"),
        "playbook": payload.get("playbook"),
        "profile": payload.get("profile"),
        "allowed": explanation.get("allowed", outputs.get("execution_allowed")),
        "category": explanation.get("category", outputs.get("reason_category")),
        "why": explanation.get("why"),
        "failed_guard": payload.get("failed_guard"),
        "blockers": explanation.get("blockers", outputs.get("blockers", [])),
        "diagnostics": payload.get("diagnostics", []),
    }


def _summarize_plan_payload(payload: dict[str, object]) -> dict[str, object]:
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        outputs = {}
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        plan = {}

    summary = {
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "workflow": payload.get("workflow"),
        "playbook": payload.get("playbook"),
        "profile": payload.get("profile"),
        "allowed": outputs.get("execution_allowed", outputs.get("can_execute")),
        "diagnostics": payload.get("diagnostics", []),
    }

    if summary["status"] == "ok" and summary["allowed"] is True:
        summary["guard_checks"] = plan.get("guard_checks", [])
        summary["step_names"] = plan.get("step_names", [])
    else:
        summary["message"] = "plan unavailable; use explain for details"

    return summary


def _summarize_check_payload(payload: dict[str, object]) -> dict[str, object]:
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        outputs = {}

    allowed = outputs.get("can_execute")
    if not isinstance(allowed, bool):
        allowed = None

    summary = {
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "workflow": payload.get("workflow"),
        "playbook": payload.get("playbook"),
        "profile": payload.get("profile"),
        "allowed": allowed,
        "diagnostics": payload.get("diagnostics", []),
        "observed_facts": _collect_observed_facts(outputs),
        "missing_facts": _collect_missing_facts(outputs),
    }

    if payload.get("failed_guard") is not None:
        summary["failed_guard"] = payload.get("failed_guard")

    if outputs.get("verdict_basis_weakened"):
        summary["message"] = "check incomplete; use --json check or explain for details"

    return summary


def _collect_observed_facts(outputs: dict[str, object]) -> list[str]:
    guard_details = outputs.get("guard_details")
    if not isinstance(guard_details, list):
        return []

    facts: list[str] = []
    seen: set[str] = set()
    for detail in guard_details:
        if not isinstance(detail, dict):
            continue
        reference = detail.get("reference")
        if reference == "git.repo" and detail.get("status") == "ok":
            _append_unique(facts, seen, "git.repo: ok")
        trace = detail.get("trace")
        if not isinstance(trace, list):
            continue
        for item in trace:
            if not isinstance(item, dict):
                continue
            if item.get("kind") not in {"probe", "state", "input"}:
                continue
            if item.get("status") != "ok":
                continue
            expr = item.get("expr")
            if not isinstance(expr, str) or not expr:
                continue
            rendered = f"{expr} = {_compact_value(item.get('value'))}"
            _append_unique(facts, seen, rendered)

    return _limit_items(facts)


def _collect_missing_facts(outputs: dict[str, object]) -> list[str]:
    facts: list[str] = []
    seen: set[str] = set()

    weakened_scopes = outputs.get("weakened_observation_scopes")
    if isinstance(weakened_scopes, list):
        for scope in weakened_scopes:
            if isinstance(scope, str) and scope:
                _append_unique(facts, seen, f"fresh facts unavailable for {scope}")

    unevaluated_guards = outputs.get("unevaluated_relevant_guards")
    if isinstance(unevaluated_guards, list):
        for guard in unevaluated_guards:
            if not isinstance(guard, str) or not guard:
                continue
            references = _extract_fact_references(guard)
            if references:
                for reference in references:
                    _append_unique(facts, seen, reference)
            else:
                _append_unique(facts, seen, guard)

    return _limit_items(facts)


def _append_unique(items: list[str], seen: set[str], value: str) -> None:
    if value in seen:
        return
    seen.add(value)
    items.append(value)


def _limit_items(items: list[str], *, limit: int = 8) -> list[str]:
    if len(items) <= limit:
        return items
    hidden_count = len(items) - limit
    return [*items[:limit], f"… and {hidden_count} more"]


def _compact_value(value: object, *, limit: int = 80) -> str:
    if isinstance(value, str):
        rendered = value
    elif isinstance(value, (int, float, bool)) or value is None:
        rendered = json.dumps(value, ensure_ascii=False)
    else:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(rendered) <= limit:
        return rendered
    return f"{rendered[: limit - 1]}…"


def _extract_fact_references(expression: str) -> list[str]:
    matches = re.findall(r"([A-Za-z_][A-Za-z0-9_.]*(?:\([^)]*\))?(?:\.[A-Za-z_][A-Za-z0-9_]*)*)", expression)
    references: list[str] = []
    seen: set[str] = set()
    for match in matches:
        if "." not in match:
            continue
        if match.startswith("inputs."):
            continue
        if match in seen:
            continue
        seen.add(match)
        references.append(match)
    return references


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
