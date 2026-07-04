"""Fail-closed registry for covered published introspection sections."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

from ordo.model.json import JSONValue

from .capabilities import describe_capabilities
from .errors import describe_errors
from .examples import describe_examples_catalog
from .operations import describe_operations
from .patterns import describe_pattern_hints
from .playbook import describe_playbook_contract
from .plugins import describe_plugin_surface_contract
from .profile import describe_profile_contract
from .state import describe_state_contract
from .workflow import describe_workflow_contract


@dataclass(frozen=True, slots=True)
class PublishedIntrospectionSection:
    """One covered published introspection section."""

    name: str
    producer_name: str
    producer: Callable[[], JSONValue]


PUBLISHED_INTROSPECTION_SECTIONS: tuple[PublishedIntrospectionSection, ...] = (
    PublishedIntrospectionSection(name="capabilities", producer_name="describe_capabilities", producer=describe_capabilities),
    PublishedIntrospectionSection(name="errors", producer_name="describe_errors", producer=describe_errors),
    PublishedIntrospectionSection(name="examples_catalog", producer_name="describe_examples_catalog", producer=describe_examples_catalog),
    PublishedIntrospectionSection(name="operations", producer_name="describe_operations", producer=describe_operations),
    PublishedIntrospectionSection(name="pattern_hints", producer_name="describe_pattern_hints", producer=describe_pattern_hints),
    PublishedIntrospectionSection(name="playbook_contract", producer_name="describe_playbook_contract", producer=describe_playbook_contract),
    PublishedIntrospectionSection(name="plugin_surface_contract", producer_name="describe_plugin_surface_contract", producer=describe_plugin_surface_contract),
    PublishedIntrospectionSection(name="profile_contract", producer_name="describe_profile_contract", producer=describe_profile_contract),
    PublishedIntrospectionSection(name="state_contract", producer_name="describe_state_contract", producer=describe_state_contract),
    PublishedIntrospectionSection(name="workflow_contract", producer_name="describe_workflow_contract", producer=describe_workflow_contract),
)


def describe_published_sections() -> dict[str, JSONValue]:
    """Return the covered published introspection sections keyed by section name."""

    return {section.name: section.producer() for section in PUBLISHED_INTROSPECTION_SECTIONS}
