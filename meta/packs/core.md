# Ordo core contract

> Generated from meta source docs. Do not edit by hand.

<!-- source: requirements/authoring/core.md -->

# Authoring requirements

## Product quality

- Agent-authorable workflow and profile composition is a core product quality, not a secondary convenience.
- The system must allow a sufficiently capable agent to learn how to compose workflows and profiles from the documented contract surface.
- Authoring support must focus first on workflows, profiles, and related declarative configuration built from existing public operations.
- Fast authoring of new connector families or operations is not a required early-stage customization path.

## Discoverability

- An author must be able to discover which public operations exist and what contracts they expose.
- An author must be able to infer the stable shape of workflows and profiles from schema, examples, and contract documentation.
- The system should prefer composition over invention: composing existing operations and profiles is the default extension path.

## Checkability

- An authored workflow or profile must be machine-checkable before execution.
- The system must help an agent distinguish at least validity, resolution, likely executability, and authoring-quality concerns.
- Validation and explanation surfaces must be structured enough for an agent to iteratively repair an authored workflow without guessing from logs.

<!-- source: requirements/connector/core.md -->

# Connector requirements

## Public connector contract

- A workflow must reference stable public connector operations.
- The initial fixed connector domains are `git`, `gh`, and `shell`.
- Connector resolution must preserve stable public semantics independent of local implementation details.
- Project-local profiles and overrides must not silently change the public meaning of a referenced global connector operation.
- Connector operation kinds fixed so far are `probe` and `action`, and they exist only inside connector families.

## Connector result discipline

- Every connector operation must return a structured result on both success and failure paths.
- Every connector operation must preserve that structured result contract even when internal exceptions occur.
- Every connector operation must support narrow local explainability of its own outcome.
- A successful `probe` result must contain meaningful observations or diagnostics, not only a bare success flag.
- A successful `action` result must contain a meaningful effect summary or diagnostics, not only a bare success flag.
- A successful `action` result must expose at least one documented action-specific output field.
- Documented operation `failure_modes` must describe expected contract-level non-success rather than exceptional runtime breakdown.
- Raw stdout/stderr, when produced by an implementation, must be treated as optional detail fields rather than the primary contract surface.

## Advisory preflight recommendation metadata

- An effectful action may expose advisory `preflight_observations` metadata that helps runtime assess and explain pre-execution support quality.
- Such templates must not redefine executability or become hidden operation-local prerequisites.
- `preflight_observations` must use the structured object shape rather than free-form prose.
- Each `preflight_observations` item must identify the probe reference and map probe arguments to action-argument placeholders.
- A `preflight_observations` item may additionally specify selected output fields when the recommendation depends on a narrower observed field path.
- A preflight-observation template should be expressed in terms of the action's own argument names rather than workflow-local value sources.
- Runtime may render those templates back into workflow-shaped expressions when producing author-facing `check` or `explain` guidance.
- Missing advisory templates must not weaken correctness, but when templates are present runtime may use them to distinguish stronger versus weaker preflight support.

## Extension boundary

- The system must allow project-local extension without forking the global contract.
- Project-specific policy must compose over stable connector operations instead of mutating their meaning.

## Probe addition policy

- Public probes should default to exposing stable observable facts rather than workflow-specific policy verdicts.
- Workflow policy should prefer composition in guard expressions over growth of specialized probe names.
- A new public probe should be added only when at least one of the following is true:
  - it exposes a stable fact that is not otherwise available through existing probe outputs;
  - repeated workflow composition would otherwise require awkward normalization in many places;
  - the needed condition would otherwise force guard-expression language growth beyond compact reviewable policy;
  - the needed condition would otherwise expose unstable operational detail that should remain inside the connector contract.
- A proposed public probe should be rejected when its primary value is merely to avoid a simple comparison or boolean composition in workflow guards.
- Public probe names should avoid encoding local policy, approval decisions, or workflow intent when those can be expressed as guard composition over existing probe results.

## Canonical git probe set

- The canonical `git` probe set should remain small and orthogonal.
- The current target set for broad repo-state coverage is:
  - `git.repo`
  - `git.branch`
  - `git.branches`
  - `git.worktree`
  - `git.worktrees`
  - `git.stash`
  - `git.state`
  - `git.ref(ref=...)`
  - `git.upstream`
  - `git.range(base=..., head=...)`
- This set should be preferred over adding many narrower git probes for local rituals.
- Older specialized policy-shaped probes should not be used as the preferred long-term public surface when the same intent can be expressed through canonical git facts and guard composition.

<!-- source: requirements/connector/gh-project-items.md -->

# GitHub Project items probe requirements

## Role

- `gh.project.items` is the public `gh` collection probe for enumerating GitHub Project membership.

## Required question

- The probe must answer which project items match one project scan plus optional structural and field-value constraints.

## Required inputs

- `project_id` is required.
- `content_kind` is optional and narrows the result by structural content kind.
- `filters` is optional and narrows the result by project field values.

## Filter contract

- `filters` is an ordered list of objects shaped as `{field, value}`.
- `field` names one project field by public project-local name.
- `value` is a scalar filter value.
- All filter entries compose with AND semantics.
- V1 filtering is equality-only; it must not introduce OR groups, negation trees, range syntax, or a free-form query language.

## Output contract

- The probe must return:
  - `count`
  - `items`
- Each returned item must expose a normalized addressable shape with:
  - `item_id`
  - `content_kind`
  - `repository`
  - `number`
  - `title`
  - `url`

## Failure contract

- Unknown field names must fail explicitly as `unknown_field`.
- Ambiguous field names must fail explicitly as `ambiguous_field`.
- Unsupported field kinds must fail explicitly as `unsupported_field_type`.
- Invalid filter values must fail explicitly as `invalid_filter_value`.
- Project lookup failure must remain distinct as `project_not_found`.

## Retrieval rule

- The probe should use one connector-owned bulk project retrieval path.
- Ordinary pagination is allowed.
- The implementation must not degrade into per-item or per-field follow-up fetches for the returned item set.

## Discovery rule

- The public contract should be discoverable through `ordo-help operation gh.project.items`.
- Discovery examples should show both:
  - one simple membership scan;
  - one filtered scan.

<!-- source: requirements/local-expressions/core.md -->

# Local expression requirements

## Role

- Local expressions are a workflow-owned declarative surface for deriving local values and conditions.
- They must not become a second orchestration language, a connector-execution surface, or a hidden scripting layer.
- Local expressions may appear in multiple contexts while remaining one product-owned expression family.

## Common obligations

- Every expression-bearing context must define which local roots are allowed there.
- Every expression-bearing context must define whether the expression is value-producing or condition-producing.
- Every expression-bearing context must preserve reviewability and explainability.
- Validation and diagnostics must identify invalid references or unsupported context use before effectful execution begins whenever the surrounding context permits that analysis.

## Context families

- The contract must distinguish condition-oriented contexts from value-oriented contexts.
- A condition-oriented context must not silently inherit the dependency rules of a value-oriented context, or vice versa.

## Common local roots

- `inputs...` is the common workflow input surface.
- `args...` is the fragment-local argument surface.
- `state...` is the runtime-state read surface when the context explicitly allows state reads.
- `step...` is the execution-local registered-step-result surface when the context explicitly allows step-result reads.

## Non-effectful observation dependencies

- Local expressions may depend on product-defined non-effectful connector observations such as read-only probes.
- Such observation dependencies must remain reviewable, explicit, and compatible with the surrounding context policy.
- A context may allow non-effectful probe observation without thereby allowing effectful connector execution.

## Derived values and representation adapters

- Local expressions may derive intermediate values from already available values.
- A workflow may declare workflow-local named expression bindings through a top-level `let` mapping.
- A `let` binding must denote one immutable local expression rather than a mutable variable, macro expansion, or user-defined function.
- A `let` binding must remain workflow-local and must not participate in inheritance, export, or cross-workflow resolution.
- A `let` binding must not reference another `let` binding.
- `let` bindings must not relax context gating; a binding is valid only in authored contexts where the equivalent inline expression would also be valid.
- Product-defined representation adapters may interpret values through stable representations such as markdown, html, json, and string.
- Representation-adapter operations must remain pure, local, and value-producing.
- Representation-adapter operations may return further derived values or addressable focus values for additional pure local evaluation.
- A context may allow read-only representation-adapter projections while still forbidding adapter write paths such as `->...`.
- Representation adapters require one shared product-defined invocation seam so concrete adapter families can participate in local-expression evaluation consistently.
- The authored addressing or selection surface between an adapter name and a terminal mutation may be adapter-defined.
- The product must not require all adapters to share one identical middle syntax when their represented structures differ materially.
- Adapter-specific authored syntax should be documented in adapter-specific requirements rather than overloaded into the shared core requirements.
- Any terminal representation-adapter mutation must return the updated root value of the adapted representation.
- Any update-style representation-adapter operation must return a new derived value rather than persisting change by itself.

## Canonical core boundary

- The canonical local-expression core should include shared non-effectful constructs for observation, comparison, composition, and value derivation.
- Shared non-effectful constructs may include literals, lists, local-root references, read-only probe observations, boolean operators, comparison operators, pipelines, built-ins, and representation-adapter operations.
- Effectful connector operations must remain outside the canonical local-expression core even when they are part of the wider connector surface.

## Product-defined pipeline filter surface

- Pipeline filters are product-defined local-expression operations applied to one already evaluated input value through the `value | filter(...)` surface.
- A pipeline filter must not widen context policy, introduce effectful connector work, or become a workflow-defined extension point.
- The product-defined pipeline filter set must be documented explicitly rather than inferred only from implementation code.
- The current product-defined filter set is:
  - `lower`;
  - `trim`;
  - `slug`;
  - `eq(...)`;
  - `ne(...)`;
  - `not`;
  - `is_string`;
  - `is_number`;
  - `is_integer`;
  - `is_boolean`;
  - `in(container)`.
- `lower`, `trim`, and `slug` are string-to-string transforming filters.
- `eq(...)`, `ne(...)`, `not`, `is_string`, `is_number`, `is_integer`, `is_boolean`, and `in(container)` are boolean-producing filters.
- Predicate-style filters such as `is_string`, `is_number`, `is_integer`, and `is_boolean` must accept any already evaluated local-expression value and return `true` or `false` without implicit coercion.
- `eq(...)` and `ne(...)` compare without implicit coercion.
- `in(container)` must evaluate its argument as a container expression and must require that container to produce a list value.
- `in(container)` must compare the pipeline input against list members without implicit coercion.
- `in(container)` must fail when the container expression does not produce a list rather than silently reinterpreting strings, objects, or scalars as membership containers.

## Probe-call execution model

- The canonical local-expression execution model must define how read-only probe-call nodes are evaluated without treating them as a second parser or second expression family.
- The canonical engine must remain the owner of probe-call node semantics, context gating, dependency visibility, caching expectations, trace shape, and diagnostics.
- Any external read-only observation needed to satisfy a probe call must pass through an explicit engine-facing probe-observation interface rather than through ad hoc legacy helper paths.
- Repeated equivalent read-only observation requests within one evaluation scope must reuse one observed result.
- A failed read-only observation must fail the surrounding expression evaluation rather than silently degrading it.
- A context that forbids non-effectful external observation must reject probe-call nodes through normal context-policy enforcement.

## Permanent exclusions

- Local expressions must never perform effectful connector work by themselves.
- Local expressions must never smuggle hidden workflow control structures such as looping or open-ended branching.
- Local expressions must never rely on project-defined syntax whose meaning is outside the stable product contract.
- Local expressions must never become a user-extensible language with workflow-defined functions, macros, or operators.
- Workflow-local `let` bindings must never become a second workflow-defined abstraction layer with parameters, overrides, or dependency chaining.
- Representation-adapter operations must never perform connector invocation, hidden I/O, or other effectful work.
- Representation-adapter families and operations must remain product-defined rather than workflow-defined extensions.

## Product discipline

- The product should prefer one local-expression family with context-specific restrictions over multiple independent expression languages for nearby workflow surfaces.
- Context-specific restrictions should change allowed dependencies or expected result shape rather than introducing separate read-only execution engines for equivalent expression constructs.
- Syntax and evaluation detail may differ by authored context, but those differences must not silently fragment the conceptual model into unrelated expression systems.
- Condition-oriented contexts such as guards may still impose a result-shape contract, for example requiring a final boolean result without thereby becoming a separate expression language.

<!-- source: requirements/local-expressions/adapters.md -->

# Representation-adapter requirements

## Role

- Representation adapters are product-defined local-expression surfaces for interpreting already available root values through stable representation-specific semantics.
- They exist to let local expressions navigate, select, normalize, derive, and transform values such as markdown, html, json, or string without turning those operations into connector execution or hidden I/O.
- A representation adapter is not just a parser choice or implementation detail. It is an authored product surface that needs one shared execution seam so adapter families can participate in local-expression evaluation consistently.

## Why a shared adapter seam is required

- The product must not force each adapter family to invent its own ad hoc runtime entry path.
- The product must provide one shared adapter execution seam so a concrete adapter family such as `markdown` can be implemented as an adapter rather than as scattered special cases inside unrelated evaluator code.
- That shared seam exists to distinguish read versus write invocation, dispatch to the requested adapter family, normalize common failure categories, and preserve the root-value discipline of adapter updates.
- Adapter-specific authored syntax may vary freely inside that seam, but the surrounding invocation and result discipline must remain shared.

## Shared invocation model

- Every adapter invocation starts from an already available root value.
- Every adapter invocation names one product-defined adapter family.
- Every adapter invocation applies one adapter-defined addressing, navigation, selection, or transformation chain to that root value.
- An adapter invocation may be read-only or may end in one explicit terminal mutation.

## Adapter-owned body and host-owned parameterization

- The shared adapter seam should identify the adapter family and delimit the adapter-owned authored body, but it should not need to parse the adapter family's interior navigation, search, or action grammar.
- The interior syntax of the adapter-owned body belongs to the concrete adapter family rather than to the shared local-expression parser.
- Host local-expression references such as `inputs...`, `args...`, `state...`, `step...`, or read-only probe dependencies should not appear as bare references inside adapter-owned body syntax.
- When adapter invocation needs host-derived values, the shared seam should provide those values through an outer host-owned binding surface rather than by injecting host semantics directly into adapter grammar.
- A concrete adapter family must not take ownership of host-root policy, probe execution rules, or canonical local-expression diagnostics semantics merely because adapter behavior is parameterized by host-derived values.
- Host-side parameterization should resolve local-expression values from the outer binding surface before adapter evaluation begins and pass them to the adapter family as resolved parameter values rather than as naive string substitution.
- Host-side parameterization may supply values into adapter-family parameters, but it should not dynamically generate adapter grammar.

## Preferred outer binding form

- The shared adapter seam may expose one host-owned trailing binding form such as ` with{...}` after the adapter-owned body.
- That outer binding form belongs to the shared local-expression surface rather than to any concrete adapter family.
- The outer binding form should be recognized only as a top-level trailing suffix after the adapter-owned body.
- The outer binding form should contain ordinary Ordo value bindings rather than adapter-family syntax.
- Without such a trailing binding form, adapter invocation should still remain valid for non-parameterized use.
- The shared seam may rely on ordinary top-level lexical balancing rules to delimit a trailing binding suffix; it does not need to parse the interior grammar of the adapter-owned body to do so.
- The product should not require support for lexically malformed adapter bodies such as unpaired unescaped quotes when determining whether a top-level trailing host binding suffix is present.

## Cross-family composition

- The shared adapter seam should permit one adapter invocation result to become the root value for a later adapter invocation.
- Cross-family composition should therefore work as ordinary value flow rather than by requiring one adapter family to know the interior syntax or execution rules of another adapter family.
- When one adapter family selects or derives a value such as markdown text, json text, or a structured subvalue, that resulting value may serve as the next adapter root value if the following adapter family can interpret it.
- The shared adapter seam does not need family-to-family special cases merely to support such composition.
- A failure in one adapter invocation should fail that invocation directly rather than being hidden inside another adapter family's semantics.

## Read invocation contract

- A read invocation must treat the supplied root value as input-only.
- A read invocation may select a focus value, derive a new value, normalize a represented structure, or expose an addressable focus for further pure local evaluation.
- A read invocation must not create missing structure.
- A read invocation must not persist change.
- A read invocation result is the selected or derived value produced by the adapter family.
- When a product-owned presence-check helper explicitly admits read-only adapter invocation as an argument form, successful read invocation may be interpreted by that helper as presence and adapter `not_found` may be interpreted by that helper as absence.
- Such helper semantics must not change the ordinary standalone read-invocation rule that adapter `not_found` is an adapter failure outcome rather than an implicit null-like value.

## Write invocation contract

- A write invocation is an adapter invocation that ends in one terminal mutation.
- A write invocation may use adapter-defined navigation or selection before the terminal mutation.
- A write invocation must return the updated root value of the adapted representation.
- A write invocation must not persist change by itself.
- Any later persistence of the updated root value belongs to workflow execution surfaces outside the adapter contract.

## Shared outcome categories

- Adapter families may have family-specific diagnostics, but they should converge on one shared minimum outcome vocabulary.
- That minimum shared vocabulary should include:
  - `not_found` when a requested path or focus does not exist;
  - `ambiguous` when the invocation requires one target but the adapter surface produced multiple candidates;
  - `unsupported` when the requested operation is outside the adapter's supported contract;
  - `invalid_path` when the authored adapter path is not valid for that adapter family;
  - `invalid_action` when the terminal mutation is not valid for the selected focus or adapter family;
  - `invalid_root_value` when the supplied root value cannot be interpreted through the requested adapter family.
- A shared outcome vocabulary does not require all families to expose identical interior syntax or identical represented node types.

## Failure ownership boundary

- A failure while resolving host-owned parameter bindings remains a host local-expression failure rather than an adapter-path failure.
- A failure after host-owned parameter values from the outer binding surface have been supplied to adapter evaluation remains an adapter-family failure under the shared adapter outcome vocabulary.
- The shared adapter seam should preserve this distinction so diagnostics and explainability do not blur host local-expression failures into adapter-family path or action errors.

## Failure timing and explainability

- A malformed adapter invocation should fail as early as the shared seam can determine that the outer invocation shape is not lexically or structurally valid.
- Such early failures may include an unknown adapter family, an undelimitable adapter-owned body, or an invalid outer host-owned binding suffix.
- Host-owned binding expressions should fail at the earliest stage where their values and context restrictions can be evaluated, which may be parse-adjacent validation, `check`, preflight-style analysis, or full execution depending on availability.
- Adapter-family path or action failures should fail at the earliest stage where the adapted root value and any resolved outer binding values are available to the adapter family.
- The product should therefore report adapter-related failures as early as value availability permits rather than reserving all such failures for full execution.
- `check` or preflight-style analysis should surface host-binding failures or adapter-family failures whenever the required values are already observable through the surrounding context and runtime mode.
- Full execution remains the fallback failure stage when required root values or host-bound parameter values are not available earlier.
- Explainability should preserve whether a failure arose while resolving the outer binding surface or while evaluating the adapter-family body after parameter supply.

## Shared purity and locality rules

- Representation adapters must remain pure, local, and value-producing.
- Representation adapters must not perform connector invocation.
- Representation adapters must not perform hidden I/O.
- Representation adapters must not become a second execution or orchestration surface.
- Representation adapters must not smuggle persistence semantics into terminal mutations.

## Shared read-versus-write boundary

- The product must preserve an explicit distinction between read paths and write paths.
- A read path ends in value selection or value derivation.
- A write path ends in a terminal mutation and returns an updated root value.
- Adapter-specific middle syntax may vary, but adapter families should not blur the boundary between read-only navigation and root-transforming update.
- Any product-owned presence-check helper that admits adapter invocation must admit read paths only and must reject write paths explicitly rather than evaluating them for boolean presence.

## Shared auto-creation boundary

- Auto-creation of missing represented structure is a write-path concern only.
- Read paths must never auto-create represented structure.
- A write path may auto-create missing structure only when each missing step is unambiguous and has a canonical shape for that adapter family.
- Auto-creation must never pass through ambiguity.
- Search-style or discovery-style selectors must not silently create structure.

## Ownership split between the shared seam and each adapter family

- The shared adapter seam owns:
  - dispatch by adapter family;
  - delimiting the adapter-owned authored body;
  - recognizing and resolving any outer host-owned binding surface before adapter evaluation begins;
  - passing one adapter result value forward as the root value of a later adapter invocation;
  - the distinction between read and write invocation;
  - the rule that write invocation returns an updated root value;
  - the common boundary around auto-creation;
  - the shared minimum outcome vocabulary.
- A concrete adapter family owns:
  - its authored path syntax;
  - parsing and evaluating its adapter-owned body after host-owned parameter values from the outer binding surface have been resolved and supplied;
  - its internal represented structure model;
  - its supported focus kinds and derived values;
  - its supported terminal mutations;
  - its canonical creation shapes for write-path auto-creation;
  - any family-specific diagnostics beyond the shared minimum vocabulary.

## Documentation discipline

- Shared adapter invocation and outcome rules belong in shared adapter requirements rather than being restated independently by each adapter family.
- Concrete adapter-family documents should focus on family-specific syntax, compatibility targets, canonical creation shapes, and supported actions.
- Adapter-specific documentation must not imply that a concrete family bypasses the shared adapter seam.

<!-- source: requirements/local-expressions/contexts.md -->

# Local expression context requirements

## Embedded value context

- Embedded value contexts may use local expressions to derive one value for a surrounding field.
- Embedded value contexts may read `inputs...`.
- Embedded value contexts may read `args...` when evaluated inside a fragment instance that declared those arguments.
- Embedded value contexts may read `state...` only where the surrounding contract allows runtime-state reads.
- Embedded value contexts may read `step...` only where the surrounding contract allows execution-local step-result reads.
- Embedded value contexts may depend on read-only probe observation when the surrounding contract allows non-effectful external observation.
- Embedded value contexts must remain free of connector invocation semantics.
- Embedded value contexts must remain free of hidden workflow-control semantics.
- Presence-check helpers such as `is_missing(...)` or `is_present(...)`, if introduced later, must apply only to approved lookup-style references and approved read-only representation-adapter invocations rather than to arbitrary computed expressions.

## Guard context

- Guard context expresses pre-execution policy conditions.
- Guard context is limited to dependencies known at launch time.
- Guard context must remain compatible with read-only, pre-execution analysis.
- Guard context may use workflow-visible inputs and other roots that are safe and meaningful before effectful business steps run.
- Guard context may use pure built-ins and read-only representation-adapter projections when those constructs remain launch-time-safe and pre-execution-safe.
- Guard context must not use representation-adapter write paths such as `->...`.
- Guard context must not depend on `step...`.
- Guard context must not require action execution in order to determine whether execution may proceed.
- Guard context must evaluate to a boolean result; a successful non-boolean result is a guard error rather than an implicit truthiness rule.
- Guard context should keep routine execution policy visible in the workflow declaration rather than encoding that policy in many bespoke probe names.
- Object-form guard items using `uses` may remain available for compatibility, but they should not displace native guard expressions as the preferred stable guard surface.

## Step-condition context

- Step-condition context expresses step-local conditional execution.
- Step-condition context may depend on prior execution-local registered step results when those results already exist before the conditional step is considered.
- Step-condition context may depend on read-only probe observation when the surrounding contract allows non-effectful external observation.
- Step-condition context must remain workflow-owned condition evaluation rather than a hidden branching language.
- Native bare `if` conditions are the preferred step-condition surface.
- Embedded `if: ${...}` remains supported only as a deprecated compatibility form.
- Presence-check helpers such as `is_missing(...)` or `is_present(...)`, if introduced later, must apply only to approved lookup-style references and approved read-only representation-adapter invocations rather than to arbitrary computed expressions.

## Presence-check argument boundary

- A presence-check helper, if introduced, must accept only lookup-style references whose missingness semantics are well-defined and read-only representation-adapter invocations whose absence semantics are contractually tied to adapter `not_found`.
- Allowed argument forms should be listed explicitly rather than inferred from broad expression permissiveness.
- Arbitrary computed expressions, built-in calls, pipelines, boolean compositions, probe calls, and literals must not be treated as valid presence-check arguments.
- A read-only representation-adapter invocation used as a presence-check argument should evaluate to presence success when the invocation succeeds and to absence when it fails specifically with adapter `not_found`.
- Other adapter failures such as `ambiguous`, `invalid_path`, `invalid_root_value`, or `invalid_action` must remain ordinary failures rather than being collapsed into boolean absence.
- A write-path representation-adapter invocation must not be accepted as a presence-check argument.
- Presence checks must preserve the distinction between an explicit `null` value and a missing lookup when the surrounding contract distinguishes them.

## Include-binding context

- Include-binding context evaluates caller-scoped bindings for included fragment arguments.
- Include-binding context may read caller-local roots that are valid at the include site.
- Include-binding context must preserve the distinction between caller scope and fragment-local `args...` scope.
- Include bindings must not implicitly grant the fragment body direct caller-local `step...` scope.

## Whole-tree rule

- Context restrictions apply to the entire local-expression tree.
- A forbidden dependency class must remain forbidden even when nested inside a call argument, list item, comparison, or other subexpression.

## Native versus embedded surfaces

- A native condition context may expose expressions without an interpolation envelope.
- An embedded value context may use a distinct authored embedding form for local expressions.
- Surface differences must not erase the underlying context restrictions that determine which roots and dependencies are allowed.

<!-- source: requirements/local-expressions/markdown.md -->

# Markdown representation-adapter requirements

## Role

- The `markdown` representation adapter is a product-defined local-expression surface for interpreting and transforming already available markdown text.
- This document defines markdown-family behavior within the shared representation-adapter invocation seam described in `requirements/local-expressions/adapters.md`.
- It should prioritize compatibility with typical GitHub-authored markdown text without introducing a separate `github_markdown` adapter family.

## Compatibility target

- The adapter should target a stable markdown document model suitable for general markdown inputs.
- Compatibility should prioritize common CommonMark and commonly used GitHub Flavored Markdown constructs.
- The adapter contract should document supported constructs and should not promise perfect reproduction of every source-specific markdown dialect detail.

## Authored path surface

- Markdown path syntax belongs to the markdown adapter contract rather than to the shared local-expression core.
- The shared adapter seam should identify the markdown family and the extent of the markdown-owned body, while markdown-family parsing owns the interior markdown-specific selector and action syntax.
- Optional host-derived parameterization should live outside the markdown-owned body through the shared adapter binding surface rather than through host references embedded directly in markdown-family grammar.
- Literal title selection uses `["..."]` in authored examples, where the string is treated as a literal title or literal named selector value.
- The adapter should expose an always-present `prelude` selector for the markdown text that appears before the first heading.
- Positional disambiguation uses `[n]`.
- After one singular list or task-list target has been selected, positional indexing with `[n]` may address one top-level list item within that selected block.
- Explicit structural selection may use adapter-defined forms such as `.blocks("kind")`.
- The adapter may provide common structural shortcuts such as `.list`, `.task_list`, or `.paragraph` as convenience sugar over the explicit structural form.
- The adapter may also provide explicit collection-view shortcuts such as `.list_items` or `.task_list_items` when the product needs one array-valued projection distinct from the richer block view.
- The adapter may provide text-search helpers such as `.find("...")` when the product needs them.

## Outer parameter binding

- When markdown-family behavior needs host-derived values, those values should be supplied through the shared outer adapter binding surface rather than embedded directly inside markdown-family syntax.
- Markdown-family evaluation should therefore consume resolved parameter values rather than unresolved host-owned references.
- Host-derived parameter values may parameterize markdown-family selectors or action arguments, but they should not be treated as a way to generate markdown-family grammar dynamically.
- One preferred form is a trailing host-owned binding suffix such as ` with{...}` after the markdown-owned body.

## Shortcut discipline

- Any shortcut must remain convenience sugar over one explicit markdown-adapter form.
- A shortcut must not introduce semantic behavior that is unavailable in the explicit form.
- A shortcut must not weaken normal `not_found`, `ambiguous`, or write-path auto-creation rules.
- A shortcut should expand to one stable explicit interpretation rather than depending on hidden heuristics.
- If the adapter offers both singular and plural structural shortcuts, their plurality semantics should remain consistent across node kinds.
- If the adapter offers paired singular and plural structural shortcuts, the singular form should denote an expect-one convenience form and the plural form should denote the corresponding many-valued explicit selection.

