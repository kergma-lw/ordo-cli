# Static possible-process graph

The ordered analysis and placement baseline is described in
`../../model/runtime/graph-v1.md`.

## Purpose and boundary

`ordo-playbook graph` reconstructs static possible processes from persistent-state
read, set, and delete occurrences. It is independent of next recommendation.
The former next-shaped graph output is replaced by versioned static graph JSON.
Current activity is separate annotation: v1 reports `activity.status: not_requested`.
No state contents, external probes, business actions, or runtime expression
evaluation are required or performed. Missing inputs, profile availability, or
`.ordo.json` must not erase successfully loaded workflow structure.

## Occurrences and composition

Retain each access site, its source and structural path, authored order, and
symbolic guard, gate, conditional, and repeat context. Authored-order edges do not
assert that both sites execute. Expand used let bindings at use sites; unused let
bindings introduce no reads. Registered step values do not reread storage.
Compose known run targets with static arguments and inherited storage context.
Represent repeated bodies once symbolically; do not unroll iterations. Report
unresolved calls, recursive boundaries, unknown profile selections, and unsupported
expressions explicitly rather than inventing observations or identities.

## Address and handoff evidence

### Concrete projection

Addresses comprise store, key, and field path. The v1 static store model uses
normalized declared paths; it does not establish physical inode, symlink, or
hardlink identity. Equal normalized locations under different binding names
share an address. Distinct known keys do not match. Resolve safe static literal,
input and let values, including profile and playbook-entry bindings. Pure constant
lists, objects and map `lookup` may resolve without runtime evaluation. Finite
item/key domains retain at most 32 authored alternatives; larger or unknown
domains remain explicit uncertainty, never arbitrary body unrolling.
Same-named dynamic inputs in different workflows are not automatically equal.
Unresolved store/key identities remain explicit; possible address matches must
not be labeled proven.

Directed cross-workflow set-to-read links represent possible handoffs. Delete
links represent possible invalidation. Exact and ancestor/descendant field
relationships include parent replacement, subtree deletion, and potential
empty-parent pruning. Proven address identity never proves handoff execution,
value suitability, guard satisfiability, or exact reachability.

Workflows bridge fields through their ordered accesses. Connected contours and
strongly connected possible-loop components may cover multiple independent or
intersecting processes. They are derived from links, never file, category, role,
or one cluster per field. Cycles may contain incompatible symbolic conditions;
no executable-cycle or inferred-business-stage claim is permitted.

### Structural state families and selector parameters

For the structural graph, intermediate indices may be symbolic parameters of the
same logical state family. A family is declaration-owned and scoped to its
declaring playbook; matching role/binding names across unrelated declarations
must not manufacture family identity. Explicit aliases to the same catalog state
share its family. Nested store declarations/overrides retain their own scopes.

Profile-backed locations are concrete instances of a declared family, so a
structural template relationship does not require identical concrete profile
files. Preserve actual file identities and require matching family instances;
never alter runtime storage identity or validation to enable a graph link.
Provably disjoint fixed indices, closed selector domains and fixed store locations
remain disjoint. Literal and known protected bindings are fixed; profile-provided
input slots retain their parameter origin even with a concrete profile projection.

Retain selector origins and invocation scopes. Used let expansion, profile
selection and forwarded call arguments can establish parameter correspondence.
The same mutable source read across invocations is not proof of equal values;
independent unknown selectors require equality, not a same-spelling assumption.

Publish structural links separately from concrete address links, with explicit
relation category, correspondence and equality/instance/read-shape requirements.
Compatible field paths can support a conditional structural handoff even when
the selector is unknown. Parent replacement, subtree deletion and empty-parent
pruning retain their field relationships; read-shape availability is not assumed.
Concrete address proof remains proven/possible/disjoint independently of the
structural relation. Do not relabel a possible address as proven.

Summary placement may use parametric structural coverage, preserving each read's
selector requirements and displaying a parameter family once. Missing concrete
profile/key values alone no longer force unresolved structural placement. Distinct
reader selectors may not be collapsed so that one covered selector hides another
unsourced dependency. Multiple independent/intersecting lifecycle shapes remain
possible; shared family names alone do not connect incompatible field paths.
Structural cycles are conditional possibilities, not executable-cycle proof.

