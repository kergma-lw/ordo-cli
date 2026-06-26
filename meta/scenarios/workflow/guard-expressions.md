# Guard expression scenarios

## Short review scenario

Reviewer opens a workflow and should be able to see, in a small vertical slice:

- which conditions gate execution;
- which conditions are simple facts versus comparisons;
- which actions follow if those conditions pass.

## Shell-replacement scenario

A project has sprawling local shell helpers with many execution preconditions.

Desired migration experience:

- move operational integration details into public probes and actions;
- keep workflow policy compact enough that the preconditions are easier to read than the original shell control flow;
- avoid replacing shell sprawl with a long list of repetitive structured guard blocks.

## Agent authoring scenario

Agent composes a workflow from documented public probes and actions.

Desired experience:

- use compact expressions for ordinary policy;
- avoid inventing a new named probe only to express a simple comparison such as equality, inequality, or membership;
- receive diagnostics that identify the failing subcondition and observed value.