## Selection semantics

- The shared read-versus-write boundary and shared adapter outcome vocabulary come from `requirements/local-expressions/adapters.md`.
- Read paths must never create structure.
- A path that yields zero matches must fail as `not_found`.
- A path that yields multiple matches without explicit disambiguation must fail as `ambiguous`.
- The adapter must not silently apply implicit first-match selection.

## Terminal action surface

- A trailing `->action(...)` form may denote a terminal mutation over the selected markdown focus.
- A terminal markdown mutation is one markdown-family instance of the shared adapter write-invocation rule that returns the updated root value.
- Action names should remain author-comprehensible rather than exposing low-level parser internals.
- The markdown family should prefer one small orthogonal text-action surface for markdown text targets, such as `append(text, prefix="")`, `replace(text)`, and `remove()`.
- `append` should accept one plain text argument plus an optional plain text prefix argument whose default is the empty string.
- Markdown action arguments should be plain text rather than structured object payloads.
- The family may still expose one list-specific action such as `add(text)` when nested-list structure makes generic append semantics ambiguous at the list level.
- Large, multi-paragraph, or otherwise structurally rich markdown action text should still be treated as plain text input rather than forcing a different public payload shape.

## Prelude semantics

- `prelude` is always present.
- If a document begins with a heading, `prelude` still exists as the empty leading markdown slice rather than failing as `not_found`.
- Read and write markdown semantics should therefore treat prelude as one stable target rather than as an optional convenience surface.

## Write-path auto-creation

- The markdown adapter inherits the shared write-only auto-creation boundary from `requirements/local-expressions/adapters.md`.
- Write paths may auto-create missing structure only when each missing step is unambiguous and has a canonical markdown shape.
- Auto-creation must never pass through ambiguity.
- Search-based selectors must not trigger implicit creation.
- Read paths must not auto-create structure.

## Product-shape guidance

- The explicit form defines canonical markdown-family semantics within the shared adapter seam.
- Any shorter GitHub-friendly forms should remain convenience syntax layered over the explicit form rather than separate semantics.

<!-- source: requirements/local-expressions/text.md -->

# Text representation-adapter requirements

## Role

- The `text` representation adapter is a product-defined local-expression surface for interpreting and transforming already available plain-text string values.
- This document defines text-family behavior within the shared representation-adapter invocation seam described in `requirements/local-expressions/adapters.md`.
- The text family should remain narrow and predictable rather than becoming a general grep, regex, or stream-editing language.

## Compatibility target

- The adapter should target stable plain-text semantics over ordinary newline-delimited strings.
- The adapter should not claim richer document structure such as markdown sections or universal paragraphs.
- The adapter should prefer literal authored behavior over heuristic tokenization, linguistic inference, or dialect-specific parsing.

## Authored path surface

- Text path syntax belongs to the text adapter contract rather than to the shared local-expression core.
- The shared adapter seam should identify the text family and the extent of the text-owned body, while text-family parsing owns the interior text-specific selector and action syntax.
- Optional host-derived parameterization should live outside the text-owned body through the shared adapter binding surface rather than through host references embedded directly inside text-family grammar.
- The family should expose `.lines` for line-oriented projection.
- The family should expose `.find("...")` for singular literal substring selection.
- The family should expose `.finds("...")` for plural literal substring selection.
- The family should expose `before("...")` and `after("...")` as singular anchor-based narrowing selectors.
- Positional disambiguation uses `[n]`.

## Search and anchor semantics

- `find`, `finds`, `before`, and `after` should use literal substring matching only.
- The family should not infer token, word-boundary, case-insensitive, or regex semantics unless such behavior is introduced later as separate explicit surface.
- A literal authored to `before("...")` or `after("...")` therefore matches ordinary substring occurrences even when they appear inside larger words.
- `find("...")` must require exactly one match.
- `before("...")` and `after("...")` must require exactly one anchor occurrence within the current singular text scope.
- `.finds("...")` should return matches in source order.
- `.finds("...")` should model non-overlapping matches.

## Collection surface

- `.lines` should return an ordered collection of line focuses.
- `.finds("...")` should return an ordered collection of match focuses.
- `.lines` applied to the empty string must return an empty collection.
- `[n]` applied to a collection should select one singular member by zero-based index.
- `[n]` with an out-of-range index must fail as `not_found`.

## Singular-versus-collection boundary

- Singular text scopes may support further text selectors such as `.lines`, `.find`, `.finds`, `before`, and `after`, plus terminal text actions.
- A selected line focus is a singular text scope.
- A singular match focus is a singular text scope.
- Collection-valued focuses should not support further narrowing or search selectors directly.
- Collection-valued focuses may support terminal bulk mutation when that mutation can be applied independently across ordered non-overlapping members.

## Selection semantics

- The shared read-versus-write boundary and shared adapter outcome vocabulary come from `requirements/local-expressions/adapters.md`.
- Read paths must never create structure.
- `find("...")`, `before("...")`, and `after("...")` must fail as `not_found` when no match exists in the current singular text scope.
- `find("...")`, `before("...")`, and `after("...")` must fail as `ambiguous` when more than one match exists in the current singular text scope.
- `.finds("...")` should return an empty collection rather than fail when no matches exist.
- The adapter must not silently apply implicit first-match or last-match selection.

## Terminal action surface

- A trailing `->action(...)` form may denote a terminal mutation over the selected text focus or over one eligible collection focus.
- A terminal text mutation is one text-family instance of the shared adapter write-invocation rule that returns the updated root value.
- Action names should remain author-comprehensible rather than exposing parser internals.
- The text family should expose a small orthogonal text-action surface consisting of `append(text)`, `replace(text)`, and `remove()`.
- Text action arguments should be plain text rather than structured payloads.
- `remove()` should be equivalent in effect to replacing the selected focus with the empty string.

## Bulk mutation discipline

- Bulk mutation over a collection focus is allowed only when the targeted members are ordered and non-overlapping.
- Bulk mutation over a line collection should apply independently to each selected line focus in source order.
- Bulk mutation over a match collection should apply independently to each selected match focus in source order.
- Bulk mutation over an empty collection should succeed as a no-op and return the unchanged root value.
- The family must not imply hidden map, filter, flatten, or regroup semantics for non-terminal collection selectors.

## Product-shape guidance

- The family should remain a narrow plain-text adapter rather than a full document-structure adapter.
- The family should prefer stable literal scope narrowing and explicit collection handling over heuristic or implicit semantics.
- If richer text structure or richer search modes are needed later, they should be introduced as explicit new surface rather than silently overloaded into the MVP text contract.

<!-- source: requirements/playbook/core.md -->

# Playbook requirements

## Discovery and launch surface

- A project-local playbook must be discoverable through a deterministic default location.
- The default discovery rule must be simple enough for both humans and agents to predict without trial-and-error.
- Playbook discovery failure must produce a structured and reviewable error rather than an implicit fallback to unrelated files.
- An explicit playbook path must override default discovery when the caller provides one.

## Catalog and composition

- A playbook must support named workflow entries as the primary launch surface.
- A playbook may support named profile entries for launch-time selection and defaults.
- A playbook launch surface may support explicit launch-time input overrides for one run.
- A playbook launch surface may declare an explicit execution working directory for a run through playbook defaults, the active profile, or the active workflow entry.
- Working-directory precedence must be deterministic and follow increasing specificity from playbook defaults to profile context to workflow-entry context.
- Any declared playbook-, profile-, or workflow-level working directory may use the existing `${...}` embedded-value local-expression surface when the expression stays within an activation-time-safe subset.
- A playbook may declare a `pre_run` workflow set that executes before the requested workflow in the same runtime session.
- A `pre_run` workflow set must remain explicit, project-local, and reviewable from the playbook surface.
- Failure in any `pre_run` workflow must prevent effectful execution of the requested workflow.
- `pre_run` must have an explicit playbook-owned dependency model rather than borrowing hidden state requirements from the requested workflow contract.
- Main workflows must not be required to declare logical state needs only because playbook `pre_run` consumes that state during launch.
- When `pre_run` needs runtime state, the playbook surface must declare the necessary binding explicitly on the `pre_run` entry itself.
- A playbook must support named runtime state declarations for project-local reuse.
- A playbook must support binding workflow logical state roles to named project state declarations.
- Every workflow logical state need must have an explicit playbook binding for the active workflow entry.
- Every playbook state binding must target an existing named playbook state declaration.
- Playbook must fail validation when a workflow entry contains a state binding for an undeclared workflow logical state need.
- Playbook-owned names must be unique within their own catalogs.
- Playbook composition must remain explicit rather than relying on silent shadowing or broad filename guessing.

## Resolution discipline

- Relative workflow and profile references must resolve deterministically from playbook-owned context.
- An execution working directory must not change playbook discovery or reference resolution rules.
- A working-directory expression must be fully resolvable before the first guard or step executes.
- Named references must either resolve to one declared target or fail clearly.
- Missing catalog targets must fail validation before effectful execution starts.
- Unknown stable fields in the playbook contract should fail validation.

## Product boundary

- A playbook must remain a project-level launch surface rather than becoming a second workflow language.
- Workflow business logic should stay in workflow files rather than being duplicated into playbook entry definitions.
- Playbook ergonomics should reduce the need for handwritten bootstrap commands without hiding runtime semantics.
- Execution working directory should remain explicit runtime context rather than hidden shell-first behavior.
- A working-directory expression must reuse the documented embedded-value local-expression surface rather than introducing a second expression language.
- A working-directory expression must not read runtime state, registered step results, or any runtime-derived value that is unavailable at launch time.

<!-- source: requirements/workflow/core.md -->

# Workflow requirements

## Authoring and shape

- A workflow file must be writable by both humans and agents.
- Workflow authoring from existing public operations is a primary product path rather than a niche expert path.
- Validation must fail on unknown fields in stable workflow schema.
- A human reviewer must be able to locate policy and guardrails in the declaration itself rather than reconstructing them from implementation code alone.
- An agent author must be able to predict whether a workflow is valid, resolvable, and likely executable from schema, examples, and connector contracts.
- The contract must minimize hidden shell semantics that change workflow meaning without explicit declaration.
- The default authoring path should favor composition of existing operations and profiles over creation of new connector semantics.
- Explicit workflow-owned data flow between prior and later steps should be representable without inventing connector-local storage hacks.
- A workflow may declare workflow-local named expressions through a top-level `let` surface when that keeps long local expressions readable.
- Reusable workflow fragments should support explicit local argument contracts.
- Explicit fragment argument contracts must not by themselves force static composition and runtime-scoped invocation to collapse into one reuse primitive when their semantics diverge materially.
- If the product later introduces both `include` and `run`, the distinction must remain brief enough for humans and agents to predict from contract docs and examples.
- All user-facing activation inputs must be declared in the root workflow `inputs` contract even when they are consumed only inside included fragments or reusable run targets.
- Validation after workflow assembly must reject any `inputs.<name>` reference that does not resolve to a root-declared workflow input.
- A successful workflow run may accumulate one or more authored workflow-local return values through explicit `result` steps.
- Workflow-local result values must accumulate in execution order rather than replacing prior result values for that workflow run.
- A successful workflow run may also publish one or more authored global output values through explicit `publish` steps.
- Published global output values must accumulate in execution order across the enclosing run session rather than replacing prior published values.
- A `run` step may declare `register` when the product chooses to expose the just-completed callee workflow-local `results` list back to the caller.
- If the product later introduces `for_each` on `run`, that surface must be bounded to array-valued sources rather than to adapter-specific iterable protocols.
- If `run` later supports `for_each`, the step-level `if` condition must still apply to the whole declared step rather than becoming one per-item filter surface.
- If `run` later supports `for_each`, lexical nesting of `for_each` inside another `for_each` in the same authoring surface must remain invalid.
- If `run` later supports both `for_each` and `register`, the registered value should preserve one array of per-run workflow-local result payloads rather than flattening all returned values into one undifferentiated list.
- If the product later emits a synthetic fallback result for successful runs without explicit results, that fallback must apply only to the requested top-level workflow run rather than to internal include, `pre_run`, or nested `run` boundaries.
- Workflow input declarations may carry one optional author-provided `hint` string for invocation guidance.
- Input `hint` is guidance only, not a validation rule or runtime-inferred contract fact.

## Product boundary

- Core semantics must stay small and explainable.
- The format must prefer explicit fields over implicit behavior.
- Drift between docs, schema, examples, and runtime must be detectable.
- Workflow and profile authoring must remain easier and more common than connector authoring in early product stages.

<!-- source: requirements/runtime/core.md -->

# Runtime requirements

## Runtime behavior

- The runtime must support at least `review`, `check`, `plan`, `execute`, and `explain`.
- The runtime must return structured results, not only raw stdout/stderr.
- `plan` must describe what would be checked and executed, including known blockers.
- `explain` must return runtime reasoning in a structured form, not merely debug logs or traceback text.
- The runtime must distinguish at least validation failure, resolution failure, guard failure, execution failure, and success.
- Structured results must be usable by both a human reviewer and an automated agent without log scraping.
- Runtime diagnostics should prefer normalized categories and structured fields over ad hoc human prose.
- At minimum, the structured runtime result must preserve a human-readable message and a machine-readable code when non-success detail matters.
- The model should support fail-safe behavior for local operational rituals where risk reduction matters more than maximum flexibility.
- The runtime must expose a machine-usable decision surface, not only an execution surface.
- The runtime must respect connector-declared operation kind consistently in step context; probe operations used as steps remain probe operations during `execute`.
- The runtime should diagnose statically knowable builtin-expression misuse before `execute` when the misuse is certain from authored workflow structure.

## Runtime serialization requirements

- Structured runtime results must be losslessly JSON-serializable.
- `check`, `plan`, `execute`, and `explain` outputs must be consumable without log scraping or YAML parsing.
- Diagnostics, plan items, blockers, inferred next actions, and other contract-level runtime surfaces must be encoded as JSON-shaped fields rather than only human prose.
- Human-readable text may supplement runtime results, but it must not be the only carrier of machine-relevant meaning.

## Agent-facing decision support

- The runtime must be able to answer, in machine-readable form:
  - what is known now;
  - whether execution is allowed now;
  - why execution is blocked when blocked;
  - what next safe action is available when it can be inferred safely.
- `review`, `check`, `plan`, and `explain` must remain baseline decision-support modes rather than optional UX sugar around `execute`.
- `review` must not treat every declared workflow input as automatic missing-validation debt; it should distinguish meaningful control/effect inputs, profile-carried ambient context, and unused declarations.
- `review` must treat trusted profile-provided consumed context separately from user-driven validation candidates and must not require early re-validation of that context by default.
- Profile-supplied surplus context must not force workflows to declare unused values merely to activate successfully.
- The runtime must distinguish profile-supplied surplus context from explicit user-supplied unknown inputs.
- Default `review` and `check` outputs must not surface ordinary expected profile-surplus context as user-facing diagnostics.

## Explainability

- The system must be able to answer "why is this workflow blocked?" without requiring execution of business steps.
- The system must be able to answer "what would happen if this workflow executed now?" in a machine-readable plan/result shape.
- The system must preserve the difference between:
  - blocked before execution;
  - execution intentionally skipped;
  - execution attempted and failed.
- When a step is intentionally skipped because its `if` condition evaluated to `false`, runtime outputs should preserve that reason in machine-usable form.
- When a step `if` condition cannot be evaluated, the runtime must fail execution rather than silently treating the condition as `false`.
- `explain` output should include useful next actions when the runtime can infer them safely.
- The explanation surface must remain stable enough for agent tooling to rely on status codes and categories.
- If the product later adds bounded `for_each` on `run`, `check`, `plan`, and `explain` must preserve statically knowable fan-out facts such as whole-step eligibility, exact cardinality when knowable, and explicit unknown-cardinality state when not knowable before execution.
- If bounded `for_each` is later added on `run`, the runtime must preserve the difference between a fan-out step blocked before expansion, a fan-out step statically expanded with known item count, and a fan-out step whose item count remains runtime-only.

<!-- source: requirements/runtime/introspection.md -->

# Runtime requirements for introspection

## Role

- The runtime must expose a machine-readable introspection surface for tools and agents.
- This surface exists so external consumers can discover supported contracts and capabilities without prose parsing or direct code-reading.

## Source of truth

- Published introspection must come from runtime-owned metadata or canonical contract data.
- Introspection must not be maintained as a separate descriptive mirror of implementation behavior.
- Human-facing prose may explain the surface but must not define it.

## Minimum surface

The runtime must be able to answer, in machine-readable form:

- what discovery entrypoint exists;
- what workflow and playbook contract surfaces are supported;
- what capability states are supported, unsupported, or planned;
- what expression roots, filters, builtins, and allowed surfaces are supported;
- what public operation metadata is available.

## Growth discipline

- New runtime-visible surface should be added through canonical metadata first or in the same change.
- The project should prefer one shared metadata source over separate runtime and help descriptions.
- Introspection should fail closed for covered surfaces rather than silently omitting changed behavior.

<!-- source: requirements/runtime/state.md -->

# Runtime requirements for state

## Role

- The runtime may expose a small built-in persistent state capability for workflow coordination across runs.
- This capability belongs to runtime rather than to the public connector surface.
- The initial purpose is to remember small pieces of workflow-owned state such as task-to-branch linkage.

## MVP scope

- The initial authoring surface should support a playbook-level `states` mapping that names runtime-managed state locations.
- The initial authoring surface should support workflow-level logical state needs that remain separate from concrete project state declarations.
- The initial workflow `state_needs` surface should be marker-only rather than carrying richer per-need configuration fields.
- The initial authoring surface should support explicit effectful mutation through `state_set` and `state_delete` step forms.
- The initial authoring surface should support direct value reads through `state...` references rather than requiring a dedicated `state_get` step.
- The initial state access grammar should use one aligned path surface for reads, `state_set`, and `state_delete`.
- The initial capability should remain intentionally small and should not require a general-purpose memory or fact system.

## Minimal semantics

- A named state entry should identify a runtime-managed persistent location.
- Workflow state reads and writes should resolve through workflow logical state roles that are bound by the playbook to concrete state declarations.
- A workflow that declares a logical state need is not activatable without a corresponding playbook state binding.
- `state_set` should create or replace the addressed value deterministically.
- `state_delete` should remove the addressed value deterministically.
- State reads should resolve to stored values through the same stable state path surface used by authoring.
- Missing state reads should remain structured and predictable rather than falling back to hidden defaults.
- The initial stable state path should require a logical role, one `inputs...` key reference, and optional dotted field traversal.

## Boundary discipline

- Runtime state should not be modeled as a connector family.
- Runtime state should not be described as a broad fact or knowledge system at this stage.
- Runtime state should not introduce a broad query language, lock model, reconciliation model, or multi-scope memory model in the MVP.
- The MVP should prefer a narrow explicit surface over premature generalization.
- Runtime state should remain a cross-run memory surface rather than a substitute for per-run step registers.
- A workflow should not write or delete a logical state role before its final read of that same logical role.
- State mutation should remain a top-level workflow concern and should not appear inside included fragments or runtime-invoked fragments.

<!-- source: requirements/policy/core.md -->

# Policy requirements

## Guard phase

- Guard evaluation must be a first-class runtime phase and not only an informal step convention.
- `check` must evaluate guards and static preconditions without executing effectful business steps.
- A blocked workflow result must identify the blocking guard or guards in machine-readable form.
- The runtime should be able to report more than the first blocking policy issue when such issues can be determined safely without execution.

## Positioning

- Ordo should remain meaningfully distinct from a generic pipeline/task runner by preserving its analysis-first and explain-first behavior.
- Ordo is not required to mimic existing pipeline tools when that would weaken guards, explainability, or structured results.
- Policy evaluation must remain an explicit runtime concern and must not be recoverable only by reading connector implementation code or shell control flow.

<!-- source: domain/authoring.md -->

# Authoring domain

## Role

Authoring is a first-class product surface.

Ordo is not only meant to execute workflows. It must also be understandable and writable by a sufficiently capable agent working from the documented contract surface.

## Primary extension path

The primary extension path in early Ordo is:

- compose workflows from existing public operations;
- compose profiles from explicit presets and policy choices;
- adapt projects through explicit declarative configuration.

The primary extension path is not:

- rapidly inventing new connector families;
- casually creating new operation semantics during routine workflow authoring.

## Discoverability

An author should be able to discover:

- which operations exist;
- what each operation means;
- what inputs and result shapes are expected;
- which examples and patterns are considered idiomatic.

## Checkability

Authoring must be checkable before execution.

An agent should be able to ask, in structured form:

- is this workflow valid;
- are all references resolvable;
- is execution likely blocked now;
- what should be changed to make the declaration better or safer.

## Quality expectation

Good authoring is more than schema validity.

It should preserve:

- explicit intent;
- visible policy;
- reviewability;
- stable public semantics;
- minimal dependence on hidden shell behavior.

<!-- source: domain/connector.md -->

# Connector domain

## What a connector is

A connector is a public integration contract family that a workflow relies on.

## What a connector owns

Connector owns:
- namespace;
- shared bootstrap;
- family-level prerequisites;
- shared runtime context;
- operation registry.

Connector operations are also the semantic home for non-trivial transformation and integration logic.
Workflow files may orchestrate them, but should not absorb that algorithmic work into authored workflow structure.

## What an operation is

An operation is a concrete public operation within a connector family.

For connector operations, it is important to distinguish at least two operation kinds:
- `probe` — observes the world and returns structured observations without intended side effects;
- `action` — performs an effectful operation and returns a structured summary of its effects.

An operation contract must define:
- inputs;
- prerequisites;
- effects;
- outputs;
- failure modes.

An action contract may also expose advisory metadata that helps runtime reason about preflight support quality, for example observation invalidation scopes and recommended preflight-observation templates.

## Explainability and result discipline

Every connector operation must:
- return a structured result both on success and on failure;
- be able to explain its outcome locally within its narrow semantic domain;
- preserve the result contract even under an internal exception.

Connector operations should remain small, local, and readable authoring units.
They should expose narrow integration semantics rather than absorb runtime orchestration behavior.

Implications:
- a `probe` must return not only an outcome but also meaningful observations and diagnostics;
- an `action` must return not only an outcome but also an effect summary and diagnostics;
- raw stdout/stderr, when produced by an operation, are supplementary detail fields rather than the basis of the contract.

## Mode-agnostic operation authoring

Connector operations should be authored as mode-agnostic integration units.
They should not directly encode `check`, `plan`, `explain`, or `next` behavior.

Instead, each operation should expose a structured local surface rich enough for runtime to derive those behaviors.

Implications:
- probes should return stable observations rather than policy-shaped orchestration decisions;
- actions should return stable effect summaries rather than mode-specific execution narratives;
- operation code should stay focused on local input handling, integration work, and structured outcome shaping;
- mode semantics should remain a runtime responsibility even when an operation offers local summary text, diagnostics, or supplementary raw detail.

## Probe readiness

A probe is ready when:

- it answers one clear domain question;
- its output fields are minimal but sufficient for downstream use;
- its output fields are domain-natural rather than artificially standardized;
- it does not encode runtime mode semantics such as `check`, `plan`, `explain`, or `next`;
- it does not primarily own shared family prerequisite failures that belong to executable bootstrap;
- its remaining failure modes are narrow, local, and honest;
- its result is understandable from structured outcome fields without relying on raw transport output as the primary contract;
- it is reusable both directly and as a building block for derived probes or workflow-level composition.

Useful review questions:

- what single question does this probe answer;
- which output fields are actually needed by consumers;
- does each field carry distinct machine-relevant meaning;
- are any shared prerequisite failures still incorrectly owned by the probe;
- is any workflow or policy logic leaking into the probe;
- can the result be explained without scraping stdout or stderr;
- would this probe still look clean if reused by another probe or by guard evaluation.

## Action readiness

An action is ready when:

- it performs one clear effectful operation within a narrow semantic scope;
- it is an executable leaf operation rather than an abstract namespace or action group;
- its inputs reflect the natural semantic structure of the domain target rather than an artificial scalar-versus-batch normalization;
- its success outputs describe durable effects or effect-relevant observations rather than only a bare success flag;
- it exposes at least one documented action-specific output field on success;
- it does not encode runtime mode semantics such as `check`, `plan`, `explain`, or `next`;
- it validates only facts required for the action to be executable and to remain the action it claims to be;
- it does not hard-code workflow etiquette, safety preferences, or local policy as intrinsic action preconditions;
- distinctions that change the action's result class, failure semantics, or mental model are modeled as separate actions rather than as incidental parameters;
- incidental operational variation that does not change action identity is carried in inputs rather than expanded into many near-duplicate action names;
- its effect boundary is clear enough that a reader can tell what completion of the action actually means;
- if partial effect or partial success is possible, the contract represents that possibility honestly rather than pretending the action is all-or-nothing;
- the meaning of a repeated call is semantically clear, including whether it is idempotent, duplicate, conflicting, additive, or a no-op;
- its resulting post-state is observable through documented outputs, probes, or both;
- when the action creates, selects, moves, or updates an addressable result, that result is returned in a documented addressable form;
- if the action is a true batch operation, its atomic-versus-partial semantics are part of the contract rather than left implicit;
- its remaining failure modes are narrow, local, and honest;
- its documented `failure_modes` describe expected contract-level non-success rather than exceptional runtime breakdown;
- its result is understandable from structured outcome fields without relying on raw transport output as the primary contract;
- it would still make sense if invoked from a different workflow with different surrounding policy.
- if it declares recommended preflight observations, those recommendations remain advisory explainability support rather than hidden executability rules.

Useful review questions:

- what single effect does this action produce;
- is this operation a concrete executable leaf, or only a category that should remain non-executable;
- do the inputs reflect the natural target shape of the domain, or are they forcing an artificial scalar-versus-batch model;
- which output fields are actually needed by consumers to understand what changed;
- is there at least one documented success output field whose meaning is specific to this action rather than generic outcome scaffolding;
- which checks are truly required for executability or action identity, and which are only policy or etiquette;
- does any named variant here actually change result class, failure semantics, or mental model enough to deserve a separate action;
- does any existing action name differ only by incidental parameterization that should instead live in inputs;
- is any apparent batch shape really one aggregated domain target, or is it a set of independent repeated actions;
- where exactly is the action's effect boundary, and what does completion mean;
- can the action produce partial effect or partial success, and if so is that represented honestly in the contract;
- what does a repeated identical call mean here: idempotent retry, duplicate effect, conflict, or no-op;
- is the resulting post-state observable through documented outputs, probes, or both;
- if the action yields an addressable result, is that result returned explicitly enough for downstream use;
- if this is a true batch action, are atomic-versus-partial semantics explicit;
- do the documented `failure_modes` describe expected action-level refusal or non-success, rather than interruption, crash, timeout, or other runtime-level breakdown;
- is any workflow or approval logic leaking into the action;
- can the result be explained without scraping stdout or stderr;
- would this action still look clean if another workflow reused it under a different safety policy.
- if this action advertises recommended preflight observations, do they help `check`, `plan`, and `explain` without assuming one specific workflow-local value source.

## Action input norms

- Action inputs should reflect the natural semantic structure of the target domain rather than an artificially imposed scalar-versus-batch split.
- An action may take no inputs when its target and scope are fully determined by current context.
- When an action operates on one aggregated domain target, it may naturally affect many underlying objects without becoming a batch action.
- A batch action is not merely an action that touches many objects; it is one call that is semantically equivalent to a set of independent repeated actions over multiple targets.
- If multiplicity is an internal property of one domain target, it should remain part of the ordinary action contract rather than being forced into a separate batch surface purely because many objects are involved.
- Inputs should distinguish, when applicable:
  - `target` — what the action is directed at;
  - `payload` — what is created, transmitted, or changed;
  - `constraints` — restrictions that limit the allowed result class;
  - `justification` — explanation or grounds, when the action itself genuinely requires them.