## Published contract and parity

JSON identifies `schema: ordo.static-process-graph`, `schema_version: 1`, and
`mode: graph`. It publishes `workflows`, `accesses`, `order_edges`, `links`,
`components`, `possible_loop_components`, `boundaries`, and `activity`. Accesses
also identify `phase` (bootstrap/body), effective `profile` and `working_directory`;
finite `key_candidates` and `profile_candidates` are optional uncertainty evidence.
An additive `summary` presents existing dependency contours as context usage and
changes. Existing detailed v1 fields and bootstrap relations remain available;
corrected static bindings may refine matches. Additive `business_components`
computes connectivity using body-to-body links only. Summary uses those components
plus conditional family connectivity from `structural_components` and all body
reads for placement, retaining launch evidence in `summary.bootstrap`
(access IDs, participating and bootstrap-only workflows, and boundaries). A shared
bootstrap environment selector must not alone collapse business contours. Real
body-level cross-state bridges and intersecting cycles remain represented.

Summary is derived only from existing graph data, not a second analyzer. Common
reads of proven equal context addresses appear once with deduplicated field paths.
Unknown identities must not be equated by spelling. Consecutive mutation accesses
group by workflow, context, kind and identical conditions; reads and changed
conditions separate groups. Source site IDs and conditions remain traceable.
Grouped writes are context changes, not atomic effects or precise transitions.
The summary may aggregate equal finite possible-address domains as sets, explicitly
unresolved; this never proves selected key equality across workflow invocations.

### Static profiles and boundary scope

Load declared profile metadata without activation or observations. Apply known
literal/input/let profile switches and fixed `workflow.profile` bindings using
runtime merge/protection rules. Workflow defaults, explicit CLI inputs and entry
bindings retain their protection. Keep launch-profile name and CLI/default
provenance so a playbook-owned pre_run cannot override an explicit CLI selection.
Never consult current state contents to manufacture a selected profile.

Unknown selection preserves immutable inputs and derives bounded possibilities
for profile-owned values where the declared catalog supports them. It must not
erase all inputs or unrelated fixed addresses. Known working directories follow
effective profile context; profile switches do not silently retarget root
playbook state locations already bound at launch. Unbound calls propagate final
profile context where runtime permits; fixed caller/callee profile scopes remain
isolated. Repeated bodies stay single symbolic bodies with bounded item domains.

Boundaries distinguish context uncertainty from unknown access structure. Only
body structural boundaries can make the whole body reader footprint incomplete;
a profile/context boundary alone cannot hide proven literal-address handoffs.
Bootstrap reads remain detailed dependencies with their own provenance, not
automatic business prerequisites or an excuse to discard body structure.

JSON summary exposes conditional branches, cross-context usage, and context
users without state mutations. This does not classify external effects. A whole-
context deletion remains termination evidence; a subtree deletion remains
removal with possible empty-parent pruning. Neither becomes a fan of backward
transition arrows in default text. Do not print detailed possible-loop components as an upper-
level lifecycle claim. No role may be guessed from workflow names, and a reader
must not become a fake transition (for example, review-to-merge order).
Multiple independent and overlapping processes remain possible within the
existing dependency contours; summary must not claim a unique state machine.

### Context-user source placement

Augment business summary using every existing body reader access and body handoff
link. Retain bootstrap accesses and links separately in detailed evidence.
Do not reanalyze workflows or derive roles from names. Source group references
are contour-local JSON identifiers, never execution-step numbers. A source
may write additional irrelevant fields without losing coverage of a reader.

Place every role and pure reader using its workflow's known body read sources.
Keep proven exact-address coverage distinct from parametric
structural coverage. Partial parent/subtree links require explicit read-shape
conditions and never become concrete address proof. Preserve
joins across different sources and alternatives within each read's candidate
set, including mixed joins/alternatives. Never select an arbitrary or newest
producer, especially when a write is conditional. Conditional source availability
must remain explicit and symbolic; guards/gates are not inferred satisfied.

