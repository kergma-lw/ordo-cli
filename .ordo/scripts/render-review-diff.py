#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def render_report(body: str) -> Path:
    directory = None
    try:
        directory = Path(tempfile.mkdtemp(prefix="ordo-review-")).absolute()
        fd, name = tempfile.mkstemp(suffix=".html", dir=directory)
        try:
            stream = os.fdopen(fd, "w", encoding="utf-8")
        except OSError:
            os.close(fd)
            raise
        with stream:
            stream.write(body)
        return Path(name)
    except OSError:
        if directory is not None:
            shutil.rmtree(directory, ignore_errors=True)
        raise


def main() -> int:
    """Accept a canonical ASCII positive decimal issue number ([1-9][0-9]*).

    Reports persist for asynchronous/manual viewing. A nonzero opener exit is
    best-effort success, but failure to launch the opener remains a failure.
    """
    if len(sys.argv) != 2:
        print("usage: render-review-diff.py <issue-number>", file=sys.stderr)
        return 2

    if re.fullmatch(r"[1-9][0-9]*", sys.argv[1]) is None:
        print("issue-number must be a canonical ASCII positive decimal", file=sys.stderr)
        return 2

    try:
        diff_result = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--no-textconv", "main...HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        print("failed to launch git diff", file=sys.stderr)
        return 1
    if diff_result.returncode != 0:
        sys.stderr.write(diff_result.stderr)
        return diff_result.returncode

    try:
        render_result = subprocess.run(
            [
                "npx",
                "--yes",
                "diff2html-cli@5.2.15",
                "-i",
                "stdin",
                "-o",
                "stdout",
                "--style",
                "side",
            ],
            input=diff_result.stdout,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        print("failed to launch diff2html renderer", file=sys.stderr)
        return 1
    if render_result.returncode != 0:
        print(f"diff2html renderer failed with exit code {render_result.returncode}",
              file=sys.stderr)
        return 1
    if not render_result.stdout.strip():
        print("diff2html renderer returned empty HTML", file=sys.stderr)
        return 1

    body = render_result.stdout
    try:
        output_path = render_report(body)
    except OSError:
        print("failed to create review report", file=sys.stderr)
        return 1

    try:
        subprocess.run(
            ["xdg-open", str(output_path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        print(f"failed to launch xdg-open; review report retained at {output_path}", file=sys.stderr)
        return 1

    print(json.dumps({"path": str(output_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
