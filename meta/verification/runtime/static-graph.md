# Static graph v1 verification and parity review

## Mode impact

| Surface | Review outcome |
| --- | --- |
| graph | New source-only collector/builder and versioned JSON; no next activation or ranking calls. |
| check | No execution, observation, state-deferral, or applicability code changes. |
| review | No authoring or actual-file state-order validator changes. Graph composition is not validation permission. |
| plan | No planning, reuse, or symbolic runtime-plan changes. Graph has its own payload. |
| run | No execution, mutation, probe, call-materialization, or state-storage changes. |
| explain | No observation-based explanation or diagnostic changes. |
| next | Existing candidate construction, ranking and output remain unchanged; targeted CLI regression tests pass. |

The graph source loader is separate from activation. Its call loader reads
authored documents while preserving symbolic arguments instead of invoking
runtime argument evaluation. Initial static profile/entry bindings can establish
keys; unknown arguments, different bound profiles and runtime profile switches
retain explicit uncertainty. Static declared-path identity is deliberately
distinct from the existing physical-file validation identity.

## Describe readiness checklist

Reviewed actual output from `ordo-help describe state` and
`ordo-help describe command-line.ordo-playbook` against
`meta/requirements/runtime/help-discovery.md`:

| Checklist item | Evidence in both affected surfaces |
| --- | --- |
| Positive definition | Short opening definition of storage or the public launch command. |
| Negative boundaries | Graph explicitly disclaims execution and reachability proof. |
| Neighbor distinctions | Next recommends current work; graph reconstructs static possibilities; state validation is unchanged. |
| Understandable terminology | Ordered accesses, handoffs, deletion and uncertainty accompany the JSON names. |
| Intended-use examples | Three workflows demonstrate a field bridge and reset. |
| Larger example | A complete graph bundle replaces value-only illustration for topology. |
| Self-contained meaning | Static purpose, schema version, evidence and runtime-mode limits appear in describe output. |
| Text and JSON | Text teaches contours; JSON retains full sites, conditions and link evidence. |
| Surrounding parity | Features, overview, model, capabilities, command-line and search carry the same static purpose. |

`graph_bundle` is an actual builder-verification path. It asserts exact directed
link summaries and possible-loop components; a negative expectation test proves
incorrect links are rejected. It does not claim CLI activation or execution
verification. Existing state bundles continue to verify bound validation only.

## Targeted evidence

Using the explicitly approved project-venv targeted pytest bypass:

- `tests/test_static_graph.py` and the four help snippet/scaffold verification
  files: 46 passed, 4 subtests passed at the verification checkpoint.
- `tests/test_playbook_activation.py -k 'graph or next'`: 10 passed.
- Six selected help golden/describe checks initially produced four passes and
  two stale-golden failures. The failures also exposed existing workflows-show
  warning text missing from the goldens; snapshots were aligned with that
  preserved source text. The two failing golden checks then passed.
- A broader selected help run hit the 120-second tool timeout; it is not counted
  as a successful test run. Verification was narrowed to affected surfaces.
- `ordo-playbook graph`: 97 ordered access sites, zero unresolved boundaries,
  and the state-connected task contour, with no state reader invocation.
- `ordo-help search "static possible processes"` returns state and the playbook
  command describe handles.

No full test suite or lifecycle execution is part of this verification.

## Compact presentation follow-up

The presentation layer now derives `summary` from existing components and ordered
access sites. It does not change analyzer collection, matching, detailed links,
SCCs, or runtime execution. The original mode non-impact review above still
applies to check, review, plan, run, explain and next. Graph JSON v1 adds summary
without removing or rewriting any existing detailed field.

Presentation coverage includes deduplicated reads, grouped writes, exact symbolic
conditions, read barriers, changed gate context, one whole-context termination,
subtree removal, state-only users, independent contours, workflows bridging
contexts, unknown-identity separation, and no role inference from names. Tests
also compare the complete legacy payload before and after summary derivation,
and check rendering older v1 payloads without summary.

