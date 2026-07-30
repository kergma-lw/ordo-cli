# Examples

This page collects verified examples you can inspect as reference material.

Use this page when you want concrete repository examples to inspect side by side with the reference docs.

## minimal

- Path: `examples/minimal.yaml`
- Verified: `true`
- Highlights: `minimal_workflow`, `public_operation_composition`
- Related topics: [Overview](overview.md), [Authoring model](model.md), [Operation catalog](operations.md)

## inspect-issue

- Path: `examples/inspect-issue.yaml`
- Verified: `true`
- Highlights: `guard_probe_usage`, `blocked_before_execution`
- Related topics: [Capabilities](capabilities.md), [Authoring model](model.md), [Operation catalog](operations.md)

## inspect-pr

- Path: `examples/inspect-pr.yaml`
- Verified: `true`
- Highlights: `pull_request_probe_composition`, `orthogonal_pr_surfaces`, `published_digest_inputs`
- Related topics: [Operation catalog](operations.md), [Examples](examples.md), [Authoring model](model.md)

## set-active-task-from-gitx

- Path: `examples/set-active-task-from-gitx.yaml`
- Verified: `true`
- Highlights: `multi_step_workflow`, `state_updates`, `shell_fallback`
- Related topics: [Capabilities](capabilities.md), [Authoring model](model.md), [Operation catalog](operations.md)

## launcher-step

- Path: `examples/launcher-step.yaml`
- Status: `legacy_compatibility_example`
- Verified: `true`
- Highlights: `step_launcher_selection`, `profile_scoped_launchers`, `shell_wrapper_example`
- Related topics: [Capabilities](capabilities.md), [Authoring model](model.md), [Examples](examples.md)

## include-plain

- Path: `examples/include-plain.yaml`
- Verified: `true`
- Highlights: `workflow_include`, `plain_fragment_reuse`
- Related topics: [Authoring model](model.md), [Examples](examples.md)

## include-args

- Path: `examples/include-args.yaml`
- Verified: `true`
- Highlights: `workflow_include`, `fragment_args`, `ordo_help_aligned_fragment_contract`
- Related topics: [Capabilities](capabilities.md), [Authoring model](model.md), [Examples](examples.md)

## playbook-pre-run

- Path: `examples/playbook-pre-run.yaml`
- Verified: `true`
- Highlights: `playbook_pre_run`, `runtime_profile_switch`, `shared_preparation_stage`
- Related topics: [Authoring model](model.md), [Examples](examples.md), [Operation catalog](operations.md)

## text-adapter

- Path: `examples/text-adapter.yaml`
- Verified: `true`
- Highlights: `text_adapter_line_projection`, `text_adapter_literal_search`, `text_adapter_bulk_mutation`
- Related topics: [Capabilities](capabilities.md), [Authoring model](model.md), [Examples](examples.md)

## local-expression-filters

- Path: `examples/local-expression-filters.yaml`
- Verified: `true`
- Highlights: `type_predicate_filters`, `membership_filter`, `embedded_value_boolean_flow`
- Related topics: [Authoring model](model.md), [Examples](examples.md)

## project-items-let

- Path: `examples/project-items-let.yaml`
- Verified: `true`
- Highlights: `project_collection_probe`, `let_bound_probe_usage`, `field_based_project_filtering`
- Related topics: [Operation catalog](operations.md), [Examples](examples.md), [Authoring model](model.md)

## Full JSON reference

```json
{
  "document_kind": "examples_catalog",
  "examples": [
    {
      "name": "minimal",
      "path": "examples/minimal.yaml",
      "related_topics": [
        "overview",
        "model",
        "operations"
      ],
      "shows": [
        "minimal_workflow",
        "public_operation_composition"
      ],
      "verified": true
    },
    {
      "name": "inspect-issue",
      "path": "examples/inspect-issue.yaml",
      "related_topics": [
        "capabilities",
        "model",
        "operations"
      ],
      "shows": [
        "guard_probe_usage",
        "blocked_before_execution"
      ],
      "verified": true
    },
    {
      "name": "inspect-pr",
      "path": "examples/inspect-pr.yaml",
      "related_topics": [
        "operations",
        "examples",
        "model"
      ],
      "shows": [
        "pull_request_probe_composition",
        "orthogonal_pr_surfaces",
        "published_digest_inputs"
      ],
      "verified": true
    },
    {
      "name": "set-active-task-from-gitx",
      "path": "examples/set-active-task-from-gitx.yaml",
      "related_topics": [
        "capabilities",
        "model",
        "operations"
      ],
      "shows": [
        "multi_step_workflow",
        "state_updates",
        "shell_fallback"
      ],
      "verified": true
    },
    {
      "name": "launcher-step",
      "path": "examples/launcher-step.yaml",
      "related_topics": [
        "capabilities",
        "model",
        "examples"
      ],
      "shows": [
        "step_launcher_selection",
        "profile_scoped_launchers",
        "shell_wrapper_example"
      ],
      "status": "legacy_compatibility_example",
      "verified": true
    },
    {
      "name": "include-plain",
      "path": "examples/include-plain.yaml",
      "related_topics": [
        "model",
        "examples"
      ],
      "shows": [
        "workflow_include",
        "plain_fragment_reuse"
      ],
      "verified": true
    },
    {
      "name": "include-args",
      "path": "examples/include-args.yaml",
      "related_topics": [
        "capabilities",
        "model",
        "examples"
      ],
      "shows": [
        "workflow_include",
        "fragment_args",
        "ordo_help_aligned_fragment_contract"
      ],
      "verified": true
    },
    {
      "name": "playbook-pre-run",
      "path": "examples/playbook-pre-run.yaml",
      "related_topics": [
        "model",
        "examples",
        "operations"
      ],
      "shows": [
        "playbook_pre_run",
        "runtime_profile_switch",
        "shared_preparation_stage"
      ],
      "verified": true
    },
    {
      "name": "text-adapter",
      "path": "examples/text-adapter.yaml",
      "related_topics": [
        "capabilities",
        "model",
        "examples"
      ],
      "shows": [
        "text_adapter_line_projection",
        "text_adapter_literal_search",
        "text_adapter_bulk_mutation"
      ],
      "verified": true
    },
    {
      "name": "local-expression-filters",
      "path": "examples/local-expression-filters.yaml",
      "related_topics": [
        "model",
        "examples"
      ],
      "shows": [
        "type_predicate_filters",
        "membership_filter",
        "embedded_value_boolean_flow"
      ],
      "verified": true
    },
    {
      "name": "project-items-let",
      "path": "examples/project-items-let.yaml",
      "related_topics": [
        "operations",
        "examples",
        "model"
      ],
      "shows": [
        "project_collection_probe",
        "let_bound_probe_usage",
        "field_based_project_filtering"
      ],
      "verified": true
    }
  ]
}
```
