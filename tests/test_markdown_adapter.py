import unittest

from ordo.model.workflow import Workflow
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value


class MarkdownAdapterTest(unittest.TestCase):
    def test_prelude_exists_for_empty_document(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": ""})

        value = resolve_runtime_value('${markdown.prelude with{root: inputs.body}}', workflow)

        self.assertEqual(value, {"kind": "prelude", "blocks": [], "text": ""})

    def test_prelude_exists_as_empty_for_heading_first_document(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Tasks\n- ship\n"})

        value = resolve_runtime_value('${markdown.prelude with{root: inputs.body}}', workflow)

        self.assertEqual(value, {"kind": "prelude", "blocks": [], "text": ""})

    def test_prelude_returns_leading_blocks_before_first_heading(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": "intro\n\n- one\n\n## Tasks\n- ship\n"},
        )

        value = resolve_runtime_value('${markdown.prelude with{root: inputs.body}}', workflow)

        self.assertEqual(
            value,
            {
                "kind": "prelude",
                "blocks": [
                    {"kind": "paragraph", "text": "intro"},
                    {"kind": "list", "text": "- one", "items": ["one"]},
                ],
                "text": "intro\n\n- one",
            },
        )

    def test_prelude_supports_further_block_selection(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "intro\n\n## Tasks\n- ship\n"})

        value = resolve_runtime_value('${markdown.prelude.paragraph with{root: inputs.body}}', workflow)

        self.assertEqual(value, {"kind": "paragraph", "text": "intro"})

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

    def test_read_path_supports_indexing_into_list_items(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "body": "# Overview\n\n## Tasks\n- ship\n- verify\n",
            },
        )

        value = resolve_runtime_value(
            '${markdown["Tasks"].list[1] with{root: inputs.body}}',
            workflow,
        )

        self.assertEqual(value, "verify")

    def test_read_path_supports_list_items_collection_view(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "body": "# Overview\n\n## Tasks\n- ship\n- verify\n",
            },
        )

        value = resolve_runtime_value(
            '${markdown["Tasks"].list_items with{root: inputs.body}}',
            workflow,
        )

        self.assertEqual(value, ["ship", "verify"])

    def test_read_path_supports_task_list_items_collection_view(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "body": "## Checklist\n- [ ] ship\n- [x] verify\n",
            },
        )

        value = resolve_runtime_value(
            '${markdown["Checklist"].task_list_items with{root: inputs.body}}',
            workflow,
        )

        self.assertEqual(value, ["ship", "verify"])

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

    def test_list_add_appends_new_item_and_returns_updated_root(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Tasks\n- ship\n", "item": "verify"})

        value = resolve_runtime_value(
            '${markdown["Tasks"].list->add(item) with{root: inputs.body, item: inputs.item}}',
            workflow,
        )

        self.assertEqual(value, "## Tasks\n\n- ship\n- verify")

    def test_list_add_preserves_nested_list_structure_at_current_level(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": "## Tasks\n- parent\n  - child\n", "item": "sibling"},
        )

        value = resolve_runtime_value(
            '${markdown["Tasks"].list->add(item) with{root: inputs.body, item: inputs.item}}',
            workflow,
        )

        self.assertEqual(value, "## Tasks\n\n- parent\n  - child\n- sibling")

    def test_list_add_auto_creates_missing_section_and_list(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "# Overview", "item": "verify"})

        value = resolve_runtime_value(
            '${markdown["Tasks"].list->add(item) with{root: inputs.body, item: inputs.item}}',
            workflow,
        )

        self.assertEqual(value, "# Overview\n\n## Tasks\n\n- verify")

    def test_list_add_preserves_ambiguity_instead_of_creating_through_it(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Tasks\n\n## Tasks", "item": "verify"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value(
                '${markdown["Tasks"].list->add(item) with{root: inputs.body, item: inputs.item}}',
                workflow,
            )

        self.assertEqual(context.exception.code, "runtime.value.adapter_ambiguous")

    def test_section_append_supports_optional_prefix(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Notes\n\nalpha", "text": "beta", "prefix": "\n\n"})

        value = resolve_runtime_value(
            '${markdown["Notes"]->append(text, prefix) with{root: inputs.body, text: inputs.text, prefix: inputs.prefix}}',
            workflow,
        )

        self.assertEqual(value, "## Notes\n\nalpha\n\nbeta")

    def test_section_replace_replaces_section_body_text(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Notes\n\nalpha\n\n### Nested\n\nomega", "text": "beta\n\ngamma"})

        value = resolve_runtime_value(
            '${markdown["Notes"]->replace(text) with{root: inputs.body, text: inputs.text}}',
            workflow,
        )

        self.assertEqual(value, "## Notes\n\nbeta\n\ngamma")

    def test_section_remove_clears_section_body(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Notes\n\nalpha\n\n### Nested\n\nomega"})

        value = resolve_runtime_value('${markdown["Notes"]->remove() with{root: inputs.body}}', workflow)

        self.assertEqual(value, "## Notes")

    def test_prelude_append_and_replace_use_text_arguments(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "intro\n\n## Notes\n\nalpha", "text": "beta", "prefix": "\n\n"})

        appended = resolve_runtime_value('${markdown.prelude->append(text, prefix) with{root: inputs.body, text: inputs.text, prefix: inputs.prefix}}', workflow)
        replaced = resolve_runtime_value('${markdown.prelude->replace(text) with{root: inputs.body, text: inputs.text}}', workflow)

        self.assertEqual(appended, "intro\n\nbeta\n\n## Notes\n\nalpha")
        self.assertEqual(replaced, "beta\n\n## Notes\n\nalpha")

    def test_paragraph_append_and_remove_work_on_text_targets(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "## Notes\n\nalpha\n\nbeta", "text": " gamma"})

        appended = resolve_runtime_value('${markdown["Notes"].paragraphs[0]->append(text) with{root: inputs.body, text: inputs.text}}', workflow)
        removed = resolve_runtime_value('${markdown["Notes"].paragraphs[1]->remove() with{root: inputs.body}}', workflow)

        self.assertEqual(appended, "## Notes\n\nalpha gamma\n\nbeta")
        self.assertEqual(removed, "## Notes\n\nalpha")


if __name__ == "__main__":
    unittest.main()
