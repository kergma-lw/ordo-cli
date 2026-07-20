import unittest

from ordo.model.workflow import Workflow
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value


class MarkdownAdapterTest(unittest.TestCase):
    def test_read_path_selects_unique_list_in_named_section(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "body": "# Overview\n\n## Tasks\n- ship\n- verify\n",
            },
        )

        value = resolve_runtime_value(
            '${markdown["Tasks"].list with{root: inputs.body}}',
            workflow,
        )

        self.assertEqual(
            value,
            {
                "kind": "list",
                "text": "- ship\n- verify",
                "items": ["ship", "verify"],
            },
        )

    def test_read_path_reports_not_found_for_missing_section(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Notes\n- ship\n"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${markdown["Tasks"].list with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_not_found")

    def test_read_path_reports_ambiguity_for_multiple_lists(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "body": "## Tasks\n- one\n\n- two\n",
            },
        )

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${markdown["Tasks"].list with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_ambiguous")

    def test_read_path_allows_explicit_many_selection_and_index(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "body": "## Tasks\n- one\n\n- two\n",
            },
        )

        value = resolve_runtime_value('${markdown["Tasks"].lists[1] with{root: inputs.body}}', workflow)

        self.assertEqual(
            value,
            {
                "kind": "list",
                "text": "- two",
                "items": ["two"],
            },
        )

    def test_read_path_supports_explicit_blocks_selector(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "body": "## Notes\nfirst paragraph\n\nsecond paragraph\n",
            },
        )

        value = resolve_runtime_value('${markdown["Notes"].blocks("paragraph")[1] with{root: inputs.body}}', workflow)

        self.assertEqual(
            value,
            {
                "kind": "paragraph",
                "text": "second paragraph",
            },
        )

    def test_write_path_appends_item_and_returns_updated_root(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Tasks\n- ship\n", "item": "verify"})

        value = resolve_runtime_value(
            '${markdown["Tasks"].list->append_item(item) with{root: inputs.body, item: inputs.item}}',
            workflow,
        )

        self.assertEqual(value, "## Tasks\n\n- ship\n- verify")

    def test_write_path_auto_creates_missing_section_and_list(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "# Overview", "item": "verify"})

        value = resolve_runtime_value(
            '${markdown["Tasks"].list->append_item(item) with{root: inputs.body, item: inputs.item}}',
            workflow,
        )

        self.assertEqual(value, "# Overview\n\n## Tasks\n\n- verify")

    def test_write_path_preserves_ambiguity_instead_of_creating_through_it(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Tasks\n\n## Tasks", "item": "verify"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value(
                '${markdown["Tasks"].list->append_item(item) with{root: inputs.body, item: inputs.item}}',
                workflow,
            )

        self.assertEqual(context.exception.code, "runtime.value.adapter_ambiguous")


if __name__ == "__main__":
    unittest.main()
