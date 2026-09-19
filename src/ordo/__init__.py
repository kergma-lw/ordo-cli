"""Ordo v0 package surface."""

from .model.connector import Connector, ConnectorBootstrap, OperationContract
from .model.diagnostic import Diagnostic
from .model.profile import Override, Profile
from .model.runtime import ExecutionPlan, ExecutionResult, Mode, OperationResult, RuntimeResult, RuntimeStatus
from .model.workflow import Guard, OperationRef, Step, Workflow


def __getattr__(name: str):
    if name in {"configure_standard_runtime", "get_standard_connector_provider"}:
        from .app import configure_standard_runtime, get_standard_connector_provider

        return {
            "configure_standard_runtime": configure_standard_runtime,
            "get_standard_connector_provider": get_standard_connector_provider,
        }[name]
    if name in {"ConnectorRegistry", "get_public_connector_provider", "get_public_connector_registry"}:
        from .connectors import ConnectorRegistry, get_public_connector_provider, get_public_connector_registry

        return {
            "ConnectorRegistry": ConnectorRegistry,
            "get_public_connector_provider": get_public_connector_provider,
            "get_public_connector_registry": get_public_connector_registry,
        }[name]
    if name in {
        "ConnectorProvider",
        "GuardProbe",
        "LoadError",
        "ProfileCompositionResult",
        "StepExecutor",
        "ValidationReport",
        "WorkflowProfileApplicationResult",
        "ResolvedOperation",
        "WorkflowResolution",
        "resolve_workflow_references",
        "apply_profile_to_workflow",
        "check_workflow",
        "compose_profiles",
        "execute_workflow",
        "clear_default_connector_provider",
        "get_default_connector_provider",
        "set_default_connector_provider",
        "explain_execution_result",
        "explain_runtime_result",
        "assess_workflow_readiness",
        "plan_workflow",
        "review_workflow",
        "load_profile_file",
        "load_profile_text",
        "load_workflow_file",
        "load_workflow_text",
        "load_yaml_document",
        "validate_profile_document",
        "validate_profile_text",
        "validate_workflow_document",
        "validate_workflow_text",
    }:
        from . import runtime as runtime_module

        return getattr(runtime_module, name)
    if name in {"ActivatedPlaybook", "PlaybookError", "activate_playbook", "discover_playbook_path"}:
        from .playbook import ActivatedPlaybook, PlaybookError, activate_playbook, discover_playbook_path

        return {
            "ActivatedPlaybook": ActivatedPlaybook,
            "PlaybookError": PlaybookError,
            "activate_playbook": activate_playbook,
            "discover_playbook_path": discover_playbook_path,
        }[name]
    raise AttributeError(name)

__all__ = [
    "Connector",
    "ConnectorProvider",
    "ConnectorRegistry",
    "ConnectorBootstrap",
    "Diagnostic",
    "ExecutionPlan",
    "ExecutionResult",
    "Guard",
    "GuardProbe",
    "LoadError",
    "Mode",
    "OperationContract",
    "OperationRef",
    "OperationResult",
    "Override",
    "PlaybookError",
    "Profile",
    "ProfileCompositionResult",
    "ResolvedOperation",
    "RuntimeResult",
    "RuntimeStatus",
    "StepExecutor",
    "Step",
    "WorkflowResolution",
    "WorkflowProfileApplicationResult",
    "Workflow",
    "configure_standard_runtime",
    "clear_default_connector_provider",
    "get_default_connector_provider",
    "get_public_connector_provider",
    "get_public_connector_registry",
    "get_standard_connector_provider",
    "set_default_connector_provider",
    "apply_profile_to_workflow",
    "check_workflow",
    "compose_profiles",
    "execute_workflow",
    "explain_execution_result",
    "explain_runtime_result",
    "assess_workflow_readiness",
    "plan_workflow",
    "review_workflow",
    "load_profile_file",
    "load_profile_text",
    "load_workflow_file",
    "load_workflow_text",
    "load_yaml_document",
    "resolve_workflow_references",
    "ValidationReport",
    "ActivatedPlaybook",
    "activate_playbook",
    "validate_profile_document",
    "validate_profile_text",
    "validate_workflow_document",
    "validate_workflow_text",
    "discover_playbook_path",
]