- Free text should be preferred only when the payload structure is inherently unstable or would not produce a useful stable contract shape.
- If an action's inputs grow without clear role separation, this is a signal to review whether the action is too broad or is hiding a small workflow.
- Input differences that only change call data should remain inputs.
- Input differences that change result class, failure semantics, or mental model should lead to separate action leaves rather than one overloaded action surface.

## Contract failure versus exceptional runtime error

- An operation's documented `failure_modes` should describe expected contract-level non-success within the semantic world of that operation.
- Exceptional runtime breakdown must remain distinct from documented contract failure modes.
- Examples of exceptional runtime breakdown include interruption, timeout, transport corruption, uncaught implementation fault, and other failures that do not honestly belong to the operation's narrow domain semantics.
- Connectors should not encode catastrophic or runtime-level breakdown as if it were merely another ordinary business-style action refusal.
- Runtime should preserve the distinction between an operation that failed within contract and an operation whose execution broke down exceptionally.

## Bootstrap

A connector may have shared bootstrap or shared context for the whole family.

Shared bootstrap is a distinct layer from operation-to-operation dependency and from workflow-level policy composition.

Bootstrap owns family-wide prerequisites and capability checks that would otherwise make every operation's local failure surface broader and noisier than its narrow semantic job.

Examples:
- `gh` checks binary availability, auth, and required scopes at the family level;
- `gh.issue.view` checks its own local contract;
- `shell` defines supported interpreter policy, while `shell.command` executes a concrete command.

## Dependency layers

Connector design should distinguish at least three dependency layers:

- shared family bootstrap and shared context;
- operation-to-operation implementation dependency when one operation is explicitly derived from another;
- workflow-level composition and policy over public operation results.

These layers should not be collapsed into one another.

Implications:
- shared prerequisites should prefer bootstrap or shared family context rather than being modeled only as ordinary public probes;
- operation-to-operation dependencies are allowed when they stay explicit, local, and reduce semantic duplication;
- workflow-level policy should still compose public operation results rather than being hidden inside implementation dependency graphs;
- canonical fact probes remain preferred over an explosion of narrow policy-shaped derived probes.

## Publicness

`connectors/` is a public and stable layer.

Implications:
- connector and operation names matter;
- family-level semantics matter;
- the meaning of a same-named operation must not change silently.

## Runtime vs connector-library boundary

Connectors should be treated as a built-in public integration library rather than as private runtime internals.
They do not conceptually live inside the runtime core.

Implications:
- runtime owns orchestration, resolution, mode behavior, and explanation flow;
- connector families own integration semantics for their public namespaces;
- runtime consumes connector contracts and results, but should not silently redefine the meaning of connector operations;
- runtime should derive `check`, `plan`, `explain`, and `next` behavior from structured operation contracts and results rather than delegating those mode semantics into connector implementation code;
- runtime should preserve the distinction between family bootstrap state, operation-local outcomes, and workflow-level policy composition when building explanations and plans;
- runtime-facing wiring should flow through an explicit connector-provider surface rather than a hardcoded package location;
- application composition may choose to install the standard built-in connector provider or omit it;
- package placement should preserve this conceptual boundary even when Python packaging or repository layout introduces adapters.

## Connector package structure

The preferred connector package structure is organized first by family, then by operation kind, then by operation file.

Canonical shape:

- `connectors/<family>/bootstrap.py` for family-level bootstrap and shared prerequisites;
- `connectors/<family>/probes/<operation>.py` for one public probe per file;
- `connectors/<family>/actions/<operation>.py` for one public action per file.

Helper files such as `__init__.py` are expected when needed.

Manual central registries that duplicate the package structure should be avoided.

If a public operation exists as a file in the family package tree, that file should be the primary source of truth for its contract and implementation rather than requiring a second hand-maintained registry entry elsewhere.

Family-local autodiscovery or equivalent family-local assembly should be preferred so that each connector family assembles its public probe and action surface from its own package tree.

Operation modules should expose a uniform publication hook so family-local assembly can discover the published operation definition explicitly rather than inferring it from unrelated globals.

## Fixed v0 connector domains

- `git.*`
- `gh.*`
- `shell.*`

## Canonical git probe surface direction

The preferred long-term `git` probe surface is a compact set of repo facts rather than many policy-encoded predicates.

The main target probes are:

- `git.repo`
- `git.branch`
- `git.branches`
- `git.worktree`
- `git.worktrees`
- `git.stash`
- `git.state`
- `git.ref(ref=...)`
- `git.upstream`
- `git.range(base=..., head=...)`

Specialized policy-shaped names such as `git.branch_not_main` are not part of the desired steady-state public surface and should not be added as canonical git probes.

## Possible future connector namespaces

- `run.*`
- `ansible.*`
- `fs.*`
- `obsidian.*`

## Local extension namespaces

- `local.*`
- `project.*`

<!-- source: domain/local-expressions.md -->

# Local expressions domain

## Role

Local expressions are the workflow-owned declarative surface for reading local workflow-visible data and deriving local conditions or values without introducing connector execution, hidden imperative logic, or a second orchestration layer.

They exist to keep small workflow-local computation and condition declaration inside the public authoring surface.

## What this domain owns

This domain owns:

- the idea that workflows may carry expression-bearing fields;
- workflow-local naming of local expressions through a top-level `let` surface;
- the local data surfaces that expressions may read;
- the idea that expressions may derive intermediate values from already available values;
- product-defined representation adapters for pure value interpretation and transformation;
- the semantic distinction between expression contexts;
- the boundary between local expression evaluation and connector operation execution;
- the boundary between local expression evaluation and workflow control surfaces.

This domain does not own exact grammar, parser structure, `${...}` envelope rules, or YAML field shape details.

## Core entities

### Local expression

A local expression is a workflow-visible declarative expression whose meaning stays within local workflow semantics.

It may read documented local surfaces and derive a value or condition, but it must not become a hidden scripting layer.

### Expression context

An expression context is one product surface in which local expressions may appear.

Different contexts may permit different roots, evaluation timing, and restrictions while still belonging to one local-expression domain.

Contexts should differ by policy and expected result shape, not by fragmenting read-only expression semantics into separate engines.

### Expression root

An expression root is a documented workflow-visible surface that an expression may read.

The initial local-expression roots are:

- `inputs...` — declared workflow inputs;
- `args...` — included-fragment arguments local to one fragment instance;
- `state...` — documented runtime-state read surface when the surrounding context allows state access;
- `step...` — prior registered step results when the surrounding context allows execution-local step data.

### Read-only probe observation

A local expression may also depend on product-defined read-only connector observations when the surrounding context allows non-effectful external observation.

Such observation remains part of local-expression semantics only when it is read-only, reviewable, and does not introduce effectful connector execution.

When the same read-only observation request appears repeatedly inside one evaluation scope, canonical evaluation should reuse one observed result rather than re-issuing the same probe work.

### Derived intermediate value

A local expression may derive one value from another already available value and then continue evaluation over that derived value.

Such intermediate values remain inside local-expression semantics.
They do not by themselves introduce connector execution, workflow control, or storage ownership.

### Workflow-local binding

A workflow may name one local expression through a workflow-level `let` entry.

Such a binding remains part of local-expression authoring rather than introducing a second language layer.

It exists to let a workflow name a long or repeated expression without changing expression semantics.

### Representation adapter

A representation adapter is a product-defined local-expression surface for interpreting an already available value through a specific representation such as markdown, html, json, or string.

Representation adapters may expose pure navigation and transformation operations over those values.
They are not connectors and they do not own external integration semantics.

Concrete adapter families rely on one shared product-defined adapter invocation seam rather than bypassing local-expression evaluation through ad hoc family-specific entry paths.

Adapter-specific authored syntax belongs in adapter-specific requirements, for example `requirements/local-expressions/markdown.md` for the markdown adapter surface.

Adapter discipline:

- everything between the adapter name and a terminal mutation is adapter-defined selection or navigation surface;
- the product should not force all adapters into one fake-uniform middle syntax when the underlying representations differ materially;
- terminal adapter mutations should remain explicit and should return the updated root value rather than persisting change by themselves.

## Core contexts

### Guard context

Guard context is the pre-execution policy context.

Its job is to express whether execution may proceed before effectful business steps run.

Because of that role, guard context is limited to dependencies that are known at launch time and must remain compatible with read-only, pre-execution analysis.

Guard context may still use the same canonical local-expression family as nearby contexts, including pure built-ins and read-only representation-adapter projections, so long as those constructs remain launch-time-safe and pre-execution-safe.

Guard context must not depend on execution-local `step...` data, must not use representation-adapter write paths such as `->...`, and must ultimately yield a boolean result.

### Step-condition context

Step-condition context is the step-local conditional execution surface.

It is still workflow-owned condition evaluation, but it is not the same semantic job as guard context because it may depend on execution-local information that appears only after earlier steps run.

### Include-binding context

Include bindings belong to the local-expression domain because they may evaluate caller-scoped local expressions before fragment-local `args...` are bound.

Their semantic job is caller-side value binding for assembly-expanded material, not connector invocation.

### Embedded value context

Embedded value context covers value-bearing fields that reuse local-expression evaluation.

It may depend on whatever is available at the point where that value is resolved, but it remains a pure local-expression surface rather than a hidden execution or control surface.

## Context families

Local-expression contexts divide into two families:

- condition-oriented contexts such as guards and step conditions;
- value-oriented contexts such as embedded value fields and include bindings.

## Boundary discipline

### Expression versus connector execution

Local expressions may read documented workflow-visible data.
They may also derive additional values from those already available values through pure local operations.
They may depend on read-only connector observations when those observations are modeled as non-effectful expression dependencies.

They must not themselves become a public connector invocation surface for effectful work.

Any connector execution semantics belong to connector operations and workflow steps, not to local expressions as such.

### Canonical core direction

The canonical local-expression core should keep only non-effectful observation and value-derivation semantics.

That core includes stable value and condition constructs such as:

- literals and lists;
- local roots and their field navigation;
- read-only probe observations;
- boolean composition and comparison;
- pipelines, built-ins, and representation-adapter operations.

It excludes:

- effectful connector actions;
- hidden workflow control;
- workflow-defined language extension.

### Canonical probe-call execution boundary

Read-only probe-call semantics should remain inside the canonical local-expression execution model, but they do not collapse into ordinary local-value lookup.

The intended split is:

- the canonical engine owns parsing, canonical AST shape, context policy, dependency analysis, and the node-level meaning of read-only probe-call expressions;
- runtime probe providers own the actual external observation work needed to satisfy a read-only probe call;
- expression evaluation may therefore request a read-only observation through an engine-facing probe-observation interface without thereby becoming an effectful action surface.

Implications:

- a probe call is still one canonical local-expression node, not a second expression language hidden beside the main engine;
- probe-call caching, diagnostics, and trace behavior belong to the canonical execution model even when the observed value comes from a provider surface;
- contexts that forbid non-effectful external observation must reject probe-call nodes through normal context policy rather than through ad hoc runtime split behavior.
- when a read-only probe observation fails, the surrounding expression evaluation should fail rather than silently degrading to a partial value.

### Expression versus value adaptation

Representation adapters belong to local-expression value derivation rather than to connector execution.

Implications:

- adapter operations may interpret, navigate, select, normalize, and transform already available values;
- adapter operations may return derived values or addressable focus values for further pure local use;
- adapter-specific middle syntax may vary freely across adapters so long as the overall local-expression contract stays reviewable and non-effectful;
- a terminal adapter mutation should end the adapter chain and return an updated root value for the represented document or value;
- adapter update-style operations must still return new derived values rather than persisting changes by themselves;
- any persistence of such derived values happens only when a workflow step passes the resulting value into an effectful operation.

Implication for guard context:

- read-only adapter projections may participate in guard evaluation when the context policy allows them;
- adapter write paths such as `->...` remain incompatible with guard semantics even though they belong to the same product-defined expression family.

### Expression versus workflow control

Local expressions may derive values and conditions.

They must not silently absorb broader workflow control semantics such as branching structure, looping, or hidden execution planning.

### Expression versus user-defined extensibility

Representation-adapter operations must belong to the stable product contract.

Workflows must not define their own expression functions, operators, macros, or adapter families.

Workflow-level `let` therefore remains a product-defined authoring surface for naming ordinary expressions rather than a workflow-defined extensibility mechanism.

### Expression versus storage ownership

`state...` is a read surface inside local expressions when the surrounding context allows it.

That does not make local expressions the semantic owner of runtime state.

### Expression versus execution-local data

`step...` is execution-local.

It may appear only in contexts whose semantics legitimately depend on prior step execution.

It must not be treated as a universally available root across all expression contexts.

In particular, pre-execution policy context must not depend on execution-local `step...` data.

## Tree-wide context discipline

Context restrictions apply to the whole local-expression tree, not only to the root term.

An expression context therefore cannot regain a forbidden dependency class merely by nesting it inside a call argument, list item, comparison, or other subexpression.

## Review standard

A good local-expression surface should let a reader tell:

- what local data is being read;
- whether the expression is producing a value or a condition;
- whether the context is pre-execution, step-local, fragment-local, or caller-local;
- whether a dependency is global, fragment-local, state-backed, or execution-local.

If these distinctions are hard to recover, expression semantics are drifting out of the documented product surface.

## Related domain docs

- workflow semantics: `domain/workflow.md`
- policy semantics: `domain/policy.md`
- authoring semantics: `domain/authoring.md`

<!-- source: domain/playbook.md -->

# Playbook domain

## Role of the playbook

The playbook answers the question:

> which workflows are available in this project, under which names, with which project-local launch context.

It must not answer the question:

> what business steps a workflow performs internally.

Playbook files hold project-local launch intent and resolution context.
They may select, name, and parameterize workflows through explicit catalogs, defaults, and state bindings,
but they must not absorb workflow business-step logic.

## What a playbook owns

- project-local workflow catalog;
- named profile catalog for playbook-run profile selection;
- named runtime state declarations shared across project workflows;
- bindings from workflow-level logical state roles to concrete project state declarations;
- explicit execution working directory defaults and overrides for project-local launch context;
- explicit project-local pre-run workflow orchestration before the requested workflow executes;
- explicit playbook-owned dependency bindings for that pre-run launch phase;
- activation-time derivation of any selected execution working directory from launch-known inputs only;
- deterministic discovery of the project orchestration root;
- deterministic resolution of project-local workflow and profile references.

## What a playbook does not own

- connector semantics;
- workflow step semantics;
- runtime mode semantics such as `check`, `plan`, `execute`, or `explain`;
- hidden shell-first execution logic.

## Relationship to adjacent domains

- A workflow defines guarded operational intent.
- A profile defines reusable parameters, explicit overrides, and profile-scoped execution context.
- A playbook defines the project-local launch surface that selects one active profile per run and binds names to workflows, profiles, state declarations, logical state-role bindings, pre-run workflow orchestration, and other explicit execution context such as working-directory defaults and overrides.
- Runtime still owns mode behavior and execution semantics after playbook discovery and resolution complete.

## Quality bar

A good playbook:

- can be discovered predictably by both humans and agents;
- gives stable names to common project operations;
- keeps project-local launch concerns out of generic workflow logic;
- keeps pre-run launch dependencies in the playbook layer rather than leaking them into unrelated workflow state contracts;
- makes workflow, profile, and state resolution explicit enough for review;
- fails early when catalog entries are missing, ambiguous, or structurally invalid.

## Boundary rule

A playbook is not a workflow.

It is a project-level composition and launch document.
It may select, name, and parameterize workflows through explicit catalogs and defaults,
but it must not absorb the inner business-step logic that belongs in workflow files.

<!-- source: domain/workflow.md -->

# Workflow domain

## Role of the workflow

The workflow answers the question:

> what to check, in what order, and which public operations to call.

It must not answer the question:

> how a transformation or integration algorithm is implemented internally.

Workflow files hold orchestration intent.
They may sequence checks, guards, steps, and explicit local composition surfaces,
but they are not the place where non-trivial transformation algorithms should be implemented.

## What is acceptable in a workflow

- ordered guard and step blocks;
- reusable included workflow fragments through assembly instructions;
- future invocation-oriented reusable fragment runs when static composition is insufficient;
- guard lists inside `guards` blocks;
- ordered steps inside `steps` blocks;
- compact references and parameters that remain workflow-semantic;
- logical state needs that express workflow-owned state roles without naming project storage instances;
- compact parameters;
- workflow-local named expressions through a top-level `let` surface when they keep policy and dataflow reviewable;
- simple step-level conditional execution when it has clear semantics.
- simple branching when it has clear semantics.
- explicit authored workflow-local returns through `result` steps.
- explicit authored global publication through `publish` steps.
- optional author-provided invocation hints on input declarations.
- future bounded fan-out on `run` when it remains one workflow-composition surface rather than a general looping language.

Project-local launch context such as named workflow catalog, named profile catalog, and runtime state declarations belongs to the playbook contract rather than to the workflow domain itself.

## Assembly vs execution

An assembly instruction is a source-level workflow construct that shapes workflow assembly rather than surviving as a block kind in the assembled execution model.

`include` is the initial assembly instruction for static workflow composition.

The stable assembled execution shape is an ordered `blocks` list.
Each execution block declares exactly one of:

- `guards`
- `steps`

Top-level `guards` and `steps` may remain as compatibility-only authoring sugar when they normalize to the same block structure.

Top-level `let` belongs to workflow source authoring as a local-expression naming surface, but it does not become an execution block kind.

Assembly instructions may appear in source workflow material, but they do not survive as execution-semantic block kinds in the assembled workflow shape.

Assembly may still carry caller-scoped bindings into expanded material. That does not make the assembly instruction itself part of the assembled block model.

Named launch-time profile selection and project-local state declaration belong to playbook context rather than to generic workflow shape.

Included fragment reuse still belongs to the workflow domain when it remains declarative and workflow-semantic.

`include` specifically belongs to the static-composition side of that workflow reuse story.

If reusable fragments later need caller-scoped runtime modifiers or other invocation semantics, that pressure should be handled by a separate invocation surface such as `run` rather than by widening `include` until it stops being static composition.

That future distinction is acceptable inside the workflow domain because it separates two different jobs:

- `include` for static composition;
- `run` for runtime-scoped reusable-fragment invocation.

## Inclusion boundaries

Included fragments may declare local argument contracts.

Within an assembled workflow:

- `inputs...` remains global workflow input surface;
- `state...` remains global workflow state surface;
- `args...` is local to the included fragment instance that declared it;
- `step...` remains execution-local and must not cross included-fragment boundaries unless a later explicit export model is introduced.

## Public input contract

The public activation-input contract must stay readable from the root workflow.

- All user-facing activation inputs must be declared in the root workflow `inputs` contract.
- Any `inputs.<name>` reference that appears anywhere in the assembled workflow must refer only to a root-declared workflow input.
- Included fragments and reusable run targets may consume local `args...`, but they must not widen the public activation-input surface implicitly.
- Input-level `hint` text may help humans and agents choose values, but it remains guidance rather than a validation constraint.
- If later authoring surfaces add explicit presence-check helpers, they should stay narrowly scoped to lookup-style references and read-only representation-adapter invocations whose missingness semantics are contractually meaningful.

## What is undesirable

- large embedded shell fragments;
- complex text transformations;
- project-specific knowledge baked into a generic workflow;
- hidden side effects.
- algorithmic transformation logic that belongs in connector operation code.
- lexical nested fan-out surfaces that turn one workflow file into a control-flow mini-language.

## Workflow quality

A good workflow:
- can be read quickly from top to bottom;
- can be explained in `plan` and `explain`;
- can be validated before execution;
- can show where one guard barrier ends and the next step sequence begins;
- can be moved across projects while preserving contracts.
- can be authored and iteratively repaired by a sufficiently capable agent using contract docs, examples, and structured diagnostics.

## Workflow-local returns and global publication

Workflow-owned local return values and workflow-authored global publication both belong to the workflow domain, but they serve different scopes.

- `result` is the workflow-owned step form for authored workflow-local return values.
- Each executed `result` step appends one authored value to the current workflow run's local `results` list.
- `publish` is the workflow-owned step form for authored global publication.
- Each executed `publish` step appends one authored value to the enclosing run session's global `published` list.
- Registering one `run` step should expose the just-completed workflow-local `results` list rather than the global `published` stream.
- Authored `result` and `publish` values are stored as authored values only, without added runtime metadata.

## Planned bounded fan-out on `run`

If the product later adds `for_each` on `run`, it should remain a bounded workflow-composition surface rather than a general looping language.

- The source should be one array-valued expression.
- The step-level `if` condition should still govern the whole step rather than acting as a per-item filter.
- Lexical nesting of `for_each` inside another `for_each` in the same authoring surface should stay invalid.
- Composition through ordinary nested `run` remains acceptable because it preserves workflow boundaries instead of widening one authoring surface into nested loop syntax.

<!-- source: domain/runtime.md -->

# Runtime domain

## Baseline modes

Baseline modes are distinct runtime questions, not necessarily wholly separate evaluation pipelines.
They may share observations, diagnostics, and blocked-state facts, but they differ in primary intent.

Detailed `check` rules live in `meta/model/runtime/check-semantics.md`.
The shared internal analysis-tree model lives in `meta/model/runtime/analysis-tree.md`.

### `review`

Answers whether the authored workflow is structurally strong and explicit enough for humans and agents.

It may report authoring findings such as missing validation, delegated applicability, or weak preflight-support evidence, while staying non-effectful.

For input-related findings, `review` should distinguish between inputs that drive control/effect semantics, trusted profile-provided consumed context, profile-carried ambient surplus, and declared-but-unused inputs rather than treating every declared input as equal validation debt.

Profile-provided consumed context is still meaningful workflow input, but it is not automatically user-driven validation debt.
When a workflow consumes a value such as `repository` from the selected profile as trusted execution context, `review` should not require the workflow to re-validate that context in early guards unless the value also acts as an explicit control-bearing choice.

Its primary value is authoring-quality review rather than executability truth.

Statically knowable expression mistakes should ideally surface here or in adjacent validation surfaces before `execute` is needed.
For example, a builtin `format` expression whose placeholder count cannot match its argument count is an authoring-time problem, not merely a runtime surprise.

### `check`

Answers whether execution may proceed safely.

It evaluates guard blocks and static prerequisites.
It must not execute effectful business steps.

Its primary value is a safe preflight verdict:
- whether execution is allowed or blocked;
- which guards or prerequisites failed;
- which immediate blockers must be resolved first.

That verdict must remain honest about coverage and incompleteness as defined in `meta/model/runtime/check-semantics.md`.

### `plan`

Answers what execution shape is expected.

It builds an explainable plan that shows:
- what will be checked block by block;
- which step blocks are expected to become executable;
- which steps are expected in each step block;
- where execution is blocked.

Its primary value is execution preview, not merely blocked-versus-allowed status.

### `execute`

Executes the workflow.

Connector-declared operation kind remains semantically relevant in step context.
A step that references a probe operation is still a read-only probe step and must be dispatched through probe-capable execution semantics rather than through action-only fallback behavior.
Correct probe-step dispatch must not depend on whether execution-tree output is present.

### `explain`

Answers why the runtime reached its current decision.

It returns an explanation of the current runtime decision state, not only of completed execution:
- why execution is blocked or allowed;
- why a guard block failed;
- why a particular guard, step block, or step is relevant to the current outcome;
- which playbook-run profile is active;
- whether that profile came from explicit caller choice or playbook defaults;
- which overrides are active;
- which next action a human or agent can take when that can be inferred safely.

`explain` is a reasoning surface, not merely a verbose restatement of `check` or `plan`.

## Why this matters

For agent-authored workflows, `execute` alone is not enough.

The runtime needs modes that:
- reduce risk;
- improve reviewability;
- provide machine-readable reasoning;
- support both coarse-grained and specific questions from humans and agents.

## Runtime ownership of mode semantics

The runtime owns `review`, `check`, `plan`, `execute`, `explain`, and future next-safe-action semantics.
Connector operations should not each reimplement those modes locally.

Runtime may derive these modes from a shared internal decision model.
The modes are distinct query intents over runtime decision state, not necessarily fully separate computation paths.

Instead, runtime should derive higher-level execution meaning from structured operation contracts and structured operation outcomes.

Implications:
- connector operations may provide local observations, effect summaries, diagnostics, and supplementary raw detail;
- runtime combines those local results with workflow block structure, guard evaluation, profiles, and policy to determine authoring findings, blocked state, plan shape, explanation, and next safe action;
- richer runtime modes should come from stronger structured operation surfaces rather than from pushing orchestration logic down into connector implementations.

## Shared analysis-tree boundary

Runtime should prefer one shared context-aware analysis tree rather than separate ad hoc pipelines for `review` and `check`.

That shared tree may preserve partial knowledge under missing inputs, safe read-only observations, structural halt boundaries, and advisory recommendation coverage.

`review` and `check` are sibling projections over that tree:
- `review` reads it for authoring-quality findings;
- `check` reads it for allowed/blocked/unknown runtime truth.

`plan`, `explain`, and `next` should later reuse retained evidence from the same tree rather than reconstructing it from weaker mode summaries.

## Connector dependency direction

The runtime core should be agnostic to the physical location of built-in connectors.

It should depend on:
- connector registry data for resolution;
- probe and action execution capabilities provided through explicit wiring.

It should not depend on a hardcoded connector package path as part of its core semantics.

The runtime is not the semantic owner of built-in connector families.
Built-in connectors should be treated as a public library layer that runtime resolves and executes,
not as private helper code whose public meaning may drift with runtime refactors.

## Composition layer

A composition layer such as CLI bootstrap, application bootstrap, or tests may choose which connector provider to install or pass explicitly.

This layer may:
- use the standard built-in connector provider;
- combine the built-in provider with local or project-specific connectors;
- run with no built-in connector provider at all.

## Activation context boundary

Profiles may carry broader ambient context than any single workflow consumes.

Activation should therefore distinguish between:
- workflow-relevant inputs that the workflow declares or actually consumes;
- surplus profile-carried context that remains available to the run environment but is not part of the workflow's effective input contract.

Profile-supplied surplus context is not, by itself, an activation error.
Workflows should not need to declare unused profile values merely to tolerate reusable profiles with wider context surfaces.
Because such surplus is expected rather than actionable, default `review` and `check` outputs should not promote ordinary profile surplus to user-facing diagnostics.
Surplus-context evidence may remain available internally or in future verbose/debug/explain-oriented surfaces.

This boundary does not erase explicit caller intent.
User-supplied unknown activation inputs remain distinct from profile surplus and should stay diagnosable as explicit caller mistakes or mismatches.

<!-- source: domain/policy.md -->

# Policy domain

## Guard

A guard is a precondition check evaluated as part of policy before a later effectful step block may run.

A guard is first-class and must not collapse into a hidden step convention.

Detailed runtime expectations for guard coverage, incompleteness, and preflight verdict honesty live in `meta/model/runtime/check-semantics.md`.

## Policy

Policy is the set of constraints that determines whether a workflow may proceed and under which conditions.

In Ordo, policy must be visible and reviewable in workflow and profile structure,
not buried in shell control flow.

## Explainability

`explain` must answer these questions:

- why execution is blocked or allowed;
- which guards passed or failed;
- which steps are executable, skipped, or blocked;
- which next action a human or agent can take.

This is stronger than logs, traces, or raw exception text.

## Outcome distinctions

Policy and runtime-facing policy surfaces must preserve the distinction between:

- blocked before execution;
- planned but not executed;
- executed and failed;
- executed and succeeded.

These are not interchangeable non-success narratives.
They carry different policy and explanation meaning.

<!-- source: adr/0004-guard-expressions-prefer-orthogonal-probes.md -->

# ADR 0004: guard expressions prefer orthogonal probes

## Context

Guard expressions exist so workflow policy can remain compact and visible in the declaration.

The current connector surface can drift toward specialized probe names that encode policy directly, for example by exposing many narrow predicates whose only purpose is to avoid writing a simple comparison in the workflow.

That drift weakens one of the main reasons guard expressions exist in the first place.

## Decision

Guard-expression design should prefer a minimal and orthogonal public probe surface.

Policy composition should primarily live in the workflow declaration through guard expressions rather than in a growing catalog of bespoke policy-encoded probe names.

Specialized policy-shaped probes are not the preferred long-term direction and should be avoided in favor of canonical fact probes plus guard composition.

## Consequences

