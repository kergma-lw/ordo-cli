# Ordo positioning and value notes

## Why this document exists

This is a longer working note meant to preserve the line of thought about:

- what Ordo should be;
- what it must not become;
- where it overlaps with `pypyr` and similar tools;
- where it may have real value;
- which conceptual axes are worth keeping in mind while designing the runtime.

This document does not replace `meta/requirements/`, `meta/domain/`, or `meta/scenarios/`.
It exists as a freer but still project-internal reference for positioning.

## Short formula

The shortest formula worth preserving is:

> **Ordo = guarded, explainable, agent-safe workflow runtime.**

Or a little longer:

> **Ordo is valuable not as a step runner, but as a runtime that can validate, explain, block, and suggest the next safe step before execution.**

## What we have been trying to distinguish it from

There is a real risk that Ordo will be perceived as:

- yet another YAML task runner;
- a shell wrapper with nicer syntax;
- a `pypyr`-like pipeline tool with different terminology;
- a procedural step engine that merely has a `guards` section.

This risk is not imaginary.

At the surface level, Ordo really does overlap with an existing class of tools:

- YAML workflows;
- steps;
- CLI execution;
- Python extensibility;
- local automation;
- repo rituals / helper automation.

So YAML, steps, and operations by themselves do not create distinct value.

## Main distinction

The most useful frame for distinction right now is this:

- a task runner or pipeline engine primarily answers: **what to execute**;
- Ordo must also be able to answer: **whether execution is allowed, why, what would happen, and what to do next**.

This yields a more precise pair:

- `pypyr`-like mindset: **execution-first**;
- Ordo mindset: **analysis-first**.

This does not mean Ordo is a "compiler" in the strict sense.
But it does lean toward a multi-stage runtime:

1. parse;
2. validate;
3. resolve;
4. evaluate guards/policy;
5. plan/explain;
6. execute.

It is useful to remember: Ordo does not need compiler-like terminology,
but it must be **more contract-like and analysis-first** than a plain pipeline runner.

## Why `execute` alone is not enough

For human-authored and especially agent-authored workflows, a single execution mode is insufficient.

Separate first-class modes are needed:

- `check`
- `plan`
- `execute`
- `explain`

The reason is simple:

- a human needs to understand what will happen and why something is blocked;
- an agent needs to make decisions from data rather than guesses from logs;
- local operational automation is often risky and needs a safe-before-fast model.

If Ordo loses these modes as a first-class surface and collapses into "run steps",
its value moves much closer to existing runners.

## Why guards matter, but are not sufficient by themselves

At one point there was a hypothesis that guards could be Ordo's main differentiator.

Clarification:

- guards do matter;
- but **guards alone are not enough** for a distinct product identity.

Why:

- other systems also have assertions, prechecks, conditions, and fail-fast behavior;
- a separate `guards` section does not by itself create a new runtime class;
- if everything else remains step-runner-like, the project will still read as close to `pypyr`.

So guards matter only as part of a larger combination:

1. guards as a first-class policy phase;
2. `check/plan/explain` as real runtime modes;
3. structured results;
4. connector and operation contract;
5. agent-usable reasoning.

## Where `pypyr` looks strong and where it does not

The honest picture looks like this.

### Where `pypyr` looks strong

- a fast practical automation runner;
- YAML pipelines are already there;
- control flow, retries, and conditions already exist;
- custom Python steps are straightforward;
- error handling is mature;
- local automation is directly supported.

If the job is to **write local helper pipelines quickly**, `pypyr` may be entirely sufficient.

### Where `pypyr` looks like a less natural foundation

If the goal is to build a runtime that first-class can:

- distinguish blocked-before-execution from execution-failed;
- explain policy decisions before side effects;
- return a stable structured decision/result surface;
- support agent reasoning without log scraping;
- make guards not just a convention but a separate phase;

then `pypyr` looks like a less natural conceptual fit.

Important: this is not an accusation that `pypyr` is a weak tool.
It is a statement that its center of gravity is different: **run pipelines, manage flow, handle errors**.

## What is a weak test for Ordo and what is a strong one

### Weak test

A linear scenario like this:

1. check A
2. call B
3. do C

Such a scenario is easy to express in shell, in `pypyr`, and in dozens of other systems.

### Stronger test

A policy-heavy scenario with:

- several independent blockers;
- distinction between check, plan, and execute;
- different failure categories;
- repo-specific or profile-specific policy;
- the question "what is allowed right now?";
- a requirement for explanation, not only execution.

Examples of such scenarios:

- `close-task` with several guard failures;
- a shipping ritual with different verification profiles;
- a workflow where an agent must first determine the allowed action, not merely execute something;
- a case where it is useful to show several blockers at once rather than only the first.

## Why explainability is central here

If Ordo deserves to exist as a separate thing at all,
one of its strongest axes is the explanation surface itself.

Not a "pretty log", but a structured answer to questions such as:

- why the workflow is blocked;
- which guards failed;
- which steps are executable, blocked, or skipped;
- what would happen in `plan` mode;
- which next safe action is available.

For a human, this increases reviewability.
For an agent, it turns the runtime into a decision-support surface.

If `explain` collapses into:

- tracebacks;
- replayed error text;
- a list of steps;

then the distinction from a task or pipeline runner will be weak.
