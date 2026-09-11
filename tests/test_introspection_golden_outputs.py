import json
import unittest
from pathlib import Path

from ordo.introspection import describe_system


class IntrospectionGoldenOutputTest(unittest.TestCase):
    def test_root_introspection_matches_golden(self) -> None:
        actual = describe_system()
        expected = json.loads((Path("tests/golden") / "introspection_root.json").read_text(encoding="utf-8"))

        self.assertEqual(actual["introspection_version"], expected["introspection_version"])
        self.assertEqual(actual["sections"]["discovery"]["entrypoint"], expected["sections"]["discovery"]["entrypoint"])
        self.assertTrue(
            set(expected["sections"]["discovery"]["sections"]).issubset(
                set(actual["sections"]["discovery"]["sections"])
            )
        )
        self.assertTrue(set(expected["sections"]).issubset(set(actual["sections"])))
        self.assertIn("operations", actual["sections"])
        self.assertIn("capabilities", actual["sections"])

        actual_gh = next(
            connector for connector in actual["sections"]["operations"]["connectors"]
            if connector["namespace"] == "gh"
        )
        expected_gh = next(
            connector for connector in expected["sections"]["operations"]["connectors"]
            if connector["namespace"] == "gh"
        )
        actual_operations = {operation["name"]: operation for operation in actual_gh["operations"]}
        expected_operations = {operation["name"]: operation for operation in expected_gh["operations"]}
        for name in ("pr", "pr.checks", "pr.create", "pr.list", "pr.merge", "pr.merge.request"):
            with self.subTest(operation=name):
                self.assertEqual(actual_operations[name], expected_operations[name])


if __name__ == "__main__":
    unittest.main()
