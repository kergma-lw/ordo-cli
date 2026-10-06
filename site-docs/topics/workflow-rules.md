# Workflow rules

Author workflows that are explicit, reviewable, and safe to validate before execution.

Use these rules when adding, changing, or reviewing workflow authoring choices.

## Default loop

- After changing a workflow, run both check and review.
- Declare applicability and validate inputs near the start.
- Keep published outputs small and intentional.

## Rules



### Use both check and review

After adding or changing a workflow, run both ordo-playbook check <workflow> and ordo-playbook review <workflow>. Treat them as complementary check/review passes, not substitutes.



#### Why

- check answers whether the workflow is applicable and execution-ready now
- review answers whether the workflow still has workflow-quality findings
- using both makes it harder to mistake execution readiness for workflow completeness

#### Prefer

- use check to surface guard, explicit probe-coverage, and applicability gaps
- use review to surface workflow-quality findings
- report both results when presenting workflow changes as complete

#### Avoid

- treating check as sufficient workflow sign-off
- treating review as optional polish after the real validation is done
- skipping one pass because the other already returned clean results

### Keep workflow profiles project-local

Use top-level workflow.profile only when one workflow is intentionally bound to one project-local execution profile. Treat it as a restrictive local binding, not as the default reusable pattern.



#### Why

- workflow.profile binds execution context before guards and therefore changes the workflow's activation contract
- hard-binding one workflow to one named profile reduces portability across playbooks and projects
- the binding scopes to the current workflow subtree, so it is appropriate only when that local execution contract is intentional

#### Prefer

- prefer playbook-owned or caller-selected profile activation for portable workflows
- use workflow.profile only for internal or project-bound workflows whose meaning depends on one execution profile
- treat descendant workflow.profile declarations as subtree-local overrides rather than as caller-wide mutations

#### Avoid

- using workflow.profile merely as a convenience default for otherwise reusable workflows
- assuming workflow.profile should leak upward into the caller workflow after a nested run returns
- treating workflow.profile and profile_switch as the same authoring surface

### Publish only the result callers need

Treat extra publish fields as an authoring smell. If one field is not needed by the caller or by a downstream workflow to make a decision, do not publish it.



#### Why

- compact published outputs are easier to read, review, and trust
- copying large action outputs into publish by default turns success payloads into noise
- local agent or project rules may intentionally require an even smaller success surface

#### Prefer

- publish the smallest useful confirmation surface such as a summary, url, issue_ref, or compact identifier
- keep extra detail in step-local outputs unless a user or downstream workflow truly needs it to make a decision
- prefer one sufficient outward-facing identifier instead of several overlapping confirmation fields
- prefer a compact result such as summary + url over broader confirmation bundles
- follow stricter local payload rules when the project or agent guidance defines them

#### Avoid

- mirroring full action outputs into publish just because those fields are available
- treating publish as a general-purpose debug dump
- adding outward-facing fields that the caller did not ask for and downstream steps do not need
- publishing repository, issue_number, changed, closed, or similar step-level confirmation fields when url or issue_ref already identifies the result sufficiently
- using summary + repository + issue_number + changed + closed + url when summary + url already communicates the outcome

### Stage reusable values before results

Use value + register when a built payload must be reused by later steps. Use result only to append one workflow-local result value, not to create a reusable named binding.



#### Why

- result is an output channel for the workflow-local results list rather than a step-local variable-binding surface
- value + register gives later steps one explicit reusable read path through step.<register>.outputs.value
- separating payload staging from payload emission keeps workflow dataflow easier to read and review

#### Prefer

- stage reusable assembled payloads with value + register
- emit the staged value later through result or publish when the workflow also needs a final output
- treat step.<register>.outputs.value as the reusable read surface for staged workflow-owned payloads

#### Avoid

- treating result as a named intermediate storage surface
- expecting result to support register or to create step.<register> reads
- collapsing payload construction and payload emission into one result step when later steps still need the payload

### Choose the most structured surface first