- Public probe contracts should expose stable output fields suitable for documented guard-expression field access.
- New connector work should avoid adding specialized policy probes unless a strong public-contract reason exists.
- Drift between meta examples and connector naming should be resolved by moving toward more orthogonal probe contracts rather than by normalizing policy sprawl into the connector layer.

<!-- source: adr/0005-local-expressions-context-model.md -->

# ADR 0005: local expressions use one context-governed family

## Status

Accepted.

## Context

The project had drifted toward separate guard-expression and value-expression axes in both docs and runtime implementation.

That split obscured the intended semantic model:

- expressions are one workflow-owned local surface;
- different workflow fields impose different timing and dependency restrictions;
- those restrictions belong to expression contexts, not to unrelated per-surface languages.

## Decision

Treat local expressions as one product-owned family with explicit contexts.

The initial contexts are:

- guard context;
- step-condition context;
- embedded value context;
- include-binding context.

The initial roots are:

- `inputs...`;
- `args...`;
- `state...`;
- `step...`.

Context restrictions apply to the entire expression tree, not only to the root term.

### Guard context

Guard context is limited to dependencies known at launch time.

This means guard context may use:

- `inputs...`;
- fragment-local `args...` when present;
- `state...`;
- guard-safe pre-execution evaluation surfaces.

Guard context must not depend on `step...` anywhere in the expression tree.

### Step-condition context

Step-condition context may depend on whatever is available when the step condition is evaluated, including prior execution-local `step...` results.

### Include-binding context

Include-binding context evaluates caller-scoped bindings at the include boundary.

It may depend on whatever is available at the include site, including caller-local `step...` results.

The included fragment body does not thereby gain direct caller-local step scope; it receives only the already-bound values.

### Embedded value context

Embedded value context may depend on whatever is available at the point of value resolution.

It remains a pure local-expression surface and must not become effectful execution or hidden workflow control.

## Consequences

- documentation should be organized around `local-expressions` rather than separate guard-expression and value-expression domain axes;
- runtime implementation should converge toward a shared local-expression core with explicit context policy;
- syntax and authored-surface differences may remain, but they must not redefine the conceptual model into unrelated expression systems.

<!-- source: adr/0006-local-expressions-deprecation-plan.md -->

# ADR 0006: deprecate legacy local-expression authored surfaces through warnings first

## Status

Accepted.

## Context

The local-expressions migration established two preferred authored surfaces:

- native guard expressions instead of object-form guard `uses:` entries;
- bare step `if` conditions instead of embedded `if: ${...}`.

The runtime already accepts the preferred forms and emits compatibility warnings for the legacy forms.

The remaining open question was the retirement policy for those deprecated surfaces.

## Decision

The project will keep both legacy forms valid during the current v0 warning window.

The deprecated forms are:

- object-form guard `uses:` entries;
- embedded step `if: ${...}`.

During this warning window:

- validation warnings remain the primary deprecation signal;
- contract metadata and docs may describe the forms as deprecated compatibility surface;
- help and introspection do not need a separate dedicated warning screen beyond that contract metadata.

Removal, if it happens, must wait until a later workflow-contract revision after at least one sustained warning period in the current v0 line.

## Consequences

- workflow authors keep a stable migration window rather than facing an immediate breaking change;
- validation warnings are the canonical runtime signal for these deprecated forms;
- docs and contract metadata should continue to mark the preferred versus compatibility surfaces clearly;
- a future hard deprecation can be introduced only as an explicit follow-up contract change rather than as an incidental parser cleanup.

## Follow-up preparation

The concrete inventory and execution checklist for any future hard removal is tracked in:

- `gaps/local-expressions/hard-removal-prep.md`

<!-- source: model/local-expressions/core.md -->

# Local expression model

## Position

Local expressions form one workflow-owned expression system with multiple contexts.

The model distinguishes:

- the shared idea of local-expression evaluation;
- context-specific restrictions on roots and timing;
- product-defined value interpretation and transformation over already available values;
- authored surface forms used by different fields.

## Shared model elements

### Context

A context determines:

- whether the expression is value-oriented or condition-oriented;
- which local roots may appear;
- whether evaluation happens in pre-execution, step-local, caller-local, or fragment-local scope;
- whether the surface is native or embedded.

It should not imply a separate read-only execution engine for otherwise equivalent probe-capable expression nodes.

### Root

A root is one documented local reference family.

The initial modeled roots are `inputs...`, `args...`, `state...`, and `step...`.

### Non-effectful observation dependency

A non-effectful observation dependency is a product-defined read-only observation that a local expression may request without changing the world.

Read-only probe calls belong to this dependency class.
They are distinct from local roots, but they may participate in the same expression tree when the surrounding context permits them.

### Scope

Scope determines where a root is meaningful.

- `inputs...` is workflow-global.
- `args...` is fragment-local.
- `state...` is runtime-state-owned and context-gated.
- `step...` is execution-local and order-sensitive.

### Context family

A context family groups surfaces by semantic job.

- condition-oriented contexts produce admission or execution conditions;
- value-oriented contexts produce local derived values.

### Derived value

A derived value is a value produced from already available local-expression inputs or prior derived values.

Derived values may flow into later local-expression operations so long as the surrounding context permits the dependencies used to produce them.

### Workflow-local binding

A workflow-local binding is one authored `let` entry that gives a local expression a workflow-scoped name.

The modeled binding shape is:

- the binding name is workflow-local rather than global or inherited;
- the binding value is one ordinary local-expression tree rather than a text substitution;
- the binding is immutable for the duration of the workflow run;
- the binding may reference documented roots and other dependencies that are otherwise valid for the surrounding expression system;
- the binding may not reference another `let` binding;
- the binding does not create a new context and does not widen which dependencies are legal at one use site.

The modeled validation rule is that a `let` binding is accepted only where the equivalent inline expression would be accepted by the surrounding authored context.

### Presence check

A presence check is one product-defined boolean helper that asks whether one approved lookup-like argument is observably available without collapsing unrelated evaluation failures into boolean absence.

The narrow modeled argument classes are:

- lookup-style references whose missingness semantics are defined by the surrounding root contract;
- read-only representation-adapter invocations whose absence semantics are defined by adapter `not_found`.

For read-only adapter invocation arguments, the modeled interpretation is:

- successful invocation means present;
- adapter `not_found` means missing;
- any other adapter failure remains a real evaluation failure.

### Representation adapter

A representation adapter is a product-defined operation family for interpreting one already available value through a stable representation model.

Examples may include markdown-, html-, json-, or string-oriented operations.

An adapter operation may:

- navigate or select within a represented value;
- expose an addressable focus over part of that value for further pure local work;
- transform the represented value into a new derived value.

Such operations remain part of local value derivation rather than connector execution.

The modeled adapter shape is:

- concrete adapter families rely on one shared adapter invocation seam rather than ad hoc family-specific runtime entry points;
- adapter invocation starts one adapter-defined addressing or selection chain over an already available root value;
- the interior shape of that chain is adapter-specific rather than globally normalized;
- a terminal adapter mutation ends the chain and returns an updated root value for the represented structure.

### Canonical core

The canonical local-expression core is the shared non-effectful tree model that supports both condition-oriented and value-oriented contexts.

Its retained construct families should cover:

- literals and list values;
- local-root references and field navigation;
- read-only probe observations;
- boolean composition and comparison;
- pipelines and built-in calls;
- representation-adapter operations and their derived values.

Its excluded construct families should cover:

- effectful connector actions;
- runtime-state mutation semantics;
- hidden workflow-control structures;
- workflow-defined language extension.

### Pipeline filter

A pipeline filter is one product-defined operation applied to an already evaluated local-expression value.

The modeled pipeline shape is:

- the left side supplies one already evaluated input value;
- the filter name selects one product-defined filter contract;
- optional filter arguments are themselves local-expression values evaluated under the surrounding context policy;
- the filter result becomes the next pipeline value.

The modeled input discipline is intentionally broad:

- a pipeline input value may be any ordinary local-expression value such as a string, number, boolean, null, list, object, local-root lookup result, probe result, or prior derived value;
- individual filter contracts, rather than the pipeline surface itself, determine which input shapes are accepted.

The modeled filter families include:

- transforming filters such as `lower`, `trim`, and `slug`;
- boolean comparison filters such as `eq(...)` and `ne(...)`;
- boolean predicate filters such as `is_string`, `is_number`, `is_integer`, and `is_boolean`;
- boolean membership filters such as `in(container)`;
- boolean negation filters such as `not`.

The modeled predicate-filter semantics are:

- predicate filters consume one already evaluated input value;
- predicate filters return only boolean results;
- predicate filters do not implicitly coerce input values into another type before deciding the result.

The modeled membership-filter semantics are:

- `in(container)` consumes one already evaluated input value and one already evaluated container argument;
- the container argument must evaluate to a list value;
- membership is determined by strict element comparison without implicit coercion;
- a non-list container remains a filter misuse failure rather than a false result.

### Probe-observation execution contract

Canonical local-expression evaluation may require a read-only probe observation when the tree contains a probe-call node and the surrounding context permits such observation.

The intended execution contract is:

- canonical parsing and validation produce one tree model regardless of whether a node is satisfied from local roots or from read-only observation;
- canonical evaluation may delegate probe acquisition through a dedicated read-only observation interface;
- canonical evaluation remains the owner of node semantics, context gating, caching expectations, trace shape, and diagnostics emitted for probe-call execution.

The modeled execution expectation is that one evaluation session may cache repeated equivalent read-only observation requests and that a failed read-only observation fails the surrounding expression evaluation.

This keeps probe calls inside one local-expression engine while avoiding any claim that the engine itself performs effectful connector actions.

## Surface distinction

The model separates:

- the local-expression system itself;
- the authored surface form used in one field;
- the restrictions imposed by the surrounding context.

This means an interpolation envelope, a bare condition string, and a caller-side include binding may all belong to the same modeled local-expression system even when their authored syntax differs.

A workflow-level `let` surface therefore adds one more authored way to name local expressions without creating a second expression family or second execution engine.

## Control boundary

Local expressions may derive values and conditions.

They are not themselves the owner of:

- connector execution;
- effectful action semantics;
- hidden control-flow structure;
- runtime-state mutation semantics.

Any adapter-provided update semantics therefore describe pure value transformation only.
Persistence of a transformed value remains outside the local-expression system and belongs to workflow steps or other effectful runtime surfaces.

<!-- source: model/local-expressions/adapters.md -->

# Representation-adapter model

## Position

Representation adapters are modeled as one shared local-expression extension point with family-specific interior syntax and structure semantics.

The model therefore separates:

- the shared invocation and result discipline that lets adapter families participate consistently in local-expression evaluation;
- the family-specific path surface used inside one adapter family;
- the family-specific represented structure manipulated by that family.

## Shared modeled elements

### Adapter family

An adapter family is one product-defined representation-specific operation family such as `markdown`, `html`, `json`, or `string`.

It names the representation discipline through which one already available root value will be interpreted.

### Root value

An adapter root value is the already available value supplied to an adapter invocation.

The adapter does not own how that root value was obtained.
It only owns how that value is interpreted and transformed once supplied.

### Adapter invocation

An adapter invocation applies one adapter family to one root value through one adapter-defined path or action chain.

The shared modeled shape is:

- adapter family selection;
- root-value supply;
- adapter-defined interior navigation or selection;
- optional terminal mutation.

### Adapter-owned body

The model treats the interior body of an adapter invocation as adapter-owned.

That means:

- the shared seam identifies the adapter family and the extent of the adapter-owned body;
- the concrete adapter family owns parsing and interpretation of that interior body;
- the shared seam does not need one globally normalized grammar for family-specific search, navigation, or mutation syntax.

### Host-owned outer parameter binding

The model prefers host-owned parameter binding outside the adapter-owned body over host references embedded directly inside adapter-family grammar.

The model therefore separates:

- adapter-owned syntax and structure semantics inside the adapter body;
- host-owned value resolution for outer parameter bindings such as values derived from `inputs...`, `args...`, `state...`, `step...`, or read-only probes.

The intended modeled flow is:

- the shared seam identifies the adapter-owned body and any top-level trailing host binding suffix;
- canonical local-expression evaluation resolves the host-owned bindings under normal context policy;
- adapter evaluation receives the adapter-owned body plus resolved parameter values from the outer binding surface;
- adapter evaluation continues without taking ownership of host-root semantics.

The model prefers resolved parameter values from the outer binding surface over naive string substitution so host-owned values do not collapse prematurely into untyped text.

### Top-level trailing binding suffix

One workable modeled form is a top-level trailing host binding suffix such as ` with{...}` after the adapter-owned body.

In that form:

- the adapter-owned body remains family-specific;
- the trailing binding suffix remains host-owned;
- the shared seam only needs top-level lexical boundary detection rather than family-specific body parsing to separate the two.

### Cross-family value flow

The model permits ordinary composition across adapter families by value flow.

That means:

- one adapter invocation may yield a focus value or other derived value;
- that resulting value may become the root value of a later adapter invocation;
- the shared seam only needs to preserve value handoff, not family-specific knowledge of the next adapter's interior syntax.

This keeps cross-family composition as a normal consequence of value-producing adapter evaluation rather than as a special nested-adapter feature.

### Focus value

A focus value is the selected or derived value produced by a read invocation before any persistence semantics exist.

It may be:

- a scalar derived from the represented structure;
- a structured derived value;
- an addressable focus inside the represented structure suitable for further pure local evaluation.

### Terminal mutation

A terminal mutation is the final write operation in an adapter invocation.

It ends adapter navigation and produces an updated root value for the represented structure.

### Adapter outcome

An adapter outcome is the modeled result category returned by the shared adapter seam.

At minimum the model expects support for:

- successful selection or derivation;
- successful root update;
- `not_found`;
- `ambiguous`;
- `unsupported`;
- `invalid_path`;
- `invalid_action`;
- `invalid_root_value`.

The model also distinguishes host-side failures that occur while resolving the outer binding surface from adapter-side failures that occur after resolved parameter values have been supplied to the adapter family.

### Presence-oriented reuse of read invocation

The model allows one product-owned presence-check helper to reuse read-only adapter invocation as a special argument class without changing ordinary adapter outcome semantics.

In that reuse:

- successful read invocation is interpreted by the presence helper as present;
- adapter `not_found` is interpreted by the presence helper as missing;
- adapter outcomes other than `not_found` continue to fail evaluation;
- write invocation is outside the allowed presence-check argument class.

## Read-versus-write model

The model distinguishes two invocation kinds.

### Read invocation

A read invocation consumes a root value and yields a focus value or other derived value.

It does not create structure and does not update the root.

### Write invocation

A write invocation consumes a root value, applies one terminal mutation, and yields an updated root value.

It may auto-create missing structure only within the modeled write-path boundary.

## Auto-creation model

The modeled auto-creation rule is intentionally narrow:

- only write invocation may auto-create missing structure;
- each created step must be unambiguous;
- each created step must have a canonical family-defined shape;
- ambiguity blocks creation rather than being resolved implicitly.

## Boundary model

Representation adapters remain inside local-expression value derivation.

They are modeled as distinct from:

- connector execution;
- hidden I/O;
- persistence ownership;
- workflow control semantics.

## Modeling consequence

Because concrete families such as `markdown` require one shared invocation seam, the product model should not describe family-specific syntax without also modeling the shared adapter invocation boundary they rely on.

<!-- source: model/local-expressions/markdown.md -->

# Markdown representation-adapter model

## Position

The `markdown` adapter family models one text-oriented representation surface over a markdown root string.

It keeps authored selection and action syntax family-specific while relying on the shared representation-adapter seam for outer ` with{...}` binding, read-versus-write distinction, and shared outcome categories.

## Core modeled targets

### Document

The markdown root value is one whole markdown document string.

### Prelude

The markdown prelude is the portion of the document that appears before the first heading.

Prelude is modeled as always present.
If the document starts with a heading, prelude still exists as the empty leading markdown slice rather than as `not_found`.

### Section

A markdown section is one heading plus the markdown text governed by that heading.

Selecting a section does not require the adapter family to collapse the selection immediately to only the section body.
Further selector steps or terminal action semantics may refine how the selected section text is used.

### Block-oriented targets

The family may expose block-oriented targets such as paragraphs and lists inside a section or prelude scope.

After one singular list or task-list block has been selected, the model may allow positional indexing to address one top-level list item within that selected block.

The family may also expose a separate collection-view projection for list-like blocks, for example `.list_items` or `.task_list_items`, when the product wants an array-valued view distinct from the richer block object.

## Text-action model

The markdown family should prefer a small orthogonal text-action surface over many special-case action verbs.

The primary modeled actions are:

- `append(text, prefix="")`;
- `replace(text)`;
- `remove()`.

Those actions consume plain text arguments rather than structured object payloads.

The adapter family may interpret the selected markdown target to decide where the resulting text is inserted or replaced, but it does not need a public object-shaped fragment argument model.

## List mutation model

Because nested lists make generic append semantics ambiguous at the list level, list targets may expose one list-specific action such as `add(text)`.

`add(text)` models adding one new list item at the current list level rather than performing a generic text splice into an arbitrary list location.

## Argument discipline

Markdown action arguments are modeled as plain text.

The family should not require object-valued public action payloads merely to support large or structurally rich markdown text.

The family may still use its own internal parsing or normalization as an implementation detail when editing the root markdown string, but that does not change the modeled public action argument shape.

<!-- source: model/local-expressions/text.md -->

# Text representation-adapter model

## Position

The `text` adapter family models one plain-text representation surface over a string root value.

It keeps authored selection and action syntax family-specific while relying on the shared representation-adapter seam for outer ` with{...}` binding, read-versus-write distinction, and shared outcome categories.

## Core modeled targets

### Root text

The text root value is one whole plain-text string.

### Text scope

A text scope is one singular text slice that may serve as the current surface for further narrowing, searching, projection, or terminal mutation.

The root text is a text scope.
Derived singular text slices such as the result of `before("...")`, `after("...")`, or a singular substring match are also text scopes.

### Line collection

The family may project one text scope into an ordered collection of line focuses through `.lines`.

The line collection is modeled as a collection view rather than as a second root.
It exists so authored expressions can inspect or mutate line-oriented targets without claiming richer document semantics such as paragraphs or sections.

### Line focus

One indexed line selected from a line collection is a singular text scope.

That means a selected line may participate in further singular text operations such as search, narrowing, or terminal mutation.

### Match collection

The family may project one text scope into an ordered collection of literal substring matches through `.finds("...")`.

The match collection models zero or more non-overlapping matches in source order.

### Match focus

The family may expose one singular substring match either directly through `.find("...")` or by indexing into a match collection.

A singular match focus is a text scope.
That means search narrowing may continue after one singular match has been selected.

## Anchor narrowing model

The family may expose singular anchor-narrowing selectors such as `before("...")` and `after("...")`.

Those selectors consume one singular text scope and yield one further singular text scope bounded around one unique literal anchor occurrence.

## Collection boundary model

Collections remain ordered views over multiple focuses.

The model permits:

- indexing into a collection to recover one singular focus;
- terminal bulk mutation over a collection when the targeted members are ordered and non-overlapping.

The model does not require collection-valued focuses to support further narrowing or search selectors directly.

## Search model

The text family models literal substring search rather than token-aware search, regex search, or rich linguistic structure.

That means authored literals match ordinary substring occurrences even when they appear inside larger words or tokens.

## Text-action model

The family may expose a small text-action surface over singular focuses and selected collection views.

The primary modeled actions are:

- `append(text)`;
- `replace(text)`;
- `remove()`.

Those actions consume plain text arguments rather than structured payloads.

## Empty-line projection model

Projecting `.lines` from the empty string yields an empty collection.

The family therefore treats empty text as having zero projected line focuses rather than one synthetic empty line focus.

<!-- source: model/local-expressions/contexts.md -->

# Local expression contexts

## Embedded value context

Embedded value context models one derived value inside a larger value-bearing field.

Typical surfaces include step inputs, value-bearing workflow fields, include argument bindings, and other scalar positions that reuse local-expression evaluation.

It belongs to the value-oriented context family.

It may consume whatever roots are available at its resolution point, subject to higher-level purity and control-surface exclusions.

## Guard context

Guard context models pre-execution policy evaluation.

Its distinctive property is not a separate expression language, but a restricted dependency model:

- the expression must be meaningful from launch-time-known dependencies before effectful business steps run;
- execution-local `step...` dependencies are excluded;
- the result participates in execution admission rather than in post-step branching.

It belongs to the condition-oriented context family.

## Step-condition context

Step-condition context models conditional execution of one workflow step.

Unlike guard context, it may legitimately depend on prior execution-local registered results because it is evaluated after earlier steps may already have run.

It also belongs to the condition-oriented context family.

## Include-binding context

Include-binding context models caller-side argument preparation for included fragments.

The include site may evaluate caller-scoped local expressions before the expanded fragment body receives fragment-local `args...` bindings.

That caller-side evaluation does not make included fragment bodies owners of caller-local `step...` scope.

It belongs to the value-oriented context family.

It may consume whatever caller-scoped roots are available at the include site.

## Native and embedded authored forms

The model allows both:

- native expression contexts whose primary meaning is already conditional or predicate-oriented;
- embedded expression contexts whose expressions appear inside a broader value-bearing field.

This distinction is about authored surface, not about separate semantic languages.

## Tree-scoped restrictions

Context policy governs the whole parsed expression tree.

A context therefore validates dependency classes structurally rather than only checking the root node.

<!-- source: model/workflow/entities.md -->

# Workflow entities

## Main entities

- `Playbook`
- `Workflow`
- `WorkflowFragment`
- `FragmentArg`
- `FragmentRun` (planned)
- `StateNeed`
- `OperationRef`
- `Guard`
- `Step`
- `Profile`
- `Override`
- `Connector`
- `ConnectorBootstrap`
- `OperationContract`
- `ExecutionPlan`
- `OperationResult`
- `ExecutionResult`
- `Diagnostic`

## Key relations

- A `Playbook` names project-local workflow entries, profile entries, and runtime state declarations.
- A `Workflow` contains ordered `Guard` and `Step` entries.
- A `Workflow` may include reusable `WorkflowFragment` instances through ordered include items inside its block structure.
- A future `Workflow` surface may invoke reusable `WorkflowFragment` instances through ordered `run` step forms inside `steps` blocks.
- A `WorkflowFragment` may declare local `FragmentArg` entries and workflow payload content.
- A planned `FragmentRun` would express runtime-scoped invocation of one reusable `WorkflowFragment` with an explicit caller/callee boundary while still reading like one workflow step.
- A `Workflow` may declare logical `StateNeed` entries that are bound by the active playbook workflow entry.
- A `Guard` references an `OperationRef`.
- A `Step` is either an operation-call step that references an `OperationRef` or a built-in runtime step form.
- A `Step` may declare an `if` condition that controls whether that one declared step executes or is skipped.
- A `Step` may publish an execution-local registered result for later steps through a workflow-local `register` identifier.
- A `run` step may expose callee workflow-local `results` back to caller-local `step...` reads through that same `register` surface.
- A `Connector` groups operations and can own shared bootstrap/runtime prerequisites.
- A `Profile` supplies reusable parameters or composition defaults.
- An `Override` changes resolution explicitly, never silently.
- An `OperationContract` describes public inputs, outputs, effects, and failure modes.
- An `ExecutionPlan` describes checks, steps, and blockers without requiring effectful execution.
- An `OperationResult` captures structured connector-level outcome details.
- An `ExecutionResult` contains status plus diagnostics and outputs.

## Boundary reminder

- `Playbook` expresses project-local launch intent and resolution context.
- `Workflow`, `Guard`, and `Step` express orchestration intent.
- `StateNeed` expresses workflow-level need for persistent state without naming concrete project storage instances.
- Step conditions express per-step eligibility, not first-class branch topology.
- Built-in runtime step forms may be effectful, such as state mutation, or pure, such as value materialization.
- Registered step results express execution-local data flow, not persistent workflow state.
- Workflow-local `result` values and run-session-global `publish` values are distinct result channels with different scopes.
- Fragment arguments express local reusable-fragment binding, not global workflow input redefinition.
- Included-fragment boundaries keep registered `step...` data local unless a later explicit export surface is introduced.
- A future fragment-run boundary should keep caller-local `step...` data explicit at the call site rather than treating it as implicit fragment-body scope.
- They do not own connector implementation algorithms.
- `Profile` and `Override` express composition and explicit local adaptation.
- `Diagnostic` and execution/result entities carry machine-usable analysis and runtime surfaces.

<!-- source: model/playbook/shape.md -->

# Playbook model shape

## Position

The playbook is the project-local orchestration root.

Canonical path in the initial model:

```text
.ordo/ordo.yaml
```

## Minimal shape

```yaml
version: 1

pre_run:
  - file: workflows/resolve-context.yml
    state_bindings:
      shared_context: repo_task_state

states:
  repo_task_state:
    path: .ordo/state/task-state.json

defaults:
  profile: backend-default
  working_directory: repos/default-backend

workflows:
  inspect-issue:
    file: inspect-issue.yml

  close-task:
    file: close-task.yml
    working_directory: ${inputs.repo_root}
    state_bindings:
      task_memory: repo_task_state

profiles:
  backend-default:
    file: backend-default.yml
```

## Stable top-level concepts

- `version` — playbook contract version;
- `states` — named project-local runtime state declarations;
- `workflows` — named launchable workflow entries;
- `profiles` — named launchable profile entries;
- `pre_run` — optional project-local launch-phase workflow set that executes before the requested workflow;
- `defaults` — optional playbook-run defaults such as the active profile.

## Pre-run role

`pre_run` is an optional ordered set of playbook-owned launch-phase entries.

Each entry declares the workflow `file` to execute in the same runtime session before the requested workflow begins its own effectful execution.

Each entry may also declare launch-phase-only bindings such as `state_bindings` that belong to the playbook wrapper rather than to the requested workflow contract.

The initial model treats `pre_run` as playbook-owned orchestration for shared preparation such as context resolution, environment checks, or runtime-profile switching.

That means the requested workflow does not need to declare logical state needs that are consumed only by `pre_run`.

## Workflow entry role

A workflow entry gives a stable project-local name to a workflow file.

It may additionally declare:

- state bindings from workflow logical roles to concrete playbook state entries;
- an explicit execution `working_directory` for runs of that workflow entry, expressed either as a literal path string or as an activation-time-safe `${...}` embedded-value local expression;
- future launch metadata that remains project-local rather than workflow-semantic.

## Defaults role

Playbook defaults apply to one playbook run.

The initial important defaults are:

- `defaults.profile` — the default active profile for the run when the caller does not select one explicitly.
- `defaults.working_directory` — the default execution working directory when neither the active profile nor the active workflow entry selects a more specific one.

## Profile entry role

A profile entry gives a stable project-local name to a profile file.

The profile file contributes runtime activation context for one playbook run.

That context may include:

- input bindings;
- approved overrides;
- a profile-scoped `working_directory` default, expressed either as a literal path string or as an activation-time-safe `${...}` embedded-value local expression;
- future runtime-facing execution selectors that remain declarative and reviewable.

Profiles do not create a second orchestration language.
They make project-local launch context explicit and reviewable.

## State entry role

A state entry gives a stable project-local name to a runtime-managed state location.

The initial standard field is:

- `path` — storage path or location identifier.

Future state metadata such as format, initialization policy, or backend kind may extend the state entry shape when runtime semantics standardize them.

## State binding role

A workflow entry may bind workflow logical state roles to concrete playbook state entries.

This keeps workflow authoring focused on logical state usage such as `task_memory`,
while the playbook owns the concrete project binding such as `repo_task_state`.

## Activation rule

The initial playbook model assumes one workflow per run.
The run selects one active profile, applies that profile, executes any declared `pre_run` workflows, and then activates one named workflow entry.
When execution working directory is declared at multiple playbook-owned launch surfaces, the more specific declaration wins in this order: playbook defaults, then active profile, then active workflow entry.

<!-- source: model/playbook/discovery.md -->

# Playbook discovery model

## Default discovery rule

When the caller does not provide an explicit playbook path, CLI should look for:

```text
.ordo/ordo.yaml
```

relative to the current working directory.

## Explicit playbook path

