"""Published verified examples metadata for machine-readable introspection."""

from __future__ import annotations

from pathlib import Path

from ordo.model.examples_catalog import describe_examples_catalog_data
from ordo.model.json import JSONObject


def describe_examples_catalog() -> JSONObject:
    """Return the published verified examples discovery surface."""

    payload = describe_examples_catalog_data()
    repo_root = Path(__file__).resolve().parents[3]
    for item in payload["examples"]:
        item["verified"] = (repo_root / item["path"]).is_file()
    return payload
