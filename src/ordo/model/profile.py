"""Profile composition and explicit override models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .json import JSONObject


@dataclass(frozen=True, slots=True)
class Override:
    """Explicit local adaptation that never silently shadows base semantics."""

    target: str
    with_: JSONObject = field(default_factory=dict, kw_only=True)
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Profile:
    """Reusable composition defaults for workflows and local policy."""

    name: str
    inputs: JSONObject = field(default_factory=dict)
    checks: tuple[str, ...] = ()
    overrides: tuple[Override, ...] = ()
