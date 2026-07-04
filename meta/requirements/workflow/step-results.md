# Workflow requirements for step result registration

## Role

- The workflow authoring surface should support explicit registration of structured results from prior executed steps.
- This surface should support ordinary step-to-step data flow without requiring persistent runtime state.

## MVP semantics

- An operation-call step may declare an optional `register` identifier.
- A later value expression may read a prior registered result through the `step...` root.
- The MVP registered-result surface should expose `status`, `summary`, and `outputs...`.
- Register identifiers must be workflow-local and must not be inferred from step names.
- Register identifiers must be unique within one workflow.
- A reference to a register that does not exist must fail validation.
- A reference to a later step must fail validation.

## Boundary discipline

- Registered step results must remain execution-local rather than persistent across runs.
- Registered step results must remain distinct from the `state...` capability.
- Guard expressions must not read `step...` values.
- The MVP should not require step-result access for `state_set` or `state_delete` forms.
- The MVP should not expose raw diagnostics or arbitrary transport detail from step results as first-class value-expression surface.

## Explainability

- The authoring contract should make step-to-step data flow explicit at the use site through `step.<register>...` references.
- Validation should report duplicate registers, missing registers, and forward references with structured diagnostics.