When the caller provides an explicit playbook path, that path becomes the discovery result and default discovery is skipped.

## Initial simplicity rule

The initial model should prefer a small and predictable discovery rule over aggressive filesystem search.

Implications:

- no silent fallback from `.ordo/ordo.yaml` to alternate filenames such as `playbook.yml` or `playbook.yaml`;
- no broad directory crawling as a hidden convenience mechanism;
- no dependence on shell aliases or external wrappers for the canonical discovery rule.

## Failure rule

If default discovery does not find `.ordo/ordo.yaml`, runtime should return a structured missing-playbook outcome rather than guessing a workflow file.

## Future extensions

Possible future behaviors such as parent-directory search or alternate filenames should remain explicit additions to the model rather than being assumed by convention.

<!-- source: model/playbook/resolution.md -->

# Playbook resolution model

## Resolution base

Resolution starts from the directory that contains the discovered playbook file.

For the canonical default path:

```text
<project>/.ordo/ordo.yaml
```

the resolution base is:

```text
<project>/.ordo/
```

## Named workflow resolution

When CLI is asked to run a named workflow entry such as `close-task`, it resolves that name through `workflows.<name>` in the playbook.

The entry must resolve to exactly one workflow file.

## Pre-run workflow resolution

- `pre_run` is an optional ordered list of playbook-owned launch-phase entries declared directly on the playbook.
- Each `pre_run` item must declare its workflow `file` explicitly.
- Each `pre_run` item resolves its `file` with the same workflow-path rules as a named workflow file reference.
- Each `pre_run` item may declare launch-phase `state_bindings` that apply only while that `pre_run` workflow is being evaluated.
- `pre_run` workflows execute in declaration order before the requested workflow performs its own effectful execution.
- `pre_run` workflows run in the same runtime session as the requested workflow.
- Runtime context changes produced by `pre_run` workflows may affect later `pre_run` items and the requested workflow.
- Failure in a `pre_run` workflow prevents effectful execution of the requested workflow.
- `pre_run` state dependencies must not require the requested workflow to widen its own declared logical state contract.

## Workflow file resolution

- A bare workflow filename such as `close-task.yml` resolves under `<playbook-dir>/workflows/`.
- A relative workflow path containing directory segments resolves relative to `<playbook-dir>/`.
- An absolute workflow path remains absolute.

## Profile reference resolution

- A bare named profile reference such as `backend-default` resolves through `profiles.<name>` in the playbook.
- A bare profile filename such as `backend-default.yml` resolves under `<playbook-dir>/profiles/`.
- A relative profile path containing directory segments resolves relative to `<playbook-dir>/`.
- An absolute profile path remains absolute.

## Active profile resolution

- Each playbook run selects at most one active profile.
- If the caller specifies a profile explicitly, that selection wins.
- Otherwise `defaults.profile` becomes the active profile when present.
- If no explicit profile and no default profile are present, the run proceeds without a profile.
- Active profile resolution happens before workflow activation and step execution.
- The profile selected by activation is the starting profile for any `pre_run` workflows and for the requested workflow.

## Execution working directory

- Playbook `defaults.working_directory`, active-profile `working_directory`, and workflow-entry `working_directory` are the three explicit declaration surfaces for execution working directory.
- When more than one declaration is present, the resolved working directory follows increasing specificity in this order: playbook defaults, then active profile, then active workflow entry.
- Each `working_directory` value may be either a literal path string or a `${...}` embedded-value local expression that resolves to a path string.
- A `working_directory` expression reuses the existing embedded-value local-expression surface but with a narrower activation-time subset.
- The activation-time surface may read only launch-known input values.
- The activation-time surface must not read `state...`, `step...`, or any other runtime-derived value.
- The activation-time surface must resolve fully before the first guard or step executes.
- After expression evaluation, a relative `working_directory` path resolves relative to `<playbook-dir>/`, regardless of whether it originated from playbook defaults, the active profile, or the workflow entry.
- After expression evaluation, an absolute `working_directory` path remains absolute.
- When present, runtime executes the workflow with that resolved working directory as the execution working directory.
- Runtime may restore its prior process working directory after the run completes, but that restoration behavior must not be part of workflow semantics.
- `working_directory` changes execution context only; it must not change playbook discovery, workflow/profile reference resolution, or state-path resolution.

## Launch-time input overrides

- A playbook run may accept explicit launch-time input overrides from the caller.
- Launch-time input overrides apply to the selected workflow run only.
- Launch-time input overrides take precedence over workflow-declared input defaults.
- Launch-time input overrides also take precedence over profile-provided missing-input defaults.
- A launch-time input override may be provided either inline or from a file-backed raw string value.
- Launch-time input overrides do not mutate the playbook, workflow source file, or profile source file.

## State resolution

- Playbook state names resolve through `states.<name>`.
- A relative state `path` resolves relative to `<playbook-dir>/`.
- An absolute state `path` remains absolute.

## Workflow state binding resolution

- Workflow state reads and writes address logical roles through `state.<role>...`.
- The active workflow entry resolves those logical roles through `state_bindings.<role>`.
- Each bound value must resolve to one declared playbook state entry.
- Every workflow-declared logical state role must resolve through `state_bindings.<role>`.
- Missing state bindings fail before effectful workflow execution begins.
- Extra state bindings that do not correspond to declared workflow logical state roles fail validation.

## Resolution discipline

- Resolution must be deterministic.
- Ambiguous implicit matches are not allowed.
- Playbook resolution must complete before effectful workflow execution begins.

<!-- source: model/runtime/lifecycle.md -->

# Workflow lifecycle

## Minimal lifecycle

1. Parse
2. Validate
3. Resolve connector operations
4. Evaluate guards
5. Build plan / explain
6. Execute steps
7. Emit structured result

## Blocking states

- validation failed
- resolution failed
- guard failed
- execution failed

See `meta/model/runtime/check-semantics.md` for the normative rules that govern incomplete pre-execution verdicts and `pre_run`-related check behavior.

## Execution-tree mutation contract

The shared execution tree is the canonical runtime artifact once execute mode runs with tree assistance.

Required node-level runtime fields include at least:

- `runtime_status`;
- `revalidated`;
- `planned_observation`;
- `runtime_observation`;
- `divergence_status`;
- `divergence_reason`.

Execute mode may mutate only the execute-time fields that represent runtime progress, revalidation, reuse, and divergence.
Plan-time structural fields such as node identity, topology, and declared semantics remain stable.

When execute mode cannot use the shared tree safely, it must expose an explicit compatibility mode and fallback reason rather than silently pretending tree-driven execution happened.

## Planned fan-out node contract

If the product later adds bounded `for_each` on `run`, the shared tree should preserve that declared fan-out as one step-level structural node rather than flattening it into invisible repeated execution.

The tree-facing model should retain at least:

- that the node is one fan-out `run` step;
- whether the whole step condition made the fan-out eligible, skipped, or still unknown;
- whether the source cardinality was statically known, statically zero, or runtime-only;
- the exact item count when statically known;
- the declared failure policy for repeated execution;
- whether caller-side `register` expects one aggregated array of per-run workflow-local result payloads.

The runtime should preserve the difference between:

- fan-out blocked before expansion;
- fan-out skipped as a whole step;
- fan-out expanded with known count;
- fan-out retained as runtime-only cardinality.

<!-- source: model/runtime/check-semantics.md -->

# Check mode semantics

## Role

`check` is the runtime's pre-execution verdict surface over currently available knowledge.
It exists to answer whether execution may proceed safely without executing effectful business steps.

`check` may share its underlying analysis basis with other mode projections such as `review`, but its published verdict must remain a runtime-executability answer rather than an authoring-quality score.

## CHECK-MODE-001 — Pre-execution verdict over currently available knowledge

`check` must report its verdict only over knowledge that is available before effectful step execution in the current run.

Why this matters:
- this keeps `check` honest about what it actually knows now rather than what later execution might reveal;
- this preserves the difference between preflight decision support and post-execution explanation;
- this prevents a false impression that `check` has already established facts that only later step outcomes could establish.

## CHECK-MODE-002 — No effectful business step execution

`check` must not execute effectful business steps in order to improve or complete its verdict.

Why this matters:
- a preflight mode that performs business effects is not safe to use routinely;
- users and agents must be able to call `check` without risk of hidden operational change;
- this keeps the semantic boundary between `check` and `execute` reviewable.

## CHECK-MODE-003 — Workflow order remains semantically binding

`check` must preserve the ordered workflow block structure in its decision model even when it evaluates many guards from one pre-execution world snapshot.

Why this matters:
- the workflow contract answers what to check and in what order;
- guard barriers must remain attributable to the later step sequences they protect;
- `plan` and `explain` depend on a decision model that still reflects block boundaries rather than only a flat verdict list.

## CHECK-MODE-004 — Relevant guard coverage is part of the contract

`check` must distinguish between guards that were relevant and actually evaluated, guards that were relevant but not yet evaluable, and guards that were outside the currently supported pre-execution decision surface.

Why this matters:
- a verdict is not trustworthy when runtime cannot say which relevant guards it actually covered;
- this gives both humans and agents a way to tell the difference between a clean preflight and a partial one;
- this prevents silent loss of policy coverage when workflow structure evolves.

## CHECK-MODE-005 — No observed blocker is not the same as execution allowed

`check` must not treat the absence of observed blockers as equivalent to an allowed verdict when relevant guard coverage is incomplete.

Why this matters:
- missing evidence is not positive evidence;
- otherwise runtime can report `allowed` simply because it never reached or evaluated the real blocking conditions;
- this is the core protection against falsely optimistic preflight results.

## CHECK-MODE-006 — Incomplete analysis must be representable explicitly

`check` must be able to report an incomplete or unknown verdict when it cannot honestly establish either allowed or blocked from currently available knowledge.

Why this matters:
- some workflows cannot be fully decided before later step outcomes exist;
- runtime needs a truthful middle state between clean approval and explicit refusal;
- downstream `plan`, `explain`, and agent logic need a stable way to handle partial preflight knowledge.

## CHECK-MODE-007 — Pre-execution guard evaluation may be aggressive within safe bounds

`check` may evaluate any guard whose truth value is determined by the current pre-execution world snapshot, workflow inputs, runtime state, profile context, overrides, and read-only probe observations, so long as no effectful business step execution is required.

Why this matters:
- this allows `check` to provide stronger safety value than a minimal first-block-only preflight;
- many workflows benefit from broad early blocker discovery even when later guarded steps are not yet executable;
- this keeps the mode useful without collapsing it into simulation or effectful dry-run behavior.

## CHECK-MODE-008 — Later step outcomes must not be smuggled into preflight truth

`check` must not claim to know the truth value of a guard when that truth depends on effectful step outcomes or step-local data that do not exist yet in the current pre-execution state.

Why this matters:
- this keeps `check` from pretending that future execution results are already available;
- this protects the boundary between policy evaluation and control flow that depends on step outcomes;
- this prevents fake completeness produced by hidden simulation assumptions.

## CHECK-MODE-009 — `pre_run` semantics must be explicit in the verdict model

When playbook-owned `pre_run` orchestration affects what `check` can know about the main workflow, runtime must represent that effect explicitly rather than silently treating the main workflow as already cleared.

Why this matters:
- playbook orchestration changes the reachable pre-execution decision surface;
- without an explicit rule here, runtime can report optimistic verdicts before main-workflow guards were actually covered;
- `plan` and `explain` need a stable basis for describing whether preflight knowledge is still partial because of `pre_run`.

## CHECK-MODE-010 — Downstream modes inherit check honesty, not just check data

Any richer mode that derives from `check` must preserve `check`'s distinction between allowed, blocked, and incomplete knowledge rather than upgrading incomplete preflight results into confident approval.

Why this matters:
- `plan` and `explain` become misleading if they narrate certainty on top of an incomplete verdict;
- users and agents should be able to trust that richer reasoning surfaces do not silently erase uncertainty;
- this keeps the shared internal decision model coherent across baseline modes.

## CHECK-MODE-011 — Observation invalidation must default conservatively

When runtime tracks action-driven invalidation of probe-derived observations during `check`, missing narrow invalidation metadata for an effectful connector action must not strengthen the verdict basis; runtime should conservatively fall back to the full observation namespace of that connector family.

Why this matters:
- `check` needs a safe default when action contracts do not yet publish precise invalidation detail;
- a missing annotation should reduce precision rather than create false stability claims;
- this allows incremental adoption of invalidation metadata without weakening preflight honesty.

## CHECK-MODE-012 — Step-derived read-only knowledge may strengthen preflight analysis

`check` may use step-derived read-only knowledge when that knowledge is produced through the runtime-owned preflight step interpreter defined in `meta/model/runtime/preflight-step-interpreter.md`.
Such interpretation must remain non-effectful, ordered, conservative, and explicit about halt reasons.

Why this matters:
- relevant read-only observations may live behind step flow rather than direct guard probes;
- runtime should be able to strengthen guard coverage without turning `check` into hidden execution;
- a dedicated contract keeps richer preflight behavior reviewable.

## CHECK-MODE-013 — Advisory preflight-observation metadata may strengthen explainability without becoming a prerequisite

When an effectful action declares advisory preflight-observation templates, runtime may use them to evaluate how well the workflow's current pre-execution basis supports explanation of that step's applicability and expected effect.

Missing advisory observations must not by themselves make the workflow inapplicable.
They may weaken preflight-support quality, explanation strength, or authoring guidance, but they must not silently become hidden executability rules.

Why this matters:
- some actions remain semantically clear while still benefiting from richer preflight observation basis;
- runtime needs a way to distinguish execution validity from explanation strength;
- advisory templates allow connector families to help `check`, `plan`, and `explain` without moving workflow-policy logic into connector actions.

## CHECK-MODE-014 — Author-facing recommendations should preserve workflow expression shape when possible

When runtime renders a recommended preflight observation from action metadata, it should prefer the workflow expressions that currently supply the referenced action arguments rather than only the resolved runtime values.

Why this matters:
- author-facing recommendations are more useful when they resemble the workflow that must be edited;
- expression-shaped guidance remains stable across runs better than one-shot resolved values;
- this keeps long or awkward rendered expressions attributable to workflow authoring quality rather than pushing beautification burden into `check`.

## CHECK-MODE-015 — Recommended-observation matching must stay exact and structural

When runtime compares advisory preflight-observation templates against observations already established by the workflow, that comparison must remain deterministic and structural.

Covered means runtime can prove the same canonical probe reference, the same relevant field selection when applicable, and the same action-argument-relative workflow expressions after rendering.
Runtime must not use heuristic near-matching, guessed semantic equivalence, or value-level similarity to claim that a recommendation is already covered.

Why this matters:
- deterministic matching keeps `check` predictable for humans and agents;
- exact structural comparison avoids false positives that would hide genuinely missing observations;
- workflows that want readable stable matching can introduce early `let` bindings rather than relying on runtime guesswork.

<!-- source: model/runtime/check-analysis-model.md -->

# Check analysis model exploration

## Status

This document is exploratory rather than normative.
It captures a possible internal runtime design direction for richer `check` behavior.
It does not by itself define the public contract.
Normative `check` rules live in `meta/model/runtime/check-semantics.md`.
Verification-oriented scenario hypotheses live in `meta/verification/runtime/check-mode.md`.
Conservative default invalidation behavior is also part of the connector contract in `meta/model/connector/contract.md`.
The more concrete preflight interpreter proposal lives in `meta/model/runtime/preflight-step-interpreter.md`.

## Why this document exists

`check` now has explicit normative requirements around pre-execution honesty, incomplete verdicts, guard coverage, and `pre_run` interaction.
Those requirements are necessary, but they do not yet determine one concrete internal runtime model.

This document exists to preserve a deeper line of reasoning before it disappears into ad hoc implementation work.
Its role is to capture:

- the design pressure behind richer `check` behavior;
- candidate internal structures that could support that behavior;
- candidate data that runtime may need to compute and retain;
- open questions that should remain visible during iteration.

One such candidate concerns advisory `preflight_observations` declared by effectful actions.
Those structured probe templates are not part of the minimal normative `check` contract today, but they are a plausible source of richer verdict-basis and author-guidance data.

This document is intentionally more speculative than the normative runtime docs.

## Problem statement

The baseline `check` contract sounds simple:

- answer whether execution may proceed safely;
- evaluate guard blocks and static prerequisites;
- avoid effectful business step execution.

In practice, that simple surface quickly runs into harder questions:

1. What does it mean for a verdict to be complete rather than partial?
2. When should runtime report `allowed`, `blocked`, or `unknown`?
3. How much guard evaluation should happen before execution?
4. How should runtime preserve workflow order and guard barriers while still performing aggressive preflight analysis?
5. How should playbook-owned `pre_run` orchestration affect the truth value and completeness of the main-workflow verdict?
6. How should runtime explain not only blockers, but also the limits of what it currently knows?

The purpose of this exploration is to keep those questions explicit and connected.

## Core working idea

One promising direction is to treat `check` not as a flat blocker scan, but as a structured preflight knowledge model.

In that direction, `check` would still emit a simple public verdict surface, but internally it would maintain a richer decision model that answers questions such as:

- which guards were relevant to the current verdict;
- which of those guards were actually evaluated;
- which were not yet evaluable and why;
- which observations were used to evaluate those guards;
- which recommended preflight observations for later effectful steps were already matched or remain absent;
- which later effectful steps would invalidate or weaken those observations;
- how strong the basis of the current verdict is.

This is not the same as simulating execution.
It is closer to reasoning about what runtime currently knows, what it does not know, and how stable that knowledge is within the pre-execution phase.

## Why this is not just a confidence score

It is tempting to describe richer `check` behavior as a kind of confidence score.
That language is useful up to a point, because the runtime does need some notion of stronger and weaker verdict basis.

However, a naked numeric score would be misleading if it hides the reasons behind that score.
The important design pressure is not primarily to produce a number.
It is to preserve structural reasons such as:

- relevant guards covered versus uncovered;
- known truths versus unknown truths;
- observations that are stable now versus observations that would be invalidated by certain step families;
- blocks whose executability is already grounded versus blocks whose status depends on later effectful outcomes.

If any summary confidence surface is added later, it should be derived from these structural reasons rather than replacing them.

## Snapshot-oriented interpretation of `check`

One useful framing is to treat `check` as operating over a pre-execution world snapshot.

That snapshot may include:

- workflow inputs;
- runtime state;
- active profile context;
- explicit overrides;
- read-only observations from public probes;
- playbook and workflow structure.

Within this framing, runtime may aggressively evaluate any guard whose truth value is determined by that current pre-execution knowledge surface.

This does **not** mean:

- assuming later effectful step outcomes;
- simulating business actions;
- pretending that future step-local data already exists;
- flattening the workflow into a structureless bag of policy checks.

Instead, it means being ambitious about what can be known from the current snapshot while remaining strict about what cannot.

## Why workflow structure must remain central

Even if runtime evaluates many guards from one snapshot, the workflow is still an ordered block structure.
The design must therefore preserve:

- guard barriers;
- later step sequences protected by those barriers;
- the order in which blocks matter to the workflow contract;
- the difference between guards that are already relevant to the current verdict and guards that belong to later structural regions.

This is important because `check`, `plan`, and `explain` all depend on more than a flat list of true and false conditions.
They depend on a decision model that can still answer:

- where execution is blocked;
- which steps are currently reachable;
- which later regions remain unresolved;
- why a guard matters to the current outcome rather than merely existing somewhere in the workflow.

## Candidate model: one structural decision tree or graph

The current exploration direction should not create a separate abstract “confidence tree” disconnected from workflow shape.
Instead, a better direction is to build one structural runtime decision model that mirrors workflow structure and carries analysis annotations.

The central recommendation of this document is therefore:

> Build one workflow-shaped preflight decision tree or graph, then store knowledge, coverage, and invalidation annotations on that structure and on the final verdict summary.

This keeps reasoning localized and explainable.

## Why a tree or graph rather than a flat list

A flat list of blockers is too weak for the kinds of questions that richer `check` behavior needs to answer.

For example, a flat list cannot easily preserve:

- whether a guard belonged to an early or late barrier;
- whether a step block became blocked because of policy or because analysis never reached a required precondition;
- whether an unknown result was caused by missing current knowledge or by dependence on future step outcomes;
- whether a later step would invalidate observations used by earlier guard evaluation.

A structured model allows runtime to keep these relationships explicit.

## Candidate node kinds

An implementation does not need all of these node kinds in its first version, but the following taxonomy is useful for thinking:

- `workflow` — the root node for one assembled workflow run surface;
- `block` — one ordered workflow block;
- `guard` — one guard item inside a guard block;
- `step` — one step item inside a step block;
- `observation` — one probe-derived fact used by one or more guards;
- `verdict` — the aggregated preflight result;
- `effect-domain` — an abstract domain that may be observed or invalidated.

For an MVP, a simpler model would likely be enough:

- workflow root;
- ordered block nodes;
- guard item nodes;
- step item nodes;
- verdict summary.

The richer observation and effect-domain nodes can begin as attached metadata rather than first-class graph nodes.

## Candidate annotations on guard nodes

Each guard node may need to retain more than its expression text or reference.
Useful annotations could include:

- `reference`;
- `block_index`;
- `relevant_now`;
- `evaluable_now`;
- `evaluated`;
- `result` with values such as `true`, `false`, or `unknown`;
- `unknown_reason`;
- `depends_on_future_step_outcome`;
- `depends_on_missing_step_local_data`;
- `observation_domains_used`;
- `input_dependencies`;
- `state_dependencies`;
- `probe_dependencies`.

The key point is not the exact field names.
The key point is that `check` needs a way to express not only a truth value, but why that truth value was or was not obtainable.

## Candidate annotations on step nodes

Step nodes do not exist in `check` merely as future execution placeholders.
They matter because they determine:

- which effect domains might be changed later;
- which barriers guard those later changes;
- where current observations would stop being stable;
- which later guards could depend on future outcomes.

Useful step annotations could include:

- `name`;
- `kind` such as `probe`, `action`, `run`, or `builtin`;
- `effect_domains`;
- `may_invalidate_domains`;
- `conditional`;
- `condition_expression`;
- `declared_effect_class`;
- `currently_reachable_if_prior_guards_pass`;
- `preflight_observations`;
- `matched_preflight_observations`;
- `missing_preflight_observations`.

This is still preflight structure, not execution simulation.

## Candidate annotations on block nodes

Block-level annotations are useful because many runtime questions are really about barriers and transitions between barriers.

Useful block annotations could include:

- `type` such as `guards` or `steps`;
- `status` such as `ok`, `blocked`, `pending`, or `unknown`;
- `eligibility_now`;
- `covered_guard_count`;
- `uncovered_relevant_guard_count`;
- `unknown_guard_count`;
- `blocking_guard_references`;
- `depends_on_pre_run_outcome`;
- `future_dependent`.

These allow runtime to explain where one guard barrier ends and what remains unresolved beyond it.

## Candidate verdict-basis summary

The tree or graph should not be the only place where analysis knowledge is stored.
The final `check` result should also contain a compact verdict-basis summary derived from the structure.

Possible summary fields:

- `allowed_state` with values such as `allowed`, `blocked`, or `unknown`;
- `analysis_complete`;
- `relevant_guard_count`;
- `evaluated_relevant_guard_count`;
- `unevaluated_relevant_guard_count`;
- `blocking_guard_count`;
- `unknown_guard_count`;
- `incomplete_reasons`;
- `used_observation_domains`;
- `potential_invalidation_domains`;
- `preflight_support_strength`;
- `missing_recommended_observations`;
- `coverage_strength` or `verdict_basis_strength`.

This summary exists for quick consumption by callers.
The tree or graph exists so that the summary remains explainable rather than magical.

## Rendering recommendations back into workflow form

If action contracts expose advisory `preflight_observations` over action-argument names, one promising implementation strategy is:

- keep the action's canonical structured template objects in connector metadata;
- map each template placeholder to the workflow expression currently supplying that action argument;
- render author-facing guidance from those workflow expressions rather than only from resolved runtime values.

This would not require runtime to prove full semantic equivalence between arbitrary expressions.
It would merely require runtime to preserve and substitute the authored argument expressions that it already knows at the checked step boundary.

## Observation domains and invalidation domains

One especially promising idea is to treat observations and planned effects in terms of coarse domains.

Examples:

- `git` domain for repository facts and git actions;
- `gh` domain for GitHub facts and GitHub actions;
- `state:<name>` domains for runtime-managed state locations;
- `shell:*` or similar broad domains for shell-based actions with large or uncertain effect surfaces.

This is useful because `check` often needs to answer not only “what is true now”, but also “how far should runtime trust this truth before later planned actions may invalidate it”.

The idea here is not to predict the exact future state of the world.
The idea is to model the *stability boundary* of current observations.

## Conservative influence modeling

If influence domains are introduced, they should begin conservatively.

For a first implementation, it may be enough to say things like:

- `git.*` actions invalidate `git` observations;
- `gh.*` actions invalidate `gh` observations;
- state-setting builtins invalidate the affected `state:<name>` observations;
- shell-like actions may invalidate many domains unless a narrower contract exists.

The purpose of this model is not to be omniscient.
Its purpose is to avoid over-trusting earlier observations after known effect boundaries.

When in doubt, the system should prefer reduced certainty over false precision.

## Relevance versus existence

One important design distinction is the difference between a guard that exists somewhere in the assembled workflow and a guard that is relevant to the current preflight verdict.

At least three categories are useful:

- `relevant_now` — this guard contributes directly to the current verdict surface;
- `not_yet_relevant` — this guard belongs to a structurally later region but does not yet constrain the current verdict;
- `relevant_but_not_evaluable` — this guard matters to the verdict, but runtime cannot yet honestly determine its truth from the current snapshot.

Without such a distinction, `check` risks either:

- becoming too shallow because it evaluates almost nothing;
- or becoming noisy and hard to interpret because it evaluates everything without telling callers what actually matters.

## `pre_run` as a first-class pressure case

Playbook-owned `pre_run` orchestration is a critical test case for this model.

Why:

- `pre_run` is structurally earlier than the main workflow;
- it may influence profile context, working directory, or other activation conditions;
- it can make the main workflow verdict partial rather than final;
- it exposes the difference between “no blocker seen yet” and “main workflow actually cleared”.

Any candidate analysis model that cannot represent this honestly is probably too weak.

This makes `pre_run` not just a corner case, but a useful forcing function.

## Candidate static check-expansion test for `run`

One especially useful next-step criterion is a narrow test for whether `check` may statically expand a `run` step into a subtree rather than treating it as an opaque barrier.

This is not yet intended as the full general semantics of `run`.
It is only a candidate admissibility test for static `check` expansion.

Runtime may treat a `run` step as check-expandable only when all of the following hold:

1. the target workflow or fragment is known statically;
2. the `run` arguments are resolvable from pre-execution knowledge;
3. the target workflow or fragment is statically loadable;
4. the target subtree is check-analyzable at the depth needed by the current verdict;
5. expanding the subtree does not require pretending that effectful execution has already happened.

Why this matters:

- this gives runtime a generic criterion that is broader than special-casing one current `pre_run` fragment;
- this keeps static `check` expansion tied to honesty rather than to convenience;
- this allows profile-only or other context-shaping `run` fragments to become analyzable without turning every `run` into an automatic inline expansion.

This test should be read conservatively.
Known arguments alone are not enough.
The point is not to expand every `run`, but to identify the subset that can be turned into a static `check` subtree without erasing the boundary between preflight analysis and effectful execution.

## Relationship to `plan` and `explain`

This exploration is about `check`, but it has direct consequences for `plan` and `explain`.

If runtime builds a richer structural preflight model, then:

- `plan` can inherit structural reachability and barrier information without inventing false certainty;
- `explain` can say not only why execution is blocked or allowed, but also why the current verdict remains partial;
- downstream modes can remain honest because they derive from a decision model that already preserves incompleteness.

This is one reason to prefer a shared internal model over mode-specific one-off logic.

## What this direction is **not**

It is important to state what this exploration does **not** propose.

It does not propose:

- running effectful business steps during `check`;
- silently converting `check` into a dry-run execution engine;
- predicting concrete future action success as if those actions had already run;
- replacing workflow structure with a purely probabilistic system;
- turning `check` into an opaque confidence number.

