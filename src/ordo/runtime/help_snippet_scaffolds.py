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
    supported_targets=("state", "workflow.local_expression.filter.lookup"),
    workflow_surface="expression host inside a standard workflow scaffold",
    summary="Place one expression-valued snippet into a standard expression host without changing the authored snippet text.",
)


STEP_FIELD_CONTRACT = SnippetInsertionContract(
    mode="step_field",
    supported_targets=("workflow.step.if", "workflow.step.state_set"),
    workflow_surface="step-local field host inside a standard workflow scaffold",
    summary="Place one step-field snippet into one explicit step shell without moving placement rules into snippet worlds.",
)


STEP_FRAGMENT_CONTRACT = SnippetInsertionContract(
    mode="step_fragment",
    supported_targets=("workflow.step.if", "workflow.step.state_set"),
    workflow_surface="steps list inside a standard workflow scaffold",
    summary="Place one authored step fragment into a standard steps block without rewriting the fragment into a smaller value-only shape.",
)


INSERTION_CONTRACTS: dict[str, SnippetInsertionContract] = {
    EXPRESSION_VALUE_CONTRACT.mode: EXPRESSION_VALUE_CONTRACT,
    STEP_FIELD_CONTRACT.mode: STEP_FIELD_CONTRACT,
    STEP_FRAGMENT_CONTRACT.mode: STEP_FRAGMENT_CONTRACT,
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
blocks:
- guards: []
- steps:
  - name: demo
    {snippet.replace(chr(10), chr(10) + '    ')}
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
blocks:
- guards: []
- steps:
  {indented}
"""
    raise ValueError(f"Unsupported step-fragment target: {target}")
