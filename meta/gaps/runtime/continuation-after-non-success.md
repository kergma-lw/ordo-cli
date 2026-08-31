# Gap: continuation after blocked or failed workflow

## Status

This note records a real product gap, not a settled design.

The gap is clear enough to document now, but the runtime contract,
ranking model, and workflow-rules surface for solving it remain open.

## Problem

Ordo already aims to explain:

- whether a workflow is executable now;
- why it is blocked when blocked;
- what happened when execution was attempted.

That is necessary, but it may still be insufficient for agent-safe operation.

An agent may launch a helper workflow, only to discover that:

- one or more guards block execution;
- the workflow starts but fails to complete;
- execution succeeds only partially;
- required inputs or prerequisites are missing;
- the current workflow was the wrong next move for the actual state.

At that point the agent may have a structured explanation of the failure,
but still have no structured basis for deciding what to do next.

In other words, a blocked or failed workflow can currently leave the agent
with a diagnosis but without a continuation surface.

## Why this matters

If Ordo is meant to be a guarded, explainable, agent-safe runtime,
non-success should not throw an agent back into guesswork.

Without a continuation surface, the agent must fall back to one or more weak behaviors:

- re-read many workflows and infer the next move ad hoc;
- scrape prose diagnostics or raw stderr;
- rely on hidden external heuristics not present in the Ordo contract;
- stop entirely even when a safe preparatory or alternative workflow exists.

This weakens several intended Ordo qualities at once:

- explainability;
- machine-usable decision support;
- agent-safe iteration after non-success;
- value beyond a plain step runner.

## Desired outcome

After a blocked or failed workflow, runtime should ideally be able to return a machine-usable continuation surface such as:

- remediation for the same workflow;
- missing prerequisites or missing inputs;
- alternative workflows that improve readiness;
- candidate next moves ranked or grouped by relevance;
- reasons for each suggestion.

This note does not assume that all of those surfaces must exist in v1,
only that the missing capability is real and important.

## Core distinction

This gap should be understood carefully.

The problem is not only:

- explain the current failure.

The problem is also:

- help the agent continue reasoning after current non-success.

That continuation may point to:

- retrying the same workflow after remediation;
- performing a preparatory workflow first;
- choosing a different workflow that is now more appropriate;
- requesting missing input from a human or another system.

## Approach family A: remediation of the same workflow

The narrowest possible approach is to keep continuation local to the failed workflow.

Example intent:

- workflow `close-issue` is blocked because `git.worktree.clean` is false;
- runtime suggests cleaning the worktree, stashing changes, or committing changes;
- workflow `prepare-branch` is not yet suggested directly as a separate candidate,
  only the blocker and remediation hint are returned.

Advantages:

- conceptually small;
- close to existing `blocked` and `explain` semantics;
- avoids catalog-wide workflow search and ranking at first;
- likely easier to make reliable.

Limitations:

- may still leave the agent without a concrete next workflow to run;
- remediation hints can become vague or prose-like;
- does not solve the case where the current workflow was simply the wrong choice.

This approach is attractive as a minimum baseline,
but likely not sufficient on its own.

## Approach family B: workflow recommendation by guard satisfaction ratio

One concrete idea is to evaluate many available workflows against the current context
and rank them by how much of their guard logic already matches.

Informal intuition:

- if a large share of a workflow's guards already evaluate positively,
  that workflow is a strong candidate for the next step;
- if only a small share matches, that workflow is probably less relevant now.

This can be seen as a recommendation heuristic over existing explicit policy.

Example rough scoring shape:

- workflow A: 5 of 5 guards satisfied;
- workflow B: 8 of 10 guards satisfied;
- workflow C: 2 of 6 guards satisfied;
- workflow D: 4 of 7 guards satisfied, but 2 guards are not evaluable because inputs are missing.

Possible recommendation outcome:

- A ranks highly because it is fully ready now;
- B may also rank highly because it is close to ready and strongly matches context;
- C ranks low because current context does not resemble its intended use;
- D may appear separately as a near-match that still needs input.

Why this approach is appealing:

- it reuses the already explicit guard surface rather than requiring a second hidden prediction system;
- it is explainable in terms an author can inspect later;
- it fits the idea that workflows declare their applicability conditions openly;
- it may produce helpful candidate next moves without requiring heavy new metadata.

Why this approach is risky or incomplete:

- raw guard ratio is not always the same thing as best next step;
- a workflow with `1/1` satisfied may be more appropriate than one with `8/10` satisfied;
- one unsatisfied guard may be trivial, while another may be fundamental;
- missing inputs are not the same as failed guards;
- different workflows may have very different guard counts and granularity;
- some workflows may be intentionally broad while others are intentionally narrow.

The important memory here is that this idea is real and attractive,
but should be treated as a heuristic candidate rather than assumed final semantics.

## Approach family C: weighted recommendation over guard outcomes

This family keeps the spirit of the previous idea,
but accepts that not all guard outcomes should contribute equally.

Possible ingredients:

