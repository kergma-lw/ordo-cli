"""Command-line entrypoint for playbook-based workflow activation."""

from __future__ import annotations

import argparse
import json
import re
import sys

from ordo import check_workflow, clear_default_connector_provider, configure_standard_runtime, execute_workflow, explain_workflow, get_default_connector_provider, plan_workflow, review_workflow, set_default_connector_provider
from ordo.external_failures import describe_external_failure_context
from ordo.model.runtime import RuntimeResult, RuntimeStatus
from ordo.playbook import PlaybookError, activate_playbook, activated_working_directory, inspect_playbook_workflow, list_playbook_workflows
from ordo.runtime.human_messages import render_gate_failure_message, render_guard_failure_message
from ordo.runtime.nexting import build_next_candidate, classify_missing_input_kind_for_workflow, rank_next_candidates


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
  ordo-playbook explain set-active-task
  ordo-playbook --profile backend --input issue_number=42 explain set-active-task
  ordo-playbook explain close-task --json
"""

PLAN_MODE_HELP = """usage: ordo-playbook [options] plan WORKFLOW

Show what the selected workflow would do without making changes.

Default output is intended to be concise:
  - if planning succeeds: guard checks and planned steps
  - if planning is blocked: a short note to use explain for details

Examples:
  ordo-playbook plan set-active-task
  ordo-playbook --profile backend --input issue_number=42 plan set-active-task
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
  ordo-playbook check set-active-task
  ordo-playbook --profile backend --input issue_number=42 check set-active-task
  ordo-playbook check close-task --json
"""

REVIEW_MODE_HELP = """usage: ordo-playbook [options] review WORKFLOW

Review authoring-quality findings for the selected workflow without making changes.

Default output is intended to be concise:
  - overall review status
  - finding count
  - top findings

Examples:
  ordo-playbook review set-active-task
  ordo-playbook --profile backend --input issue_number=42 review set-active-task
  ordo-playbook review close-task --json
"""

RUN_MODE_HELP = """usage: ordo-playbook [options] run WORKFLOW

Run the selected workflow and perform real changes.

Default output is intended to be concise:
  - overall run status
  - results or published outputs on success
  - failed guard or failed step details on failure

Examples:
  ordo-playbook run set-active-task
  ordo-playbook --progress-steps run set-active-task
  ordo-playbook --profile backend --input issue_number=42 run set-active-task --json
"""

GRAPH_MODE_HELP = """usage: ordo-playbook [options] graph

Show the inferred workflow topology for the current playbook context.

Default output is intended to be concise:
  - active state paths
  - structural state clusters
  - workflows grouped by shared topology

Examples:
  ordo-playbook graph
  ordo-playbook graph --json
  ordo-playbook --profile backend graph
"""

NEXT_MODE_HELP = """usage: ordo-playbook [options] next

Suggest which workflow should run next from the current playbook context.

Priority is driven first by semantics, then by score:
  - prefer workflows tied to the active state-backed work context
  - prefer workflows that only need operator input over workflows blocked by world-state mismatch
  - keep pure inspection below real continuation candidates when both are credible

Default output is intended to be concise:
  - best candidate workflow
  - whether any workflow is runnable now
  - nearby alternatives when they are materially competitive

Examples:
  ordo-playbook next
  ordo-playbook --profile backend next
  ordo-playbook --input issue_number=42 next --json