Choose the most structured public surface that can express the intent, and move to coarser fallbacks only after exhausting direct and composed public operations.



#### Why

- a fixed decision order reduces ad hoc shortcutting and makes implementation choices easier to explain
- starting from the public model keeps workflow behavior aligned with published product semantics
- treating fallback as a late-stage decision makes missing capabilities easier to identify explicitly

#### Prefer

- check whether one published public operation already fits
- otherwise check whether multiple published public operations can be composed cleanly
- name the exact missing capability or semantic gap before considering a fallback
- ask the user before introducing a fallback when the remaining gap is semantic rather than merely mechanical

#### Avoid

- jumping to the nearest working mechanism before checking the structured public surface
- treating composition as unnecessary just because one direct operation does not exist
- treating unclear semantics as permission to improvise a fallback

### Prefer structured workflow surfaces

Prefer implementations that express product intent through typed public workflow surfaces.



#### Why

- typed public surfaces are easier to validate, inspect, and explain across check, plan, explain, and run
- structured implementations are less likely to encode accidental machine-local or repository-local behavior
- a workflow is better not merely because it works, but because its intent stays legible in product terms

#### Prefer

- optimize for product-legible workflow intent, not just immediate execution success
- prefer narrower typed operations over broader execution surfaces when both can do the job

#### Avoid

- optimizing for the first mechanism that appears to work
- choosing a broader surface merely because it is familiar or nearby

### Avoid new shell commands

shell.command is forbidden as a workflow authoring surface. Do not use it for new authoring work.



#### Why

- shell.command is the coarsest and riskiest legacy execution surface
- arbitrary inline shell makes workflows harder to validate, explain, and keep environment-stable
- a published project-local helper is more reviewable than inline shell text

#### Prefer

- prefer published connector operations first
- prefer published routine.<id> entries over any legacy shell fallback when a small project-local helper is still necessary
- treat any remaining shell.command mention as migration or compatibility work rather than a valid new design choice

#### Avoid

- introducing new shell.command steps in workflows
- treating shell.command as an acceptable shortcut just because it already exists in older material
- using shell.command to avoid publishing a routine or discussing a richer missing connector surface

#### Stop when

- the proposed authoring change still depends on adding a new shell.command step
- the only argument for shell.command is speed, familiarity, or historical precedent

### Use routines only as a narrow fallback

Use routine.* only for a narrow project-local task after published operations and clear compositions do not fit.



#### Why

- A routine can hide product behavior that belongs in a published workflow surface.
- Frequent routine use is a signal to discuss a richer published operation.

#### Prefer

- Record which published operations and compositions were considered and what small gap remains.
- Use routine.* only for a mechanical or intentionally project-local gap.
- If the gap is semantic, stop and clarify with the user.
- Keep routine usage narrow and explicit about its inputs and outputs.

#### Avoid

- Using routine.* as a first-choice tool.
- Using routine.* when a structured connector surface already exists.
- Treating routine.* as a general extension surface.

#### Stop when

- no explicit capability-gap statement has been made
- the remaining gap is semantic rather than mechanical or intentionally project-local
- routine.* is being chosen mainly because it is faster, familiar, or already available locally
- routine.* is starting to look like the default implementation path rather than a narrow exception

### Clarify semantic ambiguity

Treat semantic ambiguity as a stop signal for clarification, not as permission to invent or preserve semantics silently.



#### Why

- silent semantic invention makes workflows surprising and hard to trust later
- asking at the semantic boundary is safer than hard-coding assumptions as if they were product truth
- clarified semantics produce workflows that are more stable for later authors and agents

#### Prefer

- ask when the public surface is almost sufficient but one semantic edge remains unclear
- separate mechanical gaps from semantic gaps before choosing an implementation strategy

#### Avoid

- guessing what an unclear public surface probably means
- preserving nearby local helper semantics by default when the product contract is unclear

### Treat local artifacts as context

Treat repository-local scripts, helpers, and conventions as context, not as the default source of truth.



#### Why

