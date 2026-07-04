"""Public CLI entrypoint for ordo-help discovery."""

from __future__ import annotations

import argparse
import json
import sys

from ordo.introspection import describe_system
from ordo.model.json import JSONObject


PUBLIC_TOPICS: tuple[dict[str, str], ...] = (
    {"name": "overview", "summary": "Start with the Ordo world map"},
    {"name": "capabilities", "summary": "Inspect supported and unsupported surfaces"},
    {"name": "model", "summary": "Inspect the main authoring contracts"},
    {"name": "operations", "summary": "Inspect the public connector catalog"},
    {"name": "operation", "summary": "Inspect one public operation by reference"},
    {"name": "describe", "summary": "Resolve a supported public topic"},
    {"name": "search", "summary": "Search topics and operation references"},
)

RECOMMENDED_FIRST_CALLS: tuple[dict[str, str], ...] = (
    {"command": "ordo-help overview --json", "purpose": "Get the Ordo world map"},
    {"command": "ordo-help capabilities --json", "purpose": "Learn capability boundaries"},
    {"command": "ordo-help model --json", "purpose": "Learn the main DSL surfaces"},
    {"command": "ordo-help operations --json", "purpose": "Inspect the public operation catalog"},
)


def build_root_response() -> JSONObject:
    """Return the machine-readable root discovery response."""

    system = describe_system()
    internal_sections = system["sections"]
    return {
        "tool_name": "ordo-help",
        "purpose": "Self-describing discovery CLI for Ordo",
        "output_modes": ["text", "json"],
        "topics": [dict(topic) for topic in PUBLIC_TOPICS],
        "recommended_first_calls": [dict(item) for item in RECOMMENDED_FIRST_CALLS],
        "examples": [
            "ordo-help overview --json",
            "ordo-help capabilities --json",
            "ordo-help model --json",
            "ordo-help operations --json",
        ],
        "introspection": {
            "version": system["introspection_version"],
            "entrypoint": internal_sections["discovery"]["entrypoint"],
            "published_sections": sorted(name for name in internal_sections if name != "discovery"),
        },
    }


def render_root_text() -> str:
    """Return the human-readable bootstrap screen."""

    lines = [
        "ordo-help",
        "Self-describing discovery CLI for Ordo.",
        "",
        "Output modes:",
        "- text",
        "- json (--json)",
        "",
        "Topics:",
    ]
    for topic in PUBLIC_TOPICS:
        lines.append(f"- {topic['name']}: {topic['summary']}")
    lines.extend(
        [
            "",
            "Recommended first calls:",
            "1. ordo-help overview --json",
            "2. ordo-help capabilities --json",
            "3. ordo-help model --json",
            "4. ordo-help operations --json",
            "",
            "Next command examples:",
            "- ordo-help overview --json",
            "- ordo-help capabilities --json",
            "- ordo-help model --json",
            "- ordo-help operations --json",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the ordo-help CLI."""

    parser = argparse.ArgumentParser(prog="ordo-help", add_help=False)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("-h", "--help", action="store_true", dest="show_help")
    parser.add_argument("args", nargs="*")
    parsed = parser.parse_args(argv)

    if parsed.args:
        parser.error(f"Unsupported command for current root-only implementation: {' '.join(parsed.args)}")

    if parsed.as_json:
        json.dump(build_root_response(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(render_root_text())
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
