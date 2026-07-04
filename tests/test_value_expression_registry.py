import unittest

from ordo.runtime.value_expressions import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS


class ValueExpressionRegistryTest(unittest.TestCase):
    def test_supported_filters_are_published_in_canonical_registry(self) -> None:
        self.assertEqual(tuple(VALUE_EXPRESSION_FILTERS), ("lower", "trim", "slug", "eq", "ne", "not"))
        self.assertEqual(VALUE_EXPRESSION_FILTERS["lower"].to_contract()["input_type"], "string")
        self.assertEqual(VALUE_EXPRESSION_FILTERS["slug"].to_contract()["output_type"], "string")
        self.assertEqual(VALUE_EXPRESSION_FILTERS["not"].to_contract()["output_type"], "boolean")

    def test_supported_builtins_are_published_in_canonical_registry(self) -> None:
        self.assertEqual(tuple(VALUE_EXPRESSION_BUILTINS), ("format",))
        self.assertEqual(VALUE_EXPRESSION_BUILTINS["format"].to_contract(), {"name": "format"})


if __name__ == "__main__":
    unittest.main()
