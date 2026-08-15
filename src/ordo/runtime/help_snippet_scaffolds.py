"""Explicit placement contracts and scaffold builders for help snippets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SnippetInsertionContract:
    """Reviewable placement contract for one supported snippet insertion mode."""

    mode: str
    supported_targets: tuple[str, ...]
    workflow_surface: str
    summary: str


EXPRESSION_VALUE_CONTRACT = SnippetInsertionContract(
    mode="expression_value",
    supported_targets=("state", "workflow.local_expression.filter.lookup", "local-expressions", "adapters"),
    workflow_surface="expression host inside a standard workflow scaffold",
    summary="Place one expression-valued snippet into a standard expression host without changing the authored snippet text.",
)


STEP_FIELD_CONTRACT = SnippetInsertionContract(
    mode="step_field",
    supported_targets=("workflow.step.if", "workflow.step.state_set", "workflow.step.state_delete", "workflow.step.profile_switch", "workflow.step_forms.profile_switch"),
    workflow_surface="step-local field host inside a standard workflow scaffold",
    summary="Place one step-field snippet into one explicit step shell without moving placement rules into snippet worlds.",
)


STEP_FRAGMENT_CONTRACT = SnippetInsertionContract(
    mode="step_fragment",
    supported_targets=("workflow.step.if", "workflow.step.state_set", "workflow.step.state_delete", "workflow.step.profile_switch", "workflow.step_forms.profile_switch", "routine"),
    workflow_surface="steps list inside a standard workflow scaffold",
    summary="Place one authored step fragment into a standard steps block without rewriting the fragment into a smaller value-only shape.",
)


WORKFLOW_FRAGMENT_CONTRACT = SnippetInsertionContract(
    mode="workflow_fragment",
    supported_targets=("workflow.profile",),
    workflow_surface="full workflow document scaffold",
    summary="Place one authored workflow fragment into a full workflow host without shrinking it into a step- or value-only form.",
)


ROUTINE_BUNDLE_CONTRACT = SnippetInsertionContract(
    mode="routine_bundle",
    supported_targets=("routine",),
    workflow_surface="temporary routine bundle project with registry, implementation, and optional workflow call",
    summary="Materialize one temporary project-local routine bundle so help verification can check the registry entry, implementation file, and optional workflow call together.",
)


INSERTION_CONTRACTS: dict[str, SnippetInsertionContract] = {
    EXPRESSION_VALUE_CONTRACT.mode: EXPRESSION_VALUE_CONTRACT,
    STEP_FIELD_CONTRACT.mode: STEP_FIELD_CONTRACT,
    STEP_FRAGMENT_CONTRACT.mode: STEP_FRAGMENT_CONTRACT,
    WORKFLOW_FRAGMENT_CONTRACT.mode: WORKFLOW_FRAGMENT_CONTRACT,
    ROUTINE_BUNDLE_CONTRACT.mode: ROUTINE_BUNDLE_CONTRACT,
}


def build_expression_value_scaffold(*, target: str, snippet: str) -> str:
    """Return a standard workflow scaffold for one expression-valued snippet."""

    if target == "state":
        return f"""version: 0
workflow: snippet-state
state_needs:
  shared_state: {{}}
let:
  sample: {snippet}
blocks: []
"""
    if target == "workflow.local_expression.filter.lookup":
        return f"""version: 0
workflow: snippet-lookup
inputs:
  status_labels: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    value: {snippet}
"""
    if target == "local-expressions":
        return f"""version: 0
workflow: snippet-local-expressions
inputs:
  status: {{}}
  allowed: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    value: {snippet}
"""
    if target == "adapters":
        return f"""version: 0
workflow: snippet-adapters
inputs:
  body: {{}}
  replacement: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    value: {snippet}
"""
    raise ValueError(f"Unsupported expression-value target: {target}")


def build_step_field_scaffold(*, target: str, snippet: str) -> str:
    """Return a standard workflow scaffold for one step-field snippet."""

    if target == "workflow.step.if":
        return f"""version: 0
workflow: snippet-step-if
inputs:
  close_comment: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    if: {snippet}
    value: true
"""
    if target == "workflow.step.state_set":
        return f"""version: 0
workflow: snippet-state-set
state_needs:
  shared_state: {{}}
  task_memory: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    {snippet.replace(chr(10), chr(10) + '    ')}
"""
    if target == "workflow.step.state_delete":
        return f"""version: 0
workflow: snippet-state-delete
inputs:
  issue_ref: {{}}
state_needs:
  shared_state: {{}}
  task_memory: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    {snippet.replace(chr(10), chr(10) + '    ')}
"""
    if target in {"workflow.step.profile_switch", "workflow.step_forms.profile_switch"}:
        return f"""version: 0
workflow: snippet-profile-switch-field
inputs:
  selected_profile: {{}}
blocks:
- guards: []
- steps:
  - name: demo
    profile_switch: {snippet}
"""
    raise ValueError(f"Unsupported step-field target: {target}")


def build_step_fragment_scaffold(*, target: str, snippet: str) -> str:
    """Return a standard workflow scaffold for one authored step fragment."""

    if target == "workflow.step.if":
        indented = snippet.replace(chr(10), chr(10) + "  ")
        return f"""version: 0
workflow: snippet-step-fragment-if
inputs:
  repository: {{}}
  issue_number: {{}}
  close_comment: {{}}
blocks:
- guards: []
- steps:
  {indented}
"""
    if target == "workflow.step.state_set":
        indented = snippet.replace(chr(10), chr(10) + "  ")
        return f"""version: 0
workflow: snippet-step-fragment
state_needs:
  shared_state: {{}}
  task_memory: {{}}
blocks:
- guards: []
- steps:
  {indented}
"""
    if target == "workflow.step.state_delete":
        indented = snippet.replace(chr(10), chr(10) + "  ")
        return f"""version: 0
workflow: snippet-step-fragment-state-delete
inputs:
  issue_ref: {{}}
state_needs:
  shared_state: {{}}
  task_memory: {{}}
blocks:
- guards: []
- steps:
  {indented}
"""
    if target in {"workflow.step.profile_switch", "workflow.step_forms.profile_switch"}:
        indented = snippet.replace(chr(10), chr(10) + "  ")
        return f"""version: 0
workflow: snippet-profile-switch-fragment
inputs:
  selected_profile: {{}}
blocks:
- guards: []
- steps:
  {indented}
"""
    if target == "routine":
        indented = snippet.replace(chr(10), chr(10) + "  ")
        return f"""version: 0
workflow: snippet-routine
inputs:
  target: {{}}
  repository: {{}}
  review_mode: {{}}
blocks:
- guards: []
- steps:
  {indented}
"""
    raise ValueError(f"Unsupported step-fragment target: {target}")


def build_workflow_fragment_scaffold(*, target: str, snippet: str) -> str:
    """Return a standard workflow scaffold for one authored workflow fragment."""

    if target == "workflow.profile":
        return f"{snippet}\n"
    raise ValueError(f"Unsupported workflow-fragment target: {target}")
