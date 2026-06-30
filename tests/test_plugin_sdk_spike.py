import importlib
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from ordo.connectors.registry import get_public_connector_registry
from connectors._family import assemble_family
from ordo.model.workflow import Workflow
from ordo.runtime.resolution import ResolvedOperation


class PluginSdkSpikeTest(unittest.TestCase):
    def test_assemble_family_discovers_publication_hook_and_adapts_probe_outcome(self) -> None:
        _ = get_public_connector_registry
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_spike_family(root)

            sys.path.insert(0, tmp_dir)
            try:
                bootstrap_module = importlib.import_module("demo_sdk_family.bootstrap")
                assembled = assemble_family(
                    package_name="demo_sdk_family",
                    namespace="demo",
                    bootstrap=bootstrap_module.BOOTSTRAP,
                )

                operation = assembled.connector.operations[0]
                resolved = ResolvedOperation("demo.branch", "demo", operation, "public")
                workflow = Workflow(version=0, workflow="demo", guards=(), steps=())

                with patch("subprocess.run") as run:
                    run.return_value.returncode = 0
                    run.return_value.stdout = "feature/test\n"
                    run.return_value.stderr = ""

                    result = assembled.probe_handlers["branch"](resolved, workflow)

                self.assertEqual(operation.name, "branch")
                self.assertEqual(operation.kind, "probe")
                self.assertEqual(result.status, "ok")
                self.assertEqual(result.observations["value"], "feature/test")
                self.assertEqual(result.raw["returncode"], 0)
            finally:
                sys.path.remove(tmp_dir)
                self._clear_demo_modules()

    def test_command_failure_mapping_adapts_into_runtime_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_spike_family(root)

            sys.path.insert(0, tmp_dir)
            try:
                bootstrap_module = importlib.import_module("demo_sdk_family.bootstrap")
                assembled = assemble_family(
                    package_name="demo_sdk_family",
                    namespace="demo",
                    bootstrap=bootstrap_module.BOOTSTRAP,
                )

                operation = assembled.connector.operations[0]
                resolved = ResolvedOperation("demo.branch", "demo", operation, "public")
                workflow = Workflow(version=0, workflow="demo", guards=(), steps=())

                with patch("subprocess.run") as run:
                    run.return_value.returncode = 128
                    run.return_value.stdout = ""
                    run.return_value.stderr = "fatal: not a git repository"

                    result = assembled.probe_handlers["branch"](resolved, workflow)

                self.assertEqual(result.status, "probe_failed")
                self.assertEqual(result.diagnostics[0].code, "operation.command_failed")
                self.assertEqual(result.raw["returncode"], 128)
            finally:
                sys.path.remove(tmp_dir)
                self._clear_demo_modules()

    def _write_spike_family(self, root: Path) -> None:
        package = root / "demo_sdk_family"
        probes = package / "probes"
        package.mkdir()
        probes.mkdir()

        (package / "__init__.py").write_text("", encoding="utf-8")
        (probes / "__init__.py").write_text("", encoding="utf-8")
        (package / "bootstrap.py").write_text(
            textwrap.dedent(
                """
                from ordo.model.connector import ConnectorBootstrap

                BOOTSTRAP = ConnectorBootstrap(
                    prerequisites=("git available",),
                    context_fields=("repository_root",),
                )
                """
            ),
            encoding="utf-8",
        )
        (probes / "branch.py").write_text(
            textwrap.dedent(
                """
                from ordo.plugin_sdk import ok, probe


                def info():
                    return probe(
                        name="branch",
                        outputs={"value": "string"},
                        failure_modes=("git_unavailable", "probe_failed"),
                        handler=run,
                    )


                def run(ctx):
                    command = ctx.command(
                        ["git", "branch", "--show-current"],
                        failures={
                            "os_error": "git_unavailable",
                            "nonzero": "probe_failed",
                        },
                    )
                    return ok(
                        summary="Current branch inspected successfully",
                        outputs={"value": command.stdout.strip()},
                        raw=command.raw,
                    )
                """
            ),
            encoding="utf-8",
        )

    def _clear_demo_modules(self) -> None:
        for name in tuple(sys.modules):
            if name == "demo_sdk_family" or name.startswith("demo_sdk_family."):
                del sys.modules[name]


if __name__ == "__main__":
    unittest.main()
