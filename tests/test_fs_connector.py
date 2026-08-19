import importlib
import tempfile
import unittest
from pathlib import Path

from connectors.fs.probes.file import _split_basename
from ordo.connectors.operations import evaluate_probe
from ordo.connectors.registry import get_public_connector_registry
from ordo.model.workflow import Guard, OperationRef, Workflow
from ordo.runtime.resolution import ResolvedOperation


class FsConnectorTest(unittest.TestCase):
    def test_fs_file_probe_module_publishes_through_info_hook(self) -> None:
        fs_file_module = importlib.import_module("connectors.fs.probes.file")
        text_info = fs_file_module.info()

        self.assertEqual(text_info.name, "file")
        self.assertEqual(text_info.kind, "probe")
        self.assertIs(text_info.handler, fs_file_module.run)

    def test_fs_connector_contract_publishes_file_probe(self) -> None:
        operation = get_public_connector_registry().get_operation("fs.file")

        self.assertIsNotNone(operation)
        self.assertIsNone(get_public_connector_registry().get_operation("fs.text"))
        self.assertEqual(operation.kind, "probe")
        self.assertEqual(operation.inputs["path"], "string")
        self.assertEqual(operation.outputs["basename"], "string")
        self.assertEqual(operation.outputs["filename_without_extension"], "string")
        self.assertEqual(operation.outputs["extension"], "string")
        self.assertEqual(operation.outputs["content"], "string")
        self.assertEqual(operation.outputs["kind"], "string")
        self.assertEqual(operation.failure_modes, ("path_not_found", "not_a_file", "content_unavailable", "probe_failed"))

    def test_fs_file_probe_reads_file_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.txt"
            path.write_text("alpha: one\nbeta: two\n", encoding="utf-8")
            workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("fs.file", with_={"path": str(path)})),), steps=())
            operation = get_public_connector_registry().get_operation("fs.file")
            resolved = ResolvedOperation("fs.file", "fs", operation, "public")  # type: ignore[arg-type]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.outputs["path"], str(path))
        self.assertEqual(result.outputs["basename"], "config.txt")
        self.assertEqual(result.outputs["filename_without_extension"], "config")
        self.assertEqual(result.outputs["extension"], "txt")
        self.assertTrue(result.outputs["exists"])
        self.assertEqual(result.outputs["kind"], "file")
        self.assertEqual(result.outputs["content"], "alpha: one\nbeta: two\n")
        self.assertEqual(result.outputs["size"], len("alpha: one\nbeta: two\n".encode("utf-8")))
        self.assertRegex(result.outputs["permissions"], r"^[0-7]{4}$")
        self.assertTrue(result.outputs["modified_at"].endswith("Z"))
        self.assertEqual(result.outputs["line_count"], 2)

    def test_fs_file_probe_derives_path_outputs_for_edge_case_basenames(self) -> None:
        cases = (
            ("archive.tar.gz", "archive.tar", "gz"),
            ("README", "README", ""),
            (".env", "", "env"),
            (".gitignore.local", ".gitignore", "local"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            for basename, expected_name, expected_extension in cases:
                path = Path(temp_dir) / basename
                path.write_text("value\n", encoding="utf-8")
                workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("fs.file", with_={"path": str(path)})),), steps=())
                operation = get_public_connector_registry().get_operation("fs.file")
                resolved = ResolvedOperation("fs.file", "fs", operation, "public")  # type: ignore[arg-type]

                result = evaluate_probe(resolved, workflow)

                self.assertEqual(result.status, "ok")
                with self.subTest(basename=basename):
                    self.assertEqual(result.outputs["basename"], basename)
                    self.assertEqual(result.outputs["filename_without_extension"], expected_name)
                    self.assertEqual(result.outputs["extension"], expected_extension)

    def test_fs_file_probe_reports_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.txt"
            workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("fs.file", with_={"path": str(path)})),), steps=())
            operation = get_public_connector_registry().get_operation("fs.file")
            resolved = ResolvedOperation("fs.file", "fs", operation, "public")  # type: ignore[arg-type]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "path_not_found")
        self.assertEqual(result.diagnostics[0].code, "probe.fs_file.path_not_found")

    def test_fs_file_probe_rejects_directory_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("fs.file", with_={"path": temp_dir})),), steps=())
            operation = get_public_connector_registry().get_operation("fs.file")
            resolved = ResolvedOperation("fs.file", "fs", operation, "public")  # type: ignore[arg-type]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "not_a_file")
        self.assertEqual(result.diagnostics[0].code, "probe.fs_file.not_a_file")

    def test_fs_file_probe_reports_content_unavailable_for_non_utf8_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "binary.bin"
            path.write_bytes(b"\xff\xfe\x00\x00")
            workflow = Workflow(version=0, workflow="demo", guards=(Guard(OperationRef("fs.file", with_={"path": str(path)})),), steps=())
            operation = get_public_connector_registry().get_operation("fs.file")
            resolved = ResolvedOperation("fs.file", "fs", operation, "public")  # type: ignore[arg-type]

            result = evaluate_probe(resolved, workflow)

        self.assertEqual(result.status, "content_unavailable")
        self.assertEqual(result.diagnostics[0].code, "probe.fs_file.content_unavailable")

    def test_split_basename_matches_fs_file_contract(self) -> None:
        cases = (
            ("foo.txt", ("foo", "txt")),
            ("archive.tar.gz", ("archive.tar", "gz")),
            ("README", ("README", "")),
            (".env", ("", "env")),
            (".gitignore.local", (".gitignore", "local")),
        )

        for basename, expected in cases:
            with self.subTest(basename=basename):
                self.assertEqual(_split_basename(basename), expected)


if __name__ == "__main__":
    unittest.main()
