"""Profile composition and explicit override models."""

from __future__ import annotations

from dataclasses import dataclass, field

from .launcher import Launcher
from .json import JSONObject


@dataclass(frozen=True, slots=True)
class Override:
    """Explicit local adaptation that never silently shadows base semantics."""

    target: str
    with_: JSONObject = field(default_factory=dict, kw_only=True)
    reason: str | None = None

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped override form."""

        contract: JSONObject = {"target": self.target, "with": dict(self.with_)}
        if self.reason is not None:
            contract["reason"] = self.reason
        return contract


@dataclass(frozen=True, slots=True)
class Profile:
    """Reusable composition defaults for workflows and local policy."""

    name: str
    inputs: JSONObject = field(default_factory=dict)
    checks: tuple[str, ...] = ()
    overrides: tuple[Override, ...] = ()
    launchers: dict[str, Launcher] = field(default_factory=dict)

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped profile form."""

        return {
            "name": self.name,
            "inputs": dict(self.inputs),
            "checks": list(self.checks),
            "overrides": [override.to_contract() for override in self.overrides],
            "launchers": {name: launcher.to_contract() for name, launcher in self.launchers.items()},
        }
