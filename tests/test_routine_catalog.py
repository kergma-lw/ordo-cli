import tempfile
import textwrap
import unittest
from pathlib import Path

from ordo.routines import RoutineRegistryError, inspect_routine, list_routines


class RoutineCatalogTest(unittest.TestCase):
    def test_list_routines_returns_declared_metadata(self) -> None:
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
                        summary: Run the main check routine.
                        args:
                          count:
                            type: integer
                            required: true
                        implementation:
                          argv: [".ordo/scripts/demo-check"]
                        failure_modes: [check_failed]
                      demo.inspect:
                        kind: probe
                        summary: Inspect data.
                        implementation:
                          argv: [".ordo/scripts/demo-inspect"]
                        outputs:
                          mode: data
                        failure_modes: [probe_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            entries = list_routines(cwd=root)

        self.assertEqual([entry.id for entry in entries], ["demo.check", "demo.inspect"])
        self.assertEqual(entries[0].kind, "action")
        self.assertEqual(entries[0].args, ("count",))
        self.assertEqual(entries[1].kind, "probe")

    def test_inspect_routine_returns_declared_contract(self) -> None:
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
                        summary: Run the main check routine.
                        implementation:
                          argv: [".ordo/scripts/demo-check"]
                        failure_modes: [check_failed]
                    """
                ).strip()
                + "\n",
                encoding="utf-8",
            )

            entry = inspect_routine("demo.check", cwd=root)

        self.assertEqual(entry.id, "demo.check")
        self.assertEqual(entry.summary, "Run the main check routine.")
        self.assertEqual(entry.implementation.argv, (".ordo/scripts/demo-check",))

    def test_inspect_routine_reports_missing_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".ordo").mkdir(parents=True)
            (root / ".ordo" / "routines.yaml").write_text(
                "version: 1\nroutines: {}\n",
                encoding="utf-8",
            )

            with self.assertRaises(RoutineRegistryError) as ctx:
                inspect_routine("demo.check", cwd=root)

        self.assertEqual(ctx.exception.diagnostics[0].code, "routine.registry.missing_id")


if __name__ == "__main__":
    unittest.main()
