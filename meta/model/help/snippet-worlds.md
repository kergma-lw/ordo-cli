# Help snippet worlds

## Role

- A snippet world is a named, stable teaching context for help-example publication and verification.
- Snippet worlds exist for `ordo-help` discovery surfaces rather than for workflow runtime semantics.
- A snippet world is a help-model concept, not a workflow feature.

## Why snippet worlds exist

- Many help snippets are too small to stand alone as full workflows.
- Value-only examples are precise, but they are often weak imitation material for authors.
- Full authoring fragments are more useful for imitation, but they need shared context to remain strictly verifiable.
- One-off harnesses do not scale well and make examples harder to compare across help surfaces.

Snippet worlds exist to let help surfaces publish examples that are both:

- strict enough to verify; and
- stable enough to teach from one recognizable context.

## What a snippet world provides

A snippet world may provide a stable set of:

- inputs;
- runtime state values;
- read-only probe results;
- action outcomes;
- repeated domain entities such as repositories, issues, branches, project items, or task keys.

The point is not to simulate production reality in full detail.
The point is to provide one explicit and repeatable teaching environment for many snippets.

## Where snippet worlds are used

Snippet worlds are used in help and discovery publication, especially for:

- `ordo-help describe ...` canonical examples;
- canonical-example verification;
- snippet coverage reporting;
- future authoring-fragment examples that need shared surrounding context.

Snippet worlds may support examples for multiple forms, such as:

- expression values;
- step-field values;
- step fragments;
- workflow fragments;
- Python connector-handler fragments, through a dedicated SDK insertion mode.

## Where snippet worlds are not used

Snippet worlds must not be treated as:

- workflow runtime state semantics;
- user-authored workflow features;
- profile semantics;
- production execution environments;
- alternate sources of workflow truth.

They support help publication and verification only.

## Use conditions

Use a snippet world when an example:

- needs shared inputs, state, probe outputs, or action outcomes;
- should remain comparable to many other examples;
- is too small to stand alone as a complete workflow;
- should be shown as realistic authoring material without giving up strict verification.

Do not require a snippet world for examples that are already well served by:

- verified repository excerpts;
- self-contained complete examples;
- trivial isolated value validation.

## Relationship between world, snippet, and scaffold

The teaching model should keep three concerns separate:

- the snippet world supplies stable context;
- the snippet supplies authored example content;
- the scaffold or insertion mode supplies placement.

The world must not silently rewrite the snippet into a different authored form.
The snippet shown to the user should remain the snippet that is actually verified.

## Teaching goal

Snippet worlds exist so that many examples can belong to one stable teaching world rather than many ad hoc micro-contexts.

This should make examples:

- easier to recognize;
- easier to compare;
- easier to maintain;
- more useful as code to imitate.

## Stability rule

- A snippet world should be intentionally stable and boring.
- It should reuse the same entities and values across many examples unless a local variation is required.
- It must not become an opaque “everything passes here” environment.

## Verification rule

- Snippet-world verification may normalize only clearly safe authoring equivalences.
- It must not depend on semantic guessing.
- If the verifier cannot establish a safe equivalence, it must leave the example unmatched rather than inventing one.

## Multiplicity rule

- The help model may define more than one snippet world.
- Different worlds may exist for different teaching needs, connector families, or example shapes.
- No single snippet world should be assumed to be the only valid future teaching context.

## Bounded connector fixture execution

The GitHub asynchronous merge examples have an explicit execution path in addition
to ordinary authored-shape validation:

| Canonical snippet | World |
| --- | --- |
| `gh_pr_async_merge_head` | `gh-pr-merge-head` |
| `gh_pr_async_merge_test_merge` | `gh-pr-merge-test-merge` |
| `gh_pr_async_merge_head_context` | `gh-pr-merge-head-context` |

The canonical YAML lives in `src/ordo/model/help_snippets.py`. These examples use
`workflow_fragment` form and insertion mode and are published for
`connector.gh.pr`, `connector.gh.pr.checks`, `connector.gh.pr.merge`, and
`connector.gh.pr.merge.request`. The workflow text displayed is exactly the text
admitted and executed; the scaffold does not silently repair literals, rewrite
gates, or substitute a different workflow.

The context-backed example omits `repository` on merge submission and request
observation. Its world supplies runtime `connector_contexts.gh.repository`; the
published comments show the corresponding profile `connectors.gh.repository`
binding. This is not a new workflow YAML field. Explicit PR/check inputs are
guarded to match that fixed context. Fixture execution verifies authored omission
and context/output consistency; separate connector tests establish real handler
fallback, explicit override, and missing/invalid repository failure behavior.

