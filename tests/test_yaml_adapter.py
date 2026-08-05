import unittest

from ordo.model.workflow import Workflow
from ordo.runtime.value_resolution import ValueResolutionError, resolve_runtime_value


class YamlAdapterTest(unittest.TestCase):
    def test_empty_body_returns_complete_parsed_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "user:\n  name: Ada\nenabled: true\n"})

        value = resolve_runtime_value('${yaml with{root: inputs.body}}', workflow)

        self.assertEqual(value, {"user": {"name": "Ada"}, "enabled": True})

    def test_read_path_selects_exact_member_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "user:\n  name: Ada\n"})

        value = resolve_runtime_value('${yaml.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(value, "Ada")

    def test_read_path_selects_bracketed_literal_key(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": 'display-name: Ada\n'})

        value = resolve_runtime_value('${yaml["display-name"] with{root: inputs.body}}', workflow)

        self.assertEqual(value, "Ada")

    def test_read_path_selects_array_index(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "items:\n  - id: 1\n  - id: 2\n"})

        value = resolve_runtime_value('${yaml.items[1].id with{root: inputs.body}}', workflow)

        self.assertEqual(value, 2)

    def test_yaml_null_is_returned_as_found_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "user:\n  name: null\n"})

        value = resolve_runtime_value('${yaml.user.name with{root: inputs.body}}', workflow)

        self.assertIsNone(value)

    def test_missing_member_reports_not_found(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "user: {}\n"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_not_found")

    def test_invalid_selector_node_kind_reports_invalid_path(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "user:\n  - 1\n  - 2\n"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_path")

    def test_invalid_yaml_root_reports_invalid_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "user: [1,\n"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_root_value")

    def test_non_string_root_reports_invalid_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": {"user": {"name": "Ada"}}})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml.user.name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_root_value")

    def test_multi_document_yaml_reports_invalid_root_value(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "---\nname: Ada\n---\nname: Grace\n"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml.name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_root_value")

    def test_one_selects_one_matching_array_element(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": 'steps:\n  - name: Fetch\n  - name: Install mage\n', "target_name": "Install mage"},
        )

        value = resolve_runtime_value('${yaml.steps.one(name=target_name).name with{root: inputs.body, target_name: inputs.target_name}}', workflow)

        self.assertEqual(value, "Install mage")

    def test_one_selects_one_matching_object_value(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": 'left: skip\nmatch:\n  id: 42\n  name: Ada\nother:\n  id: 99\n  name: Grace\n', "target_id": 42},
        )

        value = resolve_runtime_value('${yaml.one(id=target_id).name with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(value, "Ada")

    def test_one_reports_not_found_when_no_matches_exist(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": 'steps:\n  - id: 1\n', "target_id": 2})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml.steps.one(id=target_id) with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_not_found")

    def test_one_reports_ambiguous_match_when_multiple_candidates_match(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": 'steps:\n  - id: 2\n  - id: 2\n', "target_id": 2})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml.steps.one(id=target_id) with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_ambiguous_match")

    def test_one_rejects_scalar_focus(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": 'value: scalar\n'})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml.value.one(id=1) with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_path")

    def test_many_returns_matching_children_in_traversal_order(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "body": 'steps:\n  - kind: keep\n    name: Ada\n  - 3\n  - kind: drop\n    name: Skip\n  - kind: keep\n    name: Grace\n',
                "target_kind": "keep",
            },
        )

        value = resolve_runtime_value('${yaml.steps.many(kind=target_kind) with{root: inputs.body, target_kind: inputs.target_kind}}', workflow)

        self.assertEqual(value, [{"kind": "keep", "name": "Ada"}, {"kind": "keep", "name": "Grace"}])

    def test_many_supports_not_equal_filtering(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={
                "body": 'steps:\n  - conclusion: success\n    name: A\n  - name: Skip\n  - conclusion: failure\n    name: B\n  - conclusion: cancelled\n    name: C\n',
                "target_conclusion": "success",
            },
        )

        value = resolve_runtime_value(
            '${yaml.steps.many(conclusion!=target_conclusion) with{root: inputs.body, target_conclusion: inputs.target_conclusion}}',
            workflow,
        )

        self.assertEqual(
            value,
            [
                {"conclusion": "failure", "name": "B"},
                {"conclusion": "cancelled", "name": "C"},
            ],
        )

    def test_many_may_be_followed_by_index_and_ordinary_navigation(self) -> None:
        workflow = Workflow(
            version=0,
            workflow="demo",
            inputs={"body": 'steps:\n  - kind: keep\n    name: Ada\n  - kind: keep\n    name: Grace\n', "target_kind": "keep"},
        )

        value = resolve_runtime_value('${yaml.steps.many(kind=target_kind)[1].name with{root: inputs.body, target_kind: inputs.target_kind}}', workflow)

        self.assertEqual(value, "Grace")

    def test_many_returns_empty_list_when_no_matches_exist(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": 'steps:\n  - id: 1\n', "target_id": 2})

        value = resolve_runtime_value('${yaml.steps.many(id=target_id) with{root: inputs.body, target_id: inputs.target_id}}', workflow)

        self.assertEqual(value, [])

    def test_yaml_adapter_rejects_write_actions_in_mvp(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "name: Ada\n", "value": "Grace"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml.name->set(value) with{root: inputs.body, value: inputs.value}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_action")

    def test_yaml_adapter_rejects_recursive_descent_in_mvp(self) -> None:
        workflow = Workflow(version=0, workflow="demo", inputs={"body": "name: Ada\n"})

        with self.assertRaises(ValueResolutionError) as context:
            resolve_runtime_value('${yaml..name with{root: inputs.body}}', workflow)

        self.assertEqual(context.exception.code, "runtime.value.adapter_invalid_path")


if __name__ == "__main__":
    unittest.main()
