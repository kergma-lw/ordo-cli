import unittest

from ordo.model.workflow import Workflow
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value


class JsonAdapterTest(unittest.TestCase):
    def test_empty_body_returns_complete_parsed_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{"name":"Ada"},"enabled":true}'})

        value = resolve_runtime_value('${json with{root: inputs.body}}', workflow)

        self.assertEqual(value, {"user": {"name": "Ada"}, "enabled": True})

    def test_read_path_selects_exact_member_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{"name":"Ada"}}'})

        value = resolve_runtime_value('${json.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(value, "Ada")

    def test_read_path_selects_bracketed_literal_key(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"display-name":"Ada"}'})

        value = resolve_runtime_value('${json["display-name"] with{root: inputs.body}}', workflow)

        self.assertEqual(value, "Ada")

    def test_read_path_selects_array_index(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"id":1},{"id":2}]}'})

        value = resolve_runtime_value('${json.items[1].id with{root: inputs.body}}', workflow)

        self.assertEqual(value, 2)

    def test_json_null_is_returned_as_found_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{"name":null}}'})

        value = resolve_runtime_value('${json.user.name with{root: inputs.body}}', workflow)

        self.assertIsNone(value)

    def test_missing_member_reports_not_found(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{}}'})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_not_found")

    def test_invalid_selector_node_kind_reports_invalid_path(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":[1,2]}'})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_path")

    def test_invalid_json_root_reports_invalid_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{oops'})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_root_value")

    def test_non_string_root_reports_invalid_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": {"user": {"name": "Ada"}}})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_root_value")


if __name__ == "__main__":
    unittest.main()