The graph bundle now checks exact renderer output in addition to detailed link
and loop expectations. Incorrect compact text fails verification, while legacy
bundles without `expected_text` remain valid. Its four-workflow example includes
conditional grouped writes, repeated context use and one deletion without
backward arrows. Detailed loop evidence remains in JSON only.

The affected state and playbook-command describe surfaces retain positive
definitions, neighbor distinctions and explicit non-goals from the checklist
above. Their expanded verified example demonstrates the compact view itself.
Features, overview, model, capabilities, CLI help and search use the same
dependency-only presentation meaning; they do not imply mandatory workflow order.

Follow-up validation results (project-venv targeted pytest bypass):

- `tests/test_static_graph.py`, `tests/test_help_snippet_runner.py`,
  `tests/test_help_snippet_verification.py`, `tests/test_help_snippets.py`, and
  `tests/test_help_snippet_scaffolds.py`: 55 passed, 4 subtests passed.
- `tests/test_playbook_activation.py -k 'graph or next'`: 10 passed.
- Six selected overview/features/command-line golden and state/command-line
  describe tests: 6 passed, 11 subtests passed.
- Both affected describe commands were executed and reviewed against the
  readiness checklist. `ordo-help search "context termination"` returns both
  state and command-line.ordo-playbook.
- Public compact graph retains 97 detailed access sites and zero unresolved
  boundaries, while showing one common read list, three grouped set operations,
  one whole-context termination and three state-only context users. No pairwise
  arrows or loop-component claims appear in the compact view.

## Source-aware context-user placement follow-up

Placement uses the existing handoff links and every collected reader occurrence.
Summary adds contour-local group references, per-reader dependency candidates and
symbolic placement evidence. A unique covering source displays its user directly
beneath that change. Joins and alternatives retain per-read source clauses;
missing or uncertain coverage remains unresolved. A join's last displayed source
is a layout anchor only, not the newest producer or a runtime predecessor.
No condition solver, workflow reanalysis, topological execution order or source-
name inference has been added. Detailed accesses, relations, invalidations and
loop components remain intact; the collector and next code are unchanged.

Coverage now includes a sufficient source with irrelevant additional/later
writes; x+y joins across distinct sources; alternatives and mixed joins; a
conditional source without an availability claim; missing sources, possible
identities and partial subtree relations; caught/fallback reads; external-effect
context users; cyclic producers without user duplication; incomplete readers;
and older summaries without placement metadata. The real project graph test
checks source-adjacent task-to-review/current-task-context placement and cancel-
task's complete five-address join, including conditional PR/request sources.

The verified graph bundle now contains both a source-adjacent user and a joined
user with a fallback read and conditional source. Exact text verification still
checks the real renderer. The state and playbook-command describe surfaces teach
the source refs, positive placement rules, uncertainty limits and external-effect
distinction. The existing nine-item describe checklist applies: definitions and
neighbor distinctions remain; the larger verified example teaches intended use;
all source-placement meaning is present in text and JSON; features, model,
capabilities, overview, CLI help, search and documentation agree.

Mode review: only graph summary/presentation changes. Check, review, plan, run,
explain and next retain their previous behavior; graph placement is neither
runtime permission nor validation of actual-file mutation ordering.

Source-placement validation results (approved targeted project-venv pytest):

- Graph plus snippet/scaffold selection: 64 passed, 4 subtests passed.
- Graph/next CLI selection: 10 passed.
- Six selected help golden/describe checks: 6 passed, 11 subtests passed.
- Both affected describe commands were executed and reviewed. Searching for
  `source placement` finds the state and playbook-command describe surfaces.
- Actual project output places task-to-review and current-task-context under S1,
  cancel-task once beside the S1/S2/S3 join, and deletion once at S4. Source
  availability stays symbolic and the detailed graph retains its 97 access sites.

No full test suite, authored project workflow modification, or remote mutation
was used for this follow-up.

## Human wording follow-up

Only human rendering changed: workflow names lead the output, single-source
readers share a `readers:` line, and joins/alternatives name workflows instead of
technical C/S identifiers. Fields, contexts or distinct write occurrences qualify
otherwise ambiguous source names. Stores use logical bindings with keys and
short distinguishing path suffixes when actual stores share a binding name.
The placement classifier, summary evidence, group IDs and detailed JSON are
unchanged; a full payload equality test verifies that rendering does not mutate
them. Check, review, plan, run, explain and next are unaffected.

