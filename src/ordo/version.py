"""Installed distribution version for public command-line entrypoints."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def distribution_version() -> str:
    """Return the installed Ordo distribution version when available."""

    try:
        return version("ordo")
    except PackageNotFoundError:
        return "unknown"
