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

    def test_one_selects_one_matching_array_element(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"id":1,"name":"Ada"},{"id":2,"name":"Grace"}]}', "target_id": 2})

        value = resolve_runtime_value('${json.items.one(id=target_id).name with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(value, "Grace")

    def test_one_selects_one_matching_object_value(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": '{"x":"t","y":{"id":42,"name":"Ada"},"z":{"id":99,"name":"Grace"}}', "target_id": 42},
        )

        value = resolve_runtime_value('${json.one(id=target_id).name with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(value, "Ada")

    def test_one_reports_not_found_when_no_matches_exist(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"id":1}]}', "target_id": 2})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.items.one(id=target_id) with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_not_found")

    def test_one_reports_ambiguous_match_when_multiple_candidates_match(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"id":2},{"id":2}]}', "target_id": 2})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.items.one(id=target_id) with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_ambiguous_match")

    def test_one_rejects_scalar_focus(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"value":"t"}'})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.value.one(id=1) with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_path")

    def test_many_returns_matching_children_in_traversal_order(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": '{"items":[{"kind":"keep","name":"Ada"},3,{"kind":"drop","name":"Skip"},{"kind":"keep","name":"Grace"}]}', "target_kind": "keep"},
        )

        value = resolve_runtime_value('${json.items.many(kind=target_kind) with{root: inputs.body, target_kind: inputs.target_kind}}', workflow)

        self.assertEqual(value, [{"kind": "keep", "name": "Ada"}, {"kind": "keep", "name": "Grace"}])

    def test_many_may_be_followed_by_index_and_ordinary_navigation(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": '{"items":[{"kind":"keep","name":"Ada"},{"kind":"keep","name":"Grace"}]}', "target_kind": "keep"},
        )

        value = resolve_runtime_value('${json.items.many(kind=target_kind)[1].name with{root: inputs.body, target_kind: inputs.target_kind}}', workflow)

        self.assertEqual(value, "Grace")

    def test_many_returns_empty_list_when_no_matches_exist(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"id":1}]}', "target_id": 2})

        value = resolve_runtime_value('${json.items.many(id=target_id) with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(value, [])

    def test_many_rejects_direct_recursive_descent_after_many_results(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"id":1}]}', "target_id": 1})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json.items.many(id=target_id)..id with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_path")

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

    def test_recursive_read_returns_many_matches(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": '{"field":0,"items":[{"field":1},{"nested":{"field":2}}],"other":{"field":3}}'},
        )

        value = resolve_runtime_value('${json..field with{root: inputs.body}}', workflow)

        self.assertEqual(value, [0, 1, 2, 3])

    def test_recursive_read_may_follow_prefix_path(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"field":1},{"nested":{"field":2}}],"field":0}'})

        value = resolve_runtime_value('${json.items..field with{root: inputs.body}}', workflow)

        self.assertEqual(value, [1, 2])

    def test_recursive_read_returns_empty_collection_when_no_matches_exist(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"id":1}]}'})

        value = resolve_runtime_value('${json..field with{root: inputs.body}}', workflow)

        self.assertEqual(value, [])

    def test_recursive_path_rejects_second_recursive_segment(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"field":1}]}'})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json..items..field with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_path")

    def test_recursive_remove_deletes_all_matching_members(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": '{"field":0,"items":[{"field":1},{"nested":{"field":2}}],"other":{"field":3}}'},
        )

        value = resolve_runtime_value('${json..field->remove() with{root: inputs.body}}', workflow)

        self.assertEqual(value, '{"items":[{},{"nested":{}}],"other":{}}')

    def test_recursive_remove_with_zero_matches_is_no_op(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"id":1}]}'})

        value = resolve_runtime_value('${json..field->remove() with{root: inputs.body}}', workflow)

        self.assertEqual(value, '{"items":[{"id":1}]}')

    def test_recursive_set_is_not_supported_in_mvp(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"items":[{"field":1}]}', "value": 2})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${json..field->set(value) with{root: inputs.body, value: inputs.value}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_action")

    def test_pipeline_may_chain_json_write_back_into_empty_body_json_read(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"field":0,"items":[{"field":1}]}'})

        value = resolve_runtime_value('${inputs.body | json..field->remove() | json}', workflow)

        self.assertEqual(value, {"items": [{}]})

    def test_pipeline_reports_invalid_root_when_json_stage_receives_non_string(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": '{"user":{"name":"Ada"}}'})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${inputs.body | json.user | json}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_root_value")

    def test_pipeline_cleanup_json_text_may_be_parsed_back_in_later_step(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={})
        digest_value = {"title": "Demo", "head_sha": "abc123", "commit_id": 17}

        digest_json = resolve_runtime_value(
            '${json->set(value) with{root: "{}", value: step.digest.outputs.value}}',
            workflow,
            step_results={"digest": {"outputs": {"value": digest_value}}},
        )
        self.assertEqual(digest_json, '{"commit_id":17,"head_sha":"abc123","title":"Demo"}')

        digest_json_clean = resolve_runtime_value(
            '${step.digest_json.outputs.value | json..["head_sha"]->remove() | json..["commit_id"]->remove()}',
            workflow,
            step_results={"digest_json": {"outputs": {"value": digest_json}}},
        )
        self.assertEqual(digest_json_clean, '{"title":"Demo"}')

        digest = resolve_runtime_value(
            '${json with{root: step.digest_json_clean.outputs.value}}',
            workflow,
            step_results={"digest_json_clean": {"outputs": {"value": digest_json_clean}}},
        )
        self.assertEqual(digest, {"title": "Demo"})


if __name__ == "__main__":
    unittest.main()
