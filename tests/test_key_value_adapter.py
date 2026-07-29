import unittest

from ordo.model.workflow import Workflow
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value


class KeyValueAdapterTest(unittest.TestCase):
    def test_parses_flat_mapping_from_colon_separated_lines(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": 'host: "db.internal"\nport: 5432\nmode : readonly'})

        value = resolve_runtime_value('${key_value with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(value, {"host": "db.internal", "port": "5432", "mode": "readonly"})

    def test_splits_on_first_separator_only(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "message: hello:world"})

        value = resolve_runtime_value('${key_value with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(value, {"message": "hello:world"})

    def test_allows_empty_values(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "empty:   "})

        value = resolve_runtime_value('${key_value with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(value, {"empty": ""})

    def test_ignores_empty_lines(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "\nalpha: one\n\n beta: two \n"})

        value = resolve_runtime_value('${key_value with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(value, {"alpha": "one", "beta": "two"})

    def test_requires_string_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": ["hello"]})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${key_value with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_root_value")

    def test_requires_non_empty_separator(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "alpha: one", "separator": ""})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${key_value with{root: inputs.body, separator: inputs.separator}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_parameter")

    def test_rejects_lines_without_separator(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "alpha"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${key_value with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_parameter")

    def test_rejects_empty_keys(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": " : value"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${key_value with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_parameter")

    def test_rejects_duplicate_keys(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "alpha: one\nalpha: two"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${key_value with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_ambiguous")

    def test_treats_unmatched_quotes_as_literal_text(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": 'quote: "unterminated'})

        value = resolve_runtime_value('${key_value with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(value, {"quote": '"unterminated'})

    def test_rejects_non_empty_adapter_body_in_mvp(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "alpha: one"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${key_value.anything with{root: inputs.body, separator: ":"}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_path")


if __name__ == "__main__":
    unittest.main()