- local artifacts may reflect convenience, history, or workaround pressure rather than the preferred product model
- defaulting to repository-local helpers encourages imitation of incidental behavior instead of deliberate workflow design
- preferring the declared public model over local history keeps workflows more portable and explainable
- local scripts often encode repository-specific semantics that should not become product truth by accident

#### Prefer

- use local artifacts to learn context, constraints, or missing capability signals
- prefer declared public contracts over incidental repository habits when choosing the workflow surface
- treat local scripts as evidence of possible user intent or product-surface gaps, not as implementation approval
- when local behavior contains semantics absent from the public model, narrow the workflow contract or ask the user

#### Avoid

- treating the existence of a local script as sufficient reason to make it the workflow implementation surface
- copying repository-local behavior into a workflow without checking whether it matches the public model
- inferring that a repository-local script defines preferred workflow semantics
- wrapping a local helper in routine.* just because it already works in this repository
- preserving local script semantics silently when those semantics are not published in the public workflow model

#### Do not infer

- there is a script for this => routine.* is acceptable here
- the repo already does it this way => this is the correct workflow contract
- a local helper covers the semantic gap => no clarification is needed

### Declare applicability early

Express workflow applicability near the start of the workflow, not as a late discovery during action execution.



#### Why

- early guards improve execution safety and make workflow applicability explicit
- early guards improve check, plan, and explain readability
- guard-rich workflows help next prefer workflows that are actually relevant now
- without guards, Ordo degrades toward being just a runner

#### Prefer

- put applicability checks near the top of the workflow
- for non-trivial workflows, phase guards in a stable order such as environment applicability, input validation, domain invariants, and structural preconditions
- when adding or changing workflow inputs, use allowed_values for a fixed set of strings; validate all other input shape and contextual requirements at the guard boundary before moving on to downstream steps
- when workflow success depends on an externally observable fact and a public probe surface can read it, prefer explicit guard probes; use read-only probe steps only when the observed fact must be reused later or a guard probe is not a good fit
- use input-validation filters such as value | is_string, value | is_number, value | is_integer, value | is_boolean, value | in(...), value | eq(...), and value | ne(...) when they make the input contract more explicit
- design guards so check and explain can name domain inapplicability before any mutating step runs
- run ordo-playbook check <workflow> while authoring to surface missing recommended explicit probe coverage or likely guard gaps whenever the current workflow shape makes those recommendations possible
- reject inapplicable situations early instead of failing deep inside execution

#### Avoid

- delaying obvious applicability checks until late steps
- letting non-trivial applicability checks collapse into one unreadable undifferentiated guard mass
- relying on late failures when the workflow could declare inapplicability up front
- treating action-local preflight or downstream action failure as the workflow's main applicability model

### Validate inputs by default

Treat input validation as a default authoring step whenever you introduce or modify workflow inputs.



#### Why

- new inputs silently widen workflow semantics unless their admissible shapes are declared near the top of the workflow
- validation guards are easier for agents and later authors to notice and preserve than downstream step failures
- type-valid input does not by itself make a workflow applicable
- neighboring workflows may be incomplete examples, so copied omissions should not become the next default

#### Prefer

- when introducing or changing any workflow input, pause and decide how that input is validated before continuing with step authoring
- add an early guard for each new or changed input whenever a public validation surface exists
- for a fixed set of string values, declare allowed_values on the input; for other string inputs prefer value | is_string; for numbers prefer value | is_number or value | is_integer; for booleans prefer value | is_boolean; use guards for contextual or non-string constraints
- after validating input shape, separately decide which observed preconditions make the workflow applicable to the current target context
- if no suitable public validation surface exists, name that exact gap explicitly instead of silently omitting validation
- treat existing workflows as style references, not as waivers for missing input validation

#### Avoid

- copying a neighboring workflow's missing validation into new authoring work
- introducing a new input and only discovering bad values inside downstream operations
- treating request-shape validation as a substitute for validating target compatibility or workflow applicability
- assuming that a repeated local pattern is automatically the preferred authoring contract

