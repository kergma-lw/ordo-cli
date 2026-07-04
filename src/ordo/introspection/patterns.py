"""Published machine-readable pattern hints for authoring guidance."""

from __future__ import annotations

from ordo.model.json import JSONObject
from ordo.model.pattern_hints import describe_pattern_hints_data


def describe_pattern_hints() -> JSONObject:
    """Return the published guidance hints kept separate from contracts."""

    return describe_pattern_hints_data()
