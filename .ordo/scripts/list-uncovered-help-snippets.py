#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    result = subprocess.run(
        [str(REPOSITORY_ROOT / "ordo-help"), "snippet-coverage", "--json"],
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

    handles = [item for item in payload.get("handles", []) if item.get("snippet_coverage") == "none"]
    by_topic: dict[str, int] = {}
    for item in handles:
        topic = item.get("topic", "unknown")
        by_topic[topic] = by_topic.get(topic, 0) + 1

    print(
        json.dumps(
            {
                "total_none": len(handles),
                "by_topic": by_topic,
                "handles": handles,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