The exact-output graph bundle and help goldens were updated. Both affected
describe surfaces were executed and reviewed against the existing checklist:
positive definitions and semantic boundaries remain, the verified larger example
teaches the new names, and text/JSON distinctions agree with features, overview,
model, capabilities, CLI help and documentation.

Targeted verification:

- Graph and snippet/scaffold selection: 68 passed, 4 subtests passed.
- Graph/next CLI selection: 10 passed.
- Six selected help golden/describe checks: 6 passed, 11 subtests passed.

Added cases cover unchanged JSON IDs/evidence, no synthetic identifiers or role
prefix in ordinary text, binding-name collisions across actual stores, identical
source fields at different keys, and distinct otherwise identical write
occurrences without choosing a newest producer. Actual output uses common_state
and retains the source-adjacent readers and conditional cancellation join.

## Minimal default tree follow-up

The default renderer now emits a generic logical context heading and workflow
tree only, with one brief non-prerequisite note. Main workflows keep summary
order. Each resolved consumer appears once beneath the workflow owning its
existing placement anchor; this preserves the cancellation join's visual
placement without implying a mandatory merge prerequisite. Unresolved consumers
have a separate section, including partially known or incomplete dependencies.
Multiple contexts/contours remain distinguishable; unknown key expressions are
not exposed in the tree.

Fields, symbolic conditions, joins/alternatives, source refs, mutation details,
activity and statistics remain in unchanged JSON. The collector, summary
construction, source-placement classification, technical IDs and next are
untouched. Check, review, plan, run and explain also have no behavior changes.

The graph bundle now verifies exact Unicode tree output. Tests continue to assert
all detailed placement and condition evidence in JSON rather than requiring it
in default text. Additional exact-tree and unresolved-section cases prove no
fields/expressions leak into the minimal tree and no unknown consumer is attached
arbitrarily. Full payload equality continues to verify rendering is read-only.

Help features, overview, model, capabilities, CLI help and both state/command-line
describe surfaces teach the text/JSON split. The larger verified example, positive
definitions, explicit non-goals, neighbor distinctions and semantic note retain
the existing describe-readiness checklist coverage.

Minimal-tree validation results (approved targeted project-venv pytest):

- Graph plus snippet/scaffold selection: 70 passed, 4 subtests passed.
- Graph/next CLI selection: 10 passed.
- Six selected help golden/describe checks: 6 passed, 11 subtests passed.
- Both affected describe commands were executed and reviewed: the verified tree
  example, generic context naming and explicit JSON-only evidence match the new
  default renderer without changing the existing definitions or runtime boundaries.
- Actual `ordo-playbook graph` output has set-active-task with task-to-review and
  current-task-context branches, merge-task with cancel-task, and close-task, under
  the common_state logical context. It contains no fields, conditions, source IDs,
  joins, statistics or inferred business lifecycle heading.

## Compact state-effect suffix follow-up

The default tree now starts with one legend and adds effect parentheses to
mutating workflow lines: `+field` writes, `−field` partial deletes, `−context`
whole-context deletes, and `?` for conditional effects. `+` is not first creation.
Effects retain first-seen order and deduplicate only the same context, operation
and field. Conditional occurrences or differing condition sets retain `?`; no
unconditional coverage is inferred across guards or complementary branches.
Ordinary guard/gate applicability alone does not mark every effect conditional,
and absence of `?` grants no readiness or execution guarantee.

The renderer qualifies multiple-context targets and literal fields named
`context` to distinguish them from whole-context deletion. Read-only-state
consumers retain their branch names without effect parentheses. Source-aware
placement, unresolved sections, detailed JSON, summary evidence and IDs are
unchanged. No analyzer or check/review/plan/run/explain/next behavior changed.

