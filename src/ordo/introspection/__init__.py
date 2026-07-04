"""Public package surface for machine-readable introspection."""

from .capabilities import describe_capabilities
from .envelope import INTROSPECTION_VERSION, build_introspection_envelope
from .operations import describe_operations
from .playbook import describe_playbook_contract
from .system import describe_system
from .workflow import describe_workflow_contract

__all__ = [
    "INTROSPECTION_VERSION",
    "build_introspection_envelope",
    "describe_capabilities",
    "describe_operations",
    "describe_playbook_contract",
    "describe_system",
    "describe_workflow_contract",
]
