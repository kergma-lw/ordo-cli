import unittest

from connectors._shared import require_input
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Workflow
from ordo.runtime.resolution import ResolvedOperation


class ConnectorSharedTest(unittest.TestCase):
    def test_require_input_prefers_materialized_resolved_inputs(self) -> None:
        registry = get_public_connector_registry()
        workflow = Workflow(version=0, workflow="demo", inputs={"repository": "ignored"})
        resolved = ResolvedOperation(
            reference="gh.issue",
            connector_namespace="gh",
            operation=registry.get_operation("gh.issue"),
            source="public",
            declared_with={"repository": "inputs.repository"},
            resolved_inputs={"repository": "kergma-lw/checklist-meta"},
        )

        value = require_input(workflow, resolved, "repository")

        self.assertEqual(value, "kergma-lw/checklist-meta")


if __name__ == "__main__":
    unittest.main()
