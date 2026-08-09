"""Helpers for surfacing visible register state in diagnostics."""

from __future__ import annotations

from ordo.model.json import JSONValue


def snapshot_visible_registers(step_results: dict[str, object]) -> dict[str, JSONValue]:
    """Return a JSON-shaped snapshot of currently visible step registers."""

    snapshot: dict[str, JSONValue] = {}
    for name, value in step_results.items():
        if isinstance(name, str) and _is_json_value(value):
            snapshot[name] = value
    return snapshot


def _is_json_value(value: object) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False
