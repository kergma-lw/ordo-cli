"""Public package surface for machine-readable introspection."""

from .capabilities import describe_capabilities
from .envelope import INTROSPECTION_VERSION, build_introspection_envelope
from .operations import describe_operations
from .system import describe_system

__all__ = [
    "INTROSPECTION_VERSION",
    "build_introspection_envelope",
    "describe_capabilities",
    "describe_operations",
    "describe_system",
]
