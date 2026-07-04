import unittest

from ordo.introspection import describe_errors, describe_system
from ordo.model.error_taxonomy import ERROR_TAXONOMY
from ordo.model.runtime import RuntimeStatus


class IntrospectionErrorsTest(unittest.TestCase):
    def test_error_taxonomy_publishes_major_failure_classes(self) -> None:
        payload = describe_errors()

        classes = {item["name"]: item for item in payload["failure_classes"]}
        self.assertIn("validation_error", classes["validation"]["runtime_statuses"])
        self.assertIn("runtime.value.expression_builtin_unsupported", classes["unsupported_feature"]["example_codes"])
        self.assertIn("runtime.state.read_failed", classes["execution_or_io"]["example_codes"])

    def test_error_taxonomy_stays_aligned_with_runtime_statuses_and_contract(self) -> None:
        payload = describe_errors()

        published_statuses = {status for item in payload["failure_classes"] for status in item["runtime_statuses"]}
        self.assertTrue({status.value for status in RuntimeStatus}.issuperset(published_statuses))
        self.assertEqual(payload, ERROR_TAXONOMY)

    def test_root_introspection_publishes_errors_section(self) -> None:
        payload = describe_system()

        self.assertEqual(payload["sections"]["discovery"]["sections"]["errors"]["producer"], "describe_errors")
        self.assertIn("errors", payload["sections"])


if __name__ == "__main__":
    unittest.main()