The proposal is about better preflight honesty, not hidden simulation.

## Suggested MVP shape

A first implementation does not need a full graph engine.

An MVP could keep the existing ordered block-oriented runtime shape and enrich it with additional annotations.

Minimum useful additions might include:

### Guard items

- whether the guard is relevant;
- whether it is evaluable now;
- whether it was evaluated;
- result value;
- unknown reason;
- observation domains used.

### Step items

- effect domains;
- may-invalidate domains;
- declared effect class.

### Verdict summary

- `analysis_complete`;
- `allowed_state`;
- `unevaluated_relevant_guards`;
- `incomplete_reasons`;
- a coarse `coverage_strength` or equivalent basis-strength field.

This would already be enough to prevent many falsely optimistic outcomes without overcommitting to a complex architecture.

## Questions that remain open

This exploration intentionally leaves several questions unresolved.

### 1. Public versus internal surface

How much of the richer analysis model should become public result payload, and how much should remain internal runtime machinery?

### 2. Domain metadata origin

Where should effect-domain or invalidation metadata live?
Possible homes include:

- connector contracts;
- operation publication metadata;
- runtime-side heuristics;
- a combination of explicit declarations and conservative fallback rules.

### 3. How strongly to distinguish relevance categories

Should runtime expose only a simple relevant/not-relevant split, or a richer distinction among relevant-now, later-relevant, and structurally present but verdict-irrelevant guards?

### 4. Summary vocabulary

Should the public surface say `confidence`, `coverage_strength`, `verdict_basis_strength`, `analysis_completeness`, or something else entirely?

The current document leans away from pure “confidence” language because it sounds probabilistic.

### 5. Treatment of shell-like actions

How broad should default invalidation be for shell-driven actions or launcher-mediated commands?

### 6. Relation to future `next` behavior

If runtime later offers richer next-safe-action behavior, should it derive directly from this same analysis structure?

The likely answer is yes, but this document does not attempt to settle that now.

## Design recommendation for now

Until a more concrete architecture is selected, the safest working recommendation is:

1. Keep `check` grounded in currently available pre-execution knowledge.
2. Preserve ordered workflow block structure in the internal decision model.
3. Track relevant guard coverage explicitly.
4. Represent incomplete verdicts explicitly.
5. Treat observation stability and invalidation as first-class analysis concerns.
6. Prefer structural reasons over opaque confidence numbers.

This recommendation is intentionally compatible with the normative `CHECK-MODE-*` rules while leaving implementation freedom.

## What a future ADR might decide

If this direction proves useful, a later ADR could settle questions such as:

- whether runtime should standardize effect domains across connectors;
- whether invalidation metadata belongs in connector publication surfaces;
- whether the internal model should remain a block list with annotations or become a more explicit graph;
- which summary fields become part of the stable public `check` result contract.

This document should therefore be read as a preserved exploration path, not as a frozen solution.

<!-- source: model/runtime/preflight-step-interpreter.md -->

# Preflight step interpreter

## Status

This document is normative for the runtime-facing contract of preflight step interpretation.
It defines the required boundary, invariants, and minimum explanation surface for using step-derived read-only knowledge inside `check`.
Normative mode-level `check` rules continue to live in `meta/model/runtime/check-semantics.md`.

## Role

The proposed preflight step interpreter is a runtime-owned analysis layer inside `check`.
Its role is to derive additional pre-execution knowledge from workflow step flow without executing effectful business steps.

## Problem

`check` already supports direct guard evaluation over pre-execution knowledge.
It is less effective when relevant read-only observations are only reachable through step flow such as:

- `probe` steps;
- `value` steps;
- `register` bindings;
- `if` conditions over already-known values;
- nested `run` fragments that remain preflight-analyzable.

This creates an avoidable gap between:

- what runtime can already describe in `plan`; and
- what runtime can honestly use to strengthen guard coverage in `check`.

## Contract

- The interpreter is part of `check`, not a hidden `execute` variant.
- The interpreter may evaluate only `read_only` and `analysis_safe` steps.
- The interpreter may derive step-local knowledge and feed that knowledge back into guard coverage.
- The interpreter must stop before any effectful business step.
- The interpreter must preserve the same honesty rules as `check` for `allowed`, `blocked`, and `unknown` verdicts.

## Scope boundary

Allowed step kinds and capabilities:

- read-only probe steps;
- pure `value` evaluation;
- `register` materialization;
- `if` evaluation when all dependencies are already known;
- nested `run` expansion when the callee remains preflight-analyzable;
- future bounded `run` fan-out when the array source, whole-step eligibility, and callee analyzability remain preflight-computable;
- deterministic runtime context shaping already allowed by `check` semantics.

Disallowed step kinds and capabilities:

- effectful connector actions;
- `state_set`;
- `state_delete`;
- any step whose inputs depend on unknown values;
- any branch whose condition truth value is not yet known;
- any nested run that requires effectful execution or unknown step-local data.
- any bounded `run` fan-out whose source cardinality or callee analyzability cannot be established well enough for the current preflight phase.

## PREFLIGHT-STEP-001 — Step interpretation remains strictly non-effectful

The preflight interpreter must never execute an effectful business step.

Why this matters:
- `check` must remain safe to call routinely;
- step-derived knowledge must not blur into hidden execution;
- richer preflight analysis must not weaken the core runtime safety boundary.

## PREFLIGHT-STEP-002 — Step-derived knowledge stays inside pre-execution truth

The preflight interpreter may derive knowledge only from currently available pre-execution sources and already interpreted read-only step results.
It must not assume future effectful outcomes, unavailable `step.*.outputs`, or mutations that have not happened.

Why this matters:
- the interpreter exists to strengthen current knowledge, not to predict execution;
- otherwise `check` could silently upgrade unknown conditions into false certainty;
- plan and explain surfaces depend on the same honest boundary.

## PREFLIGHT-STEP-003 — Classification is explicit and conservative

The runtime must classify steps for preflight purposes using a contract-backed, runtime-visible scheme.
When classification metadata is missing or insufficient, the runtime must reduce precision rather than upgrading the step to analyzable.

Why this matters:
- preflight interpretation must not depend on hidden heuristics that callers cannot reason about;
- missing metadata should produce conservative incompleteness rather than optimistic analysis;
- implementation work needs a stable public vocabulary for explainability and verification.

## PREFLIGHT-STEP-004 — Ordered step dataflow remains semantically binding

The interpreter must respect declared step order, `register` materialization, and step-local dependencies when deriving preflight knowledge.
It must not flatten a step block into an unordered bag of probes.

Why this matters:
- later read-only steps may depend on earlier derived values;
- branch reachability and stop reasons depend on dataflow, not just step presence;
- callers need explanations that match authored workflow order.

## PREFLIGHT-STEP-005 — Stop reasons are first-class runtime outputs

When the interpreter cannot continue an analyzable path, it must preserve prior knowledge and emit a machine-readable halt reason tied to the blocked step or branch.

Why this matters:
- partial knowledge should remain useful even when a later path becomes unknown;
- runtime must be able to explain why coverage stopped growing;
- downstream verdicts need a stable basis for incomplete analysis.

## PREFLIGHT-STEP-006 — Step-derived knowledge must integrate with guard coverage honestly

Knowledge produced by the preflight interpreter must feed into the same preflight decision model used by `check`, `plan`, and `explain`.
It must not upgrade incomplete relevant coverage into an `allowed` verdict.

Why this matters:
- richer preflight logic is valuable only if it improves the actual runtime verdict basis;
- downstream modes should inherit stronger evidence without erasing uncertainty;
- one shared decision model keeps runtime reasoning coherent.

## Hard invariants

- `check` must never execute an effectful business step.
- Unknown values must never be upgraded into known values by heuristic guessing.
- Missing metadata must weaken precision rather than strengthen verdicts.
- Any derived fact must remain attributable to its source input, state binding, value step, probe, or nested run.
- Any analysis stop must be recorded as structured incompleteness rather than collapsed into silence.
- Incomplete relevant coverage must continue to prevent `allowed` verdicts.

## Knowledge sources

The interpreter may read from:

- workflow inputs;
- runtime state;
- active profile context and overrides;
- literals and pure local-expression outputs;
- outputs of previously interpreted read-only steps;
- outputs of read-only probes;
- already-expanded nested preflight results.

The interpreter may not assume:

- future effectful outcomes;
- unavailable `step.*.outputs` values;
- branch results whose conditions have not been computed;
- state mutations that have not happened.

## Step classification contract

The runtime must classify steps into at least these categories:

- `read_only_analyzable`;
- `read_only_unanalyzable`;
- `effectful`;
- `context_only`;
- `unknown`.

This classification must be runtime-visible and contract-backed rather than heuristic-only.

## Evaluation model

- Interpret step blocks in declared order.
- Materialize `register` outputs for successful read-only steps.
- Evaluate `if` only from currently available knowledge.
- Skip branches whose `if` evaluates to `false`.
- Halt the current analyzable path when the next required step is effectful, unknown, or not yet computable.
- Preserve all knowledge collected before the halt.

## Stop model

The interpreter must stop a path when it encounters:

- an effectful step;
- an unknown step classification;
- an unresolved step argument;
- an `if` condition that depends on unknown data;
- a `step.*.outputs` dependency that has not been produced;
- a nested run that is not preflight-analyzable.

Each stop must emit a machine-readable reason and the exact blocked step or branch.

## Integration with `check`

- Direct guard evaluation and step-derived read-only knowledge must contribute to one preflight decision model.
- Guard coverage must distinguish:
  - directly evaluated guards;
  - guards closed by interpreter-derived observations;
  - guards still relevant but not yet evaluable.
- `allowed_state`, `analysis_complete`, `incomplete_reasons`, `guard_coverage`, and block-level status must reflect both sources of knowledge.
- `plan` and `explain` must inherit the improved preflight basis without upgrading incomplete knowledge to false certainty.

## Public explanation surface

The interpreter should produce structured outputs such as:

- `preflight_step_items`;
- `preflight_observations`;
- `preflight_halts`;
- `knowledge_sources`.

Each interpreted step item should expose at least:

- step name;
- kind/classification;
- status;
- whether it was reached;
- whether it was interpreted;
- any registered outputs retained for later reasoning;
- halt or skip reason when applicable.

## Composition with nested `run`

- Nested runs should remain caller-visible in the preflight surface.
- Nested results should preserve origin boundaries such as caller step and callee workflow.
- Callee-derived knowledge may flow back to the caller only through structured preflight outputs.
- Nested effectful or unanalyzable regions must stop analysis conservatively rather than silently flattening into success.

## Planned composition with bounded `for_each`

If `run` later gains bounded `for_each`, the preflight surface should preserve one explicit fan-out run node with its own cardinality and eligibility annotations rather than pretending the repeated calls never existed.

- Whole-step `if` still applies to the fan-out step as one unit.
- Preflight may record exact item count when the array source is statically known.
- When the array source is not statically known, preflight should record runtime-only cardinality rather than inventing a guessed count.
- Lexical nested fan-out in one authoring surface should remain invalid and therefore does not require a nested fan-out tree shape.

## Determinism and conservatism

- The same workflow plus the same pre-execution knowledge snapshot must yield the same preflight result.
- When the runtime cannot prove a read-only path is analyzable, it must mark the path incomplete rather than speculate.
- Missing narrow metadata must reduce precision, not increase confidence.

## Suggested implementation stages

1. Interpret pure `value` steps, read-only probes, and `register` chains without branch logic.
2. Add `if` evaluation over already-known values.
3. Add nested analyzable `run` interpretation with structured provenance.
4. Merge interpreter-derived knowledge into guard coverage and explanation surfaces.
5. Add targeted verification for incomplete-path honesty and stop-reason explainability.

## Acceptance direction

The proposal is successful only if it:

- reduces avoidable `unknown` preflight verdicts;
- strengthens guard coverage using genuinely available read-only knowledge;
- preserves `check` as strictly non-effectful;
- keeps the result surface explainable without log scraping;
- avoids turning `check` into a disguised `execute` or broad dry-run simulator.

<!-- source: model/runtime/state.md -->

# Runtime state model

## Position

Runtime state is a built-in runtime capability for small persistent workflow-owned values.

Its declaration point belongs to playbook-level project orchestration context rather than to individual workflow files.

It is not:

- a connector family;
- a replacement for external source-of-truth systems;
- a general-purpose memory subsystem in the initial model.

## Top-level declaration

Playbooks may declare named runtime state locations through a top-level `states` mapping.

Minimal shape:

```yaml
states:
  repo_task_state:
    path: .ordo/state/task-state.json
```

The initial model treats the declared value as a runtime-managed location identifier. The first backend may be file-backed.

Workflow files consume logical state roles through `state.<role>...` references and state mutation step forms.
The playbook binds those logical roles to declared project state entries.
If a workflow declares a logical state role, activation requires a corresponding playbook binding.

The initial `state_needs` contract is marker-only.
It declares that a workflow needs a named logical role such as `task_memory`,
but it does not yet add per-need schema, purpose, kind, or capability subfields.

Illustrative binding shape:

```yaml
workflows:
  close-task:
    file: close-task.yml
    state_bindings:
      task_memory: repo_task_state
```

## Mutation step forms

State mutation uses dedicated built-in step forms rather than connector `uses` references.

Set example:

```yaml
state_needs:
  task_memory: {}

steps:
  - name: remember-branch
    state_set:
      state.task_memory[inputs.task_key].branch: ${inputs.branch}
```

Delete example:

```yaml
steps:
  - name: forget-branch
    state_delete: state.task_memory[inputs.task_key].branch
```

These forms are effectful runtime operations even though they do not go through the public connector registry.

## Read surface

State reads use direct references instead of a dedicated retrieval step.

Illustrative form:

```yaml
${state.task_memory[inputs.task_key].branch}
```

The read surface should stay aligned with the mutation target surface so that authors do not learn two unrelated addressing models.

## Stable path grammar

The initial stable state path grammar is:

```text
state.<role>[inputs.<key-reference>][.<field>...]
```

Examples:

- `state.task_memory[inputs.task_key]`
- `state.task_memory[inputs.task_key].branch`
- `state.task_memory[inputs.task_key].metadata.owner`

Read usage wraps the same path inside a value expression:

```yaml
${state.task_memory[inputs.task_key].branch}
```

Mutation targets use the same path text directly:

```yaml
state_set:
  state.task_memory[inputs.task_key].branch: ${inputs.branch}

state_delete: state.task_memory[inputs.task_key].branch
```

## Initial grammar restrictions

- the path must start with `state.`;
- `<role>` is an identifier-like logical state role name;
- the bracketed key reference must use dotted `inputs...` form;
- at least one segment must follow `inputs` inside the key reference;
- field traversal after the key is optional and uses dotted identifiers only;
- the initial grammar does not support literal keys, quoted keys, multiple bracket segments, arbitrary nested expressions, or mixed index syntaxes.

## MVP constraints

- The initial model should remain centered on named state locations and addressed values.
- State declaration ownership should remain at playbook level so workflows do not duplicate project-local storage setup.
- Workflow authoring should use logical state roles rather than concrete project state instance names.
- A declared workflow logical state role is a required composition dependency rather than an optional hint.
- The initial state-need contract should stay marker-only until runtime owns a clear reason for richer per-need fields.
- The initial model should not assume multiple state scopes beyond explicitly declared named entries.
- The initial model should not require bulk update semantics, query semantics, or concurrency semantics.
- The initial model should not rename this capability into a larger semantic system before the runtime actually owns those broader concerns.
- The initial model should treat runtime state as persistent handoff memory across runs, not as a second per-run scratch surface beside step registers.
- State writes and deletes belong to the top-level workflow authoring surface rather than to include fragments or run-invoked fragments.
- Within one workflow, a logical state role should be written or deleted only after the final read of that same role.

<!-- source: model/runtime/guard-evaluation.md -->

# Guard evaluation runtime model

## Role

Guard evaluation is part of the runtime decision surface, not only a hidden implementation detail.
See also `meta/model/runtime/check-semantics.md` for the normative `check`-mode rules that constrain guard-coverage claims and incomplete preflight verdicts.
Step-derived read-only knowledge used by guard evaluation must follow the contract in `meta/model/runtime/preflight-step-interpreter.md`.

## Minimum runtime structure

- A failed guard result must identify the blocking guard item.
- A failed guard result must identify the failing subcondition when available.
- Runtime outputs should preserve observed values when they materially explain the outcome.
- Runtime outputs should preserve a machine-usable evaluation trace rather than collapsing everything into a single boolean.

## Outcome distinctions

Runtime guard evaluation must preserve the distinction between:

- validation failure before guard evaluation;
- resolution failure before guard evaluation;
- boolean guard failure where evaluation completed and the condition was false;
- probe evaluation failure where the condition could not be safely evaluated.

## Trace expectations

- The trace should preserve boolean structure closely enough for explanation.
- Probe-level observations should remain attributable to the probe reference that produced them.
- A repeated identical probe reference within one expression should be reusable without requiring duplicate probe execution.

<!-- source: model/runtime/package-layout.md -->

# Package layout

## v0 Python package shape

The minimal v0 package layout is:

- `ordo.model` — public domain models for workflow, profile, connector, diagnostic, and runtime result.
- `ordo.runtime` — runtime orchestration entry points and mode-specific logic.
- `connectors` — built-in public connector library packages, organized by family.
- `ordo.connectors` — runtime-facing adapter and registry surface over the built-in connector library.
- `ordo.types` — shared JSON-shaped value aliases used by public model surfaces.

## Model split inside `ordo.model`

- `workflow` owns `Workflow`, `OperationRef`, `Guard`, and `Step`.
- `profile` owns `Profile` and explicit `Override` data.
- `connector` owns `Connector`, family bootstrap data, and `OperationContract`.
- `diagnostic` owns normalized machine-usable diagnostics.
- `runtime` owns runtime mode, plan, operation result, and result envelope data.

## Boundary rule

Package layout must preserve the contract boundary:

- workflow models hold orchestration intent;
- connector models hold public operation contracts;
- runtime models hold decision and result surfaces;
- helper modules must not smuggle hidden runtime semantics into the model layer.

## v0 discipline

- The layout must stay small enough to explain directly from the public contract.
- It must support YAML authoring and JSON-shaped runtime surfaces.
- It must support `check`, `plan`, `execute`, and `explain` without treating connector authoring as the routine customization path.

## Connector library shape

The built-in connector library should live under the repository-level `connectors/` tree.

`ordo.connectors` may provide adapter and registry entry points for the runtime, but it should not become the primary home of family implementations.
The runtime core should reach built-in connectors through provider-style wiring, not through a hardcoded assumption about where family code lives.

A separate composition layer should decide whether the standard built-in connector provider is installed by default for a particular application surface.

Even when connector code is imported through `ordo.connectors`, the conceptual boundary remains:

- `ordo.runtime` is the engine and orchestration layer;
- `connectors` is the built-in public connector library consumed by the runtime;
- `ordo.connectors` is the runtime-facing adapter surface over that library.

The import path may be package-local for implementation convenience, but that should not blur ownership of connector semantics.
Built-in connectors should not be modeled as part of the runtime core merely because they are shipped with the same distribution.

Connector packages should follow the family-first layout:

- `connectors/<family>/bootstrap.py` for family-level bootstrap;
- `connectors/<family>/probes/<operation>.py` for a single public probe module;
- `connectors/<family>/actions/<operation>.py` for a single public action module.

This layout should be preferred over monolithic cross-family modules and over hand-maintained central registries that duplicate operation declarations outside the family package tree.

Assembly should prefer family-local autodiscovery or an equivalent family-local mechanism rather than a cross-family hand-edited registry list.

<!-- source: model/connector/contract.md -->

# Connector and operation contract

## Connector

Connector is a public family-level contract.

Connector owns:
- namespace
- shared bootstrap
- family-level prerequisites
- shared runtime context
- operation registry

## Operation

Operation is a public callable unit inside a connector.

Current operation kinds:
- `probe`
- `action`

Operation contract must define:
- inputs
- prerequisites
- effects
- outputs
- failure modes

Here, `prerequisites` means operation-local prerequisites that are part of the public contract of that specific operation.
Shared family prerequisites belong to connector bootstrap rather than to every operation contract entry.

Operation contract may also expose lifecycle metadata when needed, for example whether an operation is deprecated and which canonical operations should replace it.

Action contracts may also expose conservative observation-invalidation metadata for runtime `check` reasoning.
Action contracts may also expose advisory preflight-observation templates for richer `check`, `plan`, and `explain` support.

## Explainability and failure normalization

Every operation must:
- return a structured result on both success and failure paths
- support narrow local explanation of its own outcome
- normalize internal exceptions into a structured failure result rather than escaping as the only observable surface

When an implementation produces raw stdout/stderr, those streams are secondary details inside the result contract, not the primary contract itself.

## Minimal structured operation outcome surface

To stay small and mode-agnostic while still supporting runtime `check`, `plan`, `explain`, and future next-safe-action behavior, an operation outcome should expose at least:

- `status` — the operation-local normalized outcome
- `summary` — a short human-readable local explanation
- `outputs` — the structured observations or effect summary that carry the operation's machine-relevant meaning
- `diagnostics` — structured local problems, warnings, or refusal detail when needed
- `raw` — optional supplementary transport or implementation detail such as stdout, stderr, return code, or response fragments

Implications:
- probes should place their durable observed facts in `outputs` rather than in summary text alone
- actions should place their durable effect summary in `outputs` rather than in summary text alone
- `raw` is supplementary detail and must not be the only place where contract-relevant meaning exists
- runtime mode semantics should be derived from this structured local surface rather than pushed down into operation-specific mode logic

## Observation invalidation metadata

An effectful action may declare which probe-derived observation scopes it invalidates.

When such metadata is present, runtime may use it to reason conservatively about the stability limits of pre-execution knowledge during `check`.

If an effectful connector action does not declare narrower observation invalidation metadata, runtime should conservatively treat it as invalidating the full observation namespace of that connector family.

Why this matters:
- `check` should not over-trust probe observations across later effect boundaries;
- missing invalidation detail must weaken confidence rather than justify optimistic approval;
- connector authors may improve precision incrementally without requiring perfect metadata coverage before the mechanism is useful.

## Preflight observation recommendation metadata

An effectful action may declare `preflight_observations` metadata that usually helps runtime explain applicability and expected effect before execution.

This metadata is advisory rather than executable.
It is not:
- an operation-local prerequisite;
- a hidden workflow dependency;
- a requirement that a workflow invoke a probe in one literal textual form.

Instead, it is a connector-authored hint that some probe-shaped observation would strengthen preflight reasoning for that action.

`preflight_observations` should:
- be expressed as structured canonical probe templates rather than as free-form prose alone;
- refer to action-argument names rather than to workflow-local sources such as `inputs`, `state`, `let`, or step-local expressions;
- remain mode-agnostic connector metadata rather than workflow-policy logic;
- help runtime render author-facing recommendations using the workflow expressions that currently supply those action arguments.

The canonical shape is a list of objects.
Each object should contain:
- `probe` — the canonical public probe reference;
- `with` — a mapping from probe argument name to an action-argument placeholder string such as `"{project_id}"`;
- optional `fields` — an ordered list of selected output fields when the recommendation depends on a narrower field path rather than the whole probe output.

This object shape is the contract surface.
Runtime may render it into a human-facing probe-call form when showing guidance, but connector authors should publish the structured object form rather than a free-form call string.

Recommended preflight observations are intended for deterministic structural matching.
Runtime should treat a recommendation as covered only when it can prove the same canonical probe shape for the same referenced action arguments.
Runtime should not guess semantic equivalence between different expressions, infer near-matches heuristically, or treat similar-looking values as coverage.

Why this matters:
- some actions are semantically simple for authors while still benefiting from richer preflight observation basis;
- connector-authored templates can improve `check`, `plan`, and `explain` without forcing authors or agents to read connector implementation internals;
- action-argument-relative templates stay stable across workflows even when each workflow sources those arguments differently.

## Contract split

### Family-level

Connector-level bootstrap may check and prepare shared prerequisites.

Examples:
- binary exists
- auth is available
- shared scopes or session context

### Operation-level

Operation checks only its own local contract.

Examples:
- input shape
- required target object
- operation-specific flags
- operation-local prerequisites not already guaranteed by connector bootstrap

## Rule

Shared prerequisites should not be duplicated in every operation contract if they are already owned by connector bootstrap.

<!-- source: model/connector/gh-project-items.md -->

# GitHub Project items probe model

## Public reference

- `gh.project.items`

## Kind

- `probe`

## Mental model

- This probe enumerates one GitHub Project item collection and then applies narrow contract-owned filtering.
- It is not a policy-named derived probe such as `active_stories` or `ready_tasks`.

## Input shape

- `project_id: string`
- `content_kind: string` optional
- `filters: [{field: string, value: scalar}]` optional

## Output shape

```json
{
  "count": 2,
  "items": [
    {
      "item_id": "PVTI_xxx",
      "content_kind": "Issue",
      "repository": "owner/repo",
      "number": 7,
      "title": "Implement project items probe",
      "url": "https://github.com/owner/repo/issues/7"
    }
  ]
}
```

## Filtering semantics

- `content_kind` is a structural filter.
- `filters` match project fields by field name.
- Each filter compares one field value by equality.
- Multiple filters compose with AND semantics.
- Missing field values on one item mean that item does not match.

## Discovery examples

### Let-bound scan

```yaml
let:
  ready_items: >-
    gh.project.items(project_id=inputs.project_id, filters=inputs.filters)

blocks:
  - guards:
      - ready_items.count != 0
```

### Direct filtered call

```yaml
uses: gh.project.items
with:
  project_id: ${inputs.project_id}
  content_kind: Issue
  filters:
    - field: Status
      value: Ready
```

<!-- source: model/connector/authoring-surface.md -->

# Connector operation authoring surface

## Purpose

Connector operation authoring should stay small, local, and mode-agnostic while still exposing enough structure for runtime `check`, `plan`, `explain`, and future next-safe-action behavior.

This authoring surface exists to keep connector code readable without pushing runtime orchestration semantics down into each probe or action.

## Operation module responsibilities

An operation module should be responsible for:

- declaring its local operation contract;
- exposing a uniform publication hook for that operation module;
- accepting local inputs through a narrow authoring context;
- performing local integration work;
- returning a structured local outcome.

An operation module may also depend on other operations when that dependency is explicit, local, and part of the narrow integration semantics of the derived operation.

An operation module should not be responsible for:

- reimplementing runtime modes;
- knowing workflow-level orchestration policy;
- constructing the public runtime result envelope directly;
- embedding `check`, `plan`, `explain`, or `next` semantics in handler-local control flow.

## Uniform publication hook

Each operation module should expose a uniform publication hook such as `info()`.

That hook should publish the operation as a whole rather than leaving metadata and execution behavior as unrelated module globals.

Implications:

- the publication hook is distinct from the execution handler;
- the execution handler remains the operation's execution point rather than the module's publication point;
- runtime or connector-family discovery should read the operation module through this uniform publication hook;
- simple operation modules should not rely on ad hoc naming magic to bind contract metadata to execution behavior.
- effectful action publication may declare conservative observation-invalidation metadata for runtime `check` reasoning.

## Minimal authoring context

The authoring context should stay narrow.

At minimum it should support:

- access to operation-local inputs;
- reusable helpers for local integration work such as command execution;
- inline failure mapping for repetitive transport-level failures;
- narrow local context needed for diagnostics or execution environment details.

It should not require connector handlers to receive broad runtime-shaped objects such as full workflow state or resolution internals when the operation does not need them for its local job.

## Minimal structured outcome surface

At minimum an authored operation outcome should expose:

- `status` — normalized local outcome;
- `summary` — short local human-readable explanation;
- `outputs` — structured observations or structured effect summary;
- `diagnostics` — structured local problem detail when needed;
- `raw` — optional supplementary transport or implementation detail.

Implications:

- probes should place durable observed facts in `outputs`;
- actions should place durable effect facts in `outputs`;
- summary text helps reviewability but must not be the only contract-relevant meaning;
- raw detail is supplementary and must not be required to recover the main outcome semantics.

## Failure mapping expectations

