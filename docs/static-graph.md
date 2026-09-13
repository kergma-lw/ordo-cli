# Inspecting static possible processes

## Start here

**Show how workflows connect through persistent state.** Use `graph` to explore
related workflows, where they write shared data, and where that data is removed.
No active task is required.

The final line, `Full list: ordo-playbook workflows list`, points to all published
workflows, including those absent from the state graph.

```console
ordo-playbook graph
ordo-playbook --profile backend graph
ordo-playbook graph --json
```

Read `+field` as a write, `−field` as a deletion, and `?` as a conditional change.
`−context` removes the selected context. `↔` marks another role of the same
workflow, not a separate execution. Branches show data use, not required execution
order. Playbook order helps arrange workflows when relationships leave a choice.
`parameter` stands for a key that has not been selected; the relationship applies
to a matching context instance.

Graph does not read saved state, run probes, or recommend what to do next. A missing
edge does not prove independence in external systems. Use `--json` for detailed
dependencies, conditions, and unresolved relationships.

After exploring the graph, use `workflows show <workflow>` for inputs,
`check <workflow>` to check whether it can run, `explain <workflow>` to understand
why, or `next` for a recommendation in the current environment.

The sections below are the technical reference. The ordered analysis and placement
model is documented in [graph v1](../meta/model/runtime/graph-v1.md); the
[requirements](../meta/requirements/runtime/graph.md) retain the behavior contract.

## Technical reference

Run `ordo-playbook graph` to see state-connected contours without reading stored
state or running probes. Use `ordo-playbook --json graph` for ordered occurrences,
symbolic conditions, address evidence and directed links.

The JSON contract is **ordo.static-process-graph v1** (`schema_version: 1`). This
intentionally replaces the old next-shaped graph response. `next` is unchanged
and remains the command for current recommendations.

## Compact view

Plain `graph` is a minimal workflow tree:

- A generic `Context` or numbered `Contour` heading identifies logical store
  bindings and keys. No business lifecycle name is guessed from workflow names.
- Writing roles appear in existing summary order. Read-only-state consumers
  with a unique source or a join appear once beneath their existing placement
  anchor. Pure alternatives appear once as standalone rows with no selected parent.
  Such consumers may still perform external effects.
- Bootstrap dependencies stay in detailed JSON and a separate `summary.bootstrap`
  section; an optional `Bootstrap dependencies: --json.` line points to them.
  Business contours and reader placement use body-to-body relations, so a shared
  pre_run selector does not alone join otherwise independent processes. Explicit
  body reads can still bridge contexts and produce overlapping contours.
  `summary.bootstrap.only_workflows` means their state accesses are bootstrap-only;
  their main workflows may still perform external work.
- Mutating workflow names have trailing effect parentheses: `+field` for writes,
  `−field` for partial deletion and `−context` for whole-context deletion. `+`
  means a write, not guaranteed first creation. Read-only-state consumers have no
  effect parentheses.
- Joins and joins-with-alternatives use that existing visual anchor without claiming the
  parent is a mandatory prerequisite. This includes catch/fallback cases.
- Consumers with unresolved placement have a separate `Unresolved placement`
  section, rather than disappearing or attaching arbitrarily to a producer.
- Apart from the short effect suffixes, expressions, write/delete details, joins, source identities,
  technical C/S identifiers, activity and statistics are omitted from default
  text. Use `--json` for all of that evidence.

The opening effect legend is `+ writes, − deletes, ? conditional; branches show
data use, not execution order.` The tree is not a state machine, a new workflow order or permission
to run anything. Existing dependency components can contain overlapping processes.

The compact view also states: `Ties within a category follow playbook order.`
When existing dependency placement leaves main workflows or readers at the same
source anchor tied, their authored playbook entry order is retained, not
alphabetical order. Distinct source anchors take precedence: category order does
not move a reader away from its source or reorder its parent placement.

