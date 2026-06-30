"""Git family bootstrap contract."""

from ordo.model.connector import ConnectorBootstrap

BOOTSTRAP = ConnectorBootstrap(
    prerequisites=("git binary available", "inside git repository"),
    context_fields=("repository_root", "current_branch"),
)