The exact-output graph bundle verifies the legend and write/delete/conditional
suffixes with existing conditional-source and fallback-read evidence. Tests also
cover repeated effects and authored order, complementary branches, changing guard
contexts, partial and root deletion, symbolic repeats, multi-context qualification
and JSON immutability. Help features, overview, model, capabilities, CLI and both
describe surfaces publish the same marker meanings and non-readiness limits.

Effect-suffix validation (approved targeted project-venv pytest):

- Graph and snippet/scaffold selection: 76 passed, 4 subtests passed.
- Graph/next CLI selection: 10 passed.
- Six selected help golden/describe checks: 6 passed, 11 subtests passed.
- Both affected describe commands were executed and reviewed against the existing
  readiness checklist; the exact verified example demonstrates the markers while
  preserving source-placement and runtime-permission boundaries.
- Actual graph output retains the agreed tree and shows set-active-task with
  `(+issue_number, +branch)`, merge-task with
  `(+pull_number?, +merge_attempted?, +merge_request_id?)`, and close-task with
  `(−context)`, beneath the single English legend.

No full suite, authored project workflow changes, commits or remote mutations
were part of this presentation-only follow-up.

## Authored-order display ties follow-up

Inspection confirmed that catalog loading iterates the authored playbook mapping,
graph nodes preserve that order, and summary construction uses it rather than
alphabetically sorted component membership. Main-workflow ties and readers tied
at one source anchor already followed authored order, including same-category
ties. The order is now explicit in summary traversal and documented by the short
output note `Ties within a category follow playbook order.`

The existing source-anchor loop still takes precedence over reader entry order
when anchors differ. Cross-category order is unchanged; no category grouping,
sort, graph edge, applicability rule or execution precedence has been added.
Category metadata is therefore unnecessary in graph JSON. The analyzer, IDs,
placement evidence, check/review/plan/run/explain and next remain unchanged.

`tests/test_graph_display_order.py` uses real synthetic category-bearing playbook
files through the public static loader. It covers non-alphabetical producer ties,
same-anchor reader ties interleaved with another category, dependency anchors
overriding entry order, and independent contours sharing a category. Relabeling
categories produces identical complete graph JSON, proving no category-driven
links, regrouping or placement changes.

The verified graph bundle now has tied readers in non-alphabetical supplied
workflow-list order and checks the exact output note. It honestly verifies the
builder/renderer ordering; category parsing is covered separately by the public-
loader tests. The category excerpt remains valid for the unchanged authoring
shape. State, command-line and category describe surfaces explain display-only
tie-breaking, source-placement precedence and the absence of category-driven
runtime behavior, preserving the existing describe readiness boundaries.

Authored-order validation (approved targeted project-venv pytest):

- Graph display-order, static graph and snippet/scaffold selection: 80 passed,
  4 subtests passed.
- Graph/next CLI selection: 10 passed.
- Seven selected help golden/describe checks, including the category-bearing
  playbook metadata group: 7 passed, 11 subtests passed.
- State, playbook-command and category describe commands were executed and
  reviewed. Their definitions, examples and display-only boundaries remain
  consistent with the existing readiness checklist.
- Actual project graph ordering and effect suffixes remain unchanged; the sole
  visible addition is the short same-category tie-order note. Full graph JSON
  needs no extra category metadata and remains unchanged.

No full suite, authored project workflow changes, commits or remote mutations
were used for this follow-up.

## Static profile context and bootstrap/body fix

The reproduced check-list.life failure had 40 bootstrap profile reads, 32
unresolved consumers, and 27 consumers hidden despite complete address coverage.
The cause was unconditional input/base clearing on every profile switch and a
blanket incomplete-reader rule for any boundary. Known defaults and explicit
profile provenance were lost, and bootstrap reads alone joined the whole catalog.

The graph-only loader now retains launch provenance, protects workflow defaults,
CLI overrides and entry bindings, and loads declared profile data without
activation. Known native and legacy profile switches use the existing pure runtime
merge helper. Fixed workflow profiles and supported call propagation/isolation
follow runtime context rules. Working-directory changes do not retarget already
bound root playbook state files. Unknown selections retain protected values and
bounded candidate domains; missing literal profiles do not invent another profile.