- matched guard count;
- matched guard ratio;
- penalties for hard blockers;
- penalties for missing required inputs;
- penalties for probe evaluation failure;
- bonuses for full evaluability;
- bonuses for exact readiness now;
- bonuses for workflows explicitly marked as safe preparatory actions.

This can produce a more nuanced result such as:

- fully executable now;
- close match but blocked by one repo-state issue;
- relevant but awaiting user input;
- weak match for current context.

Advantages:

- often closer to intuitive usefulness than plain ratio;
- can separate "near-ready" from "not even evaluable";
- can remain explainable if the scoring fields are explicit.

Risks:

- the scoring model may become too magical or arbitrary;
- authors may not predict recommendations well;
- reviewability may drop if weights are hidden or unstable.

This family is plausible, but only if explainability remains first-class.

## Approach family D: explicit recovery or predecessor declarations

Another direction is to declare some continuation relationships directly,
rather than inferring them mostly from guards.

Examples of possible explicit declarations:

- workflow `close-issue` declares `prepare-branch` as a predecessor;
- workflow `publish-release` declares `sync-repo` as a recovery candidate when repo guards fail;
- workflow `open-pr` declares `authenticate-gh` as a prerequisite helper when auth is missing.

Advantages:

- highly predictable;
- easy to explain;
- may capture domain knowledge that guards alone do not expose.

Limitations:

- adds new authoring burden and new contract surface;
- risks duplicating logic already present in guards;
- can drift if explicit continuation declarations and guard reality diverge;
- may become noisy if every workflow needs manual edge declarations.

This direction may work well as an augmentation layer,
especially for important or non-obvious transitions.

## Approach family E: outcome-driven continuation rules

Instead of ranking all workflows against the whole current context,
runtime could look at the actual non-success category and derive next moves from that.

Examples:

- `missing_input.issue` suggests workflows that gather or create issue context;
- `git.worktree.clean == false` suggests cleanup or stash-oriented helpers;
- `gh.auth` failure suggests authentication helpers;
- a failed merge step suggests conflict-resolution helpers.

Advantages:

- continuation can be tightly connected to the reason for failure;
- recommendation may feel more concrete than generic ranking;
- likely easier to justify in explanation output.

Limitations:

- requires a taxonomy of failure and blocker categories rich enough to drive continuation;
- may become a large rule table over time;
- can miss useful workflow candidates that are contextually relevant but not directly tied to the current failure code.

This looks strong when the runtime already has well-normalized blocker categories.

## Approach family F: hybrid continuation model

The most realistic long-term direction may be hybrid.

Example layered flow:

1. explain the current non-success clearly;
2. provide remediation for the same workflow;
3. identify missing inputs separately from false guards;
4. offer explicit recovery or predecessor workflows when declared;
5. use broader recommendation heuristics to rank additional candidate workflows.

This has the advantage of not forcing one mechanism to do everything.

In that model:

- local remediation remains precise;
- explicit declared relations remain predictable;
- heuristic ranking remains available for broader next-step discovery.

The main cost is complexity.

## Important modeling questions

Several questions remain open and should be remembered explicitly.

### What should be distinguished?

Recommendation likely needs to distinguish at least:

- executable now;
- blocked but evaluable;
- not evaluable because required inputs are missing;
- not evaluable because probes could not be run safely;
- weak contextual match.

### What is the unit of suggestion?

Possible outputs include:

- a next action for the same workflow;
- a next workflow to run;
- a missing input request;
- a ranked list of candidates;
- grouped candidates by category rather than a single total order.

### How global should recommendation be?

Possible scopes include:

- only workflows explicitly related to the current one;
- all workflows visible in the current project;
- all workflows compatible with the currently resolved profile or environment.

### How should authors reason about recommendation quality?

If recommendation depends on implicit weights or unstable ranking rules,
it may become harder to review or debug than the workflows themselves.

The continuation surface should remain inspectable enough that a human or agent can answer:

- why was this workflow suggested;
- why did it rank above another candidate;
- what exact facts or blockers shaped the suggestion.

## Recommended framing for now

The most important point to preserve is this:

Ordo appears to have a real gap around continuation after blocked or failed workflows.

The gap is not merely ranking.
The gap is that an agent can be left with no structured basis for choosing the next move after non-success.

Guard-satisfaction ranking is one serious candidate approach,
not a fantasy and not a throwaway thought.
It is worth remembering because it reuses explicit workflow policy and may provide an explainable heuristic over current context.

At the same time, other approaches may prove more effective,
including remediation-first, outcome-driven, explicit recovery edges, or hybrid designs.

## Current non-decision

No stable conclusion is recorded yet about:

- whether continuation should live under `next action`, `recommendation`, or another runtime term;
- whether ranking should be ratio-based, weighted, explicit, outcome-driven, or hybrid;
- whether the first implementation should stay local to the current workflow or search a broader workflow set.

The only strong conclusion recorded here is that the gap is real,
important for agent-safe operation,
and worth treating as a first-class runtime design topic.
