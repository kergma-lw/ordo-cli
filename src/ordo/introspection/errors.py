"""Published error taxonomy for machine-readable introspection."""

from __future__ import annotations

from ordo.model.error_taxonomy import describe_error_taxonomy_data
from ordo.model.json import JSONObject


def describe_errors() -> JSONObject:
    """Return the published error and failure-class taxonomy."""

    return describe_error_taxonomy_data()
