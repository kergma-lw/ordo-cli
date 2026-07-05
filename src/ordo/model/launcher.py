"""Launcher models for rare execution wrappers."""

from __future__ import annotations

from dataclasses import dataclass

from .json import JSONObject


@dataclass(frozen=True, slots=True)
class Launcher:
    """Named execution wrapper definition."""

    connector: str | None = None
    before: str | None = None
    after: str | None = None

    def to_contract(self) -> JSONObject:
        contract: JSONObject = {}
        if self.connector is not None:
            contract["connector"] = self.connector
        if self.before is not None:
            contract["before"] = self.before
        if self.after is not None:
            contract["after"] = self.after
        return contract
