"""Contract and execution coverage for runtime.uuid.generate."""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

from connectors.runtime.actions.uuid import generate
from ordo.model.runtime import RuntimeStatus
from ordo.runtime import check_workflow, execute_workflow, load_workflow_text, plan_workflow, review_workflow

from tests.support import STANDARD_CONNECTOR_PROVIDER


def test_runtime_uuid_generate_returns_distinct_canonical_version_four_values():
    first = generate.run(None)
    second = generate.run(None)

    assert first.status == "ok"
    assert second.status == "ok"
    assert first.outputs["uuid"] != second.outputs["uuid"]
    for result in (first, second):
        value = result.outputs["uuid"]
        assert isinstance(value, str)
        assert value == value.lower()
        assert UUID(value).version == 4


def test_runtime_uuid_generate_is_available_to_later_registered_steps_during_run():
    workflow = load_workflow_text("""version: 0
workflow: uuid-flow
blocks:
- steps:
  - name: generate-request-id
    uses: runtime.uuid.generate
    register: request_id
  - name: copy-request-id
    value: step.request_id.outputs.uuid
    register: copied_request_id
""")

    result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

    assert result.status == RuntimeStatus.OK
    generated = workflow.step_results["request_id"]["outputs"]["uuid"]
    copied = workflow.step_results["copied_request_id"]["outputs"]["value"]
    assert copied == generated
    assert UUID(generated).version == 4


def test_runtime_uuid_generate_is_not_executed_by_pre_run_modes():
    workflow = load_workflow_text("""version: 0
workflow: uuid-preflight
blocks:
- steps:
  - name: generate-request-id
    uses: runtime.uuid.generate
    register: request_id
""")

    with patch.object(generate, "uuid4", return_value=UUID("12345678-1234-4abc-8def-123456789abc")) as uuid4:
        check_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        plan_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
        uuid4.assert_not_called()

        result = execute_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)

    assert result.status == RuntimeStatus.OK
    uuid4.assert_called_once_with()
