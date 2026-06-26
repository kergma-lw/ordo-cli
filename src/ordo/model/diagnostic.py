"""Structured diagnostics shared across validation, resolution, and runtime modes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .json import JSONObject

DiagnosticLevel = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Machine-usable diagnostic entry."""

    code: str
    level: DiagnosticLevel
    message: str
    path: tuple[str, ...] = ()
    details: JSONObject = field(default_factory=dict)
