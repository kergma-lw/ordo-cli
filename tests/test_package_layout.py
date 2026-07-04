import unittest

from ordo import (
    Connector,
    Diagnostic,
    Mode,
    OperationRef,
    Profile,
    RuntimeResult,
    RuntimeStatus,
    Workflow,
)
from ordo.introspection import (
    INTROSPECTION_VERSION,
    build_introspection_envelope,
    describe_capabilities,
    describe_errors,
    describe_operations,
    describe_pattern_hints,
    describe_playbook_contract,
    describe_profile_contract,
    describe_state_contract,
    describe_system,
    describe_workflow_contract,
)
from ordo.runtime.value_expressions import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS


class PackageLayoutSmokeTest(unittest.TestCase):
    def test_top_level_exports_are_importable(self) -> None:
        workflow = Workflow(version=0, workflow="demo")
        profile = Profile(name="default")
        connector = Connector(namespace="gh")
        diagnostic = Diagnostic(code="demo", level="info", message="ok")
        result = RuntimeResult(mode=Mode.CHECK, status=RuntimeStatus.OK)
        operation_ref = OperationRef(uses="gh.issue")

        self.assertEqual(workflow.version, 0)
        self.assertEqual(profile.name, "default")
        self.assertEqual(connector.namespace, "gh")
        self.assertEqual(diagnostic.code, "demo")
        self.assertEqual(result.mode, Mode.CHECK)
        self.assertEqual(operation_ref.uses, "gh.issue")
        self.assertEqual(INTROSPECTION_VERSION, 1)
        self.assertIn("introspection_version", build_introspection_envelope())
        self.assertIn("capabilities", describe_capabilities())
        self.assertEqual(describe_errors()["document_kind"], "error_taxonomy")
        self.assertIn("connectors", describe_operations())
        self.assertEqual(describe_pattern_hints()["document_kind"], "pattern_hints")
        self.assertEqual(describe_playbook_contract()["document_kind"], "playbook")
        self.assertEqual(describe_profile_contract()["document_kind"], "profile")
        self.assertEqual(describe_state_contract()["document_kind"], "state_contract")
        self.assertIn("sections", describe_system())
        self.assertEqual(describe_workflow_contract()["document_kind"], "workflow")
        self.assertIn("lower", VALUE_EXPRESSION_FILTERS)
        self.assertIn("format", VALUE_EXPRESSION_BUILTINS)


if __name__ == "__main__":
    unittest.main()
