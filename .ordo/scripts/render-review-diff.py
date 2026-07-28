#!/usr/bin/env python3

from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: render-review-diff.py <issue-number>", file=sys.stderr)
        return 2

    issue_number = sys.argv[1]
    output_path = Path(f"/tmp/ordo-review-{issue_number}.html")

    diff_result = subprocess.run(
        ["git", "diff", "main...HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if diff_result.returncode != 0:
        sys.stderr.write(diff_result.stderr)
        return diff_result.returncode

    body = (
        "<!doctype html><html><body><h1>Branch diff vs main</h1><pre>"
        + html.escape(diff_result.stdout)
        + "</pre></body></html>"
    )
    output_path.write_text(body, encoding="utf-8")

    subprocess.run(
        ["xdg-open", str(output_path)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print(json.dumps({"path": str(output_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