### Do not defer applicability to actions

Do not delegate workflow applicability to downstream action validation when the public surface can express the relevant precondition earlier.



#### Why

- workflow applicability should be reviewable in workflow structure rather than hidden inside one action's failure path
- when applicability lives only inside an action, check and explain become less able to justify why the workflow should not run
- late applicability discovery encourages cargo-cult copying of steps that happen to work in one repository state

#### Prefer

- treat action-local validation as a safety net, not as the primary way to declare whether the workflow applies now
- if a public probe surface exists for the relevant precondition, prefer an explicit guard probe and guard on the observed fact; use a read-only probe step only when that fact must be reused later or guard syntax is not a good fit
- if no public probe surface exists, name that exact capability gap instead of silently treating late failure as acceptable default behavior

#### Avoid

- assuming that a successful action preflight makes an explicit workflow guard unnecessary
- letting the first clear signal of inapplicability appear only when a mutating step starts
- treating downstream validation as sufficient merely because a neighboring workflow already does so

### Use representation adapters for transformations

Prefer representation adapters for transformations that feed guards, conditions, and published results.



#### Why

- representation adapters can simplify transformations that would otherwise become awkward inline expressions
- adapter-based workflows are often clearer than ad hoc string-shaping inside guards, conditions, and result publication
- adapters help keep structured workflow intent visible during check, plan, explain, and run

#### Prefer

- use adapters when text or markdown projections make a downstream decision or published value clearer
- in guard context, prefer read-only adapter projections and keep adapter write paths such as ->... out of guard logic
- express adapter root binding with pipe-style syntax when an equivalent pipe form exists
- keep transformations close to the structured adapter surface instead of re-encoding them manually

#### Avoid

- hand-rolling repetitive transformations in raw inline expressions when an adapter surface already matches the need
- using with{root: ...} when the same adapter binding can be expressed with pipe-style syntax
- using adapter write paths such as ->... inside guards
- ignoring published adapter families when they would make guard, condition, or publish logic easier to read

#### Stop when

- a with{root: ...} form is being introduced before checking whether the same binding works as a pipe-style adapter expression

### Make guard decisions boolean

A guard expression must evaluate to a boolean result.



#### Why

- guard success and failure are defined by boolean policy outcomes rather than arbitrary value production
- a strict boolean result keeps guard behavior readable across check, plan, explain, and execute

#### Prefer

- use filters, comparisons, builtins, and read-only adapters only when they clearly contribute to a final boolean guard result
- treat a successful non-boolean guard result as a workflow error to fix rather than as truthy or falsy shorthand

#### Avoid

- authoring guards that merely produce a string, number, list, or object without an explicit boolean decision
- relying on implicit truthiness instead of an explicit boolean result

### Publish intentional outward results

Prefer publish: for intentional outward-facing workflow results.



#### Why

- explicit published outputs make workflow intent clearer
- explicit published outputs keep success payloads focused
- fallback-only success output is a weak outward-facing contract

#### Prefer

- publish the final values that downstream readers are meant to consume
- use publish: when the workflow is meant to communicate a meaningful result beyond internal execution

#### Avoid

- leaving important final outputs implicit when the workflow is meant to communicate something downstream
- relying on fallback-only success output as the main outward-facing result contract

### Keep lifecycle state small

Use state when multiple workflows represent stages of one lifecycle, and keep stored state small.



#### Why

- state is most justified as durable coordination context across related workflow stages
- small state is easier to understand, repair, and keep consistent
- large state payloads turn hidden persistence into a brittle general-purpose cache

#### Prefer

- store minimal durable context such as active profile, current entity identity, or compact lifecycle markers
- prefer explicit inputs, lets, and published outputs over state when the data does not need cross-workflow persistence

#### Avoid

- using state as the default dataflow mechanism between unrelated workflows
- writing large payloads or easily re-fetchable remote data into state as a matter of course

### Make execution context explicit

Prefer workflows whose execution context is explicit. Do not rely on hidden ambient environment requirements inside workflow logic.



