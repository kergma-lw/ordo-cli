"""Filesystem connector family."""

from __future__ import annotations

from connectors._family import ActionHandler, ProbeHandler, assemble_family

from .bootstrap import BOOTSTRAP

ORDER = 40

_ASSEMBLED = assemble_family(package_name=__name__, namespace="fs", bootstrap=BOOTSTRAP)


def get_connector():
    return _ASSEMBLED.connector


def get_probe_handler(name: str) -> ProbeHandler | None:
    return _ASSEMBLED.probe_handlers.get(name)


def get_action_handler(name: str) -> ActionHandler | None:
    return _ASSEMBLED.action_handlers.get(name)
