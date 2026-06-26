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


class PackageLayoutSmokeTest(unittest.TestCase):
    def test_top_level_exports_are_importable(self) -> None:
        workflow = Workflow(version=0, workflow="demo")
        profile = Profile(name="default")
        connector = Connector(namespace="gh")
        diagnostic = Diagnostic(code="demo", level="info", message="ok")
        result = RuntimeResult(mode=Mode.CHECK, status=RuntimeStatus.OK)
        operation_ref = OperationRef(uses="gh.issue.view")

        self.assertEqual(workflow.version, 0)
        self.assertEqual(profile.name, "default")
        self.assertEqual(connector.namespace, "gh")
        self.assertEqual(diagnostic.code, "demo")
        self.assertEqual(result.mode, Mode.CHECK)
        self.assertEqual(operation_ref.uses, "gh.issue.view")


if __name__ == "__main__":
    unittest.main()
