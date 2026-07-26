# Playbook-wide `next` query note

## Why keep this note

This is a parking note for a possible `ordo-playbook next` surface.
It is intentionally not a meta source-of-truth document.
The goal is to preserve the idea so it can be revisited later without prematurely freezing product semantics.

## Core idea

Add a command shaped roughly like:

```bash
ordo-playbook next [--input key=value ...]
```

The command would not execute a workflow.
Instead, it would inspect the current playbook context and return a short structured recommendation surface.

Likely inputs to that reasoning:

- playbook workflows;
- currently available workflow inputs when explicitly provided;
- runtime-managed state already stored by prior workflows;
- read-only guard/probe evaluation that is safe to perform pre-execution.

## Intended value

The main value is not “smart advice” in the abstract.
The main value is context compression.

Agents often spend tokens and time scanning:

- workflow files;
- stored state;
- active profile/task context;
- guard conditions across multiple workflows.

A playbook-wide `next` query could compress that context into a much smaller machine-usable shortlist.

## Preferred output shape

This should not try to declare one universally correct next move.

The more realistic target is a short list of candidate workflows, for example:

```json
{
  "recommended_workflows": [
    {
      "workflow": "task-to-review",
      "readiness": "ready_now",
      "reason": "Stored issue and branch match current repo state; task status is In progress"
    },
    {
      "workflow": "close-task",
      "readiness": "blocked",
      "reason": "Task is not yet In review"
    }
  ]
}
```

Useful `readiness` buckets might include:

- `ready_now`
- `blocked`
- `needs_input`
- `unknown`

## Why this is attractive

- it could reuse existing guard and state surfaces rather than requiring authors to maintain an explicit transition matrix;
- it fits Ordo's analysis-first positioning better than a plain step-runner model;
- it may be especially useful for agent loops where token economy matters.

## Main risks

### Ranking problem

As soon as the system tries to return “the recommendation”, it becomes a ranking engine.
That raises questions such as:

- why this workflow and not another one;
- how to compare blocked vs near-ready vs missing-input candidates;
- how much heuristic behavior is acceptable before recommendations stop feeling trustworthy.

### Noise risk

If the query always returns too many candidates, or returns weak/obvious suggestions, agents may learn to ignore it.

### Cost risk

If the query evaluates too many probes across too many workflows, it may become expensive and noisy.

### State quality risk

If recommendations lean heavily on stored runtime state, the result must remain honest about stale, partial, or unconfirmed context.

## Current design instinct

If this is attempted at all, the safer shape seems to be:

- playbook-wide applicability query;
- short structured shortlist, not one true answer;
- strong reliance on existing state + guards + safe probes;
- no requirement for workflow authors to maintain an explicit transition matrix.

## Non-goal for now

This note does not claim that `next` is already settled, or that it should become a large recommendation subsystem.
It only preserves the narrower idea that a playbook-wide recommendation query may be a valuable runtime surface, especially for agent use.
