"""Command-line entrypoint for playbook-based workflow activation."""

from __future__ import annotations

import argparse
import json
import sys

import yaml

from ordo import check_workflow, clear_default_connector_provider, configure_standard_runtime, execute_workflow, explain_workflow, get_default_connector_provider, plan_workflow, set_default_connector_provider
from ordo.model.runtime import RuntimeResult
from ordo.playbook import PlaybookError, activate_playbook


def main() -> int:
    parser = argparse.ArgumentParser(prog="ordo-playbook")
    parser.add_argument("--file", dest="playbook_file", help="explicit playbook file path")
    parser.add_argument("--workflow", required=True, help="workflow name declared in the playbook")
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
    parser.add_argument("mode", choices=("check", "plan", "explain", "run", "next"))
    args = parser.parse_args()
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

        if args.mode == "run":
            return _emit_refusal(
                workflow=args.workflow,
                playbook=str(activated.playbook_path),
                profile=None if activated.profile is None else activated.profile.name,
                as_json=args.json,
            )

        result = _run_mode(args.mode, activated.workflow, activated.profile)
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
            payload.update(
                {
                    "workflow": activated.workflow_name,
                    "playbook": str(activated.playbook_path),
                    "profile": None if activated.profile is None else activated.profile.name,
                }
            )

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


def _run_mode(mode: str, workflow, profile) -> RuntimeResult:
    if mode == "check":
        return check_workflow(workflow, profile=profile)
    if mode == "plan":
        return plan_workflow(workflow, profile=profile)
    if mode == "run":
        return execute_workflow(workflow, profile=profile)
    explained = explain_workflow(workflow, profile=profile)
    return explained


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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
