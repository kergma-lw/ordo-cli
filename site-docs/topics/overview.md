# Overview

Find the next public help surface without learning implementation details first.

Use the feature map for authoring choices, then inspect the owning contract or rule.

## Author workflows


- [`features`](features.md): Map a task to an existing authoring surface.
- [`model`](model.md): Read workflow, playbook, profile, state, and routine contracts.
- [`workflow-rules`](workflow-rules.md): Apply the preferred workflow design rules.
- [`capabilities`](capabilities.md): Confirm supported and restricted surfaces.

## Choose control surfaces

- Use guards to decide whether a workflow applies and to reject it early.
- Use gates to decide whether an already-valid path may run.
- Use if only for optional local behavior inside an already-valid path.

## Validate changes

- Run check to see whether the workflow applies and is ready to execute.
- Run review to find workflow-quality issues that readiness alone does not answer.
- Treat check and review as complementary passes after every workflow change.

## Run and inspect


- [`command-line`](command-line.md): Use the public command-line entrypoints.
- [`operations`](operations.md): Browse published connector operations.
- [`examples`](examples.md): Inspect verified repository examples.
