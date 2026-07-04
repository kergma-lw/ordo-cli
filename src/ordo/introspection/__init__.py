"""Public package surface for machine-readable introspection."""

from .capabilities import describe_capabilities
from .envelope import INTROSPECTION_VERSION, build_introspection_envelope
from .errors import describe_errors
from .examples import describe_examples_catalog
from .operations import describe_operations
from .patterns import describe_pattern_hints
from .playbook import describe_playbook_contract
from .plugins import describe_plugin_surface_contract
from .profile import describe_profile_contract
from .state import describe_state_contract
from .system import describe_system
from .workflow import describe_workflow_contract

__all__ = [
    "INTROSPECTION_VERSION",
    "build_introspection_envelope",
    "describe_capabilities",
    "describe_errors",
    "describe_examples_catalog",
    "describe_operations",
    "describe_pattern_hints",
    "describe_playbook_contract",
    "describe_plugin_surface_contract",
    "describe_profile_contract",
    "describe_state_contract",
    "describe_system",
    "describe_workflow_contract",
]
