import textwrap
import tempfile
import unittest
from pathlib import Path

from ordo.runtime import load_workflow_text, validate_workflow_document, validate_workflow_semantics
from ordo.routines import load_routine_registry


class RoutineWorkflowValidationTest(unittest.TestCase):
    def test_routine_step_shape_accepts_id_and_args(self) -> None:
        report = validate_workflow_document(
            {
                "version": 0,
                "workflow": "demo",
                "blocks": [{"guards": []}, {"steps": [{"name": "run-check", "uses": "routine.demo.check", "with": {"args": {"enabled": True}}}]}],
            }
        )

        self.assertTrue(report.ok)

    def test_routine_step_rejects_inline_command_fields(self) -> None:
        report = validate_workflow_document(
            {
                "version": 0,
                "workflow": "demo",
                "blocks": [{"guards": []}, {"steps": [{"name": "run-check", "uses": "routine.demo.check", "with": {"command": "echo nope"}}]}],
            }
        )

        self.assertEqual(report.status.name, "VALIDATION_ERROR")
        self.assertEqual(report.diagnostics[0].code, "validation.unknown_field")

    def test_routine_step_requires_id_field(self) -> None:
        report = validate_workflow_document(
            {
                "version": 0,
                "workflow": "demo",
                "blocks": [{"guards": []}, {"steps": [{"name": "run-check", "uses": "routine."}]}],
            }
        )

        self.assertEqual(report.status.name, "VALIDATION_ERROR")
        self.assertEqual(report.diagnostics[0].code, "validation.uses.pattern")

    def test_routine_semantics_reject_unknown_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      demo.check:
                        kind: action
                        summary: Run one check.
                        implementation:
                          argv: [".ordo/scripts/demo-check"]
                        failure_modes: [check_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            registry = load_routine_registry(cwd=root)
            workflow = load_workflow_text(
                textwrap.dedent(
                    """
                    version: 0
                    workflow: demo
                    blocks:
                      - guards: []
                      - steps:
                          - name: run-check
                            uses: routine.demo.missing
                    """
                ).strip()
            )

            report = validate_workflow_semantics(workflow, routine_registry=registry)

        self.assertEqual(report.status.name, "VALIDATION_ERROR")
        self.assertEqual(report.diagnostics[0].code, "validation.workflow.routine.unknown_id")

    def test_routine_semantics_reject_missing_required_args(self) -> None:
        registry, workflow = self._registry_and_workflow(
            registry_body="""
            version: 1
            routines:
              demo.check:
                kind: action
                summary: Run one check.
                args:
                  count:
                    type: integer
                    required: true
                implementation:
                  argv: [".ordo/scripts/demo-check", "{count}"]
                failure_modes: [check_failed]
            """,
            workflow_body="""
            version: 0
            workflow: demo
            blocks:
              - guards: []
              - steps:
                  - name: run-check
                    uses: routine.demo.check
            """,
        )

        report = validate_workflow_semantics(workflow, routine_registry=registry)

        self.assertEqual(report.diagnostics[0].code, "validation.workflow.routine.arg_missing")

    def test_routine_semantics_reject_extra_args(self) -> None:
        registry, workflow = self._registry_and_workflow(
            registry_body="""
            version: 1
            routines:
              demo.check:
                kind: action
                summary: Run one check.
                implementation:
                  argv: [".ordo/scripts/demo-check"]
                failure_modes: [check_failed]
            """,
            workflow_body="""
            version: 0
            workflow: demo
            blocks:
              - guards: []
              - steps:
                  - name: run-check
                    uses: routine.demo.check
                    with:
                      args:
                        nope: true
            """,
        )

        report = validate_workflow_semantics(workflow, routine_registry=registry)

        self.assertEqual(report.diagnostics[0].code, "validation.workflow.routine.arg_unknown")

    def test_routine_semantics_reject_type_mismatch(self) -> None:
        registry, workflow = self._registry_and_workflow(
            registry_body="""
            version: 1
            routines:
              demo.check:
                kind: action
                summary: Run one check.
                args:
                  count:
                    type: integer
                    required: true
                implementation:
                  argv: [".ordo/scripts/demo-check", "{count}"]
                failure_modes: [check_failed]
            """,
            workflow_body="""
            version: 0
            workflow: demo
            blocks:
              - guards: []
              - steps:
                  - name: run-check
                    uses: routine.demo.check
                    with:
                      args:
                        count: nope
            """,
        )

        report = validate_workflow_semantics(workflow, routine_registry=registry)

        self.assertEqual(report.diagnostics[0].code, "validation.workflow.value_expr.root")

    def test_routine_semantics_emit_exception_path_warning(self) -> None:
        registry, workflow = self._registry_and_workflow(
            registry_body="""
            version: 1
            routines:
              demo.check:
                kind: action
                summary: Run one check.
                implementation:
                  argv: [".ordo/scripts/demo-check"]
                failure_modes: [check_failed]
            """,
            workflow_body="""
            version: 0
            workflow: demo
            blocks:
              - guards: []
              - steps:
                  - name: run-check
                    uses: routine.demo.check
            """,
        )

        report = validate_workflow_semantics(workflow, routine_registry=registry)

        self.assertTrue(report.ok)
        self.assertTrue(any(d.code == "validation.workflow.routine.exception_path" for d in report.diagnostics))

    def _registry_and_workflow(self, *, registry_body: str, workflow_body: str):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / ".ordo").mkdir(parents=True)
        (root / ".ordo" / "routines.yaml").write_text(textwrap.dedent(registry_body).strip() + "\n", encoding="utf-8")
        registry = load_routine_registry(cwd=root)
        workflow = load_workflow_text(textwrap.dedent(workflow_body).strip())
        return registry, workflow


if __name__ == "__main__":
    unittest.main()
