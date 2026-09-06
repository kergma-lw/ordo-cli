# Examples

This page collects verified examples you can inspect as reference material.

Use this page when you want concrete repository examples to inspect side by side with the reference docs.

## minimal

- Path: `examples/minimal.yaml`
- Verified: `true`
- Highlights: `minimal_workflow`, `public_operation_composition`
- Related topics: [Overview](overview.md), [Workflow model](model.md), [Operation catalog](operations.md)

## inspect-issue

- Path: `examples/inspect-issue.yaml`
- Verified: `true`
- Highlights: `guard_probe_usage`, `blocked_before_execution`
- Related topics: [Capabilities](capabilities.md), [Workflow model](model.md), [Operation catalog](operations.md)

## inspect-pr

- Path: `examples/inspect-pr.yaml`
- Verified: `true`
- Highlights: `pull_request_probe_composition`, `orthogonal_pr_surfaces`, `published_digest_inputs`
- Related topics: [Operation catalog](operations.md), [Examples](examples.md), [Workflow model](model.md)

## set-active-task-from-gitx

- Path: `examples/set-active-task-from-gitx.yaml`
- Verified: `true`
- Highlights: `multi_step_workflow`, `state_updates`, `shell_fallback`
- Related topics: [Capabilities](capabilities.md), [Workflow model](model.md), [Operation catalog](operations.md)

## launcher-step

- Path: `examples/launcher-step.yaml`
- Status: `legacy_compatibility_example`
- Verified: `true`
- Highlights: `step_launcher_selection`, `profile_scoped_launchers`, `shell_wrapper_example`
- Related topics: [Capabilities](capabilities.md), [Workflow model](model.md), [Examples](examples.md)

## include-plain

- Path: `examples/include-plain.yaml`
- Verified: `true`
- Highlights: `workflow_include`, `plain_fragment_reuse`
- Related topics: [Workflow model](model.md), [Examples](examples.md)

## include-args

- Path: `examples/include-args.yaml`
- Verified: `true`
- Highlights: `workflow_include`, `fragment_args`, `ordo_help_aligned_fragment_contract`
- Related topics: [Capabilities](capabilities.md), [Workflow model](model.md), [Examples](examples.md)

## playbook-workflows

- Path: `examples/playbook-workflows.yaml`
- Verified: `true`
- Highlights: `playbook_workflow_catalog`, `workflow_entry_guidance`, `entry_state_bindings`
- Related topics: [Features](features.md), [Workflow model](model.md), [Examples](examples.md)

## playbook-connectors

- Path: `examples/playbook-connectors.yaml`
- Verified: `true`
- Highlights: `playbook_version_marker`, `playbook_connector_defaults`, `profile_override_boundary`
- Related topics: [Features](features.md), [Workflow model](model.md), [Examples](examples.md)

## playbook-pre-run

- Path: `examples/playbook-pre-run.yaml`
- Verified: `true`
- Highlights: `playbook_pre_run`, `runtime_profile_switch`, `shared_preparation_stage`
- Related topics: [Workflow model](model.md), [Examples](examples.md), [Operation catalog](operations.md)

## run-fan-out

- Path: `examples/run-fan-out.yaml`
- Verified: `true`
- Highlights: `run_target_invocation`, `bounded_fan_out`, `inline_repeated_steps`
- Related topics: [Workflow model](model.md), [Examples](examples.md), [Workflow rules](workflow-rules.md)

## text-adapter

- Path: `examples/text-adapter.yaml`
- Verified: `true`
- Highlights: `text_adapter_line_projection`, `text_adapter_literal_search`, `text_adapter_bulk_mutation`
- Related topics: [Capabilities](capabilities.md), [Workflow model](model.md), [Examples](examples.md)

## local-expression-filters

- Path: `examples/local-expression-filters.yaml`
- Verified: `true`
- Highlights: `type_predicate_filters`, `membership_filter`, `embedded_value_boolean_flow`
- Related topics: [Workflow model](model.md), [Examples](examples.md)

## project-items-let

- Path: `examples/project-items-let.yaml`
- Verified: `true`
- Highlights: `project_collection_probe`, `let_bound_probe_usage`, `field_based_project_filtering`
- Related topics: [Operation catalog](operations.md), [Examples](examples.md), [Workflow model](model.md)

## Full JSON reference

```json
{
  "document_kind": "examples_catalog",
  "examples": [
    {
      "definition": "Minimal workflow example that composes one published operation into one small end-to-end workflow shape.",
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
      "definition": "Issue inspection example that uses a guard before loading one published GitHub issue probe.",
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
      "definition": "Pull-request inspection example that composes the published PR metadata, diff, comments, reviews, checks, and timeline surfaces into one summary.",
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
      "definition": "Multi-step task-activation example that combines project updates, state writes, and legacy shell fallback steps in one workflow.",
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
      "definition": "Launcher selection example that shows one step-level launcher override inside a profile-scoped execution context.",
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
      "definition": "Workflow include example that reuses one plain fragment without passing include arguments.",
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
      "definition": "Workflow include example that passes explicit arguments into one reusable fragment contract.",
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
      "definition": "Playbook workflow catalog example that shows one published workflow entry with defaults, profiles, and state bindings.",
      "name": "playbook-workflows",
      "path": "examples/playbook-workflows.yaml",
      "related_topics": [
        "features",
        "model",
        "examples"
      ],
      "shows": [
        "playbook_workflow_catalog",
        "workflow_entry_guidance",
        "entry_state_bindings"
      ],
      "verified": true
    },
    {
      "definition": "Playbook top-level example that shows the required version marker together with repository-wide connector defaults before workflow and profile activation.",
      "name": "playbook-connectors",
      "path": "examples/playbook-connectors.yaml",
      "related_topics": [
        "features",
        "model",
        "examples"
      ],
      "shows": [
        "playbook_version_marker",
        "playbook_connector_defaults",
        "profile_override_boundary"
      ],
      "verified": true
    },
    {
      "definition": "Playbook pre-run example that inserts one shared preparation workflow before the requested published workflow runs.",
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
      "definition": "Run-invocation example that contrasts named run-target fan-out with inline repeated steps, including outer if, gate, with, and register fields.",
      "name": "run-fan-out",
      "path": "examples/run-fan-out.yaml",
      "related_topics": [
        "model",
        "examples",
        "workflow-rules"
      ],
      "shows": [
        "run_target_invocation",
        "bounded_fan_out",
        "inline_repeated_steps"
      ],
      "verified": true
    },
    {
      "definition": "Text adapter example that projects, searches, and rewrites line-oriented text through the published text adapter surface.",
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
      "definition": "Local-expression filter example that demonstrates type predicates, membership tests, and boolean flow over embedded values.",
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
      "definition": "Project-items example that binds one collection probe through let and then filters it by field values.",
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