"""


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] in {"review", "check", "plan", "explain", "run", "next", "graph"} and sys.argv[2] in {"-h", "--help"}:
        if sys.argv[1] == "review":
            print(REVIEW_MODE_HELP)
        elif sys.argv[1] == "check":
            print(CHECK_MODE_HELP)
        elif sys.argv[1] == "plan":
            print(PLAN_MODE_HELP)
        elif sys.argv[1] == "run":
            print(RUN_MODE_HELP)
        elif sys.argv[1] == "next":
            print(NEXT_MODE_HELP)
        elif sys.argv[1] == "graph":
            print(GRAPH_MODE_HELP)
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
    if len(sys.argv) >= 3 and sys.argv[1] in {"-h", "--help"} and sys.argv[2] == "review":
        print(REVIEW_MODE_HELP)
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] in {"-h", "--help"} and sys.argv[2] == "run":
        print(RUN_MODE_HELP)
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] in {"-h", "--help"} and sys.argv[2] == "next":
        print(NEXT_MODE_HELP)
        return 0
    if len(sys.argv) >= 3 and sys.argv[1] in {"-h", "--help"} and sys.argv[2] == "graph":
        print(GRAPH_MODE_HELP)
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
            "deeper reference:\n"
            "  run `ordo-help` for the detailed Ordo reference model, capabilities, and examples\n\n"
            "discovery:\n"
            "  workflows  list workflow entries or show one workflow contract summary\n\n"
            "execution:\n"
            "  review   review authoring-quality findings without making changes\n"
            "  check    check whether the workflow can be run now, without making changes\n"
            "  plan     show what the workflow would do, without making changes\n"
            "  explain  explain why the workflow can or cannot be run right now\n"
            "  run      run the workflow and do the real work\n"
            "  next     suggest which workflow should run next\n"
            "  graph    show inferred workflow topology"
        ),
    )
    parser.add_argument("--file", dest="playbook_file", help="explicit playbook file path")
    parser.add_argument("--profile", help="active profile name for this run")
    parser.add_argument(
        "--input",
        dest="input_overrides",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override one workflow input for this run; repeatable; VALUE stays text except simple numbers and true/false",
    )
    parser.add_argument(
        "--input-file",
        dest="input_files",
        action="append",
        default=[],
        metavar="KEY=PATH",
        help="load one workflow input value from a file as a raw string; repeatable",
    )
    parser.add_argument(
        "--progress-steps",
        action="store_true",
        help="during run, emit each step name to stderr right before execution",
    )
    parser.add_argument("--json", action="store_true", help="emit full JSON payload including diagnostics")
    parser.add_argument("command", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()
    command = list(args.command)
    if not command:
        parser.error("missing command")
    if command[0] == "workflows":
        return _run_workflow_discovery_args(args, command[1:], parser=parser)
    if command[0] not in {"review", "check", "plan", "explain", "run", "next", "graph"}:
        parser.error(f"unknown command: {command[0]}")
    args.mode = command[0]
    if args.progress_steps and args.mode != "run":
        parser.error("--progress-steps is only supported with run")
    input_overrides = _parse_input_overrides(args.input_overrides, parser=parser)
    input_overrides.update(_parse_input_file_overrides(args.input_files, parser=parser))

    if args.mode in {"next", "graph"}:
        _reject_global_command_workflow_argument(args, parser=parser)
    else:
        args.workflow = _resolve_execution_workflow_name(args, parser=parser)

    had_previous_provider = True
    try:
        previous_provider = get_default_connector_provider()
    except RuntimeError:
        had_previous_provider = False
        previous_provider = None

    configure_standard_runtime()
    try:
        if args.mode == "next":
            return _run_next_mode(args, input_overrides=input_overrides)
        if args.mode == "graph":
            return _run_graph_mode(args, input_overrides=input_overrides)
        try:
            activated = activate_playbook(
                workflow_name=args.workflow,
                profile_name=args.profile,
                input_overrides=input_overrides,
                playbook_path=args.playbook_file,
            )
        except PlaybookError as exc:
            return _emit_error(exc, as_json=args.json, requested_mode=args.mode, requested_workflow=args.workflow)

        with activated_working_directory(activated):
            result = _run_mode(
                args.mode,
                activated.workflow,
                activated.profile,
                getattr(activated, "available_profiles", None),
                getattr(activated, "profile_working_directories", None),
                progress_steps=args.progress_steps,
            )
        payload = _public_runtime_payload(args.mode, result)
        activation_diagnostics = getattr(activated, "diagnostics", ())
        if activation_diagnostics and args.mode != "run":
            payload["diagnostics"] = [
                *payload.get("diagnostics", []),
                *[diagnostic.to_contract() for diagnostic in activation_diagnostics],
            ]
        if args.mode != "run":
            payload.update(
                {
                    "workflow": activated.workflow_name,
                    "playbook": str(activated.playbook_path),
                    "profile": None if activated.profile is None else activated.profile.name,
                }
            )
        payload.update(
            _runtime_context_fields(
                payload,
                fallback_profile=None if activated.profile is None else activated.profile.name,
                fallback_working_directory=None if activated.working_directory is None else str(activated.working_directory),
            )
        )

        if args.mode == "explain" and not args.json:
            payload = _summarize_explain_payload(payload)
        if args.mode == "plan" and not args.json:
            payload = _summarize_plan_payload(payload)
        if args.mode == "check" and not args.json:
            payload = _summarize_check_payload(payload)
        if args.mode == "review" and not args.json:
            payload = _summarize_review_payload(payload)
        if args.mode == "run" and not args.json:
            payload = _summarize_run_payload(payload)

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


def _run_mode(mode: str, workflow, profile, available_profiles=None, profile_working_directories=None, *, progress_steps: bool = False) -> RuntimeResult:
    if mode == "review":
        return review_workflow(
            workflow,
            profile=profile,
            available_profiles=available_profiles,
            profile_working_directories=profile_working_directories,
        )
    if mode == "check":
        return check_workflow(
            workflow,
            profile=profile,
            available_profiles=available_profiles,
            profile_working_directories=profile_working_directories,
        )
    if mode == "plan":
        return plan_workflow(
            workflow,
            profile=profile,
            available_profiles=available_profiles,
            profile_working_directories=profile_working_directories,
        )
    if mode == "run":
        return execute_workflow(
            workflow,
            profile=profile,
            available_profiles=available_profiles,
            profile_working_directories=profile_working_directories,
            step_reporter=_stderr_step_progress_reporter() if progress_steps else None,
        )
    explained = explain_workflow(
        workflow,
        profile=profile,
        available_profiles=available_profiles,
        profile_working_directories=profile_working_directories,
    )
    return explained


def _run_next_mode(args, *, input_overrides: dict[str, object]) -> int:
    payload = _build_next_payload(args, input_overrides=input_overrides, include_graph=False)
    if isinstance(payload, int):
        return payload
    if args.json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(_render_next_text(payload))
    return 0


def _run_graph_mode(args, *, input_overrides: dict[str, object]) -> int:
    payload = _build_next_payload(args, input_overrides=input_overrides, include_graph=True)
    if isinstance(payload, int):
        return payload
    payload = dict(payload)
    payload["mode"] = "graph"
    if args.json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(_render_graph_text(payload))
    return 0


def _build_next_payload(args, *, input_overrides: dict[str, object], include_graph: bool) -> dict[str, object] | int:
    try:
        listed_entries = list_playbook_workflows(playbook_path=args.playbook_file)
    except PlaybookError as exc:
        return _emit_error(exc, as_json=args.json, requested_mode=args.mode, requested_workflow=None)

    entries = []
    for listed_entry in listed_entries:
        try:
            entries.append(inspect_playbook_workflow(listed_entry.workflow_name, playbook_path=args.playbook_file))
        except PlaybookError:
            entries.append(listed_entry)

    candidates = []
    playbook_path = str(entries[0].playbook_path) if entries else str(args.playbook_file) if args.playbook_file else None
    for index, entry in enumerate(entries):
        candidate_input_overrides = _filter_global_next_input_overrides(entry, input_overrides=input_overrides)
        try:
            activated = activate_playbook(
                workflow_name=entry.workflow_name,
                profile_name=args.profile,
                input_overrides=candidate_input_overrides,
                playbook_path=args.playbook_file,
            )
        except PlaybookError as exc:
            relaxed = _build_relaxed_next_candidate(
                entry,
                order_index=index,
                args=args,
                candidate_input_overrides=candidate_input_overrides,
                activation_error=exc,
            )
            if relaxed is not None:
                candidates.append(relaxed)
                continue
            candidates.append(
                build_next_candidate(
                    workflow=entry.workflow_name,
                    order_index=index,
                    description=entry.workflow_description,
                    workflow_category=entry.workflow_category,
                    when=entry.workflow_when,
                    working_directory=entry.working_directory,
                    diagnostics=exc.diagnostics,
                    workflow_contract=getattr(entry, "workflow_contract", None),
                    caller_inputs=getattr(entry, "caller_inputs", ()),
                    optional_caller_inputs=getattr(entry, "optional_caller_inputs", ()),
                )
            )
            continue
        with activated_working_directory(activated):
            result = explain_workflow(
                activated.workflow,
                profile=activated.profile,
                available_profiles=getattr(activated, "available_profiles", None),
                profile_working_directories=getattr(activated, "profile_working_directories", None),
            )
        diagnostics = tuple(result.diagnostics) + tuple(getattr(activated, "diagnostics", ()))
        if diagnostics != result.diagnostics:
            result = RuntimeResult(
                mode=result.mode,
                status=result.status,
                diagnostics=diagnostics,
                plan=result.plan,
                outputs=result.outputs,
                results=result.results,
                published=result.published,
                operation_results=result.operation_results,
                failed_guard=result.failed_guard,
                failed_step=result.failed_step,
                preflight_decision=result.preflight_decision,
                analysis_tree=result.analysis_tree,
            )
        candidates.append(
            build_next_candidate(
                workflow=entry.workflow_name,
                order_index=index,
                description=entry.workflow_description,
                workflow_category=entry.workflow_category,
                when=entry.workflow_when,
                working_directory=None if activated.working_directory is None else str(activated.working_directory),
                runtime_result=result,
                workflow_contract=getattr(entry, "workflow_contract", None),
                runtime_workflow=activated.workflow,
                caller_inputs=getattr(entry, "caller_inputs", ()),
                optional_caller_inputs=getattr(entry, "optional_caller_inputs", ()),
            )
        )

    payload = rank_next_candidates(
        candidates,
        requested_profile=args.profile,
        input_override_keys=sorted(input_overrides),
        playbook_path=playbook_path or "",
        include_graph=include_graph,
    )
    return payload


def _build_relaxed_next_candidate(entry, *, order_index: int, args, candidate_input_overrides: dict[str, object], activation_error: PlaybookError):
    missing_inputs = _missing_input_names_from_diagnostics(tuple(getattr(activation_error, "diagnostics", ())))
    workflow_contract = getattr(entry, "workflow_contract", None)
    if not missing_inputs or classify_missing_input_kind_for_workflow(workflow_contract, missing_inputs) != "execution_only":
        return None
    placeholder_overrides = dict(candidate_input_overrides)
    for name in missing_inputs:
        placeholder_overrides.setdefault(name, _next_placeholder_value(name))
    try:
        activated = activate_playbook(
            workflow_name=entry.workflow_name,
            profile_name=args.profile,
            input_overrides=placeholder_overrides,
            playbook_path=args.playbook_file,
        )
    except PlaybookError:
        return None
    with activated_working_directory(activated):
        result = explain_workflow(
            activated.workflow,
            profile=activated.profile,
            available_profiles=getattr(activated, "available_profiles", None),
            profile_working_directories=getattr(activated, "profile_working_directories", None),
        )
    diagnostics = tuple(result.diagnostics) + tuple(getattr(activated, "diagnostics", ())) + tuple(getattr(activation_error, "diagnostics", ()))
    if diagnostics != result.diagnostics:
        result = RuntimeResult(
            mode=result.mode,
            status=result.status,
            diagnostics=diagnostics,
            plan=result.plan,
            outputs=result.outputs,
            results=result.results,
            published=result.published,
            operation_results=result.operation_results,
            failed_guard=result.failed_guard,
            failed_step=result.failed_step,
            preflight_decision=result.preflight_decision,
            analysis_tree=result.analysis_tree,
        )
    return build_next_candidate(
        workflow=entry.workflow_name,
        order_index=order_index,
        description=entry.workflow_description,
        workflow_category=entry.workflow_category,
        when=entry.workflow_when,
        working_directory=None if activated.working_directory is None else str(activated.working_directory),
        runtime_result=result,
        workflow_contract=workflow_contract,
        runtime_workflow=activated.workflow,
        caller_inputs=getattr(entry, "caller_inputs", ()),
        optional_caller_inputs=getattr(entry, "optional_caller_inputs", ()),
    )


def _stderr_step_progress_reporter():
    def report(event) -> None:
        sys.stderr.write(f"Running step: {event.step_name}\n")
        sys.stderr.flush()

    return report


def _summarize_review_payload(payload: dict[str, object]) -> dict[str, object]:
    findings = [item for item in payload.get("outputs", {}).get("findings", []) if isinstance(item, dict)]
    top_findings = [_summarize_review_finding(item) for item in findings[:5]]
    return {
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "workflow": payload.get("workflow"),
        "profile": payload.get("profile"),
        "active_profile": payload.get("active_profile"),
        "working_directory": payload.get("working_directory"),
        "review_status": payload.get("outputs", {}).get("review_status"),
        "finding_count": payload.get("outputs", {}).get("finding_count"),
        "top_findings": top_findings,
        "diagnostics": payload.get("diagnostics", []),
    }


def _summarize_review_finding(item: dict[str, object]) -> dict[str, object]:
    summary = {
        "code": item.get("code"),
        "category": item.get("category"),
        "message": item.get("message"),
    }
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        return summary
    if isinstance(evidence.get("suggested_fix"), str):
        summary["suggested_fix"] = evidence.get("suggested_fix")
    if isinstance(evidence.get("suggested_expression"), str):
        summary["suggested_expression"] = evidence.get("suggested_expression")
    if evidence.get("suggested_rewrite") is not None:
        summary["suggested_rewrite"] = evidence.get("suggested_rewrite")
    return summary


def _summarize_run_payload(payload: dict[str, object]) -> dict[str, object]:
    summary = {
        "status": payload.get("status"),
        "active_profile": payload.get("active_profile"),
        "working_directory": payload.get("working_directory"),
    }
    if payload.get("mode") is not None:
        summary["mode"] = payload.get("mode")
    if payload.get("workflow") is not None:
        summary["workflow"] = payload.get("workflow")
    if payload.get("profile") is not None:
        summary["profile"] = payload.get("profile")
    if payload.get("status") == "ok":
        if payload.get("results") is not None:
            summary["results"] = payload.get("results")
        if payload.get("published") is not None:
            summary["published"] = payload.get("published")
        return summary
    if payload.get("failed_guard") is not None:
        summary["failed_guard"] = payload.get("failed_guard")
    guard_detail = payload.get("guard_detail")
    if isinstance(guard_detail, dict):
        summary["guard_detail"] = guard_detail
    if payload.get("failed_step") is not None:
        summary["failed_step"] = payload.get("failed_step")
    if isinstance(payload.get("step_detail"), dict):
        summary["step_detail"] = payload.get("step_detail")
    if isinstance(payload.get("message"), str):
        summary["message"] = payload.get("message")
    diagnostics = [item for item in payload.get("diagnostics", []) if isinstance(item, dict)]
    if diagnostics and "message" not in summary:
        message = _build_run_summary_message_from_diagnostic(diagnostics[0], failed_step=payload.get("failed_step"))
        if message is not None:
            summary["message"] = message
    if diagnostics:
        details = diagnostics[0].get("details")
        if isinstance(details, dict):
            if isinstance(details.get("fan_out_item"), (str, int, float, bool)):
                summary["item"] = details.get("fan_out_item")
            if isinstance(details.get("on_fail_context"), dict):
                summary["on_fail_context"] = details.get("on_fail_context")
    if isinstance(payload.get("failed_guard"), str):
        failed_subcondition = None
        if isinstance(guard_detail, dict):
            value = guard_detail.get("failed_subcondition")
            failed_subcondition = value if isinstance(value, str) else None
        if "message" not in summary or isinstance(guard_detail, dict):
            summary["message"] = render_guard_failure_message(
                guard_reference=payload["failed_guard"],
                failed_subcondition=failed_subcondition,
            )
    if isinstance(payload.get("failure"), dict):
        summary["failure"] = payload.get("failure")
    return summary


def _public_runtime_payload(command_mode: str, result: RuntimeResult) -> dict[str, object]:
    if command_mode == "run":
        if result.status is RuntimeStatus.OK:
            results = list(result.results)
            published = list(result.published)
            if not results and not published:
                results = [_top_level_missing_output_result()]
            payload = {
                "status": "ok",
            }
            if results:
                payload["results"] = results
            if published:
                payload["published"] = published
            payload.update(
                _runtime_context_fields(
                    {"outputs": result.outputs},
                    fallback_profile=None,
                    fallback_working_directory=None,
                )
            )
            return payload
        payload = {
            "status": result.status.value,
            "failed_guard": result.failed_guard,
            "failed_step": result.failed_step,
            "diagnostics": [diagnostic.to_contract() for diagnostic in result.diagnostics],
            **({"guard_detail": guard_detail} if (guard_detail := _failed_guard_detail_from_guard_details(result.outputs.get("guard_details"), result.failed_guard)) is not None else {}),
            **({"step_detail": step_detail} if (step_detail := _failed_step_detail_from_operation_results(result.operation_results, result.failed_step)) is not None else {}),
            **({"failure": failure} if (failure := _build_run_failure_payload(result)) is not None else {}),
        }
        payload.update(
            _runtime_context_fields(
                {"outputs": result.outputs},
                fallback_profile=None,
                fallback_working_directory=None,
            )
        )
        if message := _build_run_failure_message(result):
            payload["message"] = message
        return payload
    return result.to_contract()


def _build_run_failure_message(result: RuntimeResult) -> str | None:
    if isinstance(result.failed_guard, str):
        return render_guard_failure_message(
            guard_reference=result.failed_guard,
            failed_subcondition=_failed_subcondition_from_guard_details(result.outputs.get("guard_details"), result.failed_guard),
        )
    if result.diagnostics:
        return _build_run_summary_message_from_diagnostic(result.diagnostics[0].to_contract(), failed_step=result.failed_step)
    return None


def _build_run_summary_message_from_diagnostic(diagnostic: dict[str, object], *, failed_step: object) -> str | None:
    details = diagnostic.get("details")
    code = diagnostic.get("code")
    if code in {"runtime.step.gate.failed", "runtime.step.gate.unknown"} and isinstance(details, dict):
        step_name = details.get("step") if isinstance(details.get("step"), str) else failed_step if isinstance(failed_step, str) else None
        if step_name is not None:
            verdict = details.get("verdict") if isinstance(details.get("verdict"), str) else ("unknown" if code == "runtime.step.gate.unknown" else "failed")
            return render_gate_failure_message(
                step_name=step_name,
                verdict=verdict,
                failed_conditions=[value for value in details.get("failed_conditions", []) if isinstance(value, str)],
                unknown_conditions=[value for value in details.get("unknown_conditions", []) if isinstance(value, str)],
                item=details.get("fan_out_item"),
            )
    message = diagnostic.get("message")
    return message if isinstance(message, str) else None


def _failed_subcondition_from_guard_details(guard_details: object, failed_guard: str) -> str | None:
    detail = _failed_guard_detail_from_guard_details(guard_details, failed_guard)
    if not isinstance(detail, dict):
        return None
    failed_subcondition = detail.get("failed_subcondition")
    return failed_subcondition if isinstance(failed_subcondition, str) else None


def _failed_guard_detail_from_guard_details(guard_details: object, failed_guard: object) -> dict[str, object] | None:
    if not isinstance(guard_details, list):
        return None
    for item in guard_details:
        if not isinstance(item, dict) or item.get("reference") != failed_guard:
            continue
        return item
    return None


def _failed_step_detail_from_operation_results(operation_results: object, failed_step: object) -> dict[str, object] | None:
    if not isinstance(operation_results, tuple | list) or not isinstance(failed_step, str):
        return None
    for item in reversed(operation_results):
        if not hasattr(item, "raw"):
            continue
        raw = getattr(item, "raw")
        if not isinstance(raw, dict):
            continue
        detail = raw.get("step_detail")
        if not isinstance(detail, dict):
            continue
        if detail.get("step") != failed_step:
            continue
        return detail
    return None


def _build_run_failure_payload(result: RuntimeResult) -> dict[str, object] | None:
    if not result.operation_results:
        return _build_external_run_failure_payload_from_diagnostics(result)
    failed_result = result.operation_results[-1]
    outputs = failed_result.outputs
    raw = failed_result.raw
    routine_id = outputs.get("routine_id")
    if not isinstance(routine_id, str) or not routine_id:
        return None
    stdout_log_path = outputs.get("stdout_log_path") or outputs.get("log_path") or raw.get("stdout_path")
    stderr_log_path = outputs.get("stderr_log_path") or raw.get("stderr_path")
    payload: dict[str, object] = {
        "kind": "routine_failed" if failed_result.status == "routine_failed" else "routine_start_failed",
        "routine_id": routine_id,
        "summary": failed_result.summary,
        "stdout_log_path": stdout_log_path,
        "stderr_log_path": stderr_log_path,
        "stdout_tail": outputs.get("stdout_tail", ""),
        "stderr_tail": outputs.get("stderr_tail", ""),
    }
    exit_code = outputs.get("exit_code")
    if isinstance(exit_code, int):
        payload["exit_code"] = exit_code
    if failed_result.status == "execution_error" and failed_result.summary:
        payload["message"] = failed_result.summary
    return payload


def _build_external_run_failure_payload_from_diagnostics(result: RuntimeResult) -> dict[str, object] | None:
    for diagnostic in result.diagnostics:
        details = diagnostic.details
        if not isinstance(details, dict) or not details.get("is_external"):
            continue
        payload: dict[str, object] = {
            "kind": "external_failure",
            "message": diagnostic.message,
            "diagnostic_code": diagnostic.code,
        }
        for source_key, target_key in (
            ("classification", "classification"),
            ("external_tool", "tool"),
            ("external_system", "system"),
            ("argv_summary", "argv_summary"),
            ("stderr_excerpt", "stderr_excerpt"),
            ("stdout_excerpt", "stdout_excerpt"),
            ("returncode", "returncode"),
            ("suggested_checks", "suggested_checks"),
            ("reference", "reference"),
            ("target", "target"),
        ):
            value = details.get(source_key)
            if value is not None:
                payload[target_key] = value
        context = describe_external_failure_context(details)
        if context is not None:
            payload["summary"] = context
        return payload
    return None


def _top_level_missing_output_result() -> dict[str, object]:
    return {
        "summary": "Workflow completed with no explicit result or published output.",
    }


def _resolve_execution_workflow_name(args, *, parser: argparse.ArgumentParser) -> str:
    command = list(args.command)
    if len(command) > 2:
        parser.error(f"{command[0]} accepts exactly one workflow name")
    if len(command) != 2:
        parser.error(f"{command[0]} requires a workflow name")
    return command[1]


def _reject_global_command_workflow_argument(args, *, parser: argparse.ArgumentParser) -> None:
    command = list(args.command)
    if len(command) != 1:
        parser.error(f"{command[0]} does not accept a workflow name; use check/plan/explain/run for a specific workflow")


def _filter_global_next_input_overrides(entry, *, input_overrides: dict[str, object]) -> dict[str, object]:
    if not input_overrides:
        return {}
    declared_inputs = {item.name for item in getattr(entry, "inputs", ()) if hasattr(item, "name") and isinstance(item.name, str)}
    if not declared_inputs:
        return {}
    return {key: value for key, value in input_overrides.items() if key in declared_inputs}


def _missing_input_names_from_diagnostics(diagnostics) -> tuple[str, ...]:
    names: list[str] = []
    for diagnostic in diagnostics:
        if getattr(diagnostic, "code", None) != "playbook.workflow.input_missing":
            continue
        details = getattr(diagnostic, "details", {})
        value = details.get("input") if isinstance(details, dict) else None
        if isinstance(value, str) and value not in names:
            names.append(value)
    return tuple(names)


def _next_placeholder_value(name: str) -> str:
    return f"__ordo_next_placeholder__{name}"


def _compact_mapping(**items: object) -> dict[str, object]:
    return {key: value for key, value in items.items() if value is not None}


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
            categories: list[dict[str, object]] = []
            categories_by_name: dict[str, dict[str, object]] = {}
            for entry in entries:
                category_name = entry.workflow_category if isinstance(entry.workflow_category, str) and entry.workflow_category else "Non-category"
                bucket = categories_by_name.get(category_name)
                if bucket is None:
                    bucket = {"category": category_name, "workflows": []}
                    categories_by_name[category_name] = bucket
                    categories.append(bucket)
                bucket["workflows"].append(
                    _compact_mapping(
                        workflow=entry.workflow_name,
                        description=entry.workflow_description,
                        when=entry.workflow_when,
                    )
                )
            payload = {
                "mode": "workflows.list",
                "status": "ok",
                "playbook": str(entries[0].playbook_path) if entries else str(args.playbook_file) if args.playbook_file else None,
                "categories": categories,
            }
        else:
            entry = inspect_playbook_workflow(argv[1], playbook_path=args.playbook_file)
            payload = _compact_mapping(
                mode="workflows.show",
                status="ok",
                playbook=str(entry.playbook_path),
                workflow=entry.workflow_name,
                description=entry.workflow_description,
                category=entry.workflow_category,
                when=entry.workflow_when,
                file=str(entry.workflow_path),
                working_directory=entry.working_directory,
                inputs=_workflow_entry_inputs_shape(entry),
                caller_inputs=list(entry.caller_inputs),
                optional_caller_inputs=list(entry.optional_caller_inputs) if entry.optional_caller_inputs else None,
            )
            if args.json:
                payload["declared_inputs"] = [
                    _compact_mapping(
                        name=item.name,
                        description=item.description,
                        hint=item.hint,
                    )
                    for item in entry.inputs
                ]
    except PlaybookError as exc:
        return _emit_error(exc, as_json=args.json)

    if args.json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _workflow_entry_inputs_shape(entry) -> dict[str, object]:
    inputs = dict(entry.with_)
    for name in entry.caller_inputs:
        inputs[name] = None
    for name in entry.optional_caller_inputs:
        inputs[name] = None
    return inputs


def _parse_input_overrides(raw_items: list[str], *, parser: argparse.ArgumentParser) -> dict[str, object]:
    overrides: dict[str, object] = {}
    for item in raw_items:
        if "=" not in item:
            parser.error(f"--input expects KEY=VALUE, got: {item}")
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            parser.error("--input key must not be empty")
        overrides[key] = _coerce_inline_input_value(raw_value)
    return overrides


def _coerce_inline_input_value(raw_value: str) -> object:
    lowered = raw_value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?(0|[1-9]\d*)", raw_value):
        return int(raw_value)
    if re.fullmatch(r"-?(?:0|[1-9]\d*)\.\d+", raw_value):
        return float(raw_value)
    return raw_value


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


def _emit_error(exc: PlaybookError, *, as_json: bool, requested_mode: str | None = None, requested_workflow: str | None = None) -> int:
    payload = {
        "mode": "activation",
        "status": "resolution_error",
        "diagnostics": [diagnostic.to_contract() for diagnostic in exc.diagnostics],
    }
    payload.update(_activation_error_guidance(exc.diagnostics, requested_mode=requested_mode, requested_workflow=requested_workflow))
    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(json.dumps(_summarize_activation_error_payload(payload), indent=2, sort_keys=True), file=sys.stderr)
    return 1


def _summarize_activation_error_payload(payload: dict[str, object]) -> dict[str, object]:
    diagnostics = [item for item in payload.get("diagnostics", []) if isinstance(item, dict)]
    summary: dict[str, object] = {
        "mode": payload.get("mode"),
        "status": payload.get("status"),
    }
    if payload.get("workflow") is not None:
        summary["workflow"] = payload.get("workflow")

    missing_inputs = [item for item in payload.get("missing_inputs", []) if isinstance(item, str)]
    if missing_inputs:
        summary["missing_inputs"] = missing_inputs

    unknown_inputs = _collect_activation_input_names(diagnostics, code="playbook.workflow.input_unknown")
    if unknown_inputs:
        summary["unknown_inputs"] = unknown_inputs

    message = payload.get("message")
    if not isinstance(message, str) or not message:
        first_diagnostic = diagnostics[0] if diagnostics else None
        if isinstance(first_diagnostic, dict):
            diagnostic_message = first_diagnostic.get("message")
            if isinstance(diagnostic_message, str) and diagnostic_message:
                message = diagnostic_message
    if isinstance(message, str) and message:
        summary["message"] = message

    example = payload.get("example")
    if isinstance(example, str) and example:
        summary["example"] = example
    return summary


def _collect_activation_input_names(diagnostics: list[dict[str, object]], *, code: str) -> list[str]:
    names: list[str] = []
    for item in diagnostics:
        if item.get("code") != code:
            continue
        details = item.get("details")
        if not isinstance(details, dict):
            continue
        value = details.get("input")
        if isinstance(value, str) and value not in names:
            names.append(value)
    return names


def _summarize_explain_payload(payload: dict[str, object]) -> dict[str, object]:
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        outputs = {}
    explanation = outputs.get("explanation")
    if not isinstance(explanation, dict):
        explanation = {}

    summary = {
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "workflow": payload.get("workflow"),
        "playbook": payload.get("playbook"),
        "profile": payload.get("profile"),
        "active_profile": payload.get("active_profile"),
        "working_directory": payload.get("working_directory"),
        "allowed": explanation.get("allowed", outputs.get("execution_allowed")),
        "category": explanation.get("category", outputs.get("reason_category")),
        "why": explanation.get("why"),
        "failed_guard": payload.get("failed_guard"),
        "blockers": explanation.get("blockers", outputs.get("blockers", [])),
        "diagnostics": payload.get("diagnostics", []),
    }

    nested_gate_blockers = explanation.get("nested_gate_blockers")
    if isinstance(nested_gate_blockers, list) and nested_gate_blockers:
        first = nested_gate_blockers[0]
        if isinstance(first, dict):
            item_value = first.get("expanded_item")
            if isinstance(item_value, str):
                summary["item"] = item_value
            gate_reports = first.get("gate_reports")
            if isinstance(gate_reports, list) and gate_reports and isinstance(gate_reports[0], dict):
                failed = gate_reports[0].get("failed_causes")
                if not isinstance(failed, list):
                    failed = gate_reports[0].get("failed")
                if isinstance(failed, list):
                    failed_conditions = [
                        item.get("rendered") or item.get("expression")
                        for item in failed
                        if isinstance(item, dict) and isinstance(item.get("rendered") or item.get("expression"), str)
                    ]
                    if failed_conditions:
                        summary["failed_conditions"] = failed_conditions
    return summary


def _summarize_next_payload(payload: dict[str, object]) -> dict[str, object]:
    summary = {
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "playbook": payload.get("playbook"),
        "profile": payload.get("profile"),
        "scope": payload.get("scope"),
        "ready_now_available": payload.get("ready_now_available"),
        "recommendation_strength": payload.get("recommendation_strength"),
        "current_context": payload.get("current_context"),
        "uncertainty": payload.get("uncertainty"),
    }
    best_candidate = payload.get("best_candidate")
    if isinstance(best_candidate, dict):
        summary["best_candidate"] = {
            "workflow": best_candidate.get("workflow"),
            "candidate_class": best_candidate.get("candidate_class"),
            "score": best_candidate.get("score"),
            "allowed": best_candidate.get("allowed"),
            "reason_category": best_candidate.get("reason_category"),
            "blockers": best_candidate.get("blockers", []),
            "missing_inputs": best_candidate.get("missing_inputs", []),
        }
    alternatives = payload.get("alternatives")
    if isinstance(alternatives, list) and alternatives:
        summary["alternatives"] = [
            {
                "workflow": item.get("workflow"),
                "candidate_class": item.get("candidate_class"),
                "score": item.get("score"),
            }
            for item in alternatives
            if isinstance(item, dict)
        ]
    return summary


def _render_next_text(payload: dict[str, object]) -> str:
    lines: list[str] = []
    current_context = payload.get("current_context")
    has_active_state = isinstance(current_context, dict) and bool(current_context.get("active_state_paths"))
    best_candidate = payload.get("best_candidate")
    if isinstance(best_candidate, dict):
        workflow = best_candidate.get("workflow")
        if isinstance(workflow, str) and workflow:
            prefix = "Next workflow" if has_active_state else "Generic candidate"
            lines.append(f"{prefix}: {_format_next_candidate_label(best_candidate)}")
        candidate_class = best_candidate.get("candidate_class")
        if isinstance(candidate_class, str) and candidate_class:
            status_text = candidate_class.replace("_", " ")
            lines.append(f"Status: {status_text}")
        reason_category = best_candidate.get("reason_category")
        if isinstance(reason_category, str) and reason_category and reason_category != "ok":
            lines.append(f"Reason: {reason_category.replace('_', ' ')}")
        blockers = [item for item in best_candidate.get("blockers", []) if isinstance(item, str)]
        if blockers:
            lines.append(f"Blockers: {', '.join(blockers[:3])}")
        missing_inputs = [item for item in best_candidate.get("missing_inputs", []) if isinstance(item, str)]
        if missing_inputs:
            lines.append(f"Needs: {', '.join(missing_inputs[:3])}")
    else:
        lines.append("Next workflow: unavailable")

    alternatives = payload.get("alternatives")
    if isinstance(alternatives, list):
        formatted = [
            _format_next_candidate_label(item)
            for item in alternatives
            if isinstance(item, dict) and isinstance(item.get("workflow"), str)
        ]
        if formatted:
            lines.append(f"Alternatives: {', '.join(formatted[:3])}")

    uncertainty = payload.get("uncertainty")
    if isinstance(uncertainty, dict):
        message = uncertainty.get("message")
        if isinstance(message, str) and message:
            lines.append(f"Note: {message}")
    if not has_active_state:
        lines.append("Context: no active state-backed workflow context detected")

    related_lines = _render_next_related_workflows(payload, has_active_state=has_active_state)
    if related_lines:
        lines.append("")
        lines.extend(related_lines)

    return "\n".join(lines)


def _render_next_related_workflows(payload: dict[str, object], *, has_active_state: bool) -> list[str]:
    candidates = [item for item in payload.get("candidates", []) if isinstance(item, dict)]
    if not candidates:
        return []
    best_candidate = payload.get("best_candidate")
    best_workflow = best_candidate.get("workflow") if isinstance(best_candidate, dict) and isinstance(best_candidate.get("workflow"), str) else None
    grouped: dict[str, list[dict[str, object]]] = {}
    category_order: list[str] = []
    for candidate in sorted(candidates, key=_next_related_candidate_order):
        if not _include_related_candidate(candidate, best_workflow=best_workflow, has_active_state=has_active_state):
            continue
        category = candidate.get("category") if isinstance(candidate.get("category"), str) and candidate.get("category") else "uncategorized"
        if category not in grouped:
            grouped[category] = []
            category_order.append(category)
        grouped[category].append(candidate)
    if not grouped:
        return []
    lines = ["Related workflows:" if has_active_state else "Generic workflows:"]
    for category in category_order:
        lines.append(f"  {category}:")
        for candidate in grouped[category]:
            workflow_name = candidate.get("workflow") if isinstance(candidate.get("workflow"), str) else None
            marker = "* " if workflow_name is not None and workflow_name == best_workflow else ""
            lines.append(f"  - {marker}{_format_next_candidate_label(candidate)}")
    return lines


def _include_related_candidate(candidate: dict[str, object], *, best_workflow: str | None, has_active_state: bool) -> bool:
    workflow_name = candidate.get("workflow") if isinstance(candidate.get("workflow"), str) else None
    if workflow_name is not None and workflow_name == best_workflow:
        return True
    if not has_active_state:
        return True
    state_cluster = candidate.get("state_cluster")
    if isinstance(state_cluster, list) and state_cluster:
        return True
    candidate_class = candidate.get("candidate_class")
    if candidate_class in {"ready_with_execution_input", "near_ready_contextual"}:
        return True
    return False


def _next_related_candidate_order(candidate: dict[str, object]) -> tuple[int, int, str]:
    order_index = candidate.get("order_index") if isinstance(candidate.get("order_index"), int) else 10**9
    workflow_name = candidate.get("workflow") if isinstance(candidate.get("workflow"), str) else ""
    return (order_index, 0, workflow_name)


def _render_graph_text(payload: dict[str, object]) -> str:
    lines: list[str] = []
    graph = payload.get("graph")
    if not isinstance(graph, dict):
        return "Graph: unavailable"
    active_state_paths = [item for item in graph.get("active_state_paths", []) if isinstance(item, str)]
    workflows = [item for item in graph.get("workflows", []) if isinstance(item, dict)]
    lines.append("Graph:")
    lines.append("  active state:")
    if active_state_paths:
        for path in active_state_paths:
            lines.append(f"  - {path}")
    else:
        lines.append("  - none")
    best_workflow_name = None
    best_candidate = payload.get("best_candidate")
    if isinstance(best_candidate, dict) and isinstance(best_candidate.get("workflow"), str):
        best_workflow_name = best_candidate.get("workflow")
    for cluster_name, cluster_workflows in _group_next_graph_workflows(workflows).items():
        lines.append(f"  {cluster_name}:")
        for workflow in cluster_workflows[:4]:
            workflow_name = workflow.get("workflow") if isinstance(workflow.get("workflow"), str) else None
            marker = "* " if workflow_name is not None and workflow_name == best_workflow_name else ""
            lines.append(f"  - {marker}{_format_next_candidate_graph_label(workflow)}")
    related_count = sum(1 for workflow in workflows if isinstance(workflow.get("state_cluster"), list) and workflow.get("state_cluster"))
    unrelated = [workflow for workflow in workflows if not (isinstance(workflow.get("state_cluster"), list) and workflow.get("state_cluster"))]
    if unrelated:
        lines.append("  outside active clusters:")
        for workflow in unrelated[:3]:
            workflow_name = workflow.get("workflow") if isinstance(workflow.get("workflow"), str) else None
            marker = "* " if workflow_name is not None and workflow_name == best_workflow_name else ""
            lines.append(f"  - {marker}{_format_next_candidate_graph_label(workflow)}")
    if related_count > 0 and len(workflows) > related_count + len(unrelated[:3]):
        lines.append("  note: full graph details remain available with --json")
    return "\n".join(lines)


def _group_next_graph_workflows(workflows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for workflow in workflows:
        cluster = [item for item in workflow.get("state_cluster", []) if isinstance(item, str)]
        if not cluster:
            continue
        key = _next_graph_cluster_label(cluster)
        groups.setdefault(key, []).append(workflow)
    for key, items in groups.items():
        groups[key] = sorted(items, key=_next_graph_workflow_order)
    return groups


def _next_graph_cluster_label(cluster: list[str]) -> str:
    ordered: list[str] = []
    for item in cluster:
        if item not in ordered:
            ordered.append(item)
    if not ordered:
        return "cluster"
    roots: list[str] = []
    for item in ordered:
        root = item.split(".", 1)[0]
        if root not in roots:
            roots.append(root)
    if len(roots) == 1:
        first = ordered[0]
        if "." not in first:
            return first
        root, field = first.split(".", 1)
        field_name = field.split(".", 1)[0]
        return f"{root}+{field_name}"
    return "+".join(roots[:2])


def _next_graph_workflow_order(workflow: dict[str, object]) -> tuple[int, int, int, str]:
    state_role = workflow.get("state_role")
    candidate_class = workflow.get("candidate_class")
    score = workflow.get("score")
    role_order = {
        "producer": 0,
        "transition": 1,
        "inspect": 2,
        "close": 3,
        "utility": 4,
    }
    class_order = {
        "ready_now": 0,
        "ready_with_execution_input": 1,
        "near_ready_contextual": 2,
        "near_ready": 3,
        "awaiting_context_input": 4,
        "awaiting_input": 5,
        "inspection_only": 6,
        "weak_match": 7,
        "not_evaluable_now": 8,
    }
    return (
        role_order.get(state_role, 99) if isinstance(state_role, str) else 99,
        class_order.get(candidate_class, 99) if isinstance(candidate_class, str) else 99,
        -(score if isinstance(score, int) else 0),
        workflow.get("workflow") if isinstance(workflow.get("workflow"), str) else "",
    )


def _format_next_candidate_graph_label(workflow: dict[str, object]) -> str:
    label = _format_next_candidate_label(workflow)
    parts: list[str] = []
    reads = _graph_reference_short_signatures(workflow, "reads")
    writes = _graph_reference_short_signatures(workflow, "writes")
    deletes = _graph_reference_short_signatures(workflow, "deletes")
    if reads:
        parts.append(f"reads {', '.join(reads[:2])}")
    if writes:
        parts.append(f"writes {', '.join(writes[:2])}")
    if deletes:
        parts.append(f"deletes {', '.join(deletes[:2])}")
    if not parts:
        return label
    return f"{label} [{'; '.join(parts[:3])}]"


def _graph_reference_signatures(workflow: dict[str, object], key: str) -> list[str]:
    refs = [item for item in workflow.get(key, []) if isinstance(item, dict)]
    rendered: list[str] = []
    for item in refs:
        signature = item.get("logical_signature")
        if isinstance(signature, str) and signature and signature not in rendered:
            rendered.append(signature)
    return rendered


def _graph_reference_short_signatures(workflow: dict[str, object], key: str) -> list[str]:
    rendered = []
    for signature in _graph_reference_signatures(workflow, key):
        short = signature.split(".", 1)[1] if "." in signature else signature
        if short not in rendered:
            rendered.append(short)
    return rendered


def _format_next_candidate_label(candidate: dict[str, object]) -> str:
    workflow = candidate.get("workflow")
    score = candidate.get("score")
    matched = candidate.get("matched_guard_count")
    blockers = candidate.get("blockers")
    blocker_count = len(blockers) if isinstance(blockers, list) else None
    missing_inputs = candidate.get("missing_inputs")
    details: list[str] = []
    if isinstance(score, int):
        details.append(str(score))
    if isinstance(matched, int) and isinstance(blocker_count, int):
        details.append(f"+{matched}/-{blocker_count}")
    reason_stub = _next_candidate_reason_stub(candidate)
    if reason_stub is not None:
        details.append(reason_stub)
    if isinstance(missing_inputs, list) and missing_inputs:
        details.append(f"needs {','.join(item for item in missing_inputs[:2] if isinstance(item, str))}")
    if isinstance(workflow, str) and details:
        return f"{workflow} ({', '.join(details)})"
    if isinstance(workflow, str):
        return workflow
    return "unknown"


def _next_candidate_reason_stub(candidate: dict[str, object]) -> str | None:
    candidate_class = candidate.get("candidate_class")
    state_cluster = candidate.get("state_cluster")
    world_blocker_count = candidate.get("world_blocker_count")
    missing_input_kind = candidate.get("missing_input_kind")
    state_role = candidate.get("state_role")

    tags: list[str] = []
    if isinstance(state_cluster, list) and state_cluster:
        tags.append("state")
    elif state_role == "utility":
        tags.append("unrelated")

    if candidate_class == "inspection_only":
        tags.append("inspect-only")
    elif missing_input_kind == "execution_only" or candidate_class == "ready_with_execution_input":
        tags.append("input-only")
    elif isinstance(world_blocker_count, int) and world_blocker_count > 0:
        tags.append("world-blocked")
    elif candidate_class == "ready_now":
        tags.append("ready")

    if not tags:
        return None
    return ", ".join(tags[:2])


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
        "active_profile": payload.get("active_profile"),
        "working_directory": payload.get("working_directory"),
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
        "active_profile": payload.get("active_profile"),
        "working_directory": payload.get("working_directory"),
        "active_profile_source": outputs.get("active_profile_source"),
        "allowed": allowed,
        "allowed_state": outputs.get("allowed_state"),
        "analysis_complete": outputs.get("analysis_complete"),
        "incomplete_reasons": outputs.get("incomplete_reasons", []),
        "unevaluated_relevant_guards": outputs.get("unevaluated_relevant_guards", []),
        "diagnostics": payload.get("diagnostics", []),
        "observed_facts": _collect_observed_facts(outputs),
        "missing_facts": _collect_missing_facts(outputs),
    }

    gate_blockers = [name for name in outputs.get("gate_blockers", []) if isinstance(name, str)]
    if gate_blockers:
        summary["blockers"] = gate_blockers
        gate_summary = _extract_check_gate_failure_summary(outputs)
        if gate_summary:
            summary.update(gate_summary)
        else:
            summary["message"] = "check blocked by step gate; use explain or --json check for full gate details"

    if payload.get("failed_guard") is not None:
        summary["failed_guard"] = payload.get("failed_guard")
        if "message" not in summary and isinstance(payload.get("failed_guard"), str):
            summary["message"] = render_guard_failure_message(
                guard_reference=payload["failed_guard"],
                failed_subcondition=_failed_subcondition_from_guard_details(outputs.get("guard_details"), payload["failed_guard"]),
            )

    preflight_halts = [item for item in outputs.get("preflight_halts", []) if isinstance(item, dict)]
    if preflight_halts and "message" not in summary:
        first = preflight_halts[0]
        step_name = first.get("step_name") if isinstance(first.get("step_name"), str) else None
        reason = first.get("reason") if isinstance(first.get("reason"), str) else None
        if reason == "read_only_step_failed":
            summary["blockers"] = [] if step_name is None else [step_name]
            summary["message"] = "check blocked by failing read-only observation; use explain or --json check for details"
        elif reason == "gate_unknown":
            summary["blockers"] = [] if step_name is None else [step_name]
            summary["message"] = "check blocked because a step gate could not yet be established from current read-only knowledge"

    frontier_ready_step = outputs.get("frontier_ready_step")
    if isinstance(frontier_ready_step, str):
        summary["message"] = f"workflow can run now for the current observed inputs and state; read-only preflight reached '{frontier_ready_step}'"

    if outputs.get("verdict_basis_stale"):
        summary["message"] = "check incomplete; use --json check or explain for details"

    return summary


def _extract_check_gate_failure_summary(outputs: dict[str, object]) -> dict[str, object]:
    nested_gate_blockers = outputs.get("nested_gate_blockers")
    if isinstance(nested_gate_blockers, list):
        for item in nested_gate_blockers:
            if not isinstance(item, dict):
                continue
            gate_names = [name for name in item.get("gate_blockers", []) if isinstance(name, str)]
            gate_reports = item.get("gate_reports")
            if not gate_names or not isinstance(gate_reports, list) or not gate_reports or not isinstance(gate_reports[0], dict):
                continue
            return _build_gate_failure_summary(
                step_name=gate_names[0],
                gate_report=gate_reports[0],
                item=item.get("expanded_item"),
            )

    preflight_step_items = outputs.get("preflight_step_items")
    if isinstance(preflight_step_items, list):
        for item in preflight_step_items:
            if not isinstance(item, dict) or item.get("status") != "gate_blocked":
                continue
            step_name = item.get("name")
            gate_report = item.get("gate_report")
            if not isinstance(step_name, str) or not isinstance(gate_report, dict):
                continue
            return _build_gate_failure_summary(step_name=step_name, gate_report=gate_report, item=None)

    return {}


def _activation_error_guidance(
    diagnostics: tuple[object, ...],
    *,
    requested_mode: str | None = None,
    requested_workflow: str | None = None,
) -> dict[str, object]:
    structured = [item.to_contract() for item in diagnostics if hasattr(item, "to_contract")]
    if not structured:
        return {}
    missing = [item for item in structured if item.get("code") == "playbook.workflow.input_missing" and isinstance(item.get("details"), dict)]
    if not missing:
        return {}
    first_details = missing[0]["details"]
    workflow = requested_workflow if isinstance(requested_workflow, str) else first_details.get("workflow") if isinstance(first_details.get("workflow"), str) else None
    declared_inputs = [value for value in first_details.get("declared_inputs", []) if isinstance(value, str)]
    relevant_inputs = [value for value in first_details.get("relevant_inputs", []) if isinstance(value, str)]
    missing_inputs: list[str] = []
    for item in missing:
        details = item["details"]
        for value in details.get("missing_inputs", []):
            if isinstance(value, str) and value not in missing_inputs:
                missing_inputs.append(value)
    if not missing_inputs:
        for item in missing:
            details = item["details"]
            value = details.get("input")
            if isinstance(value, str) and value not in missing_inputs:
                missing_inputs.append(value)
    payload: dict[str, object] = {}
    if workflow is not None:
        payload["workflow"] = workflow
    if declared_inputs:
        payload["declared_inputs"] = declared_inputs
    if relevant_inputs:
        payload["relevant_inputs"] = relevant_inputs
    if missing_inputs:
        payload["missing_inputs"] = missing_inputs
        payload["message"] = f"Missing required workflow inputs at activation time: {', '.join(missing_inputs)}"
    input_transport = first_details.get("input_transport")
    if isinstance(input_transport, str):
        payload["input_transport"] = input_transport
    input_file_transport = first_details.get("input_file_transport")
    if isinstance(input_file_transport, str):
        payload["input_file_transport"] = input_file_transport
    example = _activation_example_command(workflow=workflow, missing_inputs=missing_inputs, requested_mode=requested_mode)
    if example is None:
        example = first_details.get("example")
    if isinstance(example, str):
        payload["example"] = example
    return payload


def _activation_example_command(*, workflow: str | None, missing_inputs: list[str], requested_mode: str | None) -> str | None:
    if workflow is None or not missing_inputs:
        return None
    mode = requested_mode if requested_mode in {"run", "check", "plan", "explain", "review", "next"} else "run"
    input_args = " ".join(f"--input {key}=<value>" for key in missing_inputs)
    return f"ordo-playbook {input_args} {mode} {workflow}"


def _runtime_context_fields(payload: dict[str, object], *, fallback_profile: str | None, fallback_working_directory: str | None) -> dict[str, object]:
    outputs = payload.get("outputs")
    if not isinstance(outputs, dict):
        outputs = {}
    active_profile = outputs.get("active_profile") if isinstance(outputs.get("active_profile"), str) else fallback_profile
    working_directory = outputs.get("current_working_directory") if isinstance(outputs.get("current_working_directory"), str) else fallback_working_directory
    context: dict[str, object] = {}
    if active_profile is not None:
        context["active_profile"] = active_profile
    if working_directory is not None:
        context["working_directory"] = working_directory
    return context


def _build_gate_failure_summary(*, step_name: str, gate_report: dict[str, object], item: object) -> dict[str, object]:
    summary: dict[str, object] = {"failed_step": step_name}
    if isinstance(item, (str, int, float, bool)):
        summary["item"] = item
    message = _render_gate_failure_message(step_name=step_name, gate_report=gate_report, item=item)
    if message is not None:
        summary["message"] = message
    if isinstance(gate_report.get("on_fail_context"), dict):
        summary["on_fail_context"] = gate_report.get("on_fail_context")
    if isinstance(gate_report.get("on_fail_context_errors"), dict):
        summary["on_fail_context_errors"] = gate_report.get("on_fail_context_errors")
    return summary


def _render_gate_failure_message(*, step_name: str, gate_report: dict[str, object], item: object) -> str | None:
    verdict = gate_report.get("verdict")
    failed = gate_report.get("failed_causes")
    if not isinstance(failed, list):
        failed = gate_report.get("failed")
    unknown = gate_report.get("unknown_causes")
    if not isinstance(unknown, list):
        unknown = gate_report.get("unknown")
    failed_conditions = _gate_rendered_conditions(failed)
    unknown_conditions = _gate_rendered_conditions(unknown)
    return render_gate_failure_message(
        step_name=step_name,
        verdict=verdict if isinstance(verdict, str) else "failed",
        failed_conditions=failed_conditions,
        unknown_conditions=unknown_conditions,
        item=item,
    )


def _gate_rendered_conditions(nodes: object) -> list[str]:
    if not isinstance(nodes, list):
        return []
    rendered: list[str] = []
    for item in nodes:
        if not isinstance(item, dict):
            continue
        text = item.get("rendered") or item.get("expression")
        if isinstance(text, str):
            rendered.append(text)
    return rendered


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

    preflight_step_items = outputs.get("preflight_step_items")
    if isinstance(preflight_step_items, list):
        for item in preflight_step_items:
            if not isinstance(item, dict):
                continue
            if item.get("status") != "interpreted" or item.get("preflight_classification") != "context_only":
                continue
            expanded_item = item.get("expanded_item")
            if expanded_item is not None:
                _append_unique(facts, seen, f"fan_out item = {_compact_value(expanded_item)}")
            active_profile = item.get("active_profile")
            if isinstance(active_profile, str) and active_profile:
                _append_unique(facts, seen, f"active_profile = {active_profile}")

    return _limit_items(facts)


def _collect_missing_facts(outputs: dict[str, object]) -> list[str]:
    facts: list[str] = []
    seen: set[str] = set()

    if outputs.get("verdict_basis_stale"):
        weakened_scopes = outputs.get("stale_probe_scopes")
        if isinstance(weakened_scopes, list):
            for scope in weakened_scopes:
                if isinstance(scope, str) and scope:
                    _append_unique(facts, seen, f"fresh facts unavailable for {scope}")

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
    return [*items[:limit], f"... and {hidden_count} more"]


def _compact_value(value: object, *, limit: int = 80) -> str:
    if isinstance(value, str):
        rendered = value
    elif isinstance(value, (int, float, bool)) or value is None:
        rendered = json.dumps(value, ensure_ascii=False)
    else:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(rendered) <= limit:
        return rendered
    return f"{rendered[: limit - 3]}..."


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
