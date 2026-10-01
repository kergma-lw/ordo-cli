import unittest

from ordo.connectors import get_public_connector_registry


class ConnectorRegistryTest(unittest.TestCase):
    def test_registry_exposes_fixed_v0_connector_families(self) -> None:
        registry = get_public_connector_registry()

        self.assertEqual(
            tuple(connector.namespace for connector in registry.list_connectors()),
            ("runtime", "git", "compose", "gh", "shell", "fs"),
        )

    def test_registry_exposes_discoverable_operation_metadata(self) -> None:
        registry = get_public_connector_registry()

        operation = registry.get_operation("gh.issue")

        self.assertIsNotNone(operation)
        self.assertEqual(operation.kind, "probe")
        self.assertEqual(operation.summary, "Probe operation 'gh.issue'")
        self.assertEqual(operation.inputs["repository"], "string")
        self.assertEqual(operation.inputs["issue_number"], "integer")
        self.assertEqual(operation.outputs["state"], "string")
        self.assertEqual(operation.outputs["created_at"], "string")
        self.assertIn("issue_not_found", operation.failure_modes)

        issue_create = registry.get_operation("gh.issue.create")
        self.assertIsNotNone(issue_create)
        self.assertEqual(issue_create.kind, "action")
        self.assertEqual(issue_create.inputs["repository"], "string")
        self.assertEqual(issue_create.inputs["title"], "string")
        self.assertEqual(issue_create.outputs["issue_ref"], "string")
        self.assertEqual(issue_create.outputs["title"], "string")
        self.assertIn("create_blocked", issue_create.failure_modes)

        issue_comment_add = registry.get_operation("gh.issue.comment.add")
        self.assertIsNotNone(issue_comment_add)
        self.assertEqual(issue_comment_add.kind, "action")
        self.assertEqual(issue_comment_add.inputs["repository"], "string")
        self.assertEqual(issue_comment_add.inputs["issue_number"], "integer")
        self.assertEqual(issue_comment_add.inputs["body"], "string")
        self.assertEqual(issue_comment_add.outputs["comment_id"], "string")
        self.assertIn("comment_blocked", issue_comment_add.failure_modes)

        issue_body_replace = registry.get_operation("gh.issue.body.replace")
        self.assertIsNotNone(issue_body_replace)
        self.assertEqual(issue_body_replace.kind, "action")
        self.assertEqual(issue_body_replace.inputs["repository"], "string")
        self.assertEqual(issue_body_replace.inputs["issue_number"], "integer")
        self.assertEqual(issue_body_replace.inputs["body"], "string")
        self.assertEqual(issue_body_replace.outputs["changed"], "boolean")
        self.assertIn("replace_blocked", issue_body_replace.failure_modes)

        issue_body_append = registry.get_operation("gh.issue.body.append")
        self.assertIsNotNone(issue_body_append)
        self.assertEqual(issue_body_append.kind, "action")
        self.assertEqual(issue_body_append.inputs["repository"], "string")
        self.assertEqual(issue_body_append.inputs["issue_number"], "integer")
        self.assertEqual(issue_body_append.inputs["text"], "string")
        self.assertEqual(issue_body_append.outputs["changed"], "boolean")
        self.assertIn("append_blocked", issue_body_append.failure_modes)

        project_issue = registry.get_operation("gh.project.issue")
        self.assertIsNotNone(project_issue)
        self.assertEqual(project_issue.kind, "probe")
        self.assertEqual(project_issue.inputs["repository"], "string")
        self.assertEqual(project_issue.inputs["issue_number"], "integer")
        self.assertEqual(project_issue.inputs["project_id"], "string")
        self.assertEqual(project_issue.outputs["exists"], "boolean")
        self.assertEqual(project_issue.outputs["item_id"], "string")
        self.assertEqual(project_issue.outputs["custom_fields"], "object")
        self.assertIn("project_not_found", project_issue.failure_modes)

        project_issue_add = registry.get_operation("gh.project.issue.add")
        self.assertIsNotNone(project_issue_add)
        self.assertEqual(project_issue_add.kind, "action")
        self.assertEqual(project_issue_add.inputs["repository"], "string")
        self.assertEqual(project_issue_add.inputs["issue_number"], "integer")
        self.assertEqual(project_issue_add.inputs["project_id"], "string")
        self.assertEqual(project_issue_add.outputs["item_id"], "string")
        self.assertIn("project_not_found", project_issue_add.failure_modes)

        project_issue_field_single_select_set = registry.get_operation("gh.project.issue.field_single_select.set")
        self.assertIsNotNone(project_issue_field_single_select_set)
        self.assertEqual(project_issue_field_single_select_set.kind, "action")
        self.assertEqual(project_issue_field_single_select_set.inputs["repository"], "string")
        self.assertEqual(project_issue_field_single_select_set.inputs["issue_number"], "integer")
        self.assertEqual(project_issue_field_single_select_set.inputs["project_id"], "string")
        self.assertEqual(project_issue_field_single_select_set.inputs["field"], "string")
        self.assertEqual(project_issue_field_single_select_set.inputs["option"], "string")
        self.assertEqual(project_issue_field_single_select_set.outputs["changed"], "boolean")
        self.assertIn("option_not_found", project_issue_field_single_select_set.failure_modes)

        project_issue_iteration_set = registry.get_operation("gh.project.issue.field_iteration.set")
        self.assertIsNotNone(project_issue_iteration_set)
        self.assertEqual(project_issue_iteration_set.kind, "action")
        self.assertEqual(project_issue_iteration_set.inputs["repository"], "string")
        self.assertEqual(project_issue_iteration_set.inputs["issue_number"], "integer")
        self.assertEqual(project_issue_iteration_set.inputs["project_id"], "string")
        self.assertEqual(project_issue_iteration_set.inputs["iteration"], "string")
        self.assertEqual(project_issue_iteration_set.outputs["changed"], "boolean")
        self.assertIn("iteration_not_found", project_issue_iteration_set.failure_modes)

        project_issue_field_number_set = registry.get_operation("gh.project.issue.field_number.set")
        self.assertIsNotNone(project_issue_field_number_set)
        self.assertEqual(project_issue_field_number_set.kind, "action")
        self.assertEqual(project_issue_field_number_set.inputs["repository"], "string")
        self.assertEqual(project_issue_field_number_set.inputs["issue_number"], "integer")
        self.assertEqual(project_issue_field_number_set.inputs["project_id"], "string")
        self.assertEqual(project_issue_field_number_set.inputs["field"], "string")
        self.assertEqual(project_issue_field_number_set.inputs["value"], "number")
        self.assertEqual(project_issue_field_number_set.outputs["changed"], "boolean")
        self.assertIn("field_value_invalid", project_issue_field_number_set.failure_modes)

    def test_registry_contract_is_public_json_shaped_surface(self) -> None:
        registry = get_public_connector_registry()

        contract = registry.to_contract()

        self.assertEqual(contract["connectors"][0]["namespace"], "runtime")
        compose_connector = next(connector for connector in contract["connectors"] if connector["namespace"] == "compose")
        self.assertIn(
            "project",
            {operation["name"] for operation in compose_connector["operations"]},
        )
        gh_connector = next(connector for connector in contract["connectors"] if connector["namespace"] == "gh")
        self.assertIn(
            "project.issue",
            {operation["name"] for operation in gh_connector["operations"]},
        )
        self.assertNotIn(
            "issue.view",
            {operation["name"] for operation in gh_connector["operations"]},
        )
        shell_connector = next(connector for connector in contract["connectors"] if connector["namespace"] == "shell")
        self.assertIn(
            "action",
            {operation["kind"] for operation in shell_connector["operations"]},
        )


if __name__ == "__main__":
    unittest.main()
