"""Shell family bootstrap contract."""

from ordo.model.connector import ConnectorBootstrap

BOOTSTRAP = ConnectorBootstrap(
    prerequisites=("supported shell available",),
    context_fields=("shell", "working_directory"),
)