Repeated transport-level failure handling should be supported by reusable authoring helpers rather than copied `if` ladders in every operation.

Typical examples include:

- command spawn failures;
- non-zero command exit handling;
- transport response normalization.

Domain-specific negative outcomes should still remain visible in operation-local Python logic when they are part of the operation's narrow semantic job.

## Dependency expectations

The authoring surface should distinguish between:

- shared bootstrap or family capability state;
- explicit operation-to-operation dependency;
- workflow-level composition over public results.

Implications:

- a small operation should not be forced to rediscover every shared family prerequisite by itself;
- derived operations may reuse other operations explicitly when that keeps semantics clearer and avoids duplication;
- operation-to-operation reuse should not become hidden runtime magic;
- workflow and policy composition should remain visibly distinct from operation implementation dependency.

## Runtime-owned semantics

Runtime should derive higher-level mode behavior from operation contracts and structured outcomes.

The authored operation outcome is a local authoring-facing outcome surface, not the full public runtime result envelope.

Runtime owns:

- blocked-versus-runnable interpretation in workflow context;
- plan assembly;
- workflow-level explanation;
- next-safe-action reasoning;
- mapping local operation outcomes into the public runtime result envelope.

## Migration direction

Current connector implementations may still be authored against runtime-shaped models during migration.

The target direction is a dedicated connector authoring surface or plugin SDK that preserves:

- simple local operation code;
- stable structured outcomes;
- runtime ownership of orchestration semantics.

<!-- source: model/connector/bootstrap-api.md -->

# Concrete executable bootstrap API proposal

## Role

This document defines the first concrete executable bootstrap API proposal for connector families.

Its purpose is to turn family bootstrap from metadata-only declaration into a real executable capability-check layer while keeping the pattern close to the existing publication-hook direction for operations.

## Bootstrap module shape

Each connector family bootstrap module should expose exactly two primary surfaces:

- `info()` — the uniform publication hook for the family bootstrap definition;
- `run(ctx)` — the bootstrap execution hook.

The publication hook is the family bootstrap publication point.
The execution hook is the family bootstrap execution point.

## Publication hook

The uniform publication hook should be:

```python
def info() -> PublishedBootstrap
```

`info()` should return the published bootstrap definition for the family.

The first executable bootstrap step should not require additional family-bootstrap globals beyond this publication hook.

## Published bootstrap definition

The minimal published bootstrap definition should expose at least:

- `prerequisites`
- `context_fields`
- `handler`

Implications:

- `prerequisites` describe shared family prerequisites rather than operation-local prerequisites;
- `context_fields` describe the family-level capability or context facts that bootstrap may provide on success;
- the published definition does not need operation-style `inputs`, `outputs`, `effects`, or `failure_modes` fields unless later code proves they are necessary.

## Execution hook

The bootstrap execution hook should be:

```python
def run(ctx: BootstrapContext) -> BootstrapOutcome
```

The hook should remain family-capability-oriented rather than operation-oriented.
It should not know which specific probe or action will later consume the bootstrap state.

## Bootstrap context

The minimal bootstrap context should expose at least:

- `command(argv, *, failures=...)` for command-backed capability checks;
- narrow environment access needed to discover shared family context;
- a way to report or accumulate shared capability facts when bootstrap succeeds.

The first executable bootstrap step should not require workflow-level policy state or operation-local inputs.

## Bootstrap outcome

The minimal bootstrap outcome should expose at least:

- `status`
- `summary`
- `diagnostics`
- `raw`
- `context`

Where:

- `status` reports bootstrap success or bootstrap failure at the family layer;
- `summary` gives a short human-readable family-level result;
- `diagnostics` carries structured bootstrap problems or warnings;
- `raw` carries supplementary command or transport detail when helpful;
- `context` carries shared family capability facts made available to later operation execution.

The bootstrap outcome is a connector-family capability result, not an operation result and not the full public runtime envelope.

## Command helper expectations

Bootstrap should be able to use the same low-level command helper pattern as operations where appropriate.

The minimum normalized failure keys for the first executable bootstrap step should be:

- `os_error`
- `nonzero`

Additional keys may be added later if executable bootstrap checks prove they are needed.

## Runtime expectations

Runtime should evaluate executable family bootstrap before operation-local logic when a family requires shared prerequisites.

Runtime should then:

- preserve bootstrap success or failure as its own layer;
- carry bootstrap `context` into later operation execution;
- keep bootstrap failures distinct from operation-local failures and workflow-policy outcomes.

## Git first-step expectations

For the Git family, the first executable bootstrap step should be able to detect at least:

- missing `git` binary;
- non-repository context.

On success, it may provide shared facts such as:

- repository root;
- repository availability confirmation.

Additional facts such as current branch should be included only if keeping them at bootstrap level remains semantically clean.

## Low-ceremony requirement

Bootstrap authoring should stay small and direct.

The first executable Git bootstrap should not require substantially more ceremony than a small probe module, except for the extra family-level context field in its outcome.

If executable bootstrap grows into a second large authoring framework, the boundary should be reconsidered before wider rollout.

## Open questions intentionally left to code work

The first bootstrap implementation step should answer these by code rather than by abstract generalization:

- whether bootstrap should share the exact command helper implementation with operation context or only the same pattern;
- whether bootstrap diagnostics need anything beyond the current local diagnostic shape;
- whether bootstrap `context` should remain an unstructured mapping at first or immediately grow a richer view type;
- whether runtime should cache bootstrap state per family per run or simply reevaluate it at the first straightforward integration point.

<!-- source: model/connector/plugin-sdk.md -->

# Connector plugin SDK sketch

## Role

The connector plugin SDK is the concrete authoring-facing surface that should realize the connector authoring boundary.

It exists to let operation files stay small, local, and readable without importing core runtime models directly.

## Design goal

For a simple operation such as `git.branch`, the SDK should allow a single-file implementation that:

- declares its operation contract locally;
- executes narrow local integration work;
- returns a structured local outcome;
- avoids unnecessary incidental technical ceremony.

Simple operation files should not need avoidable scaffolding such as broad runtime-shaped arguments or unnecessary `from __future__ import annotations` imports.

## Minimal SDK entities

The SDK should expose only a small set of authoring-facing entities.

At minimum:

- operation metadata type for probes;
- operation metadata type for actions;
- uniform publication-hook return type for operation modules;
- narrow operation context type;
- structured operation outcome type;
- structured local diagnostic type;
- reusable local integration helper result types where needed.

The SDK should prefer one small coherent surface over many narrowly sliced helper types.

## Metadata expectations

Operation metadata should let an authored module declare at least:

- operation name;
- operation kind;
- inputs when applicable;
- outputs;
- failure modes;
- effects when applicable.

Metadata should remain local to the operation module rather than requiring a second hand-maintained registry declaration elsewhere.

The SDK should support a uniform publication hook such as `info()` that returns the published operation definition for the module.

That published definition should bind operation metadata and execution handler explicitly.

## Context expectations

The operation context should stay narrow and authoring-oriented.

At minimum it should support:

- operation-local input access;
- reusable command execution for command-backed operations;
- inline failure mapping for repetitive transport-level failures;
- narrow execution-environment access when needed for local behavior or diagnostics;
- explicit access to shared family bootstrap state or shared capability context when the operation depends on it.

The context should not require small operations to know workflow internals, guard-context expression internals, or runtime mode state.

When operation-to-operation reuse is allowed, the SDK should prefer an explicit local dependency surface over hidden runtime magic.

## Command helper expectations

Command-backed operations are expected to be common.

The SDK should therefore provide a command helper that:

- executes a command locally;
- normalizes repetitive transport-level failure categories;
- supports inline failure mapping close to the call site;
- returns a structured helper result suitable for local domain-specific checks after the command succeeds technically.

This helper exists to avoid repeated low-level `if` ladders for command spawn failure, non-zero exit handling, and similar transport concerns.

## Outcome expectations

The SDK outcome type should preserve the minimal structured operation outcome surface already defined elsewhere in meta:

- `status`;
- `summary`;
- `outputs`;
- `diagnostics`;
- `raw`.

The SDK may provide convenience constructors or helpers for common success and failure cases, but those helpers must not hide the structured outcome model itself.

For example, a helper that constructs a single structured diagnostic together with a failure outcome is a good fit for the SDK when it reduces repeated boilerplate across many operations without inventing a second failure abstraction.

## Low-ceremony requirement

The SDK should optimize for low incidental ceremony in small operation files.

Implications:

- simple probes and actions should fit comfortably in one small file;
- import surfaces should stay small;
- common success and failure paths should be concise;
- repeated one-diagnostic failure shaping should not require each operation to rebuild the same local helper function;
- publication should remain explicit without requiring ad hoc module-global binding conventions;
- operation code should remain more prominent than authoring-framework boilerplate.

## Runtime boundary

The SDK is not a second runtime.

It should not re-expose:

- workflow orchestration semantics;
- runtime mode semantics;
- full runtime result-envelope assembly;
- policy evaluation logic.

Those remain runtime responsibilities.

## Dependency-layer boundary

The SDK should help keep three layers distinct:

- family bootstrap and shared capability state;
- explicit operation-to-operation reuse;
- workflow-level policy composition.

It should not encourage simple technical prerequisites to masquerade as arbitrary public probe graphs, and it should not hide derived-operation dependencies behind opaque runtime behavior.

## Expected migration use

The first migration step should be able to prove the SDK shape on one or two very small operations before broader connector migration begins.

If the resulting operation code is not visibly simpler and more local than the current runtime-shaped form, the SDK shape should be reconsidered before wider adoption.

The concrete first-spike API proposal should live in a separate model document so code work can implement the SDK without reconstructing it from principles alone.

Executable family bootstrap should likewise have its own concrete model document so shared prerequisite evaluation can be implemented explicitly rather than inferred from metadata-only bootstrap declarations.

<!-- source: model/connector/plugin-sdk-api.md -->

# Concrete plugin SDK API proposal

## Role

This document turns the bounded plugin-SDK sketch into a concrete minimal authoring API proposal for the first implementation spike.

The goal is not to freeze every future detail.
The goal is to make the first code implementation possible without guesswork.

## Module-level shape

Each operation module should expose exactly two primary surfaces:

- `info()` — the uniform publication hook for the module;
- `run(ctx)` — the execution handler for the published operation.

The publication hook is the module's publication point.
The execution handler is the operation's execution point.

## Publication hook

The uniform publication hook should be:

```python
def info() -> PublishedOperation
```

`info()` should return a published operation definition that binds contract metadata and the execution handler explicitly.

Simple modules should not require any additional publication globals.

The first spike should not require operation-level ordering hints such as per-module `ORDER` values.
Operation publication should remain complete without a separate operation-order side channel.

## Published operation definition

The minimal published operation definition should expose at least:

- `name`
- `kind`
- `handler`
- `inputs`
- `outputs`
- `failure_modes`
- `effects`
- `prerequisites`

Implications:

- probe modules may leave `inputs`, `effects`, or `prerequisites` empty when not needed;
- action modules may leave `effects` empty only when the action has no narrower effect summary to declare;
- `prerequisites` here means operation-local prerequisites, not shared family bootstrap prerequisites.

The first spike may use separate published-definition types for probes and actions if that keeps the API simpler.

## Execution handler

The execution handler should be:

```python
def run(ctx: OperationContext) -> OperationOutcome
```

The first spike may use separate `ProbeContext` and `ActionContext` types only if the difference is concrete and small.
If the difference is weak, one `OperationContext` is preferred.

The handler should stay mode-agnostic.
It should not know whether runtime is currently building `check`, `plan`, `execute`, `explain`, or next-safe-action behavior.

## Operation context

The minimal context should expose at least:

- `input(name)` or equivalent access to operation-local inputs;
- `command(argv, *, failures=...)` for command-backed integration work;
- `bootstrap()` or equivalent access to shared family bootstrap/capability state;
- `call(name, *, inputs=None)` or equivalent explicit operation-to-operation dependency surface;
- narrow environment access when needed for local diagnostics or execution details.

The first spike should prefer plain, explicit names over abstraction-heavy helper layering.

## Command helper

The concrete command helper should support this shape or a shape very close to it:

```python
ctx.command(
    ["git", "branch", "--show-current"],
    failures={
        "os_error": "git_unavailable",
        "nonzero": "probe_failed",
    },
)
```

The minimum normalized failure keys for the first spike should be:

- `os_error`
- `nonzero`

Additional keys such as timeout handling may be added later only if the first migrated operations need them.

## Command result

The command helper result should expose at least:

- `stdout`
- `stderr`
- `returncode`
- `raw`

If additional convenience accessors are introduced, they should remain small and obviously derived from those core fields.

## Operation outcome

The concrete local outcome type should expose exactly the structured surface already defined elsewhere in meta:

- `status`
- `summary`
- `outputs`
- `diagnostics`
- `raw`

The first spike should prefer one shared `OperationOutcome` shape unless probe/action differences require a second type in practice.

## Diagnostic type

The minimal local diagnostic type should expose at least:

- `code`
- `level`
- `message`
- `details`

Path-heavy runtime-specific structure should remain outside the local plugin SDK unless a first migrated operation proves it necessary.

## Convenience helpers

The first spike may provide small convenience helpers such as:

- `ok(...)`
- `fail(...)`
- `fail_with_diagnostic(...)`

Those helpers should only construct `OperationOutcome` values more concisely.
They should not replace or obscure the underlying structured outcome model.

`fail_with_diagnostic(...)` is appropriate when many operations would otherwise repeat the same pattern of:

- `status`
- `summary`
- one structured diagnostic code and message
- optional `details`
- optional `raw`

The helper should stay small and explicit rather than growing hidden policy or operation-kind-specific semantics.

## First-spike example shape

The intended first-spike authoring style is approximately:

```python
def info() -> PublishedOperation:
    return PublishedProbe(
        name="branch",
        outputs={"value": "string"},
        failure_modes=("git_unavailable", "not_repository", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    command = ctx.command(
        ["git", "branch", "--show-current"],
        failures={
            "os_error": "git_unavailable",
            "nonzero": "probe_failed",
        },
    )

    branch = command.stdout.strip()
    if not branch:
        return fail(
            code="probe_failed",
            summary="Current branch could not be determined",
            raw=command.raw,
        )

    return ok(
        summary="Current branch inspected successfully",
        outputs={"value": branch},
        raw=command.raw,
    )
```

This example is intentionally small.
If the first migrated files need substantially more ceremony than this, the SDK API should be reconsidered before wider rollout.

## Open questions intentionally left to the spike

The first implementation spike should answer these by code rather than by further abstract discussion:

- whether one `OperationContext` is enough or probe/action split pays for itself;
- whether one `PublishedOperation` type is enough or probe/action split pays for itself;
- whether operation-to-operation dependency should use operation names or richer refs locally;
- whether `bootstrap()` should return one shared object or named capability views;
- whether convenience helpers are useful enough to keep after the first migrated operations.

<!-- source: model/connector/resolution-policy.md -->

# Resolution policy

## Baseline

Workflow references are resolved against public connector operations.

## Default policy

- same-name silent shadowing is not default behavior
- base public connector semantics must remain stable
- local adaptation must be explicit

## Allowed local adaptation

- local namespaces such as `local.*` or `project.*`
- explicit override mechanisms, if the runtime exposes them
- profiles as composition/preset layer

## Not allowed by default

- silent replacement of `gh.*`, `git.*`, or `shell.*`
- same-name semantic drift hidden from workflow readers

## Why

Workflow readability and portability depend on visible resolution semantics.

<!-- source: data/local-expressions/shape.md -->

# Local expression data shape

## Expression-bearing field families

The stable workflow contract may expose local expressions in more than one field family.

The important shape distinction is between native condition contexts and embedded value contexts.

## Embedded expression form

An embedded expression appears inside a value-bearing field that is not itself a pure expression slot.

Illustrative form:

```yaml
with:
  repository: ${inputs.repository}
  branch: ${step.issue.outputs.branch}
```

Embedded-shape rules:

- the surrounding field remains a value-bearing field rather than a dedicated condition list;
- the expression form is explicitly embedded;
- the allowed roots still depend on the surrounding context.

## Native condition form

A native condition context may use direct expression items without an interpolation envelope.

Illustrative guard form:

```yaml
guards:
  - git.worktree.clean and git.branch.value != "main"
```

Native-condition rules:

- the surrounding field is already a condition-bearing surface;
- the condition item is authored directly as a local expression;
- context restrictions still determine which roots may appear.

## Current context-specific notes

- guard items are native condition entries;
- step `if` is a condition-bearing field whose preferred stable authored form is the native bare-expression surface;
- step `if: ${...}` remains supported as a deprecated compatibility form during migration;
- include-site `with` values are embedded value entries evaluated in caller scope;
- embedded value forms may appear in other workflow fields that reuse local-expression evaluation.

This file describes only authored surface categories and stable reference forms.

It does not define the full semantic restrictions of each context.

## Root-shape notes

- `inputs...` is the stable workflow input reference form;
- `args...` is the stable included-fragment argument reference form;
- `state...` is the documented runtime-state read form where the surrounding context allows state reads;
- `step...` is the documented registered-step-result read form where the surrounding context allows execution-local step reads.

## Compatibility note

Current stable authored surfaces may include context-specific compatibility forms during migration.

Current compatibility decisions:

- object-form guard items using `uses` remain compatibility-only guard authoring surface;
- string-form native guard entries are the preferred stable guard form;
- step `if` prefers native bare condition entries;
- step `if: ${...}` remains a deprecated compatibility form.

These deprecated compatibility forms remain valid during the current v0 warning window and require an explicit future contract revision before hard removal.

Those compatibility forms do not change the higher-level local-expression model or the context restrictions that define which dependencies are allowed.

<!-- source: data/workflow/shape.md -->

# Workflow data shape

## Stable assembled top-level fields

- `version`
- `workflow`
- `inputs`
- `let`
- `state_needs`
- `blocks`

Compatibility-only top-level fields:

- `guards`
- `steps`

The stable assembled execution shape is block-based.
Top-level `guards` and `steps` remain compatibility inputs that normalize to `blocks`.
Top-level `let` is one workflow-level local-expression binding surface rather than a block kind.

Project-local launch context such as named workflow catalog, named profile catalog, and runtime state declarations belongs to the playbook contract rather than to the workflow data shape itself.

## Source workflow shape

Source workflow material may additionally use assembly instructions.

An assembly instruction is a source-level workflow construct that shapes workflow assembly rather than surviving as a block kind in the assembled execution model.

`include` is the initial assembly instruction for static workflow composition.

Assembly may still carry caller-scoped bindings into expanded material. In particular, `include.with` may bind caller-scoped expressions before the expanded fragment payload is validated as assembled workflow material.

Source workflow material may also declare a workflow-level `let` mapping for workflow-local named local expressions.

Stable `let` form:

```yaml
let:
  issue: gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number)
  issue_open: gh.project.issue(repository=inputs.repository, issue_number=inputs.issue_number).state == "OPEN"
```

`let` rules:

- `let` is optional and, when present, is an object mapping binding names to local expressions;
- `let` is allowed only at workflow top level;
- each binding name must be unique within the workflow;
- reserved roots such as `inputs`, `args`, `state`, and `step` must not be reused as `let` binding names;
- each binding value is parsed as one ordinary local expression rather than as text substitution;
- a `let` binding may not reference another `let` binding;
- `let` bindings do not normalize into `blocks` and do not form an execution block kind of their own.

## Stable assembled block shape

```yaml
blocks:
  - guards:
      - git.worktree.clean
  - steps:
      - name: verify
        uses: shell.run
        with: {}
```

Rules:

- `blocks` is an ordered non-empty list;
- each assembled block item must declare exactly one of `guards` or `steps`;
- `guards` block value is a non-empty guard list;
- `steps` block value is a non-empty step list;
- block order is semantically meaningful;
- a `guards` block is evaluated before any later `steps` block may run.
- unknown fields fail validation;

Current stable assembled shape note:

- `run` is not part of the current stable block shape.
- A future invocation-oriented step form may add `run` under `steps:` rather than changing the meaning of existing `include` items.

## Stable source assembly instruction form

Source workflow material may contain `include` as an assembly instruction.

Stable `include` instruction form:

```yaml
- include: github/check-issue
  with:
    repository: ${inputs.repository}
    issue_number: ${inputs.issue_number}
```

Include item rules:

- `include` is a non-empty string reference to an included workflow fragment;
- `with` is optional and, when present, is an object;
- `with` keys bind only declared fragment `args` keys;
- include expansion preserves block order in the assembled workflow;
- `include` participates in source assembly and does not survive as an assembled execution block kind;
- `with` bindings may carry caller-scoped expressions into the expanded fragment material without making `include` itself an assembled block kind.

## Planned fragment run step shape

Illustrative future form:

```yaml
- steps:
    - name: comment-and-status
      run: github/comment-and-set-status
      if: step.issue.outputs.open
      with:
        comment: "Issue is open."
        status: "In Progress"
```

Planned run step rules:

- `run` would be a non-empty reusable-fragment reference on one step entry;
- `name` would remain required because the author-facing surface still treats the invocation as one step;
- `with` would remain the explicit fragment-argument binding object;
- `if` would be evaluated in caller scope rather than in fragment-body scope;
- the invoked fragment would execute with its own fragment-local `args...` and `step...` scope.

## Included fragment document shape

Illustrative included fragment file:

```yaml
description: Check one issue and reuse the loaded result
args:
  repository: string
  issue_number:
    type: integer
  project_id:
    type: string
    default: null
  dry_run:
    type: boolean
    default: false

blocks:
  - steps:
      - name: inspect
        uses: gh.issue
        with:
          repository: ${args.repository}
          issue_number: ${args.issue_number}
```

Rules:

- an included fragment may declare `description`;
- an included fragment may declare `args` as a mapping of fragment-local argument names;
- an `args` entry may use a short scalar declaration such as `repository: string` for a required argument;
- an `args` entry may use an object declaration with fields such as `type`, `required`, and `default`;
- `default` may be any JSON-shaped value, including `null`;
- an omitted optional argument and an explicit `null` binding are distinct authoring cases;
- fragment-local argument reads use the `args.<name>` surface;
- included fragment payload content must still normalize to ordinary workflow block semantics after argument binding and expansion.

## Compatibility normalization

Illustrative legacy form:

```yaml
guards:
  - git.worktree.clean

steps:
  - name: verify
    uses: shell.run
    with: {}
```

Normalized form:

```yaml
blocks:
  - guards:
      - git.worktree.clean
  - steps:
      - name: verify
        uses: shell.run
        with: {}
```

Normalization rules:

- if `blocks` is present, top-level `guards` and top-level `steps` must not be present;
- if `blocks` is absent, at least one of top-level `guards` or top-level `steps` must be present;
- top-level `guards` normalizes to one leading `guards` block;
- top-level `steps` normalizes to one trailing `steps` block.

YAML is an authoring surface, not the canonical runtime model.
After loading, workflow data must remain representable as a losslessly JSON-serializable structure.
Compatibility-only legacy workflow forms must normalize to the same canonical block-based runtime structure.
Authoring convenience must not introduce YAML-only semantics into runtime behavior.

## Stable guard shape

```yaml
- uses: namespace.name
  with: {}
```

## Stable logical state need shape

```yaml
state_needs:
  task_memory: {}
```

The initial stable shape is marker-only.

Implications:

- each logical state role name maps to an empty object;
- additional per-need fields are not part of the initial stable contract;
- unknown nested fields under a logical state need fail validation.

## Stable step shape

```yaml
- name: some-step
  uses: namespace.name
  with: {}
```

Built-in runtime state mutation forms may also appear in `steps`.

Stable state target/read path grammar:

```text
state.<role>[inputs.<key-reference>][.<field>...]
```

Rules:

- reads use this path only inside `${...}`;
- `state_set` keys use this path text directly;
- `state_delete` uses this path text directly;
- the key reference inside `[...]` must use dotted `inputs...` form;
- post-key field traversal uses dotted identifiers only.

Set example:

```yaml
- name: remember-branch
  state_set:
    state.task_memory[inputs.task_key].branch: ${inputs.branch}
```

Delete example:

```yaml
- name: forget-branch
  state_delete: state.task_memory[inputs.task_key].branch
```

Workflow files do not declare runtime state locations themselves.
They declare logical state needs and reference them through the `state.<role>...` read and mutation surface.

Unsupported or ambiguous variants are outside the initial stable contract.

## Current rule

Unknown top-level and nested stable fields fail validation.

## Serialization rule

- Workflow files may be authored in YAML.
- Workflow semantics are defined over the loaded data model, not over YAML-specific syntax.
- Stable workflow data must be representable as a losslessly JSON-serializable structure after loading.
- YAML-specific mechanisms such as anchors, aliases, tags, or merge behavior must not introduce distinct runtime semantics unless explicitly standardized.

<!-- source: data/playbook/shape.md -->

# Playbook data shape

## Stable top-level fields

- `version`
- `states`
- `workflows`
- `profiles`
- `defaults`

## Stable workflow entry shape

```yaml
workflows:
  close-task:
    file: close-task.yml
    working_directory: ${inputs.repo_root}
    state_bindings:
      task_memory: repo_task_state
```

Required field:

- `file`

Optional stable field:

- `working_directory`
- `state_bindings`

## Stable pre-run shape

```yaml
pre_run:
  - workflows/resolve-context.yml
  - workflows/ensure-environment.yml
```

Optional stable top-level field:

- `pre_run`

Stable `state_bindings` shape:

```yaml
state_bindings:
  task_memory: repo_task_state
```

## Stable defaults shape

```yaml
defaults:
  profile: backend-default
  working_directory: repos/default-backend
```

Optional stable field:

- `profile`
- `working_directory`

## Stable profile entry shape

```yaml
profiles:
  backend-default:
    file: backend-default.yml
```

Required field:

- `file`

## Stable state entry shape

```yaml
states:
  task_state:
    path: .ordo/state/task-state.json
```

Required field:

- `path`

## Serialization rule

- Playbook files may be authored in YAML.
- Playbook semantics are defined over the loaded data model, not over YAML-specific syntax.
- Stable playbook data must be representable as a losslessly JSON-serializable structure after loading.
- YAML-specific mechanisms such as anchors, aliases, tags, or merge behavior must not introduce distinct runtime semantics unless explicitly standardized.

## Current rule

Unknown top-level and nested stable fields fail validation.

<!-- source: data/runtime/result-envelope.md -->

# Result envelope

## Minimal envelope

The runtime result must be able to express:

- overall status
- failed guard or failed step
- diagnostics
- outputs
- published workflow results
- skipped/executed steps
- human-readable message when useful for review
- machine-readable code when useful for classification

Connector operation results must also preserve enough structure for the runtime to expose:

- meaningful observations for successful probes
- meaningful effect summaries for successful actions
- structured failure diagnostics even when the underlying implementation raised an exception
- optional raw stdout/stderr detail fields when an implementation produces them

At minimum, a connector operation outcome should preserve:

- operation-local `status`
- short local `summary`
- structured `outputs` carrying observations or effect summary
- structured `diagnostics` when local problem detail matters
- optional supplementary `raw` detail

This operation outcome is the connector-local structured input to runtime adaptation, not the entire public runtime result envelope by itself.

## Workflow-local results and global publications

- Successful run output may include a workflow-local `results` list of authored return values produced by the requested workflow run.
- Each executed workflow `result` step appends one value to that workflow-local `results` list.
- Workflow-local result values accumulate in execution order inside that one workflow run.
- Successful run output may also include a global `published` list of authored published values.
- Each executed workflow `publish` step appends one value to that global `published` list.
- Published values accumulate in execution order across the enclosing run session, including nested `run` boundaries.
- Registering one `run` step should expose only the just-completed workflow-local `results` list rather than the global `published` stream.
- If `run` later supports bounded `for_each`, one registered caller value should preserve one array of per-run workflow-local result payloads rather than flattening all returned values into one list.
- The runtime must not inject additional metadata into authored `results` or `published` values in the initial model.
- If no `result` step executes, successful top-level run output may return `results: []` and may still choose one synthetic fallback result for compact human-facing run surfaces.
- Include expansion, playbook-owned `pre_run`, and nested reusable `run` boundaries must not emit fallback results of their own.

## Serialization constraints

