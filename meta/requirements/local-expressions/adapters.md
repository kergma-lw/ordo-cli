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
