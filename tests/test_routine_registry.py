import tempfile
import textwrap
import unittest
from pathlib import Path

from ordo.routines import (
    ROUTINE_REGISTRY_DISCOVERY_PATH,
    RoutineRegistryError,
    discover_routine_registry_path,
    load_routine_registry,
)


class RoutineRegistryTest(unittest.TestCase):
    def test_discover_routine_registry_uses_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            registry_path = root / ".ordo" / "routines.yaml"
            registry_path.write_text("version: 1\nroutines: {}\n", encoding="utf-8")

            discovered = discover_routine_registry_path(cwd=root)

        self.assertEqual(discovered, registry_path)

    def test_discover_routine_registry_reports_missing_default_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(RoutineRegistryError) as ctx:
                discover_routine_registry_path(cwd=temp_dir)

        diagnostic = ctx.exception.diagnostics[0]
        self.assertEqual(diagnostic.code, "routine.discovery.missing")
        self.assertEqual(diagnostic.details["expected_path"], str(Path(temp_dir) / ROUTINE_REGISTRY_DISCOVERY_PATH))

    def test_load_routine_registry_reads_valid_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            registry_path = root / ".ordo" / "routines.yaml"
            registry_path.write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      inspect.issue:
                        kind: probe
                        summary: Inspect one issue.
                        args:
                          repo:
                            type: string
                            required: true
                        implementation:
                          argv: [".ordo/scripts/inspect-issue", "{repo}"]
                        failure_modes:
                          - issue_not_found
                          - helper_failed
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            registry = load_routine_registry(cwd=root)

        self.assertEqual(str(registry.path), str(registry_path))
        self.assertEqual(set(registry.routines), {"inspect.issue"})
        entry = registry.routines["inspect.issue"]
        self.assertEqual(entry.kind, "probe")
        self.assertEqual(entry.summary, "Inspect one issue.")
        self.assertEqual(entry.args["repo"].type_name, "string")
        self.assertTrue(entry.args["repo"].required)
        self.assertEqual(entry.implementation.argv, (".ordo/scripts/inspect-issue", "{repo}"))
        self.assertEqual(entry.failure_modes, ("issue_not_found", "helper_failed"))

    def test_load_routine_registry_rejects_unknown_top_level_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "routines.yaml").write_text(
                "version: 1\nroutines: {}\nextra: true\n",
                encoding="utf-8",
            )

            with self.assertRaises(RoutineRegistryError) as ctx:
                load_routine_registry(cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "routine.registry.unknown_field")

    def test_load_routine_registry_rejects_unknown_entry_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      inspect.issue:
                        kind: probe
                        summary: Inspect one issue.
                        implementation:
                          argv: [".ordo/scripts/inspect-issue"]
                        failure_modes: [helper_failed]
                        extra: true
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(RoutineRegistryError) as ctx:
                load_routine_registry(cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].path, ("routines", "inspect.issue", "extra"))

    def test_load_routine_registry_rejects_malformed_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "routines.yaml").write_text("version: [\n", encoding="utf-8")

            with self.assertRaises(RoutineRegistryError) as ctx:
                load_routine_registry(cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "load.yaml.syntax")

    def test_load_routine_registry_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      inspect.issue:
                        kind: probe
                        summary: Inspect one issue.
                        implementation:
                          argv: [".ordo/scripts/inspect-issue"]
                        failure_modes: [helper_failed]
                      inspect.issue:
                        kind: probe
                        summary: Duplicate.
                        implementation:
                          argv: [".ordo/scripts/inspect-issue-2"]
                        failure_modes: [helper_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(RoutineRegistryError) as ctx:
                load_routine_registry(cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "routine.registry.duplicate_id")

    def test_load_routine_registry_rejects_missing_required_entry_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "routines.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 1
                    routines:
                      inspect.issue:
                        kind: probe
                        implementation:
                          argv: [".ordo/scripts/inspect-issue"]
                        failure_modes: [helper_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(RoutineRegistryError) as ctx:
                load_routine_registry(cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "routine.registry.summary")


if __name__ == "__main__":
    unittest.main()