Accesses retain source/order and add phase, effective profile and working-directory
evidence. Context uncertainty is distinct from unknown body access structure.
Detailed bootstrap links and full components remain; business_components and
summary reader placement use body-to-body links. summary.bootstrap retains launch
evidence and workflows with bootstrap-only state accesses. Real body cross-state
bridges and cycles remain. Literal Story links no longer disappear behind an
unrelated profile boundary.

Static lists, objects, map lookup and item/key domains are bounded to 32 values,
without body unroll or runtime expression evaluation. Equal finite address-domain
sets may share a summary context, but selected key identity stays unresolved.
Registered probe results and external issue-body relationships remain unknown.

Generic engine tests cover profile defaults/protection, explicit CLI pre_run
authority (including a different enclosing bound profile), literal/input/let and
legacy switches, call propagation and isolation, inline scope, recursion context,
working-directory scope, fixed state links under uncertainty, finite lookup and
limits, disjoint domains, and independent business contours behind a shared
bootstrap selector. State readers/evaluators are forbidden in purity tests.

The graph_bundle runner now supports real playbook_text/files source bundles.
The new profile/bootstrap example verifies actual static loading, complete raw
links and exact compact output with absent state. Existing workflow-list bundles
remain supported. State and playbook-command describe surfaces, features, model,
overview, capabilities and CLI help publish the profile/provenance boundaries.

Mode review: check, review, plan, run, explain and next implementations and
contracts are unchanged. Runtime profile helpers are reused without modification;
only graph context interpretation and graph snippet verification changed. No
execution validation or actual-file state-order rule was relaxed. Direct profile
and legacy-switch help semantics remain the existing runtime contract; graph help
now reflects those meanings. No check-list.life authored workflow was changed.

Profile/provenance fix validation:

- Generic graph/profile/display-order and snippet/scaffold selection: 100 passed,
  4 subtests passed. Repeated after the final body-coverage metadata clarification.
- Graph/next CLI selection: 10 passed.
- Seven selected help golden/describe checks: 7 passed, 11 subtests passed. The
  five affected state/command-line/overview checks were rerun after final wording
  corrections and passed again; features/category checks were unchanged.
- State and playbook-command describe surfaces were executed and reviewed against
  the readiness checklist. The new actual playbook bundle verifies profile and
  bootstrap semantics without state contents, while earlier workflow-list
  examples retain their original verification path.
- check-list.life default and explicit backend/profile-input graphs were compared
  with the ordo graph. The backend graph retains 129 accesses, including all 40
  bootstrap reads. Twenty-five workflows have bootstrap-only state accesses;
  the business view contains 15 workflows. Both set-active-task to task-to-review
  and set-active-story to story-to-review have proven exact-address handoffs.
- Default context retains five unresolved consumers because profile selection
  remains symbolic or keys depend on remote results. Explicit backend leaves
  global-status (multi-key symbolic iteration) and story-get-next-task-for-work
  (remote selected repository) unresolved. Actual body readers still bridge the
  lifecycle contexts; no business-name grouping or external issue-body inference
  was introduced. Ordo's existing compact graph is unchanged.

No full suite, remote actions, commits, pushes, or authored project workflow
changes were used. Existing runtime validation and lifecycle work were preserved.

## Parametric logical-state graph follow-up

Structural matching now uses declaration-owned state families and explicit
selector provenance in a separate graph relation. Existing concrete addresses,
links and their identity proof are retained. structural_links records parameter
correspondence plus selector-equality, family-instance and read-shape requirements;
it never promotes a possible concrete identity to proven. Profile-backed files
can instantiate one family, while unrelated declarations, fixed disjoint files,
fixed disjoint keys and disjoint closed domains remain separate.

The collector tracks input/profile/state-selection origins, used let aliases,
forwarded call arguments, iteration scopes and nested store overrides. A shared
mutable selection origin still requires equality across invocations. Different
unknown selector names or identical spelling in independent scopes do not prove
equal values. Recursive selector lets retain explicit boundaries and finite JSON.

