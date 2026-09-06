# Workflow show input discovery parity

## Scope

Discovery publishes the implemented complete input contract from `playbook.py` and `cli.py`; this documentation work does not change engine behavior. Plain and JSON show output share one `inputs` mapping and launch-profile identity. Source coverage uses the same rule as review, without publishing profile values or treating source presence as readiness.

## Describe readiness review

Reviewed the text output of these public handles against all nine points in the help-discovery describe readiness checklist:

- `workflow.inputs`: positive declaration definition, fragment-input and entry-binding boundaries, neighboring handles, readable terminology, full workflow excerpt, and source-parity caveat are present.
- `workflow.inputs_contract`: declaration requiredness is distinguished from caller slots and coverage; the full workflow excerpt demonstrates described required and optional inputs without inventing defaults.
- `playbook.workflows`: catalog definition and workflow-body/pre-run boundaries are explicit; the catalog fragment demonstrates concrete bindings and discovery metadata.
- `playbook.workflows.with`: concrete bindings and both caller-slot forms have excerpt-backed examples; provided coverage does not waive required caller input. Declaration and CLI-override boundaries remain explicit.
- `command-line.ordo-playbook`: definition, boundaries, neighboring handles, complete input output semantics, and text/JSON publication are covered. Canonical executable CLI examples remain blocked: the current snippet harness cannot validate CLI activation examples. This surface is not fully ready under the canonical-example checklist points; command strings are usage guidance, not verified execution examples.

The four authored-YAML surfaces retain the supported `excerpt_verified` path. Excerpts demonstrate intended authoring, not validation of CLI output or activation. No snippet-world or executable CLI coverage is claimed. Updated examples and `features` use the same source-presence terminology.

## Surface impact

- `check`, `plan`, `run`, `explain`, and `next`: no behavior changes in this documentation-only work. Discovery is not activation or execution readiness; required caller input remains required even if another source exists.
- `review`: shared authored missing-source coverage is documented. Plain `top_findings` contains every available finding in order with compact details, including unavailable review; JSON retains full details.
- `features`, `command-line`, relevant input and playbook describes, and searchable help metadata publish the changed discovery contract.
- `overview`, `model`, `workflow-rules`, `capabilities`, and `operations`: reviewed for impact; no new authoring primitive, runtime mode, validation rule, connector operation, or supported capability is introduced. Existing activation contracts and the paired check/review guidance remain valid.

## Verification limits

Read-only help rendering is the available check for this work. Help assertions and golden expectations are updated, but tests are not executed: workflow discovery provides no suitable targeted test workflow, and the user explicitly prohibits `verify-all-tests` until a separate instruction. Derived packs must be regenerated with `ordo-playbook run meta-packs-build`.
