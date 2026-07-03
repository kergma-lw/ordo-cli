import json
import tempfile
import unittest
from pathlib import Path

from ordo.model.workflow import Workflow
from ordo.runtime.state import (
    STATE_FILE_VERSION,
    RuntimeStateError,
    RuntimeStateRegistry,
    delete_state_value,
    read_state_document,
    read_state_value,
    write_state_document,
    write_state_value,
)


class RuntimeStateStorageTest(unittest.TestCase):
    def test_registry_resolves_relative_state_locations_against_base_dir(self) -> None:
        workflow = Workflow(version=0, workflow="open-task", states={"task_state": ".ordo/task-state.json"})

        registry = RuntimeStateRegistry.from_workflow(workflow, base_dir="/tmp/ordo-runtime-state")

        self.assertEqual(
            registry.require("task_state").path,
            Path("/tmp/ordo-runtime-state/.ordo/task-state.json"),
        )

    def test_read_missing_state_file_returns_empty_versioned_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="open-task", states={"task_state": "task-state.json"})
            registry = RuntimeStateRegistry.from_workflow(workflow, base_dir=temp_dir)

            document = read_state_document(registry.require("task_state"))

            self.assertEqual(document, {"version": STATE_FILE_VERSION, "values": {}})

    def test_write_and_delete_state_value_persist_versioned_file_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="open-task", states={"task_state": "task-state.json"})
            location = RuntimeStateRegistry.from_workflow(workflow, base_dir=temp_dir).require("task_state")

            document = read_state_document(location)
            write_state_value(document, key="owner/repo#1", fields=("branch",), value="feature/1")
            write_state_document(location, document)

            persisted = json.loads(location.path.read_text(encoding="utf-8"))
            self.assertEqual(
                persisted,
                {
                    "version": STATE_FILE_VERSION,
                    "values": {"owner/repo#1": {"branch": "feature/1"}},
                },
            )

            loaded = read_state_document(location)
            self.assertEqual(read_state_value(loaded, key="owner/repo#1", fields=("branch",)), "feature/1")
            self.assertTrue(delete_state_value(loaded, key="owner/repo#1", fields=("branch",)))
            self.assertEqual(read_state_value(loaded, key="owner/repo#1", fields=("branch",)), None)

    def test_missing_state_declaration_raises_structured_error(self) -> None:
        registry = RuntimeStateRegistry.from_workflow(Workflow(version=0, workflow="open-task"))

        with self.assertRaises(RuntimeStateError) as exc_info:
            registry.require("task_state")

        self.assertEqual(exc_info.exception.code, "runtime.state.declaration_missing")

    def test_invalid_state_file_shape_raises_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="open-task", states={"task_state": "task-state.json"})
            location = RuntimeStateRegistry.from_workflow(workflow, base_dir=temp_dir).require("task_state")
            location.path.write_text('{"version": 1, "values": []}\n', encoding="utf-8")

            with self.assertRaises(RuntimeStateError) as exc_info:
                read_state_document(location)

            self.assertEqual(exc_info.exception.code, "runtime.state.invalid_shape")


if __name__ == "__main__":
    unittest.main()
