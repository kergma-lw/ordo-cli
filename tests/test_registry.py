import unittest

from ordo.connectors import get_public_connector_registry


class ConnectorRegistryTest(unittest.TestCase):
    def test_registry_exposes_fixed_v0_connector_families(self) -> None:
        registry = get_public_connector_registry()

        self.assertEqual(
            tuple(connector.namespace for connector in registry.list_connectors()),
            ("git", "gh", "shell"),
        )

    def test_registry_exposes_discoverable_operation_metadata(self) -> None:
        registry = get_public_connector_registry()

        operation = registry.get_operation("gh.issue")

        self.assertIsNotNone(operation)
        self.assertEqual(operation.kind, "probe")
        self.assertEqual(operation.inputs["issue_ref"], "string")
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
        self.assertEqual(issue_comment_add.inputs["issue_ref"], "string")
        self.assertEqual(issue_comment_add.inputs["body"], "string")
        self.assertEqual(issue_comment_add.outputs["comment_id"], "string")
        self.assertIn("comment_blocked", issue_comment_add.failure_modes)

        issue_body_replace = registry.get_operation("gh.issue.body.replace")
        self.assertIsNotNone(issue_body_replace)
        self.assertEqual(issue_body_replace.kind, "action")
        self.assertEqual(issue_body_replace.inputs["issue_ref"], "string")
        self.assertEqual(issue_body_replace.inputs["body"], "string")
        self.assertEqual(issue_body_replace.outputs["changed"], "boolean")
        self.assertIn("replace_blocked", issue_body_replace.failure_modes)

        issue_body_append = registry.get_operation("gh.issue.body.append")
        self.assertIsNotNone(issue_body_append)
        self.assertEqual(issue_body_append.kind, "action")
        self.assertEqual(issue_body_append.inputs["issue_ref"], "string")
        self.assertEqual(issue_body_append.inputs["text"], "string")
        self.assertEqual(issue_body_append.outputs["changed"], "boolean")
        self.assertIn("append_blocked", issue_body_append.failure_modes)

        project_issue = registry.get_operation("gh.project.issue")
        self.assertIsNotNone(project_issue)
        self.assertEqual(project_issue.kind, "probe")
        self.assertEqual(project_issue.inputs["issue_ref"], "string")
        self.assertEqual(project_issue.inputs["project_id"], "string")
        self.assertEqual(project_issue.outputs["exists"], "boolean")
        self.assertEqual(project_issue.outputs["item_id"], "string")
        self.assertIn("project_not_found", project_issue.failure_modes)

        project_issue_add = registry.get_operation("gh.project.issue.add")
        self.assertIsNotNone(project_issue_add)
        self.assertEqual(project_issue_add.kind, "action")
        self.assertEqual(project_issue_add.inputs["issue_ref"], "string")
        self.assertEqual(project_issue_add.inputs["project_id"], "string")
        self.assertEqual(project_issue_add.outputs["item_id"], "string")
        self.assertIn("project_not_found", project_issue_add.failure_modes)

        project_issue_status_set = registry.get_operation("gh.project.issue.status.set")
        self.assertIsNotNone(project_issue_status_set)
        self.assertEqual(project_issue_status_set.kind, "action")
        self.assertEqual(project_issue_status_set.inputs["issue_ref"], "string")
        self.assertEqual(project_issue_status_set.inputs["project_id"], "string")
        self.assertEqual(project_issue_status_set.inputs["status"], "string")
        self.assertEqual(project_issue_status_set.outputs["changed"], "boolean")
        self.assertIn("status_not_found", project_issue_status_set.failure_modes)

        project_issue_iteration_set = registry.get_operation("gh.project.issue.iteration.set")
        self.assertIsNotNone(project_issue_iteration_set)
        self.assertEqual(project_issue_iteration_set.kind, "action")
        self.assertEqual(project_issue_iteration_set.inputs["issue_ref"], "string")
        self.assertEqual(project_issue_iteration_set.inputs["project_id"], "string")
        self.assertEqual(project_issue_iteration_set.inputs["iteration"], "string")
        self.assertEqual(project_issue_iteration_set.outputs["changed"], "boolean")
        self.assertIn("iteration_not_found", project_issue_iteration_set.failure_modes)

        project_issue_priority_set = registry.get_operation("gh.project.issue.priority.set")
        self.assertIsNotNone(project_issue_priority_set)
        self.assertEqual(project_issue_priority_set.kind, "action")
        self.assertEqual(project_issue_priority_set.inputs["issue_ref"], "string")
        self.assertEqual(project_issue_priority_set.inputs["project_id"], "string")
        self.assertEqual(project_issue_priority_set.inputs["priority"], "string")
        self.assertEqual(project_issue_priority_set.outputs["changed"], "boolean")
        self.assertIn("priority_not_found", project_issue_priority_set.failure_modes)

        project_issue_type_set = registry.get_operation("gh.project.issue.type.set")
        self.assertIsNotNone(project_issue_type_set)
        self.assertEqual(project_issue_type_set.kind, "action")
        self.assertEqual(project_issue_type_set.inputs["issue_ref"], "string")
        self.assertEqual(project_issue_type_set.inputs["project_id"], "string")
        self.assertEqual(project_issue_type_set.inputs["type"], "string")
        self.assertEqual(project_issue_type_set.outputs["changed"], "boolean")
        self.assertIn("type_not_found", project_issue_type_set.failure_modes)

        project_issue_size_set = registry.get_operation("gh.project.issue.size.set")
        self.assertIsNotNone(project_issue_size_set)
        self.assertEqual(project_issue_size_set.kind, "action")
        self.assertEqual(project_issue_size_set.inputs["issue_ref"], "string")
        self.assertEqual(project_issue_size_set.inputs["project_id"], "string")
        self.assertEqual(project_issue_size_set.inputs["size"], "string")
        self.assertEqual(project_issue_size_set.outputs["changed"], "boolean")
        self.assertIn("size_not_found", project_issue_size_set.failure_modes)

        project_issue_estimate_set = registry.get_operation("gh.project.issue.estimate.set")
        self.assertIsNotNone(project_issue_estimate_set)
        self.assertEqual(project_issue_estimate_set.kind, "action")
        self.assertEqual(project_issue_estimate_set.inputs["issue_ref"], "string")
        self.assertEqual(project_issue_estimate_set.inputs["project_id"], "string")
        self.assertEqual(project_issue_estimate_set.inputs["estimate"], "number")
        self.assertEqual(project_issue_estimate_set.outputs["changed"], "boolean")
        self.assertIn("estimate_invalid", project_issue_estimate_set.failure_modes)

    def test_registry_contract_is_public_json_shaped_surface(self) -> None:
        registry = get_public_connector_registry()

        contract = registry.to_contract()

        self.assertEqual(contract["connectors"][0]["namespace"], "git")
        self.assertIn(
            "issue",
            {operation["name"] for operation in contract["connectors"][1]["operations"]},
        )
        self.assertIn(
            "project.issue",
            {operation["name"] for operation in contract["connectors"][1]["operations"]},
        )
        self.assertNotIn(
            "issue.view",
            {operation["name"] for operation in contract["connectors"][1]["operations"]},
        )
        self.assertIn(
            "action",
            {operation["kind"] for operation in contract["connectors"][2]["operations"]},
        )


if __name__ == "__main__":
    unittest.main()
