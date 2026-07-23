import unittest

from ordo.model.workflow import Workflow
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value


class TextAdapterTest(unittest.TestCase):
    def test_lines_projection_returns_empty_collection_for_empty_root(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": ""})

        value = resolve_runtime_value('${text.lines with{root: inputs.body}}', workflow)

        self.assertEqual(value, [])

    def test_lines_projection_returns_all_lines(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "alpha\nbeta\ngamma"})

        value = resolve_runtime_value('${text.lines with{root: inputs.body}}', workflow)

        self.assertEqual(value, ["alpha", "beta", "gamma"])

    def test_find_returns_unique_match_text(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello world"})

        value = resolve_runtime_value('${text.find("world") with{root: inputs.body}}', workflow)

        self.assertEqual(value, "world")

    def test_finds_returns_non_overlapping_matches_in_source_order(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "banana"})

        value = resolve_runtime_value('${text.finds("ana") with{root: inputs.body}}', workflow)

        self.assertEqual(value, ["ana"])

    def test_find_reports_not_found_when_missing(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${text.find("world") with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_not_found")

    def test_find_reports_ambiguity_for_multiple_matches(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello hello"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${text.find("hello") with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_ambiguous")

    def test_before_and_after_narrow_scope_around_unique_anchor(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello world"})

        before = resolve_runtime_value('${text.before(" world") with{root: inputs.body}}', workflow)
        after = resolve_runtime_value('${text.after("hello ") with{root: inputs.body}}', workflow)

        self.assertEqual(before, "hello")
        self.assertEqual(after, "world")

    def test_before_matches_literal_substrings_inside_words(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "zappier"})

        value = resolve_runtime_value('${text.before("z") with{root: inputs.body}}', workflow)

        self.assertEqual(value, "")

    def test_index_selects_one_line_focus(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "alpha\nbeta\ngamma"})

        value = resolve_runtime_value('${text.lines[1] with{root: inputs.body}}', workflow)

        self.assertEqual(value, "beta")

    def test_selected_line_focus_supports_further_narrowing(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "name: world\nother: value"})

        value = resolve_runtime_value('${text.lines[0].after(": ") with{root: inputs.body}}', workflow)

        self.assertEqual(value, "world")

    def test_selected_match_focus_supports_further_narrowing(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "BEGIN: world END"})

        value = resolve_runtime_value('${text.find("world END").before(" END") with{root: inputs.body}}', workflow)

        self.assertEqual(value, "world")

    def test_collection_focus_rejects_further_narrowing(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello\nworld"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${text.lines.after("h") with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_path")

    def test_index_reports_not_found_when_out_of_range(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "hello"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${text.lines[1] with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_not_found")

    def test_requires_string_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": ["hello"]})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${text.lines with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_root_value")


if __name__ == "__main__":
    unittest.main()