- The public runtime result envelope is JSON-shaped.
- Contract-level result fields must be losslessly JSON-serializable.
- Python-specific, transport-specific, or format-specific value kinds must not be required by the public result contract.
- Human-readable summaries may be included, but machine-relevant meaning must remain available in structured fields.

## Baseline statuses

- `ok`
- `guard_failed`
- `validation_error`
- `resolution_error`
- `execution_error`

<!-- source: scenarios/core.md -->

# Core scenarios

## Scenario 1: guarded repo ritual

Workflow checks local repo state, confirms guardrails, and executes a small sequence of repo actions.

Expected Ordo value:

- guard barriers are visible before the affected steps run;
- runtime can say whether the ritual is blocked before any business action happens;
- result can tell both human and agent what to fix next.

## Scenario 2: GH-backed issue workflow

Workflow reads GitHub issue/project state through stable `gh.*` operations and composes policy at workflow/profile level.

Expected Ordo value:

- workflow policy is expressed in declarations rather than buried in shell branching;
- connector operations keep stable public semantics while project policy stays local;
- `plan` and `explain` can show issue-state blockers separately from git-state blockers.

## Scenario 3: local project override

Project adds local connector operations or profiles without changing baseline global connector semantics.

Expected Ordo value:

- local adaptation stays explicit;
- reviewers can see where a project extends behavior versus where it consumes shared contracts;
- runtime diagnostics can mention active overrides rather than silently changing behavior.

## Scenario 4: plan before execute

Agent or human asks for `plan`/`explain` before performing effectful steps.

Expected Ordo value:

- runtime returns a machine-readable plan;
- blocked steps are distinguishable from merely not-yet-run steps;
- the caller can decide whether to continue to `execute`.

## Scenario 5: non-git effector

Workflow invokes `shell.*` without assuming git-centric design.

Expected Ordo value:

- shell remains an effector, not the dominant semantic layer;
- explainability still works even when shell is involved;
- the workflow contract remains more stable than opaque shell strings alone.

## Scenario 6: multiple blockers before execution

Workflow is blocked by more than one policy issue at once, for example:

- dirty worktree;
- current branch is `main`;
- issue status is not eligible.

Expected Ordo value:

- `check`/`explain` can surface multiple blockers in one result when safe to do so;
- human does not have to fix issues one-by-one through repeated fail-fast loops;
- agent can choose the safest next question or remediation.

## Scenario 7: policy-heavy close-task ritual

Workflow for shipping/closing a task depends on repo kind, verification profile, git safety checks, and issue/project state.

Expected Ordo value:

- repo-specific verification can be selected via profiles without hiding the high-level ritual intent;
- runtime can explain why merge/close is blocked before attempting side effects;
- final result can show which checks passed, which were skipped, and which blocked execution.

## Scenario 8: agent asks what is allowed now

Agent inspects a repo and asks what action is currently safe:

- only check;
- plan available but execute blocked;
- execute allowed.

Expected Ordo value:

- runtime status is explicit enough to drive agent behavior;
- no brittle parsing of shell logs is required;
- decision support is part of the runtime contract, not an afterthought.

## Scenario 9: explainable failure, not just execution failure

User wants to know not only that a workflow failed, but whether it:

- failed validation;
- failed resolution;
- was blocked by guards;
- failed during step execution.

Expected Ordo value:

- these categories remain distinct in the result surface;
- user and agent get a clearer recovery path;
- the project stays different from a generic step runner that mainly exposes logs and exceptions.

<!-- source: scenarios/playbook/core.md -->

# Playbook scenarios

## Scenario 1: project-local workflow catalog

Repo exposes a small named set of common operational workflows through `.ordo/ordo.yaml`.

Expected Ordo value:

- humans can discover available operations quickly;
- agents can target named workflows without reconstructing local bootstrap commands;
- project launch ergonomics improve without changing workflow semantics.

## Scenario 2: default profile selection

Playbook run selects a default profile such as `backend-default` before activating one workflow.

Expected Ordo value:

- common project defaults stay reviewable in one place;
- workflow files remain less repo-specific;
- callers may still override profile selection explicitly.

## Scenario 3: shared project state declaration

Multiple workflows use one named runtime state entry such as `task_state` declared in the playbook.

Expected Ordo value:

- state naming stays stable across workflows;
- storage location is managed in project-local orchestration context;
- workflows do not each duplicate the same storage declaration.

## Scenario 3a: in-process profile switch

One workflow run reaches a point where later steps should execute in a different declared profile context such as `frontend`.

Expected Ordo value:

- the context switch is explicit and reviewable;
- subsequent execution may use the new profile without restarting the process;
- the switch remains runtime context rather than workflow-owned business state.

## Scenario 3b: runtime profile switch construct

One workflow step uses an explicit engine-level construct such as `profile_switch` to select `frontend` for later steps or nested workflow execution in the current run.

Expected Ordo value:

- the context switch is explicit and reviewable in workflow material;
- later execution in the same run may use the new profile without hidden shell state;
- later execution in the same run may also observe the new profile's missing-input defaults;
- already-completed parts of the current run are not silently reinterpreted under a different profile.

## Scenario 3c: launch-time input override

Caller launches a named workflow entry but needs to override one input such as `repository`, `issue_number`, or `enabled` for a single run.

Expected Ordo value:

- the caller can override or add the input without editing the workflow file;
- launch-time values win over workflow defaults and profile-provided defaults;
- the override remains local to that one run.

## Scenario 3d: playbook-level pre-run workflow set

Playbook declares a shared `pre_run` workflow set that executes before the requested workflow so common preparation such as context resolution or runtime-profile switching stays centralized.

Expected Ordo value:

- common preparation stays explicit in one project-local orchestration surface;
- requested workflows stay smaller and less repetitive;
- launch-phase state needs stay playbook-owned rather than leaking into the requested workflow contract;
- later execution still remains explainable because pre-run orchestration is declared rather than hidden.

## Scenario 4: logical workflow state binding

Workflow uses a logical state role such as `task_memory`, while the playbook binds that role to a concrete state entry such as `repo_task_state`.

Expected Ordo value:

- workflow files stay portable across projects with different storage naming;
- playbook owns project-local storage binding rather than workflow files;
- missing bindings fail clearly before effectful execution.

## Scenario 5: missing playbook on default discovery

Caller runs `ordo plan close-task` in a directory without `.ordo/ordo.yaml`.

Expected Ordo value:

- failure is immediate and explicit;
- runtime does not guess a workflow file from nearby YAML;
- both human and agent receive a clear next step.

## Scenario 6: unresolved named workflow

Playbook contains a named workflow entry whose target file no longer exists.

Expected Ordo value:

- validation or pre-execution resolution fails before effectful work;
- diagnostics name the missing entry and its target;
- the project can repair the catalog without inspecting runtime internals.

## Scenario 7: missing required state binding

Workflow declares `state_needs.task_memory`, but the active playbook workflow entry does not bind `task_memory`.

Expected Ordo value:

- activation fails before effectful execution;
- diagnostics identify the missing logical state role;
- runtime does not attempt to guess or auto-create a binding.

<!-- source: scenarios/authoring.md -->

# Authoring scenarios

## Human authoring

Human writes or reviews a workflow using readable connector operations, small schema surface, and examples.

Human should be able to answer, by reading the declaration:

- what policy is enforced;
- which guards can block execution;
- which steps are intended after each guard barrier passes;
- whether shell is being used as an escape hatch or as the main hidden mechanism.

## Agent authoring

Agent writes a workflow against schema + examples + connector contracts and can predict validation/runtime behavior.

This is not a marginal scenario. It is one of the main intended ways the product is used.

Agent should be able to predict:

- whether `uses` references are valid and resolvable;
- what `check` and `plan` would return in broad shape;
- what categories of failure are possible;
- which result codes are safe to branch on programmatically.

Agent should also be able to determine that the better next step is to compose an existing workflow/profile from public operations rather than invent a new connector operation.

## Mixed maintenance

Human and agent can evolve the same workflow without hidden local semantic traps.

This implies:

- local overrides stay explicit;
- public operation semantics stay stable;
- workflow meaning does not silently drift into implementation details only a shell expert can reconstruct.

## Review scenario

Reviewer should be able to tell whether a proposed workflow is:

- a clear declaration of policy and intent;
- an opaque shell script disguised as YAML;
- safe for an agent to invoke in `check`/`plan` mode.

## Composition-first scenario

Agent needs a new local ritual.

Preferred path:

- inspect available public operations and examples;
- compose a workflow from existing operations;
- add or adjust a profile when local policy or defaults differ;
- run machine-checkable validation and explanation before any execution.

Discouraged default path:

- invent a new connector family or new public operation semantics just to express routine local variation.

## Explainability scenario

Both human and agent should be able to use runtime explanation without replaying failure manually.

Desired experience:

- reviewer asks "why is this blocked?" and gets a structured answer;
- agent asks "what can I safely do next?" and gets machine-readable status plus next actions;
- explanation quality does not depend on scraping unstructured stderr.

<!-- source: adr/0001-scope.md -->

# ADR 0001: scope

## Decision

Ordo is a local declarative ritual engine, not a general distributed workflow platform.

## Why

This keeps the core small, explainable, and suitable for operational helper workflows.

<!-- source: adr/0002-connectors-are-public.md -->

# ADR 0002: connectors are public

## Decision

`connectors/` is a public contract layer.

## Why

Workflow portability and explainability depend on stable connector and operation semantics.

## Consequence

Silent same-name semantic shadowing must not be the default behavior.

<!-- source: adr/0003-packs-are-derived.md -->

# ADR 0003: packs are derived

## Decision

`meta/packs/**` is generated from source docs under `meta/{requirements,domain,model,data,scenarios,adr,verification}`.

## Why

This keeps source-of-truth documents editable while allowing compact derived packs for agents and later tooling.

<!-- source: verification/core/drift.md -->

# Verification

## Drift checks

At minimum the project must be able to check:

- workflow examples validate against schema;
- generated packs are in sync with source docs;
- public docs do not contradict core contract docs;
- connector contract changes are reflected in examples and schema where relevant.

## Review rule

If schema or runtime semantics change, corresponding `meta/` source docs must change in the same work.

<!-- source: verification/connector/invariants.md -->

# Connector invariants

## Core invariants

- workflows reference only public connector operations
- fixed v0 connector domains are `git`, `gh`, and `shell`
- connector semantics are public and stable
- connector operation kinds fixed so far are `probe` and `action`
- connector operations preserve structured results on success, failure, and exception paths
- `probe` remains semantically read-only and `action` remains the effectful operation kind
- silent same-name shadowing is not default behavior

## Drift rule

If a change breaks any invariant, `meta/` must be updated explicitly in the same work.

<!-- source: verification/local-expressions/invariants.md -->

# Local expression invariants

## Context discipline

- Local expressions remain one product-owned expression family rather than drifting into unrelated per-context languages.
- Condition-oriented and value-oriented contexts remain explicitly distinguished.
- Each expression-bearing context has explicit documented root restrictions.
- Surface-syntax differences do not silently redefine dependency rules.

## Root discipline

- `inputs...`, `args...`, `state...`, and `step...` keep distinct documented meanings.
- `step...` remains execution-local and must not drift into contexts that are meant to stay pre-execution.
- Include bindings preserve caller scope without turning fragment bodies into implicit owners of caller-local step data.

## Guard-context discipline

- Guard context must not depend on `step...`.
- Guard context must remain compatible with read-only, pre-execution analysis.
- Guard conditions must remain explainable as workflow-visible policy rather than hidden connector-local verdicts.
- Guard context may allow pure built-ins and read-only representation-adapter projections without regressing into a separate guard-only language.
- Guard context must continue to forbid representation-adapter write paths such as `->...`.
- Guard evaluation must end in a boolean result; non-boolean success must remain an error rather than collapsing into implicit truthiness.

## Value-context discipline

- Embedded value contexts must not drift into effectful connector execution.
- Value-oriented local expressions must not grow hidden workflow-control semantics.

## Pipeline-filter discipline

- Pipeline filters remain an explicit product-defined contract rather than an implementation-only registry.
- Product-defined pipeline filters must not drift into workflow-defined extensibility.
- Predicate filters such as `is_string`, `is_number`, `is_integer`, and `is_boolean` must remain boolean-only and must not silently introduce coercion semantics.
- Membership filters such as `in(container)` must preserve explicit list-container discipline rather than silently treating arbitrary strings, objects, or scalars as containers.
- Boolean-producing filters must keep stable boolean result shape across contexts.

## Workflow-local binding discipline

- Workflow-level `let` remains one local-expression naming surface rather than a second expression language.
- A `let` binding does not relax the context restrictions that would apply to the equivalent inline expression.
- A `let` binding may not reference another `let` binding.
- Reserved roots must not drift into ordinary reusable binding names.

## Representation-adapter discipline

- Representation-adapter docs must preserve the boundary between host-owned outer binding evaluation and adapter-family body evaluation.
- Representation-adapter docs must not drift back toward bare host-root references inside adapter-owned body syntax.
- Adapter-related failures should remain attributable either to outer binding resolution or to adapter-family evaluation rather than collapsing those phases into one opaque error class.

## Drift checks

- Documentation must not reintroduce separate first-class expression species such as an unrelated guard language versus an unrelated value language.
- Context-specific docs must stay aligned with the domain definition in `domain/local-expressions.md`.

<!-- source: verification/playbook/core.md -->

# Playbook verification

## Rule

Playbook must provide a deterministic and reviewable project-local launch surface.

## Checks

- `.ordo/ordo.yaml` discovery behavior is documented and testable.
- Missing playbook, missing workflow entry, and missing profile entry fail with distinct structured outcomes.
- Workflow names are unique within the playbook workflow catalog.
- Profile names are unique within the playbook profile catalog.
- State names are unique within the playbook state catalog.
- Workflow state-binding role names are unique within a workflow entry.
- Relative workflow, profile, and state paths resolve deterministically from playbook-owned context.
- Launch-time input overrides, when supported, deterministically override workflow and profile input defaults for one run only.
- Workflow logical state roles resolve deterministically to declared playbook state entries.
- Every declared workflow logical state role has a binding in the active playbook workflow entry.
- No playbook workflow entry provides extra state bindings for undeclared workflow logical state roles.
- No silent fallback resolves a missing named workflow or profile to an arbitrary nearby file.
- Workflow business logic remains in workflow files rather than being duplicated as playbook-only execution semantics.

<!-- source: verification/workflow/authoring.md -->

# Workflow authoring verification

## Rule

Workflow and profile authoring must remain a first-class and agent-usable surface.

## Checks

- Public operations are discoverable enough for composition without reading connector implementation internals.
- Schema, examples, and runtime diagnostics are sufficient for iterative repair of an authored workflow.
- Routine project adaptation prefers composing workflows and profiles over introducing new connector semantics.
- Reusable included fragments remain understandable as a static-composition `include` surface even when they declare fragment-local `args`.
- Authoring verification should not require all reusable-fragment semantics to collapse into `include` when a later runtime-scoped invocation surface would be clearer.
- If a future `run` surface is introduced, authoring verification should preserve a short explainable distinction between static composition and runtime-scoped fragment invocation.
- Workflow-level `let` should help reduce repeated expression noise without hiding whether a workflow is reading inputs, runtime state, step-local data, or read-only observations.
- Validation and diagnostics should keep `let` errors attributable both to the binding declaration and to the authored use site when that distinction matters.
- A valid declaration is not treated as fully sufficient when it is opaque, shell-heavy, or difficult to review.
- When effectful actions publish advisory preflight-observation templates, authoring diagnostics should be able to surface those templates back in workflow-shaped expressions.
- If those rendered recommendations become awkward or long, that is an authoring signal to name important values earlier rather than a reason to hide workflow structure from diagnostics.
- Authoring diagnostics may reuse the same shared context-aware analysis tree as runtime preflight, so long as authoring findings remain distinct from executability blockers.
- The shared analysis tree should preserve enough structural evidence for later `plan`, `explain`, and `next` work rather than discarding it after the first `review` or `check` projection.

<!-- source: verification/runtime/guard-evaluation.md -->

# Guard evaluation runtime verification

## Rule

Guard evaluation results must remain explainable as a machine-usable runtime surface.

## Checks

- A blocked result identifies the blocking guard item.
- A blocked result identifies the failing subcondition when available.
- Runtime output distinguishes boolean guard failure from probe evaluation failure.
- Guard-evaluation traces remain structured enough for `check`, `plan`, and `explain` to report consistent blocker identity.
- Reuse of repeated identical probe references inside one expression does not weaken explainability.

<!-- source: verification/runtime/check-mode.md -->

# Check mode verification hypotheses

## Role

This document records verification-oriented hypotheses and scenario expectations for `check`.
It is not the normative source of `check` semantics.

Normative requirements live in `meta/model/runtime/check-semantics.md`.
Exploratory internal-model discussion lives in `meta/model/runtime/check-analysis-model.md`.

The purpose of this document is to preserve concrete checks that future implementation and test work should validate.

## HYP-CHECK-001 — Incomplete relevant guard coverage must block optimistic approval

Related normative rules:
- `CHECK-MODE-004`
- `CHECK-MODE-005`
- `CHECK-MODE-006`
- `CHECK-MODE-009`

Scenario shape:
- a playbook or workflow structure places `pre_run` or some other structurally earlier step region before main-workflow guards;
- the runtime does not actually evaluate one or more relevant main-workflow guards;
- no explicit blocking guard has yet been observed.

Expected result:
- `check` must not report a clean allowed verdict;
- the result must contain an explicit incomplete or unknown signal;
- the result should indicate that relevant guard coverage is incomplete rather than pretending that main-workflow policy has cleared.

Why this matters:
- this is the clearest protection against falsely optimistic preflight results;
- it verifies that runtime distinguishes “no blocker found yet” from “workflow is cleared to run”;
- it directly exercises the pressure case introduced by `pre_run`.

Failure meaning:
- a failure here means runtime is upgrading missing coverage into positive approval;
- downstream `plan` and `explain` will likely inherit misleading certainty from the same defect.

## HYP-CHECK-002 — Guard coverage must be represented structurally, not only as blockers

Related normative rules:
- `CHECK-MODE-004`
- `CHECK-MODE-006`
- `CHECK-MODE-010`

Scenario shape:
- a workflow contains several relevant guards;
- at least one relevant guard evaluates true;
- at least one relevant guard evaluates false;
- at least one relevant guard remains unevaluable from current pre-execution knowledge.

Expected result:
- `check` should distinguish these categories explicitly rather than collapsing everything into a blocker list;
- the runtime result should make it possible to tell which relevant guards were evaluated and which were not;
- an unknown or incomplete region should remain visible even if a different guard already failed.

Why this matters:
- the quality of a preflight result depends not only on blockers but on coverage transparency;
- both human readers and agents need to tell whether a verdict is fully grounded or only partially grounded;
- this prevents a false appearance of completeness when some policy surface was never actually checked.

Failure meaning:
- a failure here means runtime is hiding important coverage distinctions;
- later explanation quality will degrade because `explain` cannot narrate distinctions that `check` discarded.

## HYP-CHECK-003 — Aggressive preflight guard evaluation is allowed within current snapshot bounds

Related normative rules:
- `CHECK-MODE-001`
- `CHECK-MODE-003`
- `CHECK-MODE-007`

Scenario shape:
- a workflow contains later guard regions beyond the first immediate barrier;
- those later guards depend only on current inputs, runtime state, profile context, overrides, and read-only probe observations;
- no later guard in this scenario depends on future effectful step outcomes.

Expected result:
- runtime may evaluate those later guards during `check`;
- the result must still preserve block structure and guard attribution rather than flattening the workflow into one verdict list;
- any such additional evaluation should strengthen preflight knowledge without pretending that later effectful steps have already run.

Why this matters:
- this verifies that `check` can be meaningfully strong rather than stopping at the first narrow barrier by habit;
- it allows earlier discovery of blockers when those blockers are already decidable from the current snapshot;
- it protects against the opposite failure mode where `check` becomes too weak to be useful.

Failure meaning:
- a failure here means runtime is unnecessarily shallow even when more knowledge is safely available;
- this would undercut one of the main reasons to enrich `check` at all.

## HYP-CHECK-004 — Future-step-dependent guards must remain unknown rather than guessed

Related normative rules:
- `CHECK-MODE-001`
- `CHECK-MODE-006`
- `CHECK-MODE-008`

Scenario shape:
- a later guard depends on an effectful step outcome, a step-local output, or some other future execution product that does not yet exist in the pre-execution state.

Expected result:
- `check` must not invent a truth value for that guard;
- the runtime result should mark the guard as unknown, incomplete, or not yet evaluable;
- the result should preserve the reason that this guard depends on future execution knowledge.

Why this matters:
- this preserves the boundary between preflight analysis and actual execution;
- it prevents `check` from silently turning into speculative simulation;
- it ensures that later richer modes inherit honest uncertainty rather than fabricated certainty.

Failure meaning:
- a failure here means runtime is smuggling future execution assumptions into present knowledge;
- once that happens, the trustworthiness of `check` collapses even if the surface still looks structured.

## HYP-CHECK-005 — Observation invalidation should weaken verdict basis conservatively

Related normative rules:
- `CHECK-MODE-001`
- `CHECK-MODE-003`
- `CHECK-MODE-007`
- `CHECK-MODE-010`

Scenario shape:
- one or more guards are evaluated from current probe observations in some domain such as `git`;
- later planned steps belong to effect domains that may invalidate those observations, such as `git.*` actions or broad shell-like actions.

Expected result:
- `check` may still report what is currently true from the present snapshot;
- however, the runtime result should preserve that these observations sit before a potential invalidation boundary;
- if the implementation exposes verdict-basis or coverage-strength metadata, that metadata should reflect reduced certainty or reduced downstream stability rather than ignoring the invalidation risk.

Why this matters:
- this is the bridge between simple guard truth evaluation and richer preflight honesty;
- it gives runtime a way to preserve structural reasons for weaker verdict basis without faking future outcomes;
- it supports stronger later `plan` and `explain` behavior by making observation boundaries explicit.

Failure meaning:
- a failure here means runtime is treating all observations as equally stable even when later effect surfaces obviously threaten them;
- the result may still look correct in narrow cases while remaining conceptually unsafe in more complex workflows.

## HYP-CHECK-006 — Missing narrow invalidation metadata must fall back conservatively

Related normative rules:
- `CHECK-MODE-011`

Scenario shape:
- an effectful connector action appears in the workflow;
- runtime tracks observation invalidation during `check`;
- that action does not declare narrower invalidation metadata.

Expected result:
- runtime should not treat the action as preserving prior observations by default;
- runtime should conservatively fall back to invalidating the full observation namespace of that connector family;
- any verdict-basis reasoning should therefore become weaker rather than stronger in the face of missing narrow metadata.

Why this matters:
- a safe default is necessary if invalidation metadata is adopted incrementally;
- otherwise missing metadata would silently behave like proof of stability;
- this preserves honesty while allowing connector contracts to become more precise over time.

Failure meaning:
- a failure here means the system is optimistic exactly where it should be conservative;
- partial metadata rollout would then make `check` less trustworthy instead of more useful.

## HYP-CHECK-007 — Missing advisory preflight observations should weaken explanation quality without becoming blockers

Related normative rules:
- `CHECK-MODE-013`

Scenario shape:
- an effectful action appears in the workflow;
- that action declares advisory preflight-observation templates;
- the workflow does not currently establish one or more equivalent observations before the step.

Expected result:
- `check` should be able to report weaker or partial preflight support for that step;
- `check` must not upgrade the missing advisory observation into an executability failure by itself;
- any author-facing guidance should identify which recommended observation shape is absent.

Why this matters:
- the point of advisory metadata is to strengthen explanation quality without creating hidden prerequisites;
- otherwise connector-authored hints would silently become policy gates;
- both humans and agents need to distinguish inapplicability from weak preflight support.

Failure meaning:
- a failure here means advisory metadata has leaked into executability semantics;
- authors and agents would lose trust in `check` because suggestions would behave like undocumented blockers.

## HYP-CHECK-008 — Rendered recommendations should prefer workflow expressions over one-shot values

Related normative rules:
- `CHECK-MODE-014`

Scenario shape:
- an effectful step argument is supplied through a workflow expression such as `inputs.foo`, `state.bar`, or an early `let` binding;
- the action metadata declares a recommended preflight-observation template that references that action argument.

Expected result:
- when `check` renders author-facing guidance, it should prefer the workflow expression currently supplying that action argument;
- if no such expression is available, a fallback surface may still be shown, but expression-shaped guidance is preferred.

Why this matters:
- recommendations are more actionable when they resemble the authored workflow structure;
- long rendered expressions remain an authoring-quality signal rather than a reason for runtime to invent prettier names;
- agents can repair workflows more directly when recommendations are phrased in workflow terms.

Failure meaning:
- a failure here means `check` guidance is less actionable than it could be;
- the system would push users toward ephemeral run-instance values instead of durable workflow structure.

## HYP-CHECK-009 — Recommended-observation coverage must not rely on heuristic equivalence

Related normative rules:
- `CHECK-MODE-015`

Scenario shape:
- an action declares a recommended preflight-observation template;
- the workflow has already established a similar-looking observation before that step;
- the two observation shapes differ by argument expression, selected field path, or canonical probe form.

Expected result:
- `check` must treat the recommendation as covered only when the canonical shapes match exactly after rendering action-argument expressions;
- `check` must not mark the recommendation as covered because the values happen to look equal in one run or because the expressions appear semantically close;
- if exact structural matching is unavailable, `check` should leave the recommendation missing or unknown rather than guessing.

Why this matters:
- deterministic exact matching is more trustworthy than clever-looking heuristics in a structured workflow system;
- false-positive coverage would make `check` hide missing observations precisely where author guidance is needed most;
- this keeps the burden of naming or normalizing important expressions in workflow authoring rather than in speculative runtime inference.

Failure meaning:
- a failure here means `check` has started inventing equivalence classes it cannot actually prove;
- recommendation coverage would then become surprising, unstable, and hard to debug.

<!-- source: verification/runtime/introspection-drift.md -->

# Verification for introspection drift

## Rule

If a runtime-visible surface changes, the published introspection surface must change in the same work.

## Runtime-visible surface

At minimum this includes:

- root discovery surface;
- workflow contract surface;
- playbook contract surface;
- capability states exposed to tools;
- expression roots, filters, builtins, and allowed surfaces;
- public operation metadata exposed for machine-readable consumption.

## Source-of-truth rule

Introspection must be assembled from runtime-owned metadata or from canonical contract data owned by the runtime-facing product layer.

Prose documents must not be the source of truth for published introspection.

## Enforcement expectations

The project must verify, at minimum:

- published introspection is machine-readable;
- published introspection is versioned;
- covered runtime-visible surface changes fail verification when introspection is not updated;
- parity checks detect drift between runtime-owned metadata and published introspection output.

## Review rule

A change that widens, narrows, renames, removes, or reclassifies a covered runtime-visible surface is incomplete unless the corresponding introspection and verification updates are included in the same work.

<!-- source: verification/runtime/invariants.md -->

# Invariants

## Core invariants

- unknown fields fail validation
- unknown operations fail resolution
- workflow holds orchestration, not algorithmic implementation
- structured result is required
- `check`, `plan`, `execute`, and `explain` are baseline runtime modes
- blocked-before-execution is distinct from execution failure
- runtime explanation is a structured surface, not merely logs or tracebacks
- runtime remains analysis-first rather than execute-first
- runtime is usable as a machine-readable decision surface, not only as an execution entrypoint
- contract-level runtime structures are losslessly JSON-serializable
- runtime decision surfaces remain machine-readable without format-specific parsing beyond standard JSON data handling

## Drift rule

If a change breaks any invariant, `meta/` must be updated explicitly in the same work.

<!-- source: verification/meta/packs.md -->

# Pack verification

## Rule

Generated files under `meta/packs/` must never be edited by hand.

Regenerate packs with `python3 tools/build_domain_packs.py meta/domain-packs.toml`.

## Check mode

The pack builder must support a `--check` mode that fails when generated output differs from committed output.

Verification command:

`python3 tools/build_domain_packs.py meta/domain-packs.toml --check`
