import unittest

from ordo.model.workflow import Step, Workflow
from ordo.runtime.preflight_interpreter import evaluate_preflight_value_step, store_preflight_register_output


class PreflightInterpreterTest(unittest.TestCase):
    def test_evaluates_pure_value_step_from_inputs(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"branch": "main"}, steps=())
        step = Step(name="copy", value="${inputs.branch}", register="branch")

        result = evaluate_preflight_value_step(step, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["value"], "main")

    def test_reports_structured_error_when_value_step_cannot_be_resolved(self) -> None:
        workflow = Workflow(version=0, workflow="demo", steps=())
        step = Step(name="copy", value="${inputs.branch}", register="branch")

        result = evaluate_preflight_value_step(step, workflow)

        self.assertEqual(result.status, "state_error")
        self.assertEqual(result.diagnostics[0].code, "runtime.value.input_missing")

    def test_stores_value_step_output_for_later_preflight_dataflow(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"branch": "main"}, steps=())
        step = Step(name="copy", value="${inputs.branch}", register="branch")

        result = evaluate_preflight_value_step(step, workflow)
        step_results = {}
        store_preflight_register_output("branch", result, step_results=step_results)

        self.assertEqual(step_results["branch"]["outputs"]["value"], "main")


if __name__ == "__main__":
    unittest.main()
