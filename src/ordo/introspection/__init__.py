"""Public package surface for machine-readable introspection."""

from .envelope import INTROSPECTION_VERSION, build_introspection_envelope

__all__ = ["INTROSPECTION_VERSION", "build_introspection_envelope"]
