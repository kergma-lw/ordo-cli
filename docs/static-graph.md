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

Shared context: writers → readers, not execution order. A free reader root is
marked `(data use; alternative sources)`: it uses data without mutating the context.
This shows shared data, not a mandatory sequence. Guards and `check` determine
applicability; alternative ends are not sequential steps.

Read `+field` as a write, `−field` as a deletion, and `?` as a conditional change.
`−context` removes the selected context. `↔ state/kind` marks another role of the same
workflow, not a separate execution. Branches show data use, not required execution
order. Playbook order helps arrange workflows when relationships leave a choice.
`parameter` stands for a key that has not been selected; the relationship applies
to a matching context instance.

Writers and deletions can also appear on branches. A workflow using several
sources sits under the deepest source when those sources already form a chain.
`also reads from: name` keeps its other source visible. For distinct data from incomparable
sources, the operation appears under each source. The first source in display
order holds the full occurrence; other sightings are `↔ (reference)` leaves,
without repeating the operation's subtree or execution. Alternative writers of
the same data stay together rather than spreading across branches.
`reads from: name?` marks known conditional
or fallback data use; it is separate from the conditional write in `+field?`.
Fallback reads still count as data use.

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

- A single contour has no heading. Multiple contours use short `Contour 1`,
  `Contour 2` headings without address lists. Detailed identities stay in JSON.
- Writing roles, deleting roles and pure readers use the same source-parent rules.
  A unique source anchors its users; an established source chain anchors a join at
  its deepest source. Incomparable joins and alternatives use a common ancestor
  outside their source candidates when available, otherwise remain roots.
  Root alternatives are marked `(data use; alternative sources)`.
  Unambiguous joins using distinct data pieces have one full occurrence on the
  first source branch and reference-only leaves on the other source branches.
  This display choice does not make a source a preferred prerequisite.
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
- Compact `read sources:` and `also reads from:` references preserve joins without requiring
  every source to execute. This includes catch/fallback cases.
- Unknown sources and incomplete structure remain short notes beside established
  placement. Unknown optionality does not remove any known source or parent.
- Expressions, detailed evidence, technical C/S identifiers, activity and
  statistics stay in `--json`.

The opening line is `Shared context: writers → readers, not execution order.`
The next legend is `+ write, − delete, ? conditional.` Only repeated roles add
`↔ another role of the same workflow.` The tree is not a state machine, a new workflow order or permission
to run anything. Existing dependency components can contain overlapping processes.
If reference leaves exist, a short `↔ (reference) the same operation, shown again.`
legend distinguishes them from state/kind role markers. Leaves show no effects
or descendants. `[conditional use]` preserves a known conditional/fallback relation.

When existing dependency placement leaves main workflows or readers at the same
source anchor tied, their authored playbook entry order is retained, not
alphabetical order. Distinct source anchors take precedence: category order does
not move a reader away from its source or reorder its parent placement.

Free roots and siblings retain authored workflow order. Within one workflow,
existing role occurrence order breaks ties; deletions follow other children of
their section. Categories remain discovery metadata and do not override this
ordering or create data links. Sorted component membership is not display order.

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
suppresses pairwise invalidation fans and executable-cycle claims, but every original detailed
relation and `possible_loop_components` value remains intact in `--json`.

### Mutation roles and terminal placement

The display vertex is **workflow × logical state × mutation kind** (`write` or
`delete`). Logical state means the existing declaration-owned store family, not
each root field or key. Aliased bindings of the same declared family share a role;
unknown families retain a workflow-local unresolved binding identity. A workflow
mutating N states, of which M have both writes and deletes, has N + M roles.
Fields, keys and established parameter selectors constrain affected data without
creating more roles. Contours remain unchanged, rather than becoming per-address
sections. Every role and pure reader has one full occurrence. `↔ state/kind` marks repeated appearances of
the same workflow, never repeated executions.

The finite placement algorithm operates within each existing contour:

1. Project ordered mutation groups onto state/kind roles. Map all known body
   handoffs to write roles through source-site IDs. Every role uses its workflow's
   actual shared read footprint; this does not invent role-specific executions.
   Preserve per-read alternatives and all conditional/fallback accesses.
2. Compute handoff-only SCCs. Invalidation is not parent precedence, and internal
   SCC edges cannot choose parents. Establish unique-source anchors first, then
   resolve chain joins and common ancestors in a bounded fixed-point pass. Check
   ancestry before nesting so every display vertex has exactly one acyclic slot.
3. A delete with no known read sources may use trusted creator-overlap evidence.
   Existing address predicates constrain this to affected fields/subtrees. Keep
   cross-context users as evidence without using unrelated sections as terminal
   anchors. No new handoff or execution edge is added for this visual placement.
4. Order free roots and children by authored workflow order. Nested deletions
   follow other children; root deletions follow their related creator/local-user
   sections. Preserve isolated/unresolved authored-position fallback where no
   trusted section exists. No mandatory path or reader-before-delete rule is inferred.
5. Add source-local reference rows for incomparable joins whose distinct reads
   have unambiguous sources. Pick the first cycle-safe source in established
   forest display order for the full occurrence, without modifying source-parent
   evidence. Attach one reference leaf per other source vertex; repeated sites and
   fields do not multiply sightings. Alternatives, incomplete source sets and
   internal SCC placements keep their existing conservative presentation. A
   reference never owns children. Canonical ancestry and rendering visited checks
   keep traversal finite. Conditional/fallback use is not a requiredness filter.

This is visual termination, not a requirement to run all readers before deletion.
Cycles, alternatives, selector/instance requirements and conditional rewrites stay
symbolic. A delete followed by a write in the actual workflow remains in that
authored order in detailed JSON, regardless of role display order.

`contour.role_view` is additive: roles retain original `workflow`, state identity,
mutation `sites`, projected `groups` and relevant `read_sites`; rows reference
those roles. Additive `forest` nodes identify the actual compact parents and
children, sources, per-source read IDs, conditional-source annotations, unknown
reads and incomplete structure. Legacy rows and per-user placements remain
compatibility evidence; they do not choose the new forest parents.
`forest.display_rows` adds the final full/reference occurrence layout, with a
target `node`, display `parent`, `reference` flag, source-use `conditional` flag
and `basis`. Node identities and established parents remain unchanged; display
parent choices never become source-chain evidence.
Deletion `termination` retains overlap evidence, creator roles,
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

- **Single source:** known handoffs identify one source write role. The tree uses
  that role as parent, while JSON distinguishes concrete from structural evidence.
- **Join:** different sources cover different reads. Per-field source references
  preserve the combined dependencies without inventing workflow execution order.
- **Alternatives:** multiple candidate roles can supply a read. The forest selects
  none of those candidates as parent, even when the writers form a chain. It uses
  an established common ancestor outside the candidate set or a standalone row.
  Joins with alternatives preserve each
  read's candidate set instead of enumerating speculative execution paths.
- **Unknown sources:** absent compatible producers, unrelated/unknown logical
  families or incomplete reader analysis retain explicit notes. Known anchors
  remain usable. No known producer does not mean the workflow
  cannot use previously persisted state.

A join uses its deepest source only when all sources form an established ancestor
chain. Otherwise it uses an established common ancestor outside the candidate set
or stays at root with all references. No last-source tie-break is used. Every role
and pure reader has one canonical identity. The display-reference pass can show
unambiguous distinct-data joins under each source without copying their subtrees.
Internal handoff cycles remain unnested with explicit
data-use-cycle notes; downstream unique users can still nest below cyclic writers.

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