Reads protected by catch/fallback and conditional reads remain dependencies in
this conservative view; do not assert that all such reads or sources are mandatory
runtime prerequisites. Incomplete readers and missing/uncertain source coverage
retain explicit uncertainty without erasing established anchors. State-only users
may still have external effects. Unknown optionality never affects parent choice.

Unique sources justify nesting. Distinct read sources in an established ancestor
chain use the deepest source, with explicit compact references to other sources.
Incomparable joins and per-read alternatives select no candidate arbitrarily:
use an established common ancestor outside the candidate set or stay at root.
Compute handoff-only SCCs before nesting; invalidation must not flatten a valid
handoff chain. Internal SCC edges cannot choose a parent. An ancestry check and
bounded fixed-point pass ensure a finite acyclic forest with every vertex once.
Use references instead of duplicating readers or inventing executions. Source
placement is data use, not value availability, runtime permission or mandatory
execution. Legacy user placement fields remain compatibility evidence; the
additive `role_view.forest` publishes the new parent decisions.

For incomparable joins using distinct data pieces with unambiguous source sets,
add source-local display sightings. One canonical full occurrence uses the first
cycle-safe source in established forest display order. This is deterministic
layout, not a selected prerequisite or a new chain edge. Each other source vertex
gets one reference-only leaf targeting the same workflow/role node. Deduplicate
source vertices across fields/sites, never recursively duplicate descendants.
Unknown/incomplete source sets and alternatives within any read (including mixed
joins-with-alternatives) must not expand into a source fan. Conditional/fallback
reads do not disqualify an otherwise unambiguous join. Internal SCC placements
remain conservative; downstream unambiguous joins can still have reference leaves.

`forest.display_rows` is additive occurrence metadata with `node`, `parent`,
`reference`, `conditional`, and `basis`. Existing nodes, established parents,
source identities, links and role counts stay unchanged. Every node has exactly
one full row. Check canonical ancestry before attachment, use visited tracking
when rendering, and cut references without traversing their targets. Reference
count is bounded by distinct qualifying source vertices, not by paths or fields.

Add summary `placement_version`, group IDs and per-user dependency/placement
evidence. Preserve all detailed graph JSON fields, including handoffs and
invalidation relations; next and the underlying analyzer remain unchanged.

### Display tie-breaking

When source placement leaves display order ambiguous, retain authored playbook
entry order. This applies to
tied main/producer workflows and readers at the same source anchor. Do not apply
an alphabetical fallback that overrides that order. Distinct dependency/source
anchors take precedence over category/order; ties do not move parent placement.

Category metadata creates no links, contours or precedence, and does not override
author order in the forest. Keep existing first-occurrence role order as a final
tie-break; terminal roles follow related users. Explain ordering in help/model,
not in the default opening legend.

Default human text starts with `Shared context: writers → readers, not execution order.`
and the legend `+ write, − delete, ? conditional.` Add
`↔ another role of the same workflow.` only when repeated roles are present.
When reference leaves exist, add `↔ (reference) the same operation, shown again.`
Use `workflow ↔ (reference)` for a leaf, or `workflow ↔ state/kind (reference)`
when its existing workflow has multiple roles. Leaves omit effects and descendants;
known conditional source use may retain `[conditional use]`. These sightings
never assert multiple executions or alternative prerequisites.
Omit detailed ordering and visual-deletion explanations from default text; retain their
explanations in help/model. A single contour has no heading; multiple contours
use `Contour 1`, `Contour 2`, etc., without address lists. JSON identities remain intact.
Writing and deleting roles may now be nested. Unique-source and chain-join users
have justified parents; root alternatives are marked `(data use; alternative sources)`.
The graph shows shared data, with these annotated readers distinguished from
mutations. Guards and `check` determine applicability; alternative ends are not
sequential steps. This is a
visual data relationship, not a claim that the parent is a mandatory prerequisite;
in particular, fallback reads do not become mandatory execution requirements.

Unknown sources remain compact notes beside the known placement. Never omit a
vertex or attach it arbitrarily. Workflow lines may carry effect suffixes and
compact `read sources:`, `also reads from:`, conditional `reads from:` and data-use-cycle notes.
Do not print expressions, verbose evidence, technical C/S identifiers, activity
or statistics in default text. Keep that evidence unchanged in `--json`. Do not infer
business lifecycle headings such as Task context from workflow names.

