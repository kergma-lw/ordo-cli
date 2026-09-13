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

V1 applies five stages in order:

1. **Extract ordered accesses.** Preserve occurrence identity, conditions, and
   composition. Expand used let bindings without treating registered values as
   fresh storage reads. Keep bootstrap provenance separate from body accesses;
   bootstrap alone must not determine business contours or reader placement.
2. **Infer data relationships.** Match compatible storage, key, and field paths.
   Separately derive conditional structural links within declaration-owned state
   families, retaining selector and instance correspondence requirements. Build
   connected contours from these relationships, not from names or categories.
3. **Lay out writers.** Form display roles by workflow, logical state family, and
   mutation kind. Start write-role blocks in authored workflow order, with roles
   within a workflow ordered by first occurrence. V1 does not topologically sort
   writers by their reads. Read-only workflows remain placement candidates rather
   than mutation roles.
4. **Place readers.** Find source groups covering their body reads. A unique
   source anchors a reader beside its writer. Joins use the last selected source
   group in the original group order, mapped to a write role; this is a layout
   choice, not a newest-writer claim. Pure alternatives remain standalone rows.
   Use compatible same-category author order to place those free rows without
   splitting anchored blocks. Keep unresolved readers visible separately.
5. **Place deletions.** Match deleted data to creator roles and local users, then
   insert each delete role immediately after the last related displayed block.
   Partial deletion concerns overlapping fields or subtrees, not all data in the
   state. Cross-context users retain their own anchors without pulling deletion
   into unrelated sections. With no established section, use an explicitly
   isolated or unresolved authored-position fallback, not the global end.

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

- writer blocks start in authored order;
- unique-source anchors are preserved;
- pure alternatives select no parent and retain all candidates in detailed data;
- joins and joins with alternatives retain their layout anchors without claiming
  that every source must execute;
- compatible category order guides free-row placement; conflicting bounds fall
  back to authored root-row order while preserving anchored blocks;
- deletion placement follows its affected region rather than enforcing the
  original position among unrelated rows.

Thus v1 is not accurately described as a full dependency sort with playbook order
used only to break ties. It is an authored writer layout refined by reader and
deletion placement.

## Evidence and explanation

Concrete address identity and structural parameter correspondence are distinct.
Matching field names alone do not connect unrelated state declarations. Unknown
selectors can support conditional family links without proving equal runtime
values. Fixed incompatible addresses remain distinguishable.

Compact text shows workflow names, effect summaries, reader branches, repeated
role markers, and unresolved placement when needed. JSON retains source sites,
conditions, candidate sources, address evidence, and placement reasons.

Fallback reads are included conservatively, not converted into mandatory runtime
requirements. Unknown structure must not be silently hidden; uncertainty in one
context must not erase independently established relationships.

## Non-goals and runtime parity

V1 does not infer business meaning from workflow or field names, reconstruct
external object lifecycles from GitHub issue contents, prove path reachability,
or require all displayed readers to execute before deletion. Possible graph loops
are not executable-cycle proofs.

This model changes neither `next` selection nor the applicability and execution
contracts of `check`, `review`, `plan`, `run`, and `explain`. Static storage-family
relationships do not replace actual-file identity in runtime validation.
