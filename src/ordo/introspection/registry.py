"""Fail-closed registry for covered published introspection sections."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.json import JSONValue

from .capabilities import describe_capabilities
from .operations import describe_operations
from .playbook import describe_playbook_contract
from .workflow import describe_workflow_contract


@dataclass(frozen=True, slots=True)
class PublishedIntrospectionSection:
    """One covered published introspection section."""

    name: str
    producer_name: str
    producer: callable


PUBLISHED_INTROSPECTION_SECTIONS: tuple[PublishedIntrospectionSection, ...] = (
    PublishedIntrospectionSection(name="capabilities", producer_name="describe_capabilities", producer=describe_capabilities),
    PublishedIntrospectionSection(name="operations", producer_name="describe_operations", producer=describe_operations),
    PublishedIntrospectionSection(name="playbook_contract", producer_name="describe_playbook_contract", producer=describe_playbook_contract),
    PublishedIntrospectionSection(name="workflow_contract", producer_name="describe_workflow_contract", producer=describe_workflow_contract),
)


def describe_published_sections() -> dict[str, JSONValue]:
    """Return the covered published introspection sections keyed by section name."""

    return {section.name: section.producer() for section in PUBLISHED_INTROSPECTION_SECTIONS}