The summary uses concrete and conditional structural body links. Parameter
families can supply structural coverage without a selected concrete profile;
distinct read selectors remain separate dependencies so one covered selector
cannot hide another unsourced one. Parent paths keep read-shape requirements and
deletions keep subtree/pruning semantics. Conditional structural components and
loop components do not prove executable cycles. Bootstrap provenance is retained.

Generic tests cover default profile-domain lifecycles, shared-origin and
independent-parameter equality requirements, fixed keys/defaults/domains, fixed
store disjointness, cross-profile family instances with disjoint concrete files,
declaration scope across playbooks, explicit aliases, nested overrides, call/let
origin forwarding, recursive selectors, shape bridges and independent loops.
The verified parameter-family playbook bundle asserts concrete links remain
possible and separately verifies structural equality requirements and exact text.

Mode review: graph semantics changed as explicitly approved; next ranking,
check/review/plan/run/explain behavior and actual-file storage validation did not.
Runtime state/profile code and project workflows were not modified. Help features,
overview, model, capabilities, state and command-line describe surfaces distinguish
structural parameter correspondence from concrete identity and runtime permission.

Parametric graph validation (approved targeted project-venv pytest):

- Structural parameter, profile, static graph, display-order and snippet/scaffold
  selection: 118 passed, 4 subtests passed.
- Graph/next CLI selection: 10 passed.
- Seven selected help golden/describe checks: 7 passed, 11 subtests passed.
- Both affected describe surfaces were executed and reviewed against the readiness
  checklist. The new real playbook bundle checks possible concrete links, separate
  shared-origin structural correspondence, the selector_equal requirement, and
  exact compact output; incorrect requirement expectations fail verification.
- Default check-list.life now places task-commit/task-to-review under
  set-active-task through common_state[parameter], without choosing a profile or
  reading state. The inspected concrete task handoff is still possible; its
  structural relation is parametric with independent-parameter equality required.
- Explicit backend retains the proven concrete backend store/key handoff. The
  human family view is the same structural template, not a new concrete identity
  claim. Ordo retains its prior compact tree and concrete handoffs.

No full suite, project workflow changes, probes, commits, pushes or remote actions
were used. Existing lifecycle work and runtime storage-validation semantics were
preserved.

## Standalone alternatives placement fix

Pure alternatives no longer select the last source as a parent: their summary
keeps kind=alternatives and every candidate/evidence record, with after=null.
The renderer shows them once as standalone rows, including older summaries that
still contain a last-source anchor. They are not relabeled unresolved. Unique
source dependencies, joins and join_with_alternatives retain existing anchors.

Workflow nodes may carry an additive category field for display only. Free rows
use compatible authored category-order bounds around indivisible source/reader
blocks. If those bounds conflict, anchors win and authored root-row fallback is
used; free same-category rows retain their mutual order. No category edges,
value/guard solver or global regrouping were added. This allows an earlier free
lifecycle row to precede the whole block containing a later anchored reader.

Generic regressions cover alternatives without a parent, retained candidate data,
older cached after values, category placement before an anchored successor,
conflicting category bounds, consumers declared before producers, and unchanged
join/unique-source behavior. A real playbook bundle verifies exact standalone
output and all source links. The classifier and dependency matcher are unchanged;
only placement/rendering and optional display metadata changed. Next, execution,
state validation and authored project workflows are unaffected.

Standalone-alternatives validation:

- Graph/display-order/profile/parameter and snippet selection: 123 passed,
  4 subtests passed.
- Graph/next CLI selection: 10 passed.
- Seven selected help golden/describe checks: 7 passed, 11 subtests passed.
- The category describe surface was also inspected directly; the state and
  playbook-command checks cover the updated wording and real verified bundle.
- Actual story-to-ready JSON retains alternatives and S1/S3/S5/S6/S9 source
  candidates, with after=null. story-to-review retains single_source/S4, and
  current-task-context retains join_with_alternatives/S9. The tree places
  story-to-ready before the intact set-active-story/story-to-review block.
- Ordo's compact tree remains unchanged. No full suite, remote mutations,
  commits, pushes or authored project workflow edits were performed.