### Admission and execution boundary

- Execution requires the exact canonical text for the selected world, the supported
  insertion mode, and a supported target. Even a noncanonical textual variation
  is rejected rather than falling back to validation or live execution.
- World overrides vary fixture data only. Inputs must be declared workflow inputs:
  `repository`, `pull_number`, and `authorize_merge`. The canonical workflow's
  authorization default is false; the positive teaching fixture explicitly supplies
  true. An undeclared freshness flag or another arbitrary input is not supported.
- The runner uses the workflow executor and an injected connector provider. Only
  `gh.pr`, `gh.pr.checks`, `gh.pr.merge`, and `gh.pr.merge.request` may resolve to
  fixtures. There is no remote-provider fallback, live GitHub request, shell,
  routine, reusable workflow, state mutation, or profile execution in this path.
- Each call's fully resolved input map must match its fixture exactly, including
  JSON value types; boolean true is not integer 1. Preflight probe bindings are
  materialized with the runtime value resolver before the same comparison.
- The action fixture is permitted only during execution and at most once. The
  runner has a 32-call budget. PR fixtures represent before/after submission,
  rather than relying on an assumed preflight call count. This lets preflight
  re-observe the same fixture while preserving one authored request-observation
  step; it does not introduce polling.
- Required public connector output fields must exist in the registry before
  execution. Fixtures cannot stand in for unpublished operation contracts.

### Evidence published by verification

Successful admission to this path reports `verification_path=fixture_execution`,
the actual `runtime_result`, and recorded operation calls with phase and resolved
inputs. Execution can then succeed or fail according to the fixture data and
authored gates; fixture execution is not an automatic successful result.

The ordinary expression/step/workflow scaffold path remains `validation_only`,
with no runtime result or call trace. `runner_verified` metadata alone therefore
does not imply connector execution; consumers must respect the concrete
verification path. Existing state-bundle and routine-bundle verification retain
their own documented boundaries and are not widened by these merge worlds.

### Supported teaching claims and limitations

These worlds verify explicit authorization, standalone admission, saved-head
binding, complete and explicitly selected trusted CI, test-merge candidate
identity gates, SHA/UUID handoff, nullable-handle skipping, honest request-state
publication, and final PR confirmation. The workflow examples require exactly
one successful `unit` check run from app ID 15368 and bind it to the selected
commit; that is example policy, not a universal GitHub merge rule.

The fixtures supply normalized probe/action outcomes. They do not execute the
connector's pre-read, stack-schema parser, HTTP requests, pagination, or server
SHA guard. Connector tests provide that evidence. They also do not establish
actual CI checkout, live permissions, request retention behavior, GitHub side
effects, persistent cross-invocation UUID storage, or atomic protection against
head/base/stack changes.

Timestamp-age freshness is not a supported canonical gate or fixture input.
Pinned-SHA rejection must not be described as timestamp freshness verification.
A workflow needing an age threshold or checkout attestation must author that
policy separately. Publishing a verified example of it requires an explicit
extension of the canonical workflow and bounded verification path; data overrides
must not pretend an unauthored policy was executed. Other arbitrary connector
workflows and modified merge YAML likewise require explicit support rather than
an execution fallback.

## PR candidate-list fixture execution

`connector.gh.pr.list` publishes the same exact `workflow_fragment` document in
five cases: `gh_pr_list_no_pr`, `gh_pr_list_exactly_one_open`,
`gh_pr_list_ambiguous_multiple_open`, `gh_pr_list_only_closed_history`, and
`gh_pr_list_unknown_metadata`. Their worlds are respectively `gh-pr-list-no-pr`,
`gh-pr-list-exactly-one-open`, `gh-pr-list-ambiguous-multiple-open`,
`gh-pr-list-only-closed-history`, and `gh-pr-list-unknown-metadata`.

The separate `_execute_gh_pr_list_snippet` path admits only the exact displayed
YAML and this handle. It uses the real executor with an injected provider,
permits only `gh.pr.list`, requires its published registry output contract,
records phase and fully resolved inputs, and enforces a 20-call budget. Every
resolved input map must match the single observation fixture exactly, including
JSON types. There is no live dispatch fallback or hidden mutation. The scaffold
returns the document unchanged; fixture overrides vary data, not authored policy.