#### Why

- hidden environment assumptions make workflows brittle
- explicit execution context is easier to explain, validate, and reuse
- workflows are easier for agents to author correctly when required context is visible

#### Prefer

- express special execution setup through routines, profiles, or explicit guards
- fail early when required execution context is missing

#### Avoid

- assuming shell bootstrap has already happened outside the workflow
- embedding silent dependence on preloaded tools, environment variables, or working-directory conventions
- making a workflow succeed only under undocumented machine-local setup

### Give each control surface one job

Use each conditional surface for its own job: guards for workflow applicability and early rejection, gates for whether a path or step may run at all, configuration for stable context variation, and if: when one local step or local branch is optional inside an already-valid path.



#### Why

- mixing these roles makes workflows harder to read and harder to explain
- hidden applicability inside step conditions weakens workflow selection and safety
- using if: as a substitute for guards, gates, configuration, or workflow structure leads to brittle branching logic

#### Prefer

- use guards for conditions that determine whether the workflow should run at all or should narrow applicability early
- use gates when the real question is whether a path or step may execute at all
- use inputs, profiles, and reusable fragments for stable context-specific variation
- use if: only when one local step or local branch is optional inside an already applicable workflow

#### Avoid

- hiding workflow inapplicability inside late step-level if: conditions
- using if: for admission, readiness, or coarse path routing when guards or gates carry that meaning more honestly
- expressing broad context variation through many ad hoc if: branches
- cloning or rewriting workflows when explicit configuration would preserve one stable behavior shape

### Keep fan-out as structured invocation

Treat bounded fan-out as a structured invocation surface, not as a general control-flow language.



#### Why

- bounded fan-out should stay visible as one author-facing workflow step
- structured repetition is easier to validate, explain, and review than flattened ad hoc repetition
- keeping repetition on the invocation surface preserves clearer check, plan, and explain output

#### Prefer

- use for_each only on one invocation-shaped step
- keep one explicit outer step that owns the repeated work
- use the outer register only for aggregated per-item results

#### Avoid

- treating for_each as a general looping primitive
- flattening repeated work into an unstructured sequence of top-level steps
- encoding repeated control flow in a way that hides the outer repeated step from analysis surfaces

#### Stop when

- the proposed repeated shape no longer reads as one explicit invocation step
- the workflow starts to depend on nested repetition or other control-flow expansion not supported by the public model

### Choose named targets for substantial fan-out

Use a named run target for reusable, guard-bearing, or non-trivially sized repeated bodies. Use inline repeated steps only for short local repeated bodies.



#### Why

- named run targets keep reusable repeated logic easier to name, review, and evolve
- inline repeated steps stay readable only while the repeated body remains small, linear, and workflow-local
- fragment-local guards belong in reusable workflow fragment material, not inside inline repeated bodies

#### Prefer

- use inline steps + for_each for one or two short local repeated steps
- allow three or four inline repeated steps only when the body is linear, local, and unlikely to be reused
- use run + for_each when the repeated body already exists as reusable workflow fragment material
- use run + for_each when the repeated body needs fragment-local guards
- use run + for_each when the repeated body has its own clear domain purpose or reuse value

#### Avoid

- keeping a large repeated body inline merely because it currently works
- keeping reusable repeated logic inline when a named run target would express the intent more honestly
- trying to place guards inside an inline repeated body
- using inline repeated steps for bodies that are already large, branchy, or semantically reusable

#### Stop when

- the inline repeated body grows to five or more steps
- the inline repeated body needs fragment-local guards
- the inline repeated body becomes branchy or hard to review as one local repeated action
- the same repeated body is now needed in another workflow
- the repeated body needs its own explicit name or argument contract

### Keep fan-out scope and conditions explicit

Author bounded fan-out with explicit scope boundaries: outer if gates the whole repeated step, inner if applies per iteration, and inline repeated bodies keep iteration-local scope only.



#### Why

- explicit scope boundaries make repeated workflows easier to reason about
- outer and inner conditions answer different questions and should not be conflated
- iteration-local register scope prevents accidental cross-item coupling

