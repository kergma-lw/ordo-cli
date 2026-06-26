"""Ordo v0 package surface."""

from .connectors import ConnectorRegistry, get_public_connector_registry
from .model.connector import Connector, ConnectorBootstrap, OperationContract
from .model.diagnostic import Diagnostic
from .model.profile import Override, Profile
from .model.runtime import ExecutionPlan, ExecutionResult, Mode, OperationResult, RuntimeResult, RuntimeStatus
from .model.workflow import Guard, OperationRef, Step, Workflow
from .runtime import LoadError, ProfileCompositionResult, ValidationReport, WorkflowProfileApplicationResult
from .runtime import apply_profile_to_workflow, compose_profiles
from .runtime import load_profile_file, load_profile_text, load_workflow_file, load_workflow_text, load_yaml_document
from .runtime import validate_profile_document, validate_profile_text, validate_workflow_document, validate_workflow_text

__all__ = [
    "Connector",
    "ConnectorRegistry",
    "ConnectorBootstrap",
    "Diagnostic",
    "ExecutionPlan",
    "ExecutionResult",
    "Guard",
    "LoadError",
    "Mode",
    "OperationContract",
    "OperationRef",
    "OperationResult",
    "Override",
    "Profile",
    "ProfileCompositionResult",
    "RuntimeResult",
    "RuntimeStatus",
    "Step",
    "WorkflowProfileApplicationResult",
    "Workflow",
    "get_public_connector_registry",
    "apply_profile_to_workflow",
    "compose_profiles",
    "load_profile_file",
    "load_profile_text",
    "load_workflow_file",
    "load_workflow_text",
    "load_yaml_document",
    "ValidationReport",
    "validate_profile_document",
    "validate_profile_text",
    "validate_workflow_document",
    "validate_workflow_text",
]
