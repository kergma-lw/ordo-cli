#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
try:
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


def parse_minimal_toml(text: str) -> dict:
    version = None
    packs: list[dict] = []
    current: dict | None = None
    collecting_sources = False
    sources: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[packs]]":
            if current is not None:
                current["sources"] = sources
                packs.append(current)
            current = {}
            sources = []
            collecting_sources = False
            continue
        if line.startswith("version ="):
            version = int(line.split("=", 1)[1].strip())
            continue
        if current is None:
            continue
        if line.startswith("sources = ["):
            collecting_sources = True
            continue
        if collecting_sources:
            if line == "]":
                collecting_sources = False
                continue
            sources.append(line.rstrip(",").strip().strip('"'))
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            current[key.strip()] = value.strip().strip('"')

    if current is not None:
        current["sources"] = sources
        packs.append(current)
    return {"version": version, "packs": packs}


def load_config(config_path: Path) -> dict:
    text = config_path.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)
    return parse_minimal_toml(text)


def render_pack(meta_dir: Path, pack: dict) -> str:
    title = pack["title"]
    lines = [f"# {title}", "", "> Generated from meta source docs. Do not edit by hand.", ""]
    for rel in pack["sources"]:
        src = meta_dir / rel
        text = src.read_text(encoding="utf-8").rstrip()
        lines.append(f"<!-- source: {rel} -->")
        lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", help="Path to domain-packs.toml")
    ap.add_argument("--check", action="store_true", help="Fail if generated files differ")
    args = ap.parse_args()

    config_path = Path(args.config).resolve()
    meta_dir = config_path.parent
    data = load_config(config_path)
    packs = data.get("packs", [])
    if not isinstance(packs, list) or not packs:
        raise SystemExit("No packs defined")

    mismatches: list[str] = []
    for pack in packs:
        rendered = render_pack(meta_dir, pack)
        out_path = meta_dir / pack["output"]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if args.check:
            current = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
            if sha(current) != sha(rendered):
                mismatches.append(str(out_path))
            continue
        out_path.write_text(rendered, encoding="utf-8")
        print(f"Wrote {out_path}")

    if args.check and mismatches:
        for path in mismatches:
            print(f"Out of date: {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
