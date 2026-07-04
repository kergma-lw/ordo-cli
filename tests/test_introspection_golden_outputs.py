import json
import unittest
from pathlib import Path

from ordo.introspection import describe_system


class IntrospectionGoldenOutputTest(unittest.TestCase):
    def test_root_introspection_matches_golden(self) -> None:
        actual = describe_system()
        expected = json.loads((Path("tests/golden") / "introspection_root.json").read_text(encoding="utf-8"))

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
