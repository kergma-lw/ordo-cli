# `next` v1 selection model

## Purpose

This document records one implementable baseline for no-argument `next`.

It does not close the broader design space around local per-workflow continuation,
explicit recovery relations, or richer long-term recommendation semantics.

## Question answered

The v1 question is:

- given the current playbook context, which workflow should run next?

This is a playbook-level recommendation question, not a request to compute the next internal step of one named workflow.

The baseline CLI shape is therefore `ordo-playbook next` without a workflow argument.

## Inputs

V1 should consume, for each visible workflow candidate:

- activation and profile context;
- known versus missing workflow inputs;
- guard evaluation results;
- blocker categories;
- whether required read-only probes were safely evaluable;
- whether the workflow is runnable now.

The model should reuse shared analysis-tree evidence rather than re-deriving weaker summaries from logs.

## Candidate set

Unless a narrower justified scope is selected by runtime policy,
the baseline candidate set is all workflows visible in the current playbook.

Runtime may filter candidates that are clearly incompatible with already-resolved profile or environment context,
but should preserve enough evidence to explain why a candidate was excluded.

## Candidate classes

Each candidate should be placed into one primary class:

1. `ready_now`
2. `near_ready`
3. `awaiting_input`
4. `not_evaluable_now`
5. `weak_match`

An implementation may refine that baseline with narrower explanatory classes such as:

- `context_inspector`
- `near_ready_contextual`
- `awaiting_context_input`
- `ready_with_execution_input`

Recommended meanings:

- `ready_now` — the workflow can run now from currently established read-only knowledge.
- `near_ready` — the workflow is structurally relevant and mostly satisfied, but one or more known blockers prevent running now.
- `awaiting_input` — the workflow may be relevant, but required caller input is missing.
- `not_evaluable_now` — the workflow depends on required read-only facts that runtime could not establish safely enough to judge now.
- `weak_match` — the current context does not strongly resemble the workflow's declared applicability.

## Ranking flow

V1 should rank candidates in layers:

1. identify workflows that belong to the currently active state-backed context whenever runtime can establish that cluster structurally;
2. if an active state-backed context exists, keep unrelated utility workflows behind that context unless the context yields no credible continuation candidate at all;
3. inside one active state-backed context, prefer workflows whose world-state already fits over workflows that require world-state changes;
4. inside one active state-backed context, prefer workflows blocked only by execution-only operator input over workflows blocked by non-input world-state mismatch;
5. keep inspection-only workflows below continuation-capable workflows when the latter are otherwise credible;
6. when no strong state cluster is available, fall back toward the simpler readiness-first ranking;
7. within a semantic precedence tier, apply an explainable weighted score.

Suggested weighted ingredients:

- positive weight for state-affinity with the active runtime-managed context;
- positive weight for shared state-cluster membership when one workflow clearly bridges the current context;
- penalties for pure inspection workflows when state-connected continuation workflows are also competitive;
- positive weight for matched guard count;
- positive weight for matched guard ratio;
- strong positive weight for exact readiness now;
- positive weight for full evaluability;
- negative weight for hard blockers;
- negative weight for missing required inputs;
- negative weight for non-evaluable guard dependencies.

The exact numeric weights are intentionally left flexible,
but the public explanation surface should name which ingredients materially affected the ranking.

## Input sensitivity

V1 should distinguish, when possible, between:

- context-bearing missing inputs that decide which work item or workflow family is relevant;
- execution-only missing inputs that mainly unblock execution of an otherwise already-identified next move.

Execution-only missing inputs should not erase strong state-backed continuation evidence.

## Short human explanation surface

The compact text output for `next` should annotate surfaced workflows with a short reason tag,
for example by indicating that the workflow is state-connected, blocked only by execution input,
inspection-only, world-blocked, or unrelated utility.

That text is not a second recommendation engine.
It is a short rendering of the same semantic axes already used for ranking.

## Tie handling

If multiple candidates remain materially close after ranking,
v1 should not force a fake single-answer certainty.

Instead it should:

- select one best candidate only when the advantage is explainable;
- return nearby alternatives;
- mark the recommendation as competitive or weak when appropriate.

## Output shape expectations

V1 output should contain:

- `best_candidate` when one exists;
- `alternatives` for nearby candidates;
- `candidate_class` for every returned workflow;
- structured ranking reasons;
- key blockers or missing inputs;
- explicit uncertainty when the recommendation is weak.

When explicitly requested for debugging or inspection,
the same result family may expose a graph-oriented view of:

- active state paths;
- the inferred active state cluster;
- workflow-level state reads, writes, and deletes;
- the inferred per-workflow role and cluster membership.

## Non-goals for v1

V1 does not require:

- explicit predecessor declarations;
- explicit recovery-edge authoring;
- one universal global score that is treated as semantically complete;
- guessing hidden workflow intent from prose or neighboring examples.

Those may be explored later as augmentation layers rather than prerequisites for the baseline feature.
