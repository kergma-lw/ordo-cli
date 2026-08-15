from __future__ import annotations

import json


def render_gate_failure_message(
    *,
    step_name: str,
    verdict: str,
    failed_conditions: list[str],
    unknown_conditions: list[str],
    item: object | None = None,
) -> str:
    if item is not None:
        item_label = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, sort_keys=True)
        if failed_conditions:
            if len(failed_conditions) == 1:
                return f"Item '{item_label}' failed gate '{step_name}': {failed_conditions[0]}"
            return f"Item '{item_label}' failed gate '{step_name}'. Failed conditions: {'; '.join(failed_conditions)}"
        if unknown_conditions:
            if len(unknown_conditions) == 1:
                return f"Item '{item_label}' could not establish gate '{step_name}': {unknown_conditions[0]}"
            return f"Item '{item_label}' could not establish gate '{step_name}'. Unknown conditions: {'; '.join(unknown_conditions)}"
        return f"Item '{item_label}' failed gate '{step_name}'"

    if verdict == "unknown":
        if len(unknown_conditions) == 1:
            return f"Step gate could not be fully established for '{step_name}': {unknown_conditions[0]}"
        if unknown_conditions:
            return f"Step gate could not be fully established for '{step_name}'. Unknown conditions: {'; '.join(unknown_conditions)}"
        return f"Step gate could not be fully established for '{step_name}'"

    if len(failed_conditions) == 1:
        return f"Step gate blocked execution for '{step_name}': {failed_conditions[0]}"
    if failed_conditions:
        return f"Step gate blocked execution for '{step_name}'. Failed conditions: {'; '.join(failed_conditions)}"
    return f"Step gate blocked execution for '{step_name}'"


def render_guard_failure_message(*, guard_reference: str, failed_subcondition: str | None = None) -> str:
    if isinstance(failed_subcondition, str) and failed_subcondition and failed_subcondition != guard_reference:
        return f"Guard blocked execution for '{guard_reference}': {failed_subcondition}"
    return f"Guard blocked execution for '{guard_reference}'"
