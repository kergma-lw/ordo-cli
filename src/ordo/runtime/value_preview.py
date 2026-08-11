"""Compact observed-value previews for runtime diagnostics."""

from __future__ import annotations

from ordo.model.json import JSONObject, JSONValue


def summarize_json_value(value: JSONValue, *, max_depth: int = 2, max_string: int = 80) -> JSONObject:
    """Return a compact, shape-aware preview for one JSON runtime value."""

    return _summarize_json_value(value, depth=0, max_depth=max_depth, max_string=max_string)


def _summarize_json_value(value: JSONValue, *, depth: int, max_depth: int, max_string: int) -> JSONObject:
    if value is None:
        return {"type": "null", "value": None}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"type": "integer", "value": value}
    if isinstance(value, float):
        return {"type": "number", "value": value}
    if isinstance(value, str):
        preview = value if len(value) <= max_string else value[: max_string - 1] + "…"
        return {"type": "string", "length": len(value), "preview": preview}
    if isinstance(value, list):
        payload: JSONObject = {
            "type": "array",
            "length": len(value),
            "item_types": _unique_types(value),
        }
        if value:
            payload["first_item_preview"] = _summarize_json_value(
                value[0], depth=depth + 1, max_depth=max_depth, max_string=max_string
            )
        return payload
    if isinstance(value, dict):
        payload = {
            "type": "object",
            "size": len(value),
            "keys_preview": list(value.keys())[:5],
        }
        if depth < max_depth and value:
            sample: JSONObject = {}
            for key, item in list(value.items())[:3]:
                sample[key] = _summarize_json_value(item, depth=depth + 1, max_depth=max_depth, max_string=max_string)
            payload["entries_preview"] = sample
        return payload
    return {"type": type(value).__name__}


def _unique_types(values: list[JSONValue]) -> list[str]:
    types: list[str] = []
    for item in values:
        name = _json_type_name(item)
        if name not in types:
            types.append(name)
        if len(types) >= 3:
            break
    return types


def _json_type_name(value: JSONValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__
