# `graph` v1 analysis and placement model

## Purpose

This document records the implemented baseline for static graph analysis and
compact placement. The detailed contract is in
`../../requirements/runtime/graph.md`.

It answers: which possible processes connect the published workflows through
persistent state, and how can those relationships be presented compactly?

Unlike `next`, it does not recommend an action for the current environment.
V1 does not read stored values, evaluate external probes, or invoke next ranking.
Activity remains a separate, unrequested annotation.

## Inputs

The model consumes:

- published workflows in authored playbook order and their categories;
- ordered state read, set, and delete occurrences;
- declared storage bindings, profile metadata, and safely resolved inputs;
- symbolic conditions, calls, and repeat bodies;
- concrete address evidence and parameterized state-family relationships.

Missing current state does not remove authored structure. Unknown inputs or
composition boundaries retain explicit uncertainty.

## Analysis and placement flow

V1 applies six stages in order:

1. **Extract ordered accesses.** Preserve occurrence identity, conditions, and
   composition. Expand used let bindings without treating registered values as
   fresh storage reads. Keep bootstrap provenance separate from body accesses;
   bootstrap alone must not determine business contours or reader placement.
2. **Infer data relationships.** Match compatible storage, key, and field paths.
   Separately derive conditional structural links within declaration-owned state
   families, retaining selector and instance correspondence requirements. Build
   connected contours from these relationships, not from names or categories.
3. **Project sources onto all roles.** Form display roles by workflow, logical
   state family, and mutation kind. Map each body's existing read/handoff sites
   to source write roles using proven concrete or established structural links.
   All roles of a workflow share its actual workflow read footprint; state-local
   role `read_sites` remain intact. Pure readers have one display vertex. Ignore
   same-workflow sources as parents. Retain per-read alternatives and unknown
   source evidence. Fallback and conditional reads participate without filtering.
4. **Build a bounded forest.** Compute handoff-only workflow SCCs before nesting;
   invalidation is not precedence. Do not choose a parent across an internal SCC
   edge. Establish unique-source parents, then resolve multi-source placements
   to a fixed point (at most vertex-count + 1 passes). When different reads'
   sources form an already established ancestor chain, choose its deepest source.
   Retain other sources as compact references. Multiple source roles for the same
   read are alternatives, even if those writers form a chain. Incomparable joins
   and alternatives use their deepest established common ancestor outside the
   candidate set, or stay at root. Never use the last source as a tie-break.
   Check candidate ancestry before attaching; every vertex has one forest slot.
5. **Order sections and terminal roles.** Use authored workflow order for free
   roots and siblings, with existing occurrence order for same-workflow ties.
   Delete roles follow other children of their parent. A delete with no known
   read sources may use its existing trusted creator-overlap evidence to identify
   a section. Root deletions follow the last related creator/local-user section;
   partial deletions do not use unrelated sibling fields or cross-context users
   as terminal anchors. Without an established section, retain authored position
   and the isolated/unresolved termination evidence.
6. **Add multi-source sightings.** For an incomparable `join` with distinct,
   unambiguous body-read source roles, display the operation beneath each source.
   Walk the established forest in display order and choose its first cycle-safe
   source for the one full occurrence. This is a layout choice, not an inferred
   dependency or an input to chain inference. Other source sightings are reference
   leaves pointing at the same node. Deduplicate by source vertex, not field/site;
   never copy the target's children. Per-read alternatives, mixed joins with
   alternatives, incomplete/unknown source sets, creator-only deletion anchors
   and internal SCC placements keep the established forest presentation. Conditional
   and fallback data use is eligible without a requiredness filter.

These are sequential placement heuristics, not a global optimization or an
execution scheduler. In particular, the deletion pass can change relative order
between a delete role and unrelated writer rows.

## Role identity

A workflow may have one write role and one delete role for each mutated logical
state family. Fields and keys constrain effects but do not create extra roles.
For N mutated states, M of which have both mutation kinds, there are N + M roles.

Repeated appearances reference one original workflow, not independent calls.
Reading alone does not create extra mutation roles. Detailed accesses retain
intra-workflow ordering, conditional effects, and deletion followed by rewriting;
visual role separation does not change any of those semantics.

## Ambiguity and author order

The playbook provides stable presentation preferences, not causal edges:

- all roles and pure readers use the same source-parent rules;
- unique-source anchors are preserved;
- alternatives select no candidate parent and retain all source references;
- chain joins use the deepest established source, not a mandatory predecessor;
- incomparable sources may share an ancestor without selecting any one source;
- categories do not override authored order within the new forest;
- deletion placement follows its affected region rather than enforcing the
  original position among unrelated rows.

This is a bounded display forest, not a full dependency sort or a workflow DAG.
Legacy summary rows and user placements remain available for compatibility;
`role_view.forest` retains established source parents. Its additive `display_rows`
is the final occurrence layout: `node`, `parent`, `reference`, `conditional` and
`basis` distinguish full occurrences from reference leaves. It does not add
workflow/role identities or change established parents. Each node has one full
row and at most one leaf for each other distinct source vertex. Canonical parent
ancestry is checked before moving; iterative rendering cuts revisited targets
to leaves and never expands a reference's subtree.

## Evidence and explanation

Concrete address identity and structural parameter correspondence are distinct.
Matching field names alone do not connect unrelated state declarations. Unknown
selectors can support conditional family links without proving equal runtime
values. Fixed incompatible addresses remain distinguishable.

Compact text shows workflow names, effect summaries, reader branches, repeated
role markers, and unresolved placement when needed. The opening is
`Shared context: writers → readers, not execution order.` followed by
`+ write, − delete, ? conditional.` Pure alternative reader roots carry
`(data use; alternative sources)` rather than suggesting a mutation. A singleton
contour has no heading; multiple contours use short numbered headings without
address lists. Ordering and visual-deletion explanations belong here and in help,
not in the default opening legend. JSON retains source sites,
conditions, candidate sources, address evidence, and placement reasons.

Fallback reads are data use, not mandatory runtime requirements. Unknown
optionality never changes a parent. Existing read branch conditions and a narrowly
recognized direct state pipeline with a missing-state `catch` may annotate a
source name with `?`; this means some use is conditional/fallback and is separate
from `+field?` mutation conditions. Unrecognized complex expressions receive no
speculative `?`. Annotation never prunes source links. Unknown source identities
and incomplete structure remain explicit notes without erasing known anchors.
Forest nodes retain shared-workflow read IDs, per-source read IDs, source roles,
conditional-source annotations, unknown reads, incompleteness, parent and reason.

`↔ (reference)` means the same operation is shown again, not another execution or
an alternative prerequisite. For a mixed workflow, `↔ state/kind (reference)`
also identifies which existing role the leaf refers to. The full occurrence keeps
its effects and extra source references; the leaf omits effects and descendants.
A conditional leaf carries `[conditional use]`, independently of effect `?`.

## Non-goals and runtime parity

V1 does not infer business meaning from workflow or field names, reconstruct
external object lifecycles from GitHub issue contents, prove path reachability,
or require all displayed readers to execute before deletion. Possible graph loops
are not executable-cycle proofs.

This model changes neither `next` selection nor the applicability and execution
contracts of `check`, `review`, `plan`, `run`, and `explain`. Static storage-family
relationships do not replace actual-file identity in runtime validation.