The observer supplies explicit repository, head branch, head owner, base branch,
and `state: all`. The operation also supports optional repository via standard gh
bootstrap; this example's execution does not prove that fallback. A completeness
and all-candidate identity gate precedes exact source-repository selection. The
gate also requires a known `head_repository_key`. Selection compares this
probe-supplied lowercase canonical repository key with
`inputs.head_repository | lower` using the supported pipeline RHS of `only`.
Raw `head_repository` remains available with its API casing; branch names retain
their exact case. This avoids false absence when caller and API repository casing
differ. One owner may have multiple repositories with the same branch. Unknown source
identity blocks publication rather than being discarded to manufacture “no PR.”
Conditional publication distinguishes absence, one open PR, ambiguous open PRs,
and closed history. Counts preserve nullable merge facts. The unknown-metadata
world intentionally fails its gate; ambiguity is published, with no number selected.
A workflow that selects a PR number must gate on exactly one matching open PR
before selection. This observer never authorizes creation or any other mutation.

These worlds establish executed workflow decisions over normalized fixture data.
They do not establish actual GitHub API filtering, pagination, authentication, or
transport failures. The connector's successful full filtered traversal is not an
atomic snapshot; no partial success or workflow-owned page cursor is implied.
Concurrent changes can invalidate an absence observation before a later action.
Connector tests remain the evidence for actual API traversal and failure behavior.
This addition changes help-verification admission only: public `check`, `review`,
`plan`, `run`, `explain`, and `next` semantics are not changed by the fixture path.

## PR create-only fixture execution

`connector.gh.pr.create` publishes `gh_pr_create_new_only` in the
`gh-pr-create-new-only` world. The exact displayed workflow is admitted by a
separate, 20-call-budget runner with real registry contracts, strict resolved
JSON input matching, and fixture-only `gh.pr.list`, `gh.pr.create`, and `gh.pr`
dispatch. Create is execution-only and allowed at most once. No SDK handler,
internal dependency reuse, HTTP POST, authentication, or live fallback executes.

Authorization defaults false and draft defaults true. The workflow checks the
source owner against the explicit source repository name and identity, lists
`state: all`, requires complete known candidate identities, then compares the
canonical lowercase repository key. It refuses every existing exact-source PR,
including closed history and multiple candidates. This is explicitly example
workflow policy; the action's independent open-only recheck is a different
contract. An absence observation is not atomic authorization.

The workflow passes the known optional `head_repository` for a fork and supplies
repository explicitly; this does not make repository required by the action API.
It registers the create output, requires confirmed creation and a nonzero integer
returned number, then observes that number through one authored `gh.pr` step.
Failure or unknown creation blocks final publication, with no workflow retry.
Injected race/provider outcomes prove workflow stopping, not actual POST counts
or SDK dependency behavior; separate connector/SDK tests must establish those.

This verification extension does not change public `check`, `review`, `plan`,
`run`, `explain`, or `next` semantics. The canonical YAML is exercised through
those existing surfaces with injected fixtures.

## SDK Python handler fixture execution

`connector.authoring` publishes `sdk_same_family_probe_inputs` in world
`gh-sdk-probe-call`. Its `python_fragment` form stores source in `python`, not
`yaml`; text help labels it Python. Insertion mode `sdk_probe_fragment` hosts
the exact `def run(ctx)` fragment as a synthetic gh-family published action.
It is connector-author Python, not new workflow YAML syntax. Its nonempty
`filters` input supplies repository, head, head_owner, base, and state.

The separate `help_sdk_snippet_runner.py` path verifies source, world, handle,
and insertion mode before compiling the exact trusted repository-owned source.
This is not a general Python sandbox: changed source is rejected, overrides are
literal JSON fixture data, and no data can supply code or import targets. The
runner uses real `_adapt_published_handler` wrappers and `OperationContext.call`
for both the caller and dependency. The public `gh.pr.list` contract and
publication are retained; only its handler body is replaced with a strict
fixture reader using real `ctx.input` calls. A closed synthetic import map
exposes only that family and its fixture bootstrap. No live API, subprocess,
action dependency, or arbitrary import fallback exists in this path.

Fully resolved dependency inputs are compared as type-strict JSON. Nonempty
inputs stay literal and isolated; missing state propagates the real SDK
`operation.input_missing` diagnostic even though the synthetic workflow has
conflicting fallback bindings. Dependency failure outcomes propagate without
retry. A four-call budget includes bootstrap and successful fixture-body calls.

Results report `verification_path=sdk_fixture_execution`, exact `python_text`,
the actual `operation_result`, and calls. `workflow_text` is empty and
`runtime_result` is absent because no workflow is executed. Ordinary help display
publishes source only; repository verification is the execution surface.

