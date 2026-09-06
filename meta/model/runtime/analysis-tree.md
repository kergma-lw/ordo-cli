# Shared analysis-tree model

## Role

Runtime may build one shared context-aware analysis tree before choosing which public mode-specific question to answer.

That tree is not itself a public mode.
It is the reusable internal evidence model that later projections such as `review`, `check`, `plan`, `explain`, and `next` may read differently.

## Core idea

The shared tree should preserve one workflow-shaped pre-execution analysis basis rather than splitting equivalent reasoning across separate ad hoc pipelines.

The same analysis tree may retain:
- validation and semantic-validation outcomes;
- activated profile, override, and playbook context;
- known versus missing activation inputs when structure is still analyzable;
- workflow-relevant versus surplus profile-supplied activation context;
- declared-input usage classification and evidence for why each input was treated as control-bearing, trusted profile-provided consumed context, ambient profile context, effect-targeting, or unused;
- ordered block, guard, and step structure;
- read-only observations and their canonical shapes;
- step-level operation kind information needed to keep probe-versus-action semantics aligned across analysis and execution;
- statically knowable expression diagnostics for builtin misuse that can be proven before execution;
- advisory preflight-observation recommendations together with matched and missing coverage;
- incomplete, weakened, or halted analysis reasons.
- deferred top-level state mutation nodes, without mutation results or reusable observations, and subsequent invocation barriers.

## Projection rule

Different public modes ask different questions of the same underlying tree.

- `review` asks authoring-quality questions such as whether applicability is expressed early and whether useful observations are missing.
- `check` asks runtime-truth questions such as whether execution is allowed, blocked, or still unknown from current knowledge.
- `plan`, `explain`, and `next` may reuse the same retained evidence later rather than reconstructing it indirectly from weaker summaries.

These projections are siblings.
`review` is not merely an earlier `check`, and `check` must not silently inherit authoring-only advice as executability policy.

## Boundary rule

Authoring guidance and runtime executability semantics must remain distinct even when both are computed from the same shared tree.

In particular:
- advisory recommendation gaps may weaken authoring guidance, explanation strength, or preflight-support quality;
- those same gaps must not by themselves become hidden blockers or implicit workflow prerequisites.

Expression-diagnostic advice follows the same boundary:
- a builtin misuse that is statically certain from authored workflow structure should surface before execution where practical;
- canonical examples include wrong builtin arity or a `format` expression whose placeholder count cannot match its argument count;
- dynamic or unresolved expressions that are not statically decidable should remain runtime-only rather than produce false positives.

Input-classification advice follows the same boundary:
- a declared input that meaningfully drives applicability, control flow, profile switching, state writes, publish shape, or effectful target selection may justify a missing-validation finding;
- a consumed input that is supplied by the selected profile as trusted workflow context is not automatically missing-validation debt merely because it reaches workflow operations or publish surfaces;
- a declared input that is merely carried in from profile defaults as stable repository or project context is not automatically missing-validation debt;
- a declared input that is not meaningfully used at all should surface as unused declaration debt rather than as missing validation.

Input-authoring advice is separate from missing-validation classification:
- `review.workflow.input_description_missing` warns for every root workflow input whose description is absent, null, empty, or whitespace-only, including optional, defaulted, profile-supplied, and unused inputs. Its suggested fix is `add_input_description`.
- `review.playbook.input_caller_slot_missing` warns for every declared input with neither a non-user source (a declared default, selected launch-profile input, or concrete workflow-entry binding) nor a caller slot in the playbook entry's `with` mapping. Unselected profiles and one-run CLI overrides do not count as non-user sources.
- The caller-slot finding suggests `expose_caller_input`, with `x:` for a required workflow input or `x?:` for an optional one. Either existing caller-slot form suppresses this advisory, but does not change the workflow's required-input contract.
- Both codes have level `warning` and category `input_authoring`. Presence of a default or supplied key counts even when its value is null, false, or zero.
- Available static findings remain published when review is `unavailable`, including activation failures after the root declarations can be inspected. Existing validation and resolution diagnostics, statuses, and exit behavior remain authoritative; these warnings do not make activation succeed or fail.
- Compact CLI review output includes every available finding, in order, under the compatibility field `top_findings`; only individual finding details are summarized. This also applies to unavailable review after activation failure. JSON output retains full finding details.
- `check`, `plan`, `run`, `explain`, and `next` do not publish these authoring advisories and retain their existing semantics. Required caller slots still require explicit caller input even when a default exists; optional caller slots do not relax required workflow inputs.

Activation-context advice follows a related boundary:
- profiles may provide more ambient context than one workflow uses;
- profile-supplied surplus context should remain non-blocking unless the workflow actually depends on it;
- explicit caller-supplied unknown inputs remain separately diagnosable because they express direct user intent rather than reusable profile breadth.
- expected profile surplus should remain preserved as internal analysis evidence rather than promoted to ordinary default review/check diagnostics.

## Preservation rule

The shared tree should retain enough material for later runtime-oriented consumers.

At minimum it should preserve:
- guard relevance and evaluated-versus-pending state;
- structural halt boundaries and incomplete reasons;
- observation coverage and exact missing-observation shapes;
- context effects that influence later reasoning surfaces;
- weakening or invalidation evidence needed for later `plan`, `explain`, and `next` work.