Anchored source/reader blocks retain their order. Free alternative rows use
compatible same-category authored-order bounds around those whole blocks. For
example, a free earlier lifecycle row can precede the producer block containing
a later lifecycle reader, without detaching that reader. If category bounds
conflict inside an indivisible anchored block, preserve the anchor and fall back
to authored root-row order; free same-category rows retain their mutual order.
There is no global category grouping. Category is still discovery metadata: it
does not create links, merge contours, establish applicability or assert execution
precedence. Workflow nodes may carry an additive `category` field for this display
tie-break. Sorted component membership is not display order.

Effects keep first-seen field order and deduplicate by context, operation and
field. `?` comes from existing local if, iteration, short-circuit or conditional-
gate controls. If a repeated effect has any conditional occurrence, or its
occurrences have different guard/gate conditions, the deduplicated effect keeps
`?`. Complementary branches are never treated as unconditional coverage. Ordinary
guard/gate admission alone does not mark every effect with `?`; absence of `?`
is not readiness or execution proof.

With multiple contexts, targets include the logical context label to preserve
ownership; a qualified whole-context deletion names that context directly. A
literal field named `context` is also qualified to distinguish it from root
deletion. The suffix is only a compact inventory, not an atomic transaction or
the exact mutation sequence. Full ordered occurrences stay unchanged in JSON.

`summary` is an **additive** v1 JSON field containing `contours` (context reads,
ordered change/removal groups and users) plus `without_state_access`. Summary
items retain source site IDs; conditions remain available in full. Unknown address
identities are not merged merely because expressions look alike. Plain output
suppresses pairwise invalidation fans and cycle claims, but every original detailed
relation and `possible_loop_components` value remains intact in `--json`.

### Mutation roles and terminal placement

The display vertex is **workflow × logical state × mutation kind** (`write` or
`delete`). Logical state means the existing declaration-owned store family, not
each root field or key. Aliased bindings of the same declared family share a role;
unknown families retain a workflow-local unresolved binding identity. A workflow
mutating N states, of which M have both writes and deletes, has N + M roles.
Fields, keys and established parameter selectors constrain affected data without
creating more roles. Contours remain unchanged, rather than becoming per-address
sections. Pure readers appear once. `↔ state/kind` marks repeated appearances of
the same workflow, never repeated executions.

The finite placement algorithm operates within each existing contour:

1. Project ordered mutation groups onto state/kind roles. Keep writing roles in
   their existing workflow and first-occurrence order. Map existing reader anchors
   to writing roles through source group/site IDs, retaining single-source, join,
   alternatives and unresolved classifications. Insert free alternatives using the
   existing category/authored-order rules around intact blocks.
2. For each delete site, compare body reads and writes with the existing concrete
   and structural address predicates. Only proven concrete overlap or conditional
   family correspondence can justify an anchor. Partial deletes use matching
   fields/subtrees, including possible empty-parent pruning; unrelated sibling
   fields cannot supply an anchor.
3. Identify matching creator blocks and local users whose entire read footprint is
   affected. This includes mutating users through their relevant state role reads.
   Cross-context readers stay at their original anchors and remain in termination
   evidence, without dragging a deletion to an unrelated state's block.
4. Insert the deletion after the last identified block, after its readers. Several
   candidates retain their full bounded candidate-block list; no scoring, recursive
   expansion or mandatory path is invented. Tied deletions retain authored order.
   With only unresolved local readers, use the end of that related unresolved group.
   Without a trusted visible related section, retain an authored-position fallback,
   explicitly marked unresolved when alias evidence is uncertain (otherwise isolated).

This is visual termination, not a requirement to run all readers before deletion.
Cycles, alternatives, selector/instance requirements and conditional rewrites stay
symbolic. A delete followed by a write in the actual workflow remains in that
authored order in detailed JSON, regardless of role display order.

