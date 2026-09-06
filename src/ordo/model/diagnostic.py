"""Structured diagnostics shared across validation, resolution, and runtime modes."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from .json import JSONObject

DiagnosticLevel = Literal["error", "warning", "info"]
StateMissingTarget = tuple[str, str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Machine-usable diagnostic entry."""

    code: str
    level: DiagnosticLevel
    message: str
    path: tuple[str, ...] = ()
    details: JSONObject = field(default_factory=dict)
    _state_missing_target: StateMissingTarget | None = field(default=None, repr=False, compare=False)
    _state_missing_events: tuple[Diagnostic, ...] = field(default=(), repr=False, compare=False)

    def to_contract(self) -> JSONObject:
        """Return the stable JSON-shaped diagnostic form."""

        return {
            "code": self.code,
            "level": self.level,
            "message": self.message,
            "path": list(self.path),
            "details": dict(self.details),
        }


def group_state_missing_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> tuple[Diagnostic, ...]:
    """Group emitted missing-state events, never inferred reads or other errors.

    occurrence_count counts emitted events; reported_at lists their unique
    effective structural locations, not all dependent uses.
    """

    groups: dict[StateMissingTarget, list[Diagnostic]] = {}
    for diagnostic in diagnostics:
        if diagnostic.code == "runtime.value.state_missing" and diagnostic._state_missing_target is not None:
            groups.setdefault(diagnostic._state_missing_target, []).extend(diagnostic._state_missing_events or (diagnostic,))
    if not groups:
        return diagnostics
    result: list[Diagnostic] = []
    emitted: set[StateMissingTarget] = set()
    for diagnostic in diagnostics:
        target = diagnostic._state_missing_target
        if diagnostic.code != "runtime.value.state_missing" or target is None:
            result.append(diagnostic)
            continue
        if target in emitted:
            continue
        emitted.add(target)
        events = groups[target]
        if len(events) == 1:
            result.append(events[0])
            continue
        sites: dict[tuple[str, ...], JSONObject] = {}
        for event in events:
            site = sites.setdefault(event.path, {"path": list(event.path), "references": []})
            reference = {"expression": event.details.get("expression"), "state": event.details.get("state")}
            references = site["references"]
            assert isinstance(references, list)
            if reference not in references:
                references.append(reference)
        result.append(replace(
            events[0],
            path=events[0].path if len(sites) == 1 else (),
            details={**events[0].details, "occurrence_count": len(events), "reported_at": list(sites.values())},
            _state_missing_events=tuple(events),
        ))
    return tuple(result)


def attribute_state_missing_diagnostics(
    diagnostics: tuple[Diagnostic, ...], path: tuple[str, ...], *, prefix: bool = False,
) -> tuple[Diagnostic, ...]:
    """Attribute original events before regrouping, including nested child groups."""

    result: list[Diagnostic] = []
    for diagnostic in diagnostics:
        if diagnostic.code != "runtime.value.state_missing" or diagnostic._state_missing_target is None:
            result.append(diagnostic)
            continue
        events = tuple(
            replace(event, path=path + event.path if prefix else path)
            for event in diagnostic._state_missing_events or (diagnostic,)
        )
        result.extend(group_state_missing_diagnostics(events) if diagnostic._state_missing_events else events)
    return tuple(result)
