import unittest

from ordo.introspection import describe_pattern_hints, describe_system
from ordo.model.pattern_hints import PATTERN_HINTS


class IntrospectionPatternHintsTest(unittest.TestCase):
    def test_pattern_hints_publish_small_guidance_layer(self) -> None:
        payload = describe_pattern_hints()

        hints = {item["name"]: item for item in payload["hints"]}
        self.assertEqual(hints["profiles.prefer_for_environment_differences"]["category"], "authoring_strategy")
        self.assertIn("profile_contract", hints["profiles.prefer_for_environment_differences"]["prefer"])
        self.assertIn("shell.command", hints["shell_command.use_as_capability_fallback"]["prefer"])

    def test_pattern_hints_stay_separate_from_contract_truth(self) -> None:
        payload = describe_pattern_hints()

        self.assertEqual(payload, PATTERN_HINTS)
        self.assertEqual(payload["document_kind"], "pattern_hints")

    def test_root_introspection_publishes_pattern_hints_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["pattern_hints"]["producer"], "describe_pattern_hints")
        self.assertIn("pattern_hints", payload["sections"])


if __name__ == "__main__":
    unittest.main()