`contour.role_view` is additive: roles retain original `workflow`, state identity,
mutation `sites`, projected `groups` and relevant `read_sites`; rows reference
those roles. Deletion `termination` retains overlap evidence, creator roles,
affected reads, cross-context users, cycles and rewrites. Original workflow nodes,
accesses, conditions, groups, links and order edges are unchanged. This layer does
not change check, review, plan, run, explain, next, validation or bootstrap handling.

### Context names and detailed placement

Stores are shown by logical bindings such as `common_state`, with their key.
If one name denotes different actual stores, the shortest distinguishing path
suffix qualifies it. Different keys and unresolved occurrences stay distinct;
an absolute path is not printed merely to replace a short, unambiguous binding.
Unbound indices in a known logical family can be labeled as `parameter`; their
individual expressions, scopes and equality requirements remain in JSON. Unknown
state families or missing compatible sources remain unresolved.

JSON mutation groups retain contour-local references such as `S1` and `S2`. Existing
handoff links map each reader address to its source candidates; no new analyzer
or condition solver is involved. A source can cover more fields than the reader
uses, and unrelated later writes do not move the reader away from its source.

- **Single source:** one unambiguous change group covers all read addresses by
  concrete or conditional structural handoffs. The tree uses that group's workflow
  as parent, while JSON distinguishes address-only from parametric coverage.
- **Join:** different sources cover different reads. Per-field source references
  preserve the combined dependencies without inventing workflow execution order.
- **Alternatives:** multiple candidates can supply a read. JSON retains all
  candidates and `kind: alternatives`, with `after: null`. The workflow is a
  standalone row, not unresolved and not a child of the last candidate.
  Joins with alternatives preserve each
  read's candidate set instead of enumerating speculative execution paths.
- **Unresolved:** absent compatible producers, unrelated/unknown logical families
  or incomplete reader analysis prevent structural coverage. JSON
  retains source references and their coverage evidence; the tree lists the
  consumer in `Unresolved placement`. No known producer does not mean the workflow
  cannot use previously persisted state.

A join or join-with-alternatives user retains its last displayed source anchor solely for
layout. The tree projects source groups to their writing role without changing JSON
placement. Unresolved users are separate even when they have some known sources.
Pure alternatives have no source anchor; the renderer also handles older cached
summaries that still carry a last-source `after` without nesting that row.
Every user appears once. Cyclic producer dependencies are not topologically sorted
or recursively expanded.

In JSON, conditional source groups remain marked as conditional, and all source/reader
conditions and containing expressions remain in summary evidence or detailed
JSON. Exact address coverage proves neither a suitable value nor source
availability. Placement is data dependence, **not runtime permission**.

Summary adds `placement_version: 1`, group `id`, and each user's `dependencies`
and `placement`. The graph schema remains v1. Older summaries without placement
metadata can be rendered by deriving it from their unchanged detailed data.

### Static profile context

Graph loads declared profiles as data, without activation, probes or current
state reads. Known literal/input/let profile switches and fixed workflow profile
bindings now merge values rather than erasing inputs. Declared workflow defaults,
explicit CLI overrides and playbook entry values remain protected. Explicit CLI
profile authority applies to playbook-owned pre_run switches as in runtime.
Supported unbound calls propagate profile context; bound caller/callee scopes
retain their runtime isolation.

Working directories follow the effective profile. Root playbook state locations
retain their launch-time binding, as in activation: changing cwd does not
silently rebind an already absolute store. Missing profile information is context
uncertainty, not an unknown body access footprint. Fixed-address Story-style state
links remain visible even when an unrelated bootstrap profile selection is unknown.

Unknown selections retain known defaults and bounded possible profile-owned
values. Constant `lookup` over authored maps and symbolic `item` domains can
produce `key_candidates` (up to 32 alternatives) without unrolling the body.
Matching domains are sets of possible addresses, not proof that two runs select
the same key. Text may summarize them as `5 possible keys`; JSON retains their
values and individual access evidence. Unbounded values and remote step results
remain unknown. Graph does not infer task references from external issue bodies.

