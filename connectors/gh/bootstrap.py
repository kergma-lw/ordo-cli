"""GitHub family bootstrap contract."""

from ordo.model.connector import ConnectorBootstrap

BOOTSTRAP = ConnectorBootstrap(
    prerequisites=("gh binary available", "GitHub auth available"),
    context_fields=("host", "viewer", "scopes"),
)
