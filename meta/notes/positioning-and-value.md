# Ordo positioning and value notes

## Why this document exists

This is a longer working note meant to preserve the line of thought about:

- what Ordo should be;
- what it must not become;
- where it overlaps with `pypyr` and similar tools;
- where it may have real value;
- which conceptual axes are worth keeping in mind while designing the runtime.

This document does not replace `requirements/`, `domain/`, or `scenarios/`.
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

## Ordo as an assistant to both humans and agents

### For humans

A good Ordo should let a person read workflow and runtime output in a way that makes these things visible:

- which policy is enforced;
- why something is blocked;
- what has not yet been executed;
- which steps will be taken after unblocking;
- where review or approval is required.

### For agents

A good Ordo should give an agent a surface that can be relied on programmatically:

- stable status and code categories;
- structured blockers;
- remediation hints;
- explicit next actions;
- distinction between safe or read-only actions and effectful actions.

This matters especially because interactive prompts inside scripts cannot be relied on.

## Why the model should not rely on interactive prompts

A practical constraint:

- an agent is usually good at running non-interactive commands;
- it is poor at, or should not depend on, TTY prompts;
- `read -p`, interactive confirmations, `fzf`, and editor-like flows are an unreliable basis for agent-safe automation.

This leads to an important conceptual idea:

- approval and human gates are better expressed **as data and statuses**;
- not as runtime confirmations inside steps.

A good form is:

- the runtime returns `requires_approval`;
- a human or orchestrating agent explicitly reruns the workflow with approval input;
- no hidden prompt inside a step is needed.

## What analogy is useful to keep in mind

One useful thought was that, in execution philosophy, Ordo may be closer not to ansible or pypyr-style thinking,
but to a more declarative contract/runtime mindset in the spirit of Kubernetes.

Not in scale or distributed architecture, but in emphasis on:

- contract;
- validation;
- eligibility;
- status;
- explanation;
- distinction between intent and action.

Useful caution:

- this analogy must not be stretched too far;
- Ordo must not become fake Kubernetes;
- but the idea of a declarative contract runtime matters here more than the idea of simple step orchestration.

## Which conceptual additions could materially raise value

If thinking about growing project value, it is more important to add meaningful semantics than more step features.

### 1. Effect / capability model

Operations could declare that they:

- only read state;
- mutate local state;
- mutate remote state;
- touch repo / branch / issue / project.

Value:

- better plan/explain;
- better safety;
- more agent-usable risk signaling.

### 2. Approval gates

An explicit status such as:

- safe;
- requires approval;
- manual-only.

Value:

- no hidden interactivity;
- explicit human handoff;
- safer agent execution.

### 3. Remediation model

Not only why something failed, but also:

- can it be fixed;
- what is suggested;
- whether the fix is safe, automatic, or manual.

### 4. Decision provenance

The runtime should be able to explain:

- which profile is active;
- which overrides applied;
- why a particular operation semantics was chosen;
- where the current policy picture came from.

### 5. Next actions as first-class result data

Not just a status, but also:

- rerun check;
- switch branch;
- clean worktree;
- request approval;
- execute now allowed.

### 6. Eligibility model

Separate meaningful states, for example:

- invalid;
- unresolved;
- blocked;
- planned;
- requires_approval;
- executable;
- executed;
- failed.

This is stronger than ordinary `ok/error`.

### 7. Reviewability / agent-safety lint

Even a valid workflow can be poor in quality:

- too shell-heavy;
- hides meaning in string commands;
- uses overly generic operations;
- is poorly explainable.

A separate lint layer could be very valuable.

## What is especially important not to forget

There are several theses worth preserving almost verbatim.

### Thesis 1

**Ordo is not justified merely because it can rewrite a shell ritual into YAML.**

Other tools can already do that well enough.

### Thesis 2

**Ordo is justified only if it provides a stricter execution and decision model than an ordinary pipeline runner.**

### Thesis 3

**The distinction must lie not in syntax but in runtime semantics.**

### Thesis 4

**If `check/plan/explain` do not become first-class and useful, the project can easily slide into pypyr-like territory.**

### Thesis 5

**If the result surface cannot be used reliably by an agent without scraping logs, one of the main goals has failed.**

## What already counts as project truth

It is also important not to forget the repository's own meta-level rule:

- `meta/` is the source of truth;
- when `meta/` fixes something, it is no longer just an idea but a normative project frame.

So after updates in `domain/requirements/scenarios`, the right mindset is:

- pypyr-like framing no longer matches the current meta truth;
- the task is no longer to "decide what Ordo wants to be";
- the task is to **avoid betraying that fixed frame in implementation**.

## What will be the clearest sign of drift

Watch for warning signs such as:

- `explain` becomes merely prettified error output;
- `plan` becomes merely a list of steps;
- guards are implemented as ordinary steps before steps without separate semantics;
- structured result degenerates into log + exit code + text message;
- connector operations lose their semantic and public nature and become thin wrappers around scripts;
- workflow meaning drifts back into shell strings.

If this happens, the project is drifting toward the existing class of pipeline runners.

## What will be a sign that things are going well

By contrast, good signs look like this:

- blocked-before-execution is expressed as a separate concept;
- the runtime can show more than one blocker when it is safe to do so;
- `check` is useful on its own, not merely as "execute lite";
- `explain` provides reasoning categories and next actions;
- a human reviewer can read policy directly in the workflow or profile;
- an agent can branch on structured result codes and statuses;
- operations begin to resemble a small stable contract API.

## Short practical conclusion

If there is ever doubt about why Ordo exists at all,
it is useful to ask:

> **What does a human or agent get here that an ordinary YAML step runner would not provide?**

If the answer is weak, the project is drifting in the wrong direction.

If the answer sounds like:

- better guard semantics;
- better planning;
- better explanation;
- better structured decisions;
- safer agent collaboration;

then the direction is still being held.