This resolves the same-family probe-input snippet support gap through real SDK
dispatch, not a stub `ctx.call`. It does not prove the actual PR-list handler's
validation, HTTP filtering, pagination, authentication, or provider failures.
Local dotted aliases, legacy empty-input lookup, cross-family rejection, and
probe/action restrictions remain covered by separate SDK unit tests. Public
workflow `check`, `review`, `plan`, `run`, `explain`, and `next` behavior is not
changed by this help-verification path.

## Actions observation fixture execution

The handles `connector.gh.actions.run`, `connector.gh.actions.run.jobs`,
`connector.gh.pr.checks`, and `connector.gh` share identical verified source:

| Example | World | Expected execution |
| --- | --- | --- |
| `gh_actions_direct` | `gh-actions-direct` | Publish all jobs for the observed numbered attempt |
| `gh_actions_bridge` | `gh-actions-bridge` | Select a check suite from complete PR checks, observe its run, publish pinned jobs |
| `gh_actions_null_suite` | `gh-actions-null-suite` | Block before run lookup on a null suite selector |
| `gh_actions_no_run` | `gh-actions-no-run` | Block before jobs on normal `found=false` |

The direct document and larger bridge document live in
`src/ordo/model/help_snippets.py`; all three bridge cases execute exactly the same
YAML. A caller selects check runs by explicit suite ID rather than treating check
IDs, names, or URLs as run IDs. Multiple checks may belong to one suite. Complete
checks are required before selection; a null selector or no matching suite gates
lookup. The suite-to-run result is registered, and its `found` gate precedes jobs.
Jobs receives that registered `run_id` and `run_attempt` as its required `attempt`.
The workflow requires `complete` and publishes the entire `items` collection and
count; an empty complete collection is valid. There is no acceptance or merge
policy, trusted-job selection, polling, or timestamp freshness claim.

The existing normalized fixture execution approach is extended through a reusable
read-only provider. Admission requires exact canonical text, the named world,
`workflow_fragment` insertion mode, and one of these four targets. Scaffolds
preserve source verbatim. World input keys must match declared workflow inputs.
Only `gh.pr.checks`, `gh.actions.run`, and `gh.actions.run.jobs` may dispatch;
each has exactly one normalized fixture, matched against fully resolved input
maps using type-strict JSON comparison. All successful output fields, including
nested collection fields, must match the real public registry schema. Scalar
nulls remain supported by these descriptive schemas; this does not add a new
runtime nullability validator. Declared failure outcomes may supply empty outputs.
The provider enforces a 20-call budget and records phase and resolved inputs.
Neither missing fixtures nor changed source can fall back to live dispatch.

These fixtures establish exact-source execution, registered handoff, gate
stopping, and publication over normalized results. They **cannot prove HTTP
source acquisition**: repository bootstrap/authentication, CheckSuite GraphQL
association and backreference, latest-to-numbered-attempt acquisition, validated
official check-run URL extraction, HTTP failures, and complete bounded pagination
belong to connector transport tests. `found=false` here represents an already
normalized null workflow-run association, not HTTP 404. Fixtures do not prove
worker checkout, immutable event snapshots, or atomic observations.

`tests/test_gh_actions_modes.py` exercises the exact observer sources through
`check`, `review`, `plan`, `run`, `explain`, and CLI `next`, with injected fixtures
and live dispatch forbidden. It covers direct and suite lookup, null and missing
associations, empty jobs, incomplete collections, and probe failures. The existing
read-only preflight classification and authored gate semantics apply in every
mode; this help runner extension changes no public runtime semantics. Static
graph non-impact is checked through published probe/effect/invalidation metadata
and actual static graph construction, with no observation or lifecycle YAML.

Describe readiness review covers all four handles against the nine-point
help-discovery checklist: positive definitions, negative boundaries, neighboring
surfaces, understandable input/output terminology, executable intended-use
examples, larger bridge source, self-contained explanations, text/JSON parity,
and feature/operation routing. `tests/test_gh_actions_help.py` renders and checks
those surfaces without weakening its expectations. Normalized fixture evidence
is explicitly distinguished from connector transport evidence in every example.

## Git remote observation fixture execution

`connector.git.remote` publishes `git_remote_exists` and `git_remote_missing` in
worlds `git-remote-exists` and `git-remote-missing`. Both use the exact standalone
`inspect-configured-origin` workflow document from `help_snippets.py`, preserved
verbatim by the `workflow_fragment` scaffold. This is a local observer example,
not the repository's lifecycle workflow composition.

The required probe input is `remote`; the workflow defaults it to `origin` and
passes the resolved input explicitly. Normalized outputs are exactly `name`,
`exists`, `fetch_urls`, `push_urls`, and `mirror`. The existing world uses literal
example.com HTTPS/SSH URLs and `mirror=false`; the missing world preserves the
requested name with `exists=false`, empty URL lists, and `mirror=null`.