Access records expose bootstrap/body `phase`, `profile` and `working_directory`;
boundaries expose `impact` as context uncertainty or unknown structure. The full
`components` and `links` still include bootstrap; `business_components` retains
concrete body connectivity, while `structural_components` adds conditional family
connectivity for the summary. Both exclude bootstrap-only links. User placement explicitly
reports `phase: body`, so its all-read coverage is scoped to body accesses.
The graph-bundle verification
path supports real `playbook_text`/`files` fixtures in addition to workflow lists.

## Detailed evidence

### Parametric state families

Intermediate selectors inside one logical state can be structural parameters.
The family is owned by its playbook state declaration (including the declaring
playbook), not by a coincidentally matching workflow role or input name. Explicit
role aliases can reference that same declaration. A nested store override has
its own declaration scope. For engine-supplied models without catalog provenance,
the fallback requires both the binding and known storage path, not names alone.

Literal indices and known protected input bindings remain fixed. Disjoint fixed
indices and closed domains do not link. Profile-supplied inputs describe parameter
slots instantiated by profiles; their concrete values remain in the address.
Profile-backed files can be instances of one declared logical store family. A
structural link between them is conditional on instance correspondence and does
not mean their concrete files alias. Distinct fixed store locations do not merge.

Each address adds `family` and `selector` metadata. Selector origins distinguish
independent workflow/call input scopes, profile selection, shared state-value
origins, iterations and registered results. Used let aliases and forwarded call
arguments preserve known correspondence. Reading the same mutable selection
origin in separate runs still does not prove equal values: equality remains a
requirement. Same variable spelling in independent workflows never proves it.

`structural_links` is separate from the existing concrete `links`. It records
`relation_category`, `selector_correspondence`, `concrete_address_identity` and
requirements such as `selector_equal`, `same_family_instance` and
`read_shape_available`. Compatible ancestor/descendant field paths retain shape
conditions; deletes retain subtree invalidation and possible parent pruning.
No possible concrete address match is relabeled as proven.

`structural_components` and `structural_loop_components` include conditional
family relationships in the body graph. The summary can use `parametric` source
coverage, rendering `common_state[parameter]` and the family lifecycle even when
no concrete profile/key was selected. Distinct selectors remain separate reader
dependencies even when the presentation groups them into one family. Every
equality requirement and original concrete address remains available in JSON.
The single parametric footer is a condition on the picture, not runtime permission.

This changes structural graph semantics only. Next ranking, execution, state
storage identity and actual-file write-before-last-read validation are unchanged.
The verified graph bundle can assert `expected_structural_links`, including its
equality requirements, alongside unchanged concrete-link expectations.

- `accesses` retains each read/set/delete site; `order_edges` records authored
  order, not guaranteed consecutive execution.
- `links` connects cross-workflow sets to reads and deletes to affected reads.
  `address_identity` distinguishes proven static addresses from possible matches;
  `execution` is always possible. Field relationships include ancestor replacement,
  subtree deletion, and possible empty-parent pruning.
- `components` are connected workflow contours; `possible_loop_components` are
  strongly connected sets, which can contain multiple intersecting cycles.
  Neither proves that guards admit an executable cycle.
- Known calls compose and repeated bodies are symbolic, without iteration unroll.
  `boundaries` records incomplete analysis. Unused let definitions create no reads;
  using a registered value does not reread its original storage.
- `activity.status` is `not_requested`. Missing `.ordo.json`, required inputs, or
  available probes does not remove loaded topology.

Store identity uses normalized declared paths, not physical filesystem identity.
Keys are resolved conservatively from static inputs, literals and let bindings.
Dynamic inputs with the same name in different workflows are not proof of equal
values. Unresolved profile selections remain explicit context boundaries.

Graph does not infer business stages, exact reachability, or mutation validity.
The actual-file write-before-last-read rule and check/review/plan/run/explain/next
semantics are unchanged. Source loading failures remain visible boundaries.
