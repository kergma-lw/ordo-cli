import importlib
import tempfile
import unittest
from pathlib import Path

from ordo.connectors.operations import evaluate_probe
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Guard, OperationRef, Workflow
from ordo.runtime.resolution import ResolvedOperation


class FsConnectorTest(unittest.TestCase):
    def test_fs_text_probe_module_publishes_through_info_hook(self) -> None:
        fs_text_module = importlib.import_module("connectors.fs.probes.text")
        text_info = fs_text_module.info()

        self.assertEqual(text_info.name, "text")
        self.assertEqual(text_info.kind, "probe")
        self.assertIs(text_info.handler, fs_text_module.run)

    def test_fs_connector_contract_publishes_text_probe(self) -> None:
        operation = get_public_connector_registry().get_operation("fs.text")

        self.assertIsNotNone(operation)
        self.assertEqual(operation.kind, "probe")
        self.assertEqual(operation.inputs["path"], "string")
        self.assertEqual(operation.outputs["text"], "string")
        self.assertEqual(operation.failure_modes, ("path_not_found", "not_a_file", "not_text", "probe_failed"))

    def test_fs_text_probe_reads_plain_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.txt"
            path.write_text("alpha: one\nbeta: two\n", encoding="utf-8")
            workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("fs.text", with_={"path": str(path)})),), steps=())
            operation = get_public_connector_registry().get_operation("fs.text")
            resolved = ResolvedOperation("fs.text", "fs", operation, "public")  # type: ignore[arg-type]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["path"], str(path))
        self.assertEqual(result.outputs["text"], "alpha: one\nbeta: two\n")
        self.assertEqual(result.outputs["line_count"], 2)

    def test_fs_text_probe_reports_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.txt"
            workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("fs.text", with_={"path": str(path)})),), steps=())
            operation = get_public_connector_registry().get_operation("fs.text")
            resolved = ResolvedOperation("fs.text", "fs", operation, "public")  # type: ignore[arg-type]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "path_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.fs_text.path_not_found")

    def test_fs_text_probe_rejects_directory_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("fs.text", with_={"path": temp_dir})),), steps=())
            operation = get_public_connector_registry().get_operation("fs.text")
            resolved = ResolvedOperation("fs.text", "fs", operation, "public")  # type: ignore[arg-type]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "not_a_file")
        self.assertEqual(result.diagnostics[0].code, "probe.fs_text.not_a_file")

    def test_fs_text_probe_rejects_non_utf8_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "binary.bin"
            path.write_bytes(b"\xff\xfe\x00\x00")
            workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("fs.text", with_={"path": str(path)})),), steps=())
            operation = get_public_connector_registry().get_operation("fs.text")
            resolved = ResolvedOperation("fs.text", "fs", operation, "public")  # type: ignore[arg-type]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "not_text")
        self.assertEqual(result.diagnostics[0].code, "probe.fs_text.not_text")


if __name__ == "__main__":
    unittest.main()
