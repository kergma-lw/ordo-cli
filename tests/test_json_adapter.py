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

    def test_set_updates_existing_exact_target_and_returns_compact_json_text(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{"name":"Ada","age":12}}', "value": "Grace"})

        value = resolve_runtime_value('${json.user.name->set(value) with{root: inputs.body, value: inputs.value}}', workflow)

        self.assertEqual(value, '{"user":{"age":12,"name":"Grace"}}')

    def test_set_may_replace_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{"name":"Ada"}}', "value": {"ok": True}})

        value = resolve_runtime_value('${json->set(value) with{root: inputs.body, value: inputs.value}}', workflow)

        self.assertEqual(value, '{"ok":true}')

    def test_set_may_auto_create_missing_object_members(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{}', "value": 7})

        value = resolve_runtime_value('${json.user.profile.id->set(value) with{root: inputs.body, value: inputs.value}}', workflow)

        self.assertEqual(value, '{"user":{"profile":{"id":7}}}')

    def test_set_rejects_missing_array_index_gap_creation(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[]}', "value": 7})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.items[0]->set(value) with{root: inputs.body, value: inputs.value}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_not_found")

    def test_remove_deletes_exact_object_member(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{"name":"Ada","age":12}}'})

        value = resolve_runtime_value('${json.user.age->remove() with{root: inputs.body}}', workflow)

        self.assertEqual(value, '{"user":{"name":"Ada"}}')

    def test_remove_deletes_exact_array_element(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[1,2,3]}'})

        value = resolve_runtime_value('${json.items[1]->remove() with{root: inputs.body}}', workflow)

        self.assertEqual(value, '{"items":[1,3]}')

    def test_remove_requires_explicit_target(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{"name":"Ada"}}'})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json->remove() with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_action")

    def test_set_rejects_non_json_compatible_parameter_values(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{"name":"Ada"}}', "value": (1, 2)})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.user.name->set(value) with{root: inputs.body, value: inputs.value}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_action")


if __name__ == "__main__":
    unittest.main()
