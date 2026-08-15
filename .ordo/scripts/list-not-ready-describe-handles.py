#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


READINESS_PATH = Path(__file__).resolve().parents[1] / "describe-readiness.json"


def _load_readiness_registry() -> dict[str, dict[str, object]]:
    try:
        payload = json.loads(READINESS_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        print(f"invalid describe readiness registry: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    handles = payload.get("handles", {})
    if not isinstance(handles, dict):
        print("invalid describe readiness registry: handles must be an object", file=sys.stderr)
        raise SystemExit(2)
    return {str(handle): dict(entry) for handle, entry in handles.items() if isinstance(entry, dict)}


def main() -> int:
    readiness_registry = _load_readiness_registry()
    result = subprocess.run(
        ["ordo-help", "snippet-coverage", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"invalid snippet coverage json: {exc}", file=sys.stderr)
        return 2

    handles = []
    for item in payload.get("handles", []):
        if not isinstance(item, dict):
            continue
        handle = str(item.get("handle") or "")
        topic = str(item.get("topic") or "unknown")
        readiness_entry = readiness_registry.get(handle, {})
        describe_readiness = str(readiness_entry.get("describe_readiness", "unreviewed"))
        if describe_readiness == "ready":
            continue
        known_gaps = readiness_entry.get("describe_known_gaps", [])
        if not isinstance(known_gaps, list):
            known_gaps = []
        handles.append(
            {
                "handle": handle,
                "topic": topic,
                "describe_readiness": describe_readiness,
                "known_gaps": [str(gap) for gap in known_gaps],
            }
        )
    by_status: dict[str, int] = {}
    by_topic: dict[str, int] = {}
    for item in handles:
        status = str(item.get("describe_readiness", "unknown"))
        by_status[status] = by_status.get(status, 0) + 1
        topic = str(item.get("topic", "unknown"))
        by_topic[topic] = by_topic.get(topic, 0) + 1

    print(
        json.dumps(
            {
                "total_not_ready": len(handles),
                "by_status": by_status,
                "by_topic": by_topic,
                "handles": handles,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
