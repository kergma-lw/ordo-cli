"""Public connector registry and discoverable metadata surface."""

from __future__ import annotations

from dataclasses import dataclass

from ordo.model.connector import Connector, ConnectorBootstrap, OperationContract
from ordo.model.json import JSONObject


@dataclass(frozen=True, slots=True)
class ConnectorRegistry:
    """Discoverable public registry of stable connector families and operations."""

    connectors: tuple[Connector, ...]

    def list_connectors(self) -> tuple[Connector, ...]:
        return self.connectors

    def get_connector(self, namespace: str) -> Connector | None:
        for connector in self.connectors:
            if connector.namespace == namespace:
                return connector
        return None

    def get_operation(self, reference: str) -> OperationContract | None:
        namespace, separator, operation_name = reference.partition(".")
        if not separator:
            return None

        connector = self.get_connector(namespace)
        if connector is None:
            return None

        for operation in connector.operations:
            if operation.name == operation_name:
                return operation
        return None

    def to_contract(self) -> JSONObject:
        return {"connectors": [connector.to_contract() for connector in self.connectors]}


def get_public_connector_registry() -> ConnectorRegistry:
    """Return the fixed public v0 connector registry."""

    return ConnectorRegistry(
        connectors=(
            Connector(
                namespace="git",
                bootstrap=ConnectorBootstrap(
                    prerequisites=("git binary available", "inside git repository"),
                    context_fields=("repository_root", "current_branch"),
                ),
                operations=(
                    OperationContract(
                        name="clean_worktree",
                        kind="probe",
                        outputs={"clean": "boolean", "dirty_paths": ["string"]},
                        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
                    ),
                    OperationContract(
                        name="branch_not_main",
                        kind="probe",
                        outputs={"allowed": "boolean", "current_branch": "string"},
                        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
                    ),
                    OperationContract(
                        name="single_worktree",
                        kind="probe",
                        outputs={"single_worktree": "boolean", "worktree_count": "integer"},
                        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
                    ),
                    OperationContract(
                        name="sync_main_ff_only",
                        kind="action",
                        effects=("fast-forward main branch",),
                        outputs={"synced": "boolean", "base_branch": "string"},
                        failure_modes=("git_unavailable", "not_repository", "non_fast_forward", "action_failed"),
                    ),
                    OperationContract(
                        name="branch_from_issue",
                        kind="action",
                        inputs={"issue": "string", "branch": "string"},
                        effects=("create or switch task branch",),
                        outputs={"branch": "string", "created": "boolean"},
                        failure_modes=("git_unavailable", "not_repository", "invalid_issue", "action_failed"),
                    ),
                    OperationContract(
                        name="merge_to_main_ff",
                        kind="action",
                        effects=("fast-forward current work into main",),
                        outputs={"merged": "boolean", "base_branch": "string"},
                        failure_modes=("git_unavailable", "not_repository", "non_fast_forward", "action_failed"),
                    ),
                    OperationContract(
                        name="worktree",
                        kind="probe",
                        outputs={"clean": "boolean", "dirty_paths": ["string"]},
                        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
                    ),
                    OperationContract(
                        name="branch",
                        kind="probe",
                        outputs={"value": "string"},
                        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
                    ),
                ),
            ),
            Connector(
                namespace="gh",
                bootstrap=ConnectorBootstrap(
                    prerequisites=("gh binary available", "GitHub auth available"),
                    context_fields=("host", "viewer", "scopes"),
                ),
                operations=(
                    OperationContract(
                        name="issue.view",
                        kind="probe",
                        inputs={"issue": "string"},
                        outputs={"issue": "object", "project_items": ["object"]},
                        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
                    ),
                    OperationContract(
                        name="issue_status",
                        kind="probe",
                        inputs={"issue": "string", "equals": "string"},
                        outputs={"status": "string", "matches": "boolean"},
                        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
                    ),
                    OperationContract(
                        name="issue_status_not_in",
                        kind="probe",
                        inputs={"issue": "string", "statuses": ["string"]},
                        outputs={"status": "string", "allowed": "boolean"},
                        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
                    ),
                    OperationContract(
                        name="issue_project_membership",
                        kind="probe",
                        inputs={"issue": "string"},
                        outputs={"member": "boolean", "project_items": ["object"]},
                        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
                    ),
                    OperationContract(
                        name="project_set_status",
                        kind="action",
                        inputs={"issue": "string", "status": "string"},
                        effects=("update project status field",),
                        outputs={"issue": "string", "status": "string"},
                        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "action_failed"),
                    ),
                    OperationContract(
                        name="project_set_iteration",
                        kind="action",
                        inputs={"issue": "string", "value": "string"},
                        effects=("update project iteration field",),
                        outputs={"issue": "string", "iteration": "string"},
                        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "action_failed"),
                    ),
                    OperationContract(
                        name="close_issue",
                        kind="action",
                        inputs={"issue": "string"},
                        effects=("close GitHub issue",),
                        outputs={"issue": "string", "closed": "boolean"},
                        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "action_failed"),
                    ),
                    OperationContract(
                        name="issue",
                        kind="probe",
                        inputs={"issue": "string"},
                        outputs={
                            "status": "string",
                            "project": {"member": "boolean", "items": ["object"]},
                            "issue": "object",
                        },
                        failure_modes=("gh_unavailable", "auth_missing", "issue_not_found", "probe_failed"),
                    ),
                ),
            ),
            Connector(
                namespace="shell",
                bootstrap=ConnectorBootstrap(
                    prerequisites=("supported shell available",),
                    context_fields=("shell", "working_directory"),
                ),
                operations=(
                    OperationContract(
                        name="command",
                        kind="action",
                        inputs={"command": "string"},
                        effects=("execute shell command",),
                        outputs={"exit_code": "integer", "stdout": "string", "stderr": "string"},
                        failure_modes=("shell_unavailable", "command_failed", "action_failed"),
                    ),
                ),
            ),
        )
    )