The authored existence gate precedes publication and dependent URL counts.
Missing-remote preflight retains the observed facts in analysis and reports a
failed gate. Direct run re-observes the remote and stops at that gate, retaining
the operation result while skipping every dependent step. It publishes no result.
Existing observations
publish all five facts and counts computed with `length`, without indexing lists.
Empty-list overrides exercise workflow robustness, not a claim that the Git
handler returns successful empty URLs for an existing remote. Similarly, fixture
schema validation is type validation, not validation of every cross-field Git
invariant. `mirror=true` and unusual literal URL strings do not imply rejection:
destination acceptance and other remote policies belong to the caller.

Execution admits only the exact canonical source, named world, target, and
insertion mode. Declared input keys must match, and semantic validation precedes
the real workflow executor. The shared normalized fixture provider permits only
`git.remote`, with one fixture and a 12-call budget, recording resolved inputs
and phase. Input maps match using type-strict JSON comparison; output fields and
collection element types match the public registry. This path requires explicit
scalar nullability (`boolean | null` for mirror); the Actions worlds retain their
existing descriptive-schema scalar-null behavior. Missing fixtures, extra fields,
actions, unlisted references, and exhausted budgets cannot fall back to live IO.

The example preserves observed URL strings, order, and duplicates without
normalization, trimming, redaction, or destination admission. Normalized fixture
data means the operation's output shape, not normalized URL values. No secret
policy is introduced. Verification does not execute Git, family bootstrap,
configuration reads, URL rewrites, or network access and cannot establish their
acquisition correctness, atomic freshness, or push safety.

`tests/test_git_remote_modes.py` exercises the exact source through `check`,
`review`, `plan`, `run`, `explain`, and CLI `next`, with live execution forbidden.
It checks existing/missing observations, literal URLs, mirror facts, empty-list
handling, and `probe_failed`, including read-only preflight classification and
gate blocking. Published effect/invalidation metadata and actual static graph
construction establish graph non-impact. This help-verification extension does
not change public runtime semantics. `tests/test_git_remote_help.py` checks
describe readiness, text/JSON examples, neighboring surfaces, exact operation
schema, feature discovery, and search routing without relaxing expectations.

## Adding a new world-backed snippet

When adding a new world-backed snippet, the author should make four decisions explicitly:

1. which snippet world supplies the teaching context;
2. which snippet form is being published;
3. which insertion mode or scaffold places the snippet into a verifiable host;
4. which verification mode proves the snippet stays valid.

The snippet world should answer only the first question.
It must not answer placement or rendering questions by itself.

### Contribution contract

- Choose an existing snippet world when it already supplies the needed teaching context.
- Add a new snippet world only when the example honestly needs a different stable teaching context rather than a local override.
- Declare the snippet form explicitly so readers can tell whether they are looking at a value example, a step-field example, a step fragment, or a workflow fragment.
- Declare the insertion mode explicitly so placement remains reviewable as a scaffold concern rather than leaking into world data.
- Keep the published snippet body aligned with the snippet that the verifier actually runs.
- Do not rely on decorative rendering tricks to make one snippet form look like another.
- Keep verification in repository tests rather than in normal `ordo-help` runtime calls.

### Verification expectations for contributors

- A new world-backed snippet should fail visibly when its verified shape drifts.
- A new world-backed snippet should participate in ordinary repository verification.
- If the supported snippet-world path cannot yet express the required example shape honestly, treat that as a support gap and call it out explicitly instead of inventing an unverifiable workaround.

## Bound state bundles

The `state_bundle` form and insertion mode publish an explicit bundle, not a
disguised workflow document. Its `workflow_text` is the exact authored workflow;
`state_bindings` maps logical roles to names in the world's existing `state`
fixtures. The runner materializes each fixture as one temporary absolute file,
so two roles bound to one fixture genuinely share storage. It applies those
bindings and calls bound semantic validation, comparing exact
`expected_diagnostic_codes` as well as the example's expected status.

This path verifies same-file aliases and distinct fixture files without executing
mutations, reading state contents, or simulating check outcomes. Outside the
explicit bounded fixture-execution path above, ordinary expression/step/workflow
scaffolds still verify unbound authored shape. The state-bundle path does
not claim profile-switch context, symlink/hardlink fixture, cross-invocation,
cross-iteration, preflight-continuation, or execution verification. Runtime tests
remain the evidence for those implemented behaviors. A future example requiring
one of those unsupported fixture shapes must extend the runner explicitly rather
than presenting prose as a verified demonstration.
