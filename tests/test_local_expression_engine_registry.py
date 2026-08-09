import unittest

from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS


class LocalExpressionEngineRegistryTest(unittest.TestCase):
    def test_supported_filters_are_published_in_canonical_registry(self) -> None:
        self.assertEqual(
            tuple(VALUE_EXPRESSION_FILTERS),
            (
                "lower",
                "trim",
                "slug",
                "eq",
                "ne",
                "not",
                "is_string",
                "is_number",
                "is_integer",
                "is_boolean",
                "in",
                "field",
                "lookup",
                "only",
                "flatten",
                "first",
                "last",
                "length",
                "unique",
            ),
        )
        self.assertEqual(VALUE_EXPRESSION_FILTERS["lower"].to_contract()["input_type"], "string")
        self.assertEqual(VALUE_EXPRESSION_FILTERS["slug"].to_contract()["output_type"], "string")
        self.assertEqual(VALUE_EXPRESSION_FILTERS["not"].to_contract()["output_type"], "boolean")
        self.assertEqual(VALUE_EXPRESSION_FILTERS["lookup"].to_contract()["argument_count"], 1)
        self.assertEqual(VALUE_EXPRESSION_FILTERS["length"].to_contract()["output_type"], "number")
        self.assertEqual(VALUE_EXPRESSION_FILTERS["only"].to_contract()["authored_form"], "only(field=value) / only(field!=value)")

    def test_supported_builtins_are_published_in_canonical_registry(self) -> None:
        self.assertEqual(tuple(VALUE_EXPRESSION_BUILTINS), ("format", "is_missing", "is_present"))
        self.assertEqual(VALUE_EXPRESSION_BUILTINS["format"].to_contract(), {"name": "format"})


if __name__ == "__main__":
    unittest.main()