#### Prefer

- use the outer if when the entire repeated step should be skipped
- use inner step if only for item-local branching inside inline repeated steps
- treat item as iteration-local input
- treat inner step registers as visible only within the same iteration body
- treat the outer register as the only caller-visible aggregate result surface for inline repeated work

#### Avoid

- assuming that an inner if can replace the whole-step gate of the outer if
- assuming that one iteration can read another iteration's inner registers
- assuming that inline repeated bodies support nested guards
- assuming that nested for_each is a valid repeated-body shape

#### Stop when

- the repeated body now depends on nested guards
- the repeated body now depends on nested for_each
- the proposed design assumes cross-iteration visibility of inner step registers

### Stay within the inline fan-out shape

Keep inline bounded fan-out inside the published shape: for_each must be array-valued, nested for_each is invalid, nested guards are invalid, and outer with belongs only to named run targets.



#### Why

- explicit invalid-shape reminders help agents stop before drifting outside the public workflow model
- inline repeated bodies are intentionally narrower than named run targets
- shape errors are easier to avoid when the forbidden combinations are stated directly in authoring guidance

#### Prefer

- use a named run target when repeated item processing needs guard blocks
- keep inline repeated bodies as step lists only
- treat for_each as one array-valued repeated-item source

#### Avoid

- placing guards inside an inline repeated body
- adding nested for_each inside the repeated body
- using outer with on inline repeated steps
- assuming that any non-array for_each source is valid repeated input

#### Stop when

- the proposed inline repeated body now needs guards
- the proposed repeated shape introduces nested for_each
- the proposed inline step needs outer with bindings instead of local step inputs or item scope

### Name important expressions early

Prefer an early let block when the workflow uses long, repeated, or semantically important expressions.



#### Why

- named bindings shorten long fragments and reduce repetition
- named bindings improve readability across check, plan, explain, and run surfaces
- early let bindings make workflow intent easier to scan

#### Prefer

- name important values early
- bind repeated or hard-to-scan expressions once and reuse them

#### Avoid

- repeating the same long inline expression across multiple guards or steps
- hiding important intent inside one-off inline expressions when a stable let binding would clarify it

### Use native expression contexts directly

Prefer bare expressions in native and expression-first value contexts such as let:, with:, value:, publish:, result:, and for_each. For bare step if:, use either a compact expression or an equal-authority structured all/any/not form. When a step condition compares more than three predicates, require structured condition form instead of one long boolean string. Quote literal strings explicitly. Do not rely on expression-looking bare values silently falling back to literal text when evaluation fails.



#### Why

- bare expressions reduce visual noise across the workflow surfaces that are usually expression-driven
- quoted literals make string intent explicit without forcing the common expression case through an extra envelope
- using one bare-first value model across with, value, publish, result, and for_each keeps authored workflow dataflow easier to scan
- fail-closed expression evaluation keeps author intent visible instead of silently reinterpreting a broken expression as plain text
- structured step conditions stay reviewable once predicate count grows beyond a small compact expression

#### Prefer

- write let bindings as bare expressions
- write short step if conditions without ${...}
- rewrite step if conditions into structured all/any/not form when more than three predicates are being compared
- write with, value, publish, result, and for_each entries as bare expressions when they are meant to evaluate
- quote literal strings explicitly when a value-bearing field should preserve raw text
- treat runtime evaluation failure in a bare expression as a real error to fix rather than a cue to keep the bare form as text
- use ${...} only when YAML would otherwise read the expression as YAML syntax rather than as one expression; for example, quote `${inputs.title}` when the surrounding YAML position cannot safely hold the bare expression

#### Avoid

- wrapping native expression contexts in ${...} just by habit
- using ${...} in value-bearing fields that now prefer bare expressions
- packing more than three step-condition predicates into one boolean string
- leaving intended string literals unquoted in expression-first value-bearing fields
- depending on a broken bare expression to degrade into a literal string at runtime
