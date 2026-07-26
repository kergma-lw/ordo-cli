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
- ordered block, guard, and step structure;
- read-only observations and their canonical shapes;
- advisory preflight-observation recommendations together with matched and missing coverage;
- incomplete, weakened, or halted analysis reasons.

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

## Preservation rule

The shared tree should retain enough material for later runtime-oriented consumers.

At minimum it should preserve:
- guard relevance and evaluated-versus-pending state;
- structural halt boundaries and incomplete reasons;
- observation coverage and exact missing-observation shapes;
- context effects that influence later reasoning surfaces;
- weakening or invalidation evidence needed for later `plan`, `explain`, and `next` work.