Mutating workflow lines have trailing parentheses listing first-seen effects:
`+field` means write, never guaranteed first creation; `−field` means partial
delete; `−context` means whole-context deletion. The effect legend is
`+ write, − delete, ? conditional.` after the shared-context opening line.
An optional `Details: --json.` footer must not repeat the legend. Read-only-state
users have no effect parentheses.

Append `?` from existing if, iteration, short-circuit or conditional-gate controls.
Deduplicate by context, operation and field in stable first-seen order, retaining
`?` if any occurrence is conditional or duplicate occurrences have different
condition sets. Do not infer unconditional coverage across guards or complementary
branches. Ordinary guard/gate applicability alone does not mark every effect
conditional, and absence of `?` is not readiness or execution proof. Qualify
effects when multiple contexts or the reserved root label would be ambiguous.
This inventory does not alter or replace ordered JSON occurrences or IDs.

A source reference such as `reads from: merge-task?` marks known conditional/fallback
data use independently of mutation-effect question marks. Existing read branch
conditions and a direct state pipeline catching `runtime.value.state_missing`
may supply this annotation. Unrecognized expressions must not gain a speculative
question mark. Annotation must not filter dependencies or influence placement.

Name stores through their logical playbook binding and preserve the key. Avoid
absolute path verbosity when a short name is unambiguous. If one logical name
denotes several actual stores, use distinguishing path suffixes; do not merge
different stores, keys or unresolved identities for presentation. Unknown key
expressions stay in JSON; text identifies distinct unknown contexts. This wording
change must not alter summary evidence, technical JSON IDs or placement decisions.

Runtime-mode non-impact: check and review retain applicability and authoring
validation; plan retains existing planning and reuse; run retains ordered actual
execution; explain retains current observation-based explanations; next retains
its existing candidate classification, ranking, and result contract. The actual-
file write-before-last-read validator is unchanged. Static graph composition is
not permission to execute a workflow rejected by that validator.

Help features, overview, model, capabilities, command-line, state describe and
search must publish the static purpose and limits. A graph-bundle snippet must
verify actual builder output rather than merely bound-state validation. Graph
bundles may additionally assert exact compact text via `expected_text`; existing
bundles without that optional expectation remain supported. A graph bundle may
use `playbook_text` plus relative authored `files` instead of `workflows` to verify
real static profile/pre_run loading without reading state or executing effects.
It may also assert `expected_structural_links` with correspondence and requirement
predicates independently of its concrete link expectations.
## Mutation-role presentation

- Display vertices are workflow × declaration-owned logical state family × write/delete.
  Keys and fields constrain affected data, not the number of logical states. N mutated
  states with M mixed states yield N + M roles. Unknown families remain unresolved
  workflow-local bindings; matching names do not establish alias identity.
- Preserve existing contours and source-site evidence. Apply source parents to all roles.
  Every role and pure reader has one full occurrence, with optional reference leaves.
  Repeated roles and references explicitly share one workflow identity, not executions.
- Place delete roles at the end of related creator/local-user blocks using the existing
  concrete and structural overlap predicates for actually affected data, including subtree
  and parent-prune evidence. Use the last of the bounded candidate blocks, retaining all
  candidates and uncertainty. Partial deletion must not anchor on unrelated sibling fields.
- Cross-context users retain their evidence and source-based parents. Mutating roles retain
  state-local reads plus explicit shared-workflow read attribution in the forest.
  No scoring, path expansion, mandatory reader-before-delete ordering,
  execution edges or per-address contour replacement is permitted.
- Missing trusted visible sections use authored-position fallback, explicitly unresolved
  for uncertain alias evidence and otherwise isolated. Preserve alternatives, conditions,
  cycles, selector/instance requirements and actual delete/rewrite occurrence order.
- Additive contour.role_view must preserve original workflow nodes, access sites, groups,
  dependencies, conditions and detailed links. Keep effect parentheses and +/−/? legend;
  add shared-identity markers only for repeated roles. Bootstrap and runtime modes are unchanged.
