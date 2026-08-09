"""Public CLI entrypoint for ordo-help discovery."""

from __future__ import annotations

import argparse
import json
import re
import sys

from ordo.connectors import get_public_connector_registry
from ordo.introspection import (
    describe_capabilities,
    describe_examples_catalog,
    describe_operations,
    describe_playbook_contract,
    describe_profile_contract,
    describe_routine_contract,
    describe_state_contract,
    describe_system,
    describe_workflow_contract,
)
from ordo.runtime.representation_adapters import describe_representation_adapter_surface
from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_FILTERS
from ordo.model.runtime import Mode, RuntimeStatus
from ordo.model.json import JSONObject


PUBLIC_TOPICS: tuple[dict[str, str], ...] = (
    {"name": "overview", "summary": "Start with the Ordo world map"},
    {"name": "model", "summary": "Inspect the main authoring contracts"},
    {"name": "workflow-authoring", "summary": "Inspect preferred workflow authoring patterns, paired check/review passes, routine cautions, early guards, and let usage"},
    {"name": "capabilities", "summary": "Inspect supported and unsupported surfaces"},
    {"name": "command-line", "summary": "Inspect the public command-line launch surface, including distinct check and review roles"},
    {"name": "operations", "summary": "Inspect the public connector catalog"},
    {"name": "examples", "summary": "Inspect verified repository examples"},
    {"name": "operation", "summary": "Inspect one public operation by reference"},
    {"name": "describe", "summary": "Resolve a supported public topic"},
    {"name": "search", "summary": "Search topics, contract facts, and operation references"},
)

_SEARCH_TOKEN_RE = re.compile(r"[a-z0-9_.#:/-]+")

DESCRIBABLE_TOPICS: tuple[str, ...] = ("overview", "model", "workflow-authoring", "capabilities", "command-line", "operations", "examples")

RECOMMENDED_FIRST_CALLS: tuple[dict[str, str], ...] = (
    {"command": "ordo-help overview --json", "purpose": "Get the Ordo world map"},
    {"command": "ordo-help model --json", "purpose": "Learn the main DSL surfaces"},
    {"command": "ordo-help workflow-authoring --json", "purpose": "Learn preferred workflow authoring patterns, including paired check/review passes"},
    {"command": "ordo-help capabilities --json", "purpose": "Learn capability boundaries"},
    {"command": "ordo-help command-line --json", "purpose": "Inspect public launch commands, flags, and distinct check/review roles"},
    {"command": "ordo-help operations --json", "purpose": "Inspect the public operation catalog"},
    {"command": "ordo-help examples --json", "purpose": "Inspect verified repository examples"},
)

WORKFLOW_AUTHORING_RULES: tuple[dict[str, object], ...] = (
    {
        "name": "paired_authoring_passes",
        "priority": "critical_authoring_loop",
        "guidance_level": "required_default",
        "rule": "After adding or changing a workflow, run both ordo-playbook check <workflow> and ordo-playbook review <workflow>. Treat them as complementary authoring passes, not substitutes.",
        "why": [
            "check answers whether the workflow is applicable and execution-ready now",
            "review answers whether the workflow still has authoring-quality findings",
            "using both makes it harder to mistake execution readiness for authoring completeness",
        ],
        "prefer": [
            "use check to surface guard, explicit probe-coverage, and applicability gaps",
            "use review to surface workflow authoring-quality findings",
            "report both results when presenting workflow changes as complete",
        ],
        "avoid": [
            "treating check as sufficient workflow-authoring sign-off",
            "treating review as optional polish after the real validation is done",
            "skipping one pass because the other already returned clean results",
        ],
    },
    {
        "name": "minimal_publish_payload",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Treat extra publish fields as an authoring smell. If one field is not needed by the caller or by a downstream workflow to make a decision, do not publish it.",
        "why": [
            "compact published outputs are easier to read, review, and trust",
            "copying large action outputs into publish by default turns success payloads into noise",
            "local agent or project rules may intentionally require an even smaller success surface",
        ],
        "prefer": [
            "publish the smallest useful confirmation surface such as a summary, url, issue_ref, or compact identifier",
            "keep extra detail in step-local outputs unless a user or downstream workflow truly needs it to make a decision",
            "prefer one sufficient outward-facing identifier instead of several overlapping confirmation fields",
            "prefer a compact result such as summary + url over broader confirmation bundles",
            "follow stricter local payload rules when the project or agent guidance defines them",
        ],
        "avoid": [
            "mirroring full action outputs into publish just because those fields are available",
            "treating publish as a general-purpose debug dump",
            "adding outward-facing fields that the caller did not ask for and downstream steps do not need",
            "publishing repository, issue_number, changed, closed, or similar step-level confirmation fields when url or issue_ref already identifies the result sufficiently",
            "using summary + repository + issue_number + changed + closed + url when summary + url already communicates the outcome",
        ],
    },
    {
        "name": "value_register_before_result",
        "priority": "critical_scope_boundary",
        "guidance_level": "required_default",
        "rule": "Use value + register when a built payload must be reused by later steps. Use result only to append one workflow-local result value, not to create a reusable named binding.",
        "why": [
            "result is an output channel for the workflow-local results list rather than a step-local variable-binding surface",
            "value + register gives later steps one explicit reusable read path through step.<register>.outputs.value",
            "separating payload staging from payload emission keeps workflow dataflow easier to read and review",
        ],
        "prefer": [
            "stage reusable assembled payloads with value + register",
            "emit the staged value later through result or publish when the workflow also needs a final output",
            "treat step.<register>.outputs.value as the reusable read surface for staged workflow-owned payloads",
        ],
        "avoid": [
            "treating result as a named intermediate storage surface",
            "expecting result to support register or to create step.<register> reads",
            "collapsing payload construction and payload emission into one result step when later steps still need the payload",
        ],
    },
    {
        "name": "decision_order",
        "priority": "critical_decision_policy",
        "guidance_level": "strong_recommendation",
        "rule": "Choose the most structured public surface that can express the intent, and move to coarser fallbacks only after exhausting direct and composed public operations.",
        "why": [
            "a fixed decision order reduces ad hoc shortcutting and makes implementation choices easier to explain",
            "starting from the public model keeps workflow behavior aligned with published product semantics",
            "treating fallback as a late-stage decision makes missing capabilities easier to identify explicitly",
        ],
        "prefer": [
            "check whether one published public operation already fits",
            "otherwise check whether multiple published public operations can be composed cleanly",
            "name the exact missing capability or semantic gap before considering a fallback",
            "ask the user before introducing a fallback when the remaining gap is semantic rather than merely mechanical",
        ],
        "avoid": [
            "jumping to the nearest working mechanism before checking the structured public surface",
            "treating composition as unnecessary just because one direct operation does not exist",
            "treating unclear semantics as permission to improvise a fallback",
        ],
    },
    {
        "name": "structured_surface_bias",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Prefer implementations that express product intent through typed public workflow surfaces.",
        "why": [
            "typed public surfaces are easier to validate, inspect, and explain across check, plan, explain, and run",
            "structured implementations are less likely to encode accidental machine-local or repository-local behavior",
            "a workflow is better not merely because it works, but because its intent stays legible in product terms",
        ],
        "prefer": [
            "optimize for product-legible workflow intent, not just immediate execution success",
            "prefer narrower typed operations over broader execution surfaces when both can do the job",
        ],
        "avoid": [
            "optimizing for the first mechanism that appears to work",
            "choosing a broader surface merely because it is familiar or nearby",
        ],
    },
    {
        "name": "shell.command",
        "priority": "critical_caution",
        "guidance_level": "forbidden",
        "rule": "shell.command is forbidden as a workflow authoring surface. Do not use it for new authoring work.",
        "why": [
            "shell.command is the coarsest and riskiest legacy execution surface",
            "arbitrary inline shell makes workflows harder to validate, explain, and keep environment-stable",
            "routine publication now provides a more reviewable bounded local-automation surface than inline shell text",
        ],
        "prefer": [
            "prefer published connector operations first",
            "prefer published routine.<id> entries over any legacy shell fallback when bounded project-local automation is still necessary",
            "treat any remaining shell.command mention as migration or compatibility work rather than a valid new design choice",
        ],
        "avoid": [
            "introducing new shell.command steps in workflows",
            "treating shell.command as an acceptable shortcut just because it already exists in older material",
            "using shell.command to avoid publishing a routine or discussing a richer missing connector surface",
        ],
        "stop_when": [
            "the proposed authoring change still depends on adding a new shell.command step",
            "the only argument for shell.command is speed, familiarity, or historical precedent",
        ],
    },
    {
        "name": "routine.*",
        "priority": "critical_caution",
        "guidance_level": "strong_restriction",
        "rule": "routine.* is a bounded opaque local-automation exception surface, not a normal extension path. Use it only after explicitly proving that no published structured workflow surface can express the required behavior more honestly.",
        "why": [
            "routine.* can still hide project-local semantics that should not silently become product truth",
            "routine publication is safer than inline shell but still acts as a controlled fallback rather than a rich public domain model",
            "routine-heavy workflows can hide missing connector surface that should be discussed explicitly",
            "a partial public-surface match is not permission to encode the semantic remainder in a routine",
            "routine fallback changes the workflow contract, not just its implementation detail",
            "routine.* is an exception path, so frequent routine use is itself a design smell",
        ],
        "prefer": [
            "check whether one published public operation fits directly",
            "otherwise check whether multiple published public operations compose cleanly",
            "before using routine.*, explicitly name which published operations were considered, why no direct operation fits, why no clean composition fits, and what exact capability gap remains",
            "use routine.* only when the remaining gap is mechanical or intentionally project-local rather than semantic",
            "if the remaining gap is semantic, stop and clarify with the user instead of preserving semantics through routine.*",
            "keep routine usage narrow, reviewable, and easy to reason about",
            "when a routine needs ambient caller context, forward it through with.env as a short explicit list of scalar references rather than as broad implicit environment mirroring",
            "treat repeated routine usage as pressure to discuss richer connector publication",
        ],
        "avoid": [
            "using routine.* as a first-choice implementation tool",
            "using routine.* for inspection, transformation, or orchestration when structured connector surfaces already exist",
            "using routine.* to wrap repository-local automation without first exhausting public operations",
            "using routine.* merely because a nearby local script already implements something similar",
            "bridging a partial public-surface match with routine.* without explicit justification",
            "silently preserving repository-local semantics through routine.* when the public model does not define those semantics",
            "treating routine.* as a cheerful general extension API",
        ],
        "stop_when": [
            "no explicit capability-gap statement has been made",
            "the remaining gap is semantic rather than mechanical or intentionally project-local",
            "routine.* is being chosen mainly because it is faster, familiar, or already available locally",
            "routine.* is starting to look like the default implementation path rather than a narrow exception",
        ],
    },
    {
        "name": "semantic_ambiguity",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Treat semantic ambiguity as a stop signal for clarification, not as permission to invent or preserve semantics silently.",
        "why": [
            "silent semantic invention makes workflows surprising and hard to trust later",
            "asking at the semantic boundary is safer than hard-coding assumptions as if they were product truth",
            "clarified semantics produce workflows that are more stable for later authors and agents",
        ],
        "prefer": [
            "ask when the public surface is almost sufficient but one semantic edge remains unclear",
            "separate mechanical gaps from semantic gaps before choosing an implementation strategy",
        ],
        "avoid": [
            "guessing what an unclear public surface probably means",
            "preserving nearby local helper semantics by default when the product contract is unclear",
        ],
    },
    {
        "name": "local_artifacts_are_context",
        "priority": "recommended_caution",
        "guidance_level": "strong_restriction",
        "rule": "Treat repository-local scripts, helpers, and conventions as context, not as the default source of truth.",
        "why": [
            "local artifacts may reflect convenience, history, or workaround pressure rather than the preferred product model",
            "defaulting to repository-local helpers encourages imitation of incidental behavior instead of deliberate workflow design",
            "preferring the declared public model over local history keeps workflows more portable and explainable",
            "local scripts often encode repository-specific semantics that should not become product truth by accident",
        ],
        "prefer": [
            "use local artifacts to learn context, constraints, or missing capability signals",
            "prefer declared public contracts over incidental repository habits when choosing the workflow surface",
            "treat local scripts as evidence of possible user intent or product-surface gaps, not as implementation approval",
            "when local behavior contains semantics absent from the public model, narrow the workflow contract or ask the user",
        ],
        "avoid": [
            "treating the existence of a local script as sufficient reason to make it the workflow implementation surface",
            "copying repository-local behavior into a workflow without checking whether it matches the public model",
            "inferring that a repository-local script defines preferred workflow semantics",
            "wrapping a local helper in routine.* just because it already works in this repository",
            "preserving local script semantics silently when those semantics are not published in the public workflow model",
        ],
        "must_not_infer": [
            "there is a script for this => routine.* is acceptable here",
            "the repo already does it this way => this is the correct workflow contract",
            "a local helper covers the semantic gap => no clarification is needed",
        ],
    },
    {
        "name": "early_guards",
        "priority": "critical_applicability_policy",
        "guidance_level": "required_default",
        "rule": "Express workflow applicability near the start of the workflow, not as a late discovery during action execution.",
        "why": [
            "early guards improve execution safety and make workflow applicability explicit",
            "early guards improve check, plan, and explain readability",
            "guard-rich workflows help next prefer workflows that are actually relevant now",
            "without guards, Ordo degrades toward being just a runner",
        ],
        "prefer": [
            "put applicability checks near the top of the workflow",
            "for non-trivial workflows, phase guards in a stable order such as environment applicability, input validation, domain invariants, and structural preconditions",
            "when adding or changing workflow inputs, stop and validate each input at the guard boundary before moving on to downstream steps",
            "when workflow success depends on an externally observable fact and a public probe surface can read it, prefer explicit guard probes; use read-only probe steps only when the observed fact must be reused later or a guard probe is not a good fit",
            "use input-validation filters such as value | is_string, value | is_number, value | is_integer, value | is_boolean, value | in(...), value | eq(...), and value | ne(...) when they make the input contract more explicit",
            "design guards so check and explain can name domain inapplicability before any mutating step runs",
            "run ordo-playbook check <workflow> while authoring to surface missing recommended explicit probe coverage or likely guard gaps whenever the current workflow shape makes those recommendations possible",
            "reject inapplicable situations early instead of failing deep inside execution",
        ],
        "avoid": [
            "delaying obvious applicability checks until late steps",
            "letting non-trivial applicability checks collapse into one unreadable undifferentiated guard mass",
            "relying on late failures when the workflow could declare inapplicability up front",
            "treating action-local preflight or downstream action failure as the workflow's main applicability model",
        ],
    },
    {
        "name": "input_validation_default",
        "priority": "strong_recommendation",
        "guidance_level": "required_default",
        "rule": "Treat input validation as a default authoring step whenever you introduce or modify workflow inputs.",
        "why": [
            "new inputs silently widen workflow semantics unless their admissible shapes are declared near the top of the workflow",
            "validation guards are easier for agents and later authors to notice and preserve than downstream step failures",
            "type-valid input does not by itself make a workflow applicable",
            "neighboring workflows may be incomplete examples, so copied omissions should not become the next default",
        ],
        "prefer": [
            "when introducing or changing any workflow input, pause and decide how that input is validated before continuing with step authoring",
            "add an early guard for each new or changed input whenever a public validation surface exists",
            "for string inputs prefer value | is_string; for numbers prefer value | is_number or value | is_integer; for booleans prefer value | is_boolean; for enumerated values prefer value | in(...), value | eq(...), or value | ne(...) as appropriate",
            "after validating input shape, separately decide which observed preconditions make the workflow applicable to the current target context",
            "if no suitable public validation surface exists, name that exact gap explicitly instead of silently omitting validation",
            "treat existing workflows as style references, not as waivers for missing input validation",
        ],
        "avoid": [
            "copying a neighboring workflow's missing validation into new authoring work",
            "introducing a new input and only discovering bad values inside downstream operations",
            "treating request-shape validation as a substitute for validating target compatibility or workflow applicability",
            "assuming that a repeated local pattern is automatically the preferred authoring contract",
        ],
    },
    {
        "name": "delegated_applicability",
        "priority": "critical_explainability_policy",
        "guidance_level": "required_default",
        "rule": "Do not delegate workflow applicability to downstream action validation when the public surface can express the relevant precondition earlier.",
        "why": [
            "workflow applicability should be reviewable in workflow structure rather than hidden inside one action's failure path",
            "when applicability lives only inside an action, check and explain become less able to justify why the workflow should not run",
            "late applicability discovery encourages cargo-cult copying of steps that happen to work in one repository state",
        ],
        "prefer": [
            "treat action-local validation as a safety net, not as the primary way to declare whether the workflow applies now",
            "if a public probe surface exists for the relevant precondition, prefer an explicit guard probe and guard on the observed fact; use a read-only probe step only when that fact must be reused later or guard syntax is not a good fit",
            "if no public probe surface exists, name that exact capability gap instead of silently treating late failure as acceptable default behavior",
        ],
        "avoid": [
            "assuming that a successful action preflight makes an explicit workflow guard unnecessary",
            "letting the first clear signal of inapplicability appear only when a mutating step starts",
            "treating downstream validation as sufficient merely because a neighboring workflow already does so",
        ],
    },
    {
        "name": "representation_adapters",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Prefer representation adapters for transformations that feed guards, conditions, and published results.",
        "why": [
            "representation adapters can simplify transformations that would otherwise become awkward inline expressions",
            "adapter-based workflows are often clearer than ad hoc string-shaping inside guards, conditions, and result publication",
            "adapters help keep structured workflow intent visible during check, plan, explain, and run",
        ],
        "prefer": [
            "use adapters when text or markdown projections make a downstream decision or published value clearer",
            "in guard context, prefer read-only adapter projections and keep adapter write paths such as ->... out of guard logic",
            "express adapter root binding with pipe-style syntax when an equivalent pipe form exists",
            "keep transformations close to the structured adapter surface instead of re-encoding them manually",
        ],
        "avoid": [
            "hand-rolling repetitive transformations in raw inline expressions when an adapter surface already matches the need",
            "using with{root: ...} when the same adapter binding can be expressed with pipe-style syntax",
            "using adapter write paths such as ->... inside guards",
            "ignoring published adapter families when they would make guard, condition, or publish logic easier to read",
        ],
        "stop_when": [
            "a with{root: ...} form is being introduced before checking whether the same binding works as a pipe-style adapter expression",
        ],
    },
    {
        "name": "guard_result_contract",
        "priority": "critical_guard_contract",
        "guidance_level": "required",
        "rule": "A guard expression must evaluate to a boolean result.",
        "why": [
            "guard success and failure are defined by boolean policy outcomes rather than arbitrary value production",
            "a strict boolean result keeps guard behavior readable across check, plan, explain, and execute",
        ],
        "prefer": [
            "use filters, comparisons, builtins, and read-only adapters only when they clearly contribute to a final boolean guard result",
            "treat a successful non-boolean guard result as a workflow error to fix rather than as truthy or falsy shorthand",
        ],
        "avoid": [
            "authoring guards that merely produce a string, number, list, or object without an explicit boolean decision",
            "relying on implicit truthiness instead of an explicit boolean result",
        ],
    },
    {
        "name": "publish_outputs",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Prefer publish: for intentional outward-facing workflow results.",
        "why": [
            "explicit published outputs make workflow intent clearer",
            "explicit published outputs keep success payloads focused",
            "fallback-only success output is a weak outward-facing contract",
        ],
        "prefer": [
            "publish the final values that downstream readers are meant to consume",
            "use publish: when the workflow is meant to communicate a meaningful result beyond internal execution",
        ],
        "avoid": [
            "leaving important final outputs implicit when the workflow is meant to communicate something downstream",
            "relying on fallback-only success output as the main outward-facing result contract",
        ],
    },
    {
        "name": "lifecycle_state",
        "priority": "recommended_caution",
        "guidance_level": "recommended",
        "rule": "Use state when multiple workflows represent stages of one lifecycle, and keep stored state small.",
        "why": [
            "state is most justified as durable coordination context across related workflow stages",
            "small state is easier to understand, repair, and keep consistent",
            "large state payloads turn hidden persistence into a brittle general-purpose cache",
        ],
        "prefer": [
            "store minimal durable context such as active profile, current entity identity, or compact lifecycle markers",
            "prefer explicit inputs, lets, and published outputs over state when the data does not need cross-workflow persistence",
        ],
        "avoid": [
            "using state as the default dataflow mechanism between unrelated workflows",
            "writing large payloads or easily re-fetchable remote data into state as a matter of course",
        ],
    },
    {
        "name": "explicit_execution_context",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Prefer workflows whose execution context is explicit. Do not rely on hidden ambient environment requirements inside workflow logic.",
        "why": [
            "hidden environment assumptions make workflows brittle",
            "explicit execution context is easier to explain, validate, and reuse",
            "workflows are easier for agents to author correctly when required context is visible",
        ],
        "prefer": [
            "express special execution setup through routines, profiles, or explicit guards",
            "fail early when required execution context is missing",
        ],
        "avoid": [
            "assuming shell bootstrap has already happened outside the workflow",
            "embedding silent dependence on preloaded tools, environment variables, or working-directory conventions",
            "making a workflow succeed only under undocumented machine-local setup",
        ],
    },
    {
        "name": "separate_control_surfaces",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Use the right control surface for the right kind of decision: guards for workflow applicability, configuration for context variation, and if: for local step branching.",
        "why": [
            "mixing these roles makes workflows harder to read and harder to explain",
            "hidden applicability inside step conditions weakens workflow selection and safety",
            "using if: as a substitute for configuration or workflow structure leads to brittle branching logic",
        ],
        "prefer": [
            "use guards for conditions that determine whether the workflow should run at all",
            "use inputs, profiles, and reusable fragments for stable context-specific variation",
            "use if: only for step-local optional behavior inside an already applicable workflow",
        ],
        "avoid": [
            "hiding workflow inapplicability inside late step-level if: conditions",
            "expressing broad context variation through many ad hoc if: branches",
            "cloning or rewriting workflows when explicit configuration would preserve one stable behavior shape",
        ],
    },
    {
        "name": "bounded_fan_out_is_structured_invocation",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Treat bounded fan-out as a structured invocation surface, not as a general control-flow language.",
        "why": [
            "bounded fan-out should stay visible as one author-facing workflow step",
            "structured repetition is easier to validate, explain, and review than flattened ad hoc repetition",
            "keeping repetition on the invocation surface preserves clearer check, plan, and explain output",
        ],
        "prefer": [
            "use for_each only on one invocation-shaped step",
            "keep one explicit outer step that owns the repeated work",
            "use the outer register only for aggregated per-item results",
        ],
        "avoid": [
            "treating for_each as a general looping primitive",
            "flattening repeated work into an unstructured sequence of top-level steps",
            "encoding repeated control flow in a way that hides the outer repeated step from analysis surfaces",
        ],
        "stop_when": [
            "the proposed repeated shape no longer reads as one explicit invocation step",
            "the workflow starts to depend on nested repetition or other control-flow expansion not supported by the public model",
        ],
    },
    {
        "name": "run_target_vs_inline_fan_out",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Use a named run target for reusable, guard-bearing, or non-trivially sized repeated bodies. Use inline repeated steps only for short local repeated bodies.",
        "why": [
            "named run targets keep reusable repeated logic easier to name, review, and evolve",
            "inline repeated steps stay readable only while the repeated body remains small, linear, and workflow-local",
            "fragment-local guards belong in reusable workflow fragment material, not inside inline repeated bodies",
        ],
        "prefer": [
            "use inline steps + for_each for one or two short local repeated steps",
            "allow three or four inline repeated steps only when the body is linear, local, and unlikely to be reused",
            "use run + for_each when the repeated body already exists as reusable workflow fragment material",
            "use run + for_each when the repeated body needs fragment-local guards",
            "use run + for_each when the repeated body has its own clear domain purpose or reuse value",
        ],
        "avoid": [
            "keeping a large repeated body inline merely because it currently works",
            "keeping reusable repeated logic inline when a named run target would express the intent more honestly",
            "trying to place guards inside an inline repeated body",
            "using inline repeated steps for bodies that are already large, branchy, or semantically reusable",
        ],
        "stop_when": [
            "the inline repeated body grows to five or more steps",
            "the inline repeated body needs fragment-local guards",
            "the inline repeated body becomes branchy or hard to review as one local repeated action",
            "the same repeated body is now needed in another workflow",
            "the repeated body needs its own explicit name or argument contract",
        ],
    },
    {
        "name": "fan_out_scope_and_conditions",
        "priority": "critical_applicability_policy",
        "guidance_level": "required_default",
        "rule": "Author bounded fan-out with explicit scope boundaries: outer if gates the whole repeated step, inner if applies per iteration, and inline repeated bodies keep iteration-local scope only.",
        "why": [
            "explicit scope boundaries make repeated workflows easier to reason about",
            "outer and inner conditions answer different questions and should not be conflated",
            "iteration-local register scope prevents accidental cross-item coupling",
        ],
        "prefer": [
            "use the outer if when the entire repeated step should be skipped",
            "use inner step if only for item-local branching inside inline repeated steps",
            "treat item as iteration-local input",
            "treat inner step registers as visible only within the same iteration body",
            "treat the outer register as the only caller-visible aggregate result surface for inline repeated work",
        ],
        "avoid": [
            "assuming that an inner if can replace the whole-step gate of the outer if",
            "assuming that one iteration can read another iteration's inner registers",
            "assuming that inline repeated bodies support nested guards",
            "assuming that nested for_each is a valid repeated-body shape",
        ],
        "stop_when": [
            "the repeated body now depends on nested guards",
            "the repeated body now depends on nested for_each",
            "the proposed design assumes cross-iteration visibility of inner step registers",
        ],
    },
    {
        "name": "inline_fan_out_invalid_shapes",
        "priority": "critical_shape_boundary",
        "guidance_level": "required",
        "rule": "Keep inline bounded fan-out inside the published shape: for_each must be array-valued, nested for_each is invalid, nested guards are invalid, and outer with belongs only to named run targets.",
        "why": [
            "explicit invalid-shape reminders help agents stop before drifting outside the public workflow model",
            "inline repeated bodies are intentionally narrower than named run targets",
            "shape errors are easier to avoid when the forbidden combinations are stated directly in authoring guidance",
        ],
        "prefer": [
            "use a named run target when repeated item processing needs guard blocks",
            "keep inline repeated bodies as step lists only",
            "treat for_each as one array-valued repeated-item source",
        ],
        "avoid": [
            "placing guards inside an inline repeated body",
            "adding nested for_each inside the repeated body",
            "using outer with on inline repeated steps",
            "assuming that any non-array for_each source is valid repeated input",
        ],
        "stop_when": [
            "the proposed inline repeated body now needs guards",
            "the proposed repeated shape introduces nested for_each",
            "the proposed inline step needs outer with bindings instead of local step inputs or item scope",
        ],
    },
    {
        "name": "early_let",
        "priority": "recommended_readability_pattern",
        "guidance_level": "recommended",
        "rule": "Prefer an early let block when the workflow uses long, repeated, or semantically important expressions.",
        "why": [
            "named bindings shorten long fragments and reduce repetition",
            "named bindings improve readability across check, plan, explain, and run surfaces",
            "early let bindings make workflow intent easier to scan",
        ],
        "prefer": [
            "name important values early",
            "bind repeated or hard-to-scan expressions once and reuse them",
        ],
        "avoid": [
            "repeating the same long inline expression across multiple guards or steps",
            "hiding important intent inside one-off inline expressions when a stable let binding would clarify it",
        ],
    },
    {
        "name": "native_expression_contexts",
        "priority": "recommended_readability_pattern",
        "guidance_level": "recommended",
        "rule": "Prefer bare expressions in native and expression-first value contexts such as let:, with:, value:, publish:, result:, and for_each. For bare step if:, use either a compact expression or an equal-authority structured all/any/not form. When a step condition compares more than three predicates, require structured condition form instead of one long boolean string. Quote literal strings explicitly.",
        "why": [
            "bare expressions reduce visual noise across the workflow surfaces that are usually expression-driven",
            "quoted literals make string intent explicit without forcing the common expression case through an extra envelope",
            "using one bare-first value model across with, value, publish, result, and for_each keeps authored workflow dataflow easier to scan",
            "structured step conditions stay reviewable once predicate count grows beyond a small compact expression",
        ],
        "prefer": [
            "write let bindings as bare expressions",
            "write short step if conditions without ${...}",
            "rewrite step if conditions into structured all/any/not form when more than three predicates are being compared",
            "write with, value, publish, result, and for_each entries as bare expressions when they are meant to evaluate",
            "quote literal strings explicitly when a value-bearing field should preserve raw text",
            "keep ${...} only for YAML-hostile expressions that are not viable as bare plain scalars",
        ],
        "avoid": [
            "wrapping native expression contexts in ${...} just by habit",
            "using ${...} in value-bearing fields that now prefer bare expressions",
            "packing more than three step-condition predicates into one boolean string",
            "leaving intended string literals unquoted in expression-first value-bearing fields",
        ],
    },
)


def build_root_response() -> JSONObject:
    """Return the machine-readable root discovery response."""

    system = describe_system()
    internal_sections = system["sections"]
    return {
        "tool_name": "ordo-help",
        "purpose": "Self-describing discovery CLI for Ordo",
        "output_modes": ["text", "json"],
        "topics": [dict(topic) for topic in PUBLIC_TOPICS],
        "recommended_first_calls": [dict(item) for item in RECOMMENDED_FIRST_CALLS],
        "examples": [
            "ordo-help overview --json",
            "ordo-help model --json",
            "ordo-help workflow-authoring --json",
            "ordo-help capabilities --json",
            "ordo-help command-line --json",
            "ordo-help operations --json",
            "ordo-help examples --json",
        ],
        "introspection": {
            "version": system["introspection_version"],
            "entrypoint": internal_sections["discovery"]["entrypoint"],
            "published_sections": sorted(name for name in internal_sections if name != "discovery"),
        },
    }


def build_overview_response() -> JSONObject:
    """Return the aggregated overview discovery response."""

    system = describe_system()
    operations = describe_operations()
    document_kinds = []
    for name, payload in system["sections"].items():
        if name == "discovery":
            continue
        if isinstance(payload, dict) and isinstance(payload.get("document_kind"), str):
            document_kinds.append(payload["document_kind"])

    return {
        "document_kind": "overview",
        "purpose": "World map for Ordo discovery and authoring bootstrap",
        "document_kinds": sorted(set(document_kinds)),
        "execution_concepts": {
            "modes": [mode.value for mode in Mode],
            "statuses": [status.value for status in RuntimeStatus],
        },
        "workflow_authoring_passes": {
            "rule": "Use both check and review after adding or changing a workflow; neither replaces the other.",
            "passes": [
                {
                    "command": "ordo-playbook check <workflow>",
                    "purpose": "Validate workflow applicability and execution readiness",
                },
                {
                    "command": "ordo-playbook review <workflow>",
                    "purpose": "Review workflow authoring-quality findings",
                },
            ],
        },
        "connector_namespaces": [connector["namespace"] for connector in operations["connectors"]],
        "published_topics": [topic["name"] for topic in PUBLIC_TOPICS],
        "recommended_next_calls": [dict(item) for item in RECOMMENDED_FIRST_CALLS[1:]],
    }


def build_model_response() -> JSONObject:
    """Return the aggregated model discovery response."""

    return {
        "document_kind": "model",
        "workflow": describe_workflow_contract(),
        "profile": describe_profile_contract(),
        "routine_contract": describe_routine_contract(),
        "playbook": describe_playbook_contract(),
        "state": describe_state_contract(),
        "connectors": describe_operations()["connectors"],
        "local_expressions": describe_local_expression_surface(),
        "representation_adapters": describe_representation_adapter_surface(),
    }


def describe_local_expression_surface() -> JSONObject:
    """Return the published local-expression filter discovery surface."""

    return {
        "pipeline_filters": [spec.to_contract() for spec in VALUE_EXPRESSION_FILTERS.values()],
        "condition_structures": {
            "equal_authority_if_forms": ["expression_string", "structured_condition"],
            "structured_operators": ["all", "any", "not"],
            "list_semantics": "implicit_all",
        },
    }


def build_workflow_authoring_response() -> JSONObject:
    """Return the published workflow authoring guidance surface."""

    return {
        "document_kind": "workflow_authoring",
        "purpose": "Preferred workflow authoring patterns and discouraged design choices for Ordo authors and agents",
        "audience": ["workflow_authors", "agents"],
        "disclaimer": "This guidance complements the validation contract. It does not replace the formal runtime model.",
        "authoring_heuristic": [
            "declare applicability early",
            "when adding or changing inputs, validate them before continuing",
            "validate both the request shape and the observed target context",
            "name important values early",
            "prefer bare expressions in let, with, value, publish, result, and for_each; for step if, use either a bare expression or a structured all/any/not form; when comparing more than three predicates, require structured if; quote literal strings explicitly",
            "do not use with{root: ...} if the same adapter binding can be expressed with pipe-style syntax; use with{root: ...} only as a fallback when the pipe-style form is not valid in the current construct",
            "stage reusable payloads with value + register before emitting them through result or publish",
            "keep bounded fan-out bodies short, structured, and explicit about scope boundaries",
            "use ordo-playbook check <workflow> during authoring to catch guard and explicit probe-coverage gaps early",
            "for applicability decisions, prefer guard probes first; use read-only probe steps mainly when the observed fact must be reused later",
            "treat 'observation' in runtime metadata as the internal term for the result of an explicit probe",
            "use ordo-playbook review <workflow> during authoring to catch workflow authoring-quality findings early",
            "after adding or changing a workflow, run both check and review before calling the work complete",
            "keep publish payloads minimal and follow stricter local agent or project output rules when they exist",
            "use structured Ordo surfaces before falling back to routines",
            "when a routine truly needs ambient context, use with.env only as a short explicit list of scalar workflow references such as inputs.* or step.*",
            "treat semantic ambiguity as a reason to clarify rather than improvise",
        ],
        "bounded_fan_out_examples": [
            {
                "name": "named_run_target_fan_out",
                "summary": "Use run + for_each when one reusable fragment should be invoked for each item.",
                "yaml": "- steps:\n    - name: inspect-many\n      run: github/check-issue\n      for_each: inputs.items\n      with:\n        issue_number: item\n      register: inspected",
            },
            {
                "name": "inline_fan_out_local_steps",
                "summary": "Use inline steps + for_each only for short local repeated bodies.",
                "yaml": "- steps:\n    - name: inspect-many\n      for_each: inputs.items\n      steps:\n        - name: inspect\n          uses: gh.issue\n          with:\n            issue_number: item",
            },
            {
                "name": "inline_fan_out_inner_if",
                "summary": "Use outer if for whole-step gating and inner if for per-item branching inside inline repeated steps.",
                "yaml": "- steps:\n    - name: inspect-many\n      if: inputs.enabled\n      for_each: inputs.items\n      steps:\n        - name: inspect\n          uses: gh.issue\n          with:\n            issue_number: item\n        - name: publish\n          result:\n            summary: item\n          if: item",
            },
        ],
        "routine_env_examples": [
            {
                "name": "routine_env_scalar_forwarding",
                "summary": "Forward a short explicit list of scalar workflow references into routine environment variables.",
                "yaml": "- steps:\n    - name: collect\n      value:\n        path: /tmp/demo.txt\n      register: collect\n    - name: run-routine\n      uses: routine.python.lint\n      with:\n        args:\n          target: inputs.target\n        env:\n          - inputs.profile\n          - inputs.review_mode\n          - step.collect.outputs.value.path",
                "generated_env": [
                    "inputs.profile -> ORDO_INPUTS_PROFILE",
                    "inputs.review_mode -> ORDO_INPUTS_REVIEW_MODE",
                    "step.collect.outputs.value.path -> ORDO_STEP_COLLECT_OUTPUTS_VALUE_PATH",
                ],
            },
            {
                "name": "routine_env_non_scalar_rejected",
                "summary": "Do not forward non-scalar values; object or array references fail at execution time instead of being silently serialized.",
                "yaml": "- steps:\n    - name: collect\n      value:\n        path: /tmp/demo.txt\n      register: collect\n    - name: run-routine\n      uses: routine.python.lint\n      with:\n        env:\n          - step.collect.outputs.value",
                "why_invalid": [
                    "step.collect.outputs.value is an object here, not a scalar",
                    "routine env forwarding rejects object and array payloads instead of inventing an opaque shell-facing serialization",
                ],
            },
            {
                "name": "routine_env_custom_name_not_supported",
                "summary": "Do not try to mint custom environment-variable names at the workflow call site.",
                "yaml": "- steps:\n    - name: run-routine\n      uses: routine.python.lint\n      with:\n        env:\n          ORDO_REVIEW_MODE: inputs.review_mode",
                "why_invalid": [
                    "with.env is a list of reference paths, not a mapping",
                    "runtime generates env names mechanically from the forwarded references",
                ],
            },
        ],
        "rules": [dict(rule) for rule in WORKFLOW_AUTHORING_RULES],
    }


def build_command_line_response() -> JSONObject:
    """Return the aggregated command-line discovery response."""

    workflow_contract = describe_workflow_contract()
    input_contract = workflow_contract["inputs_contract"]
    playbook_flags = [
        {"name": "--file", "value_shape": "PATH", "required": False, "effect": "override_playbook_discovery", "summary": "Use one explicit playbook file path"},
        {"name": "--profile", "value_shape": "NAME", "required": False, "effect": "select_active_profile", "summary": "Select one named profile for this run"},
        {"name": "--input", "value_shape": "KEY=VALUE", "required": False, "repeatable": True, "effect": "override_input_inline", "summary": "Add or override one top-level workflow input from inline text, with simple number and true/false coercion"},
        {"name": "--input-file", "value_shape": "KEY=PATH", "required": False, "repeatable": True, "effect": "override_input_from_file", "summary": "Add or override one top-level workflow input from a raw UTF-8 file string"},
        {"name": "--json", "required": False, "effect": "emit_json", "summary": "Emit JSON without extra decoration"},
    ]
    return {
        "document_kind": "command_line",
        "commands": [
            {
                "name": "ordo-playbook",
                "purpose": "Browse playbook workflows or launch one named workflow into one runtime mode",
                "usage": "ordo-playbook [--file PATH] [--profile NAME] [--input KEY=VALUE] [--input-file KEY=PATH] [--json] <command>",
                "discovery_commands": [
                    {"name": "workflows list", "summary": "list declared playbook workflows with project-local descriptions"},
                    {"name": "workflows show <workflow>", "summary": "show one workflow entry with file metadata, playbook-owned invocation inputs, and root-declared inputs"},
                ],
                "modes": [
                    {"name": "review <workflow>", "summary": "review authoring-quality findings without making changes"},
                    {"name": "check <workflow>", "summary": "check whether the workflow can be run now, without making changes"},
                    {"name": "plan <workflow>", "summary": "show what the workflow would do, without making changes"},
                    {"name": "explain <workflow>", "summary": "explain why the workflow can or cannot be run right now"},
                    {"name": "run <workflow>", "summary": "run the workflow and do the real work"},
                    {"name": "next <workflow>", "summary": "suggest the next workflow step to run now"},
                ],
                "authoring_passes": {
                    "rule": "When authoring or modifying workflows, run both check and review. Neither replaces the other.",
                    "passes": [
                        {
                            "mode": "check <workflow>",
                            "question": "Can this workflow run now?",
                            "purpose": "Validate applicability, explicit probe coverage, and execution readiness",
                        },
                        {
                            "mode": "review <workflow>",
                            "question": "Is this workflow well-authored?",
                            "purpose": "Surface workflow authoring-quality findings",
                        },
                    ],
                },
                "run_success_surface": "successful run emits workflow-local results, may also surface global published values, and may synthesize one top-level fallback result when neither results nor published output were produced",
                "flags": playbook_flags,
                "input_override_precedence": [
                    f"workflow.inputs declares the allowed activation keys; declared keys are required at activation={str(input_contract['declared_keys_required_at_activation']).lower()}",
                    "profile.inputs may supply values for declared workflow inputs",
                    "playbook workflow-entry with supplies static invocation inputs before one run",
                    "playbook pre_run with supplies static invocation inputs to that pre_run workflow only",
                    "--input overrides workflow and profile-provided values for one run",
                    "--input-file overrides workflow and profile-provided values for one run",
                    f"unknown activation inputs are rejected={str(input_contract['rejects_unknown_activation_inputs']).lower()}",
                    "when both --input and --input-file set the same key, --input-file wins",
                ],
                "examples": [
                    "ordo-playbook workflows list",
                    "ordo-playbook workflows show inspect-issue",
                    "ordo-playbook plan inspect-issue",
                    "ordo-playbook --profile review plan inspect-issue",
                    "ordo-playbook --input enabled=true plan inspect-issue",
                    "ordo-playbook --input-file body=./prompt.md plan inspect-issue",
                ],
            }
        ],
    }


def build_operation_response(reference: str) -> JSONObject | None:
    """Return the focused operation discovery response for one reference."""

    registry = get_public_connector_registry()
    connector_name, separator, operation_name = reference.partition(".")
    if not separator:
        return None

    connector = registry.get_connector(connector_name)
    operation = registry.get_operation(reference)
    if connector is None or operation is None:
        return None

    return {
        "document_kind": "operation",
        "reference": reference,
        "namespace": connector.namespace,
        "bootstrap": connector.bootstrap.to_contract(),
        "operation": operation.to_contract(),
        "related_commands": {
            "operations": "ordo-help operations --json",
            "capabilities": "ordo-help capabilities --json",
        },
        "operation_name": operation_name,
    }


def _build_capability_lookup() -> dict[str, JSONObject]:
    payload = describe_capabilities()
    lookup: dict[str, JSONObject] = {}
    for capability in payload["capabilities"]:
        lookup[capability["name"]] = {
            "document_kind": "capability_node",
            "node_kind": "capability",
            **capability,
        }
    for rule in payload["negative_rules"]:
        lookup[rule["name"]] = {
            "document_kind": "capability_node",
            "node_kind": "negative_rule",
            **rule,
        }
    return lookup


def _build_model_node_lookup() -> dict[str, JSONObject]:
    model = build_model_response()
    lookup: dict[str, JSONObject] = {}

    def add_node(name: str, *, contract: str, node_category: str, summary: str, metadata: JSONObject) -> None:
        lookup[name] = {
            "document_kind": "model_node",
            "node_kind": node_category,
            "name": name,
            "contract": contract,
            "summary": summary,
            "metadata": metadata,
        }

    for field in model["workflow"]["top_level_fields"]:
        add_node(f"workflow.{field['name']}", contract="workflow", node_category="field", summary="Published workflow field metadata", metadata=field)
    add_node(
        "workflow.inputs_contract",
        contract="workflow",
        node_category="input_contract",
        summary="Published workflow activation-input contract metadata",
        metadata=model["workflow"]["inputs_contract"],
    )
    add_node(
        "workflow.include_contract",
        contract="workflow",
        node_category="include_contract",
        summary="Published workflow include-resolution contract metadata",
        metadata=model["workflow"]["include_contract"],
    )
    for field in model["workflow"]["include_contract"].get("call_fields", []):
        add_node(
            f"workflow.include.{field['name']}",
            contract="workflow",
            node_category="include_field",
            summary="Published included-fragment call field metadata",
            metadata=field,
        )
    for field in model["workflow"]["include_contract"].get("fragment_metadata_fields", []):
        add_node(
            f"workflow.fragment.{field['name']}",
            contract="workflow",
            node_category="fragment_metadata_field",
            summary="Published included-fragment metadata field",
            metadata=field,
        )
    add_node(
        "workflow.run_contract",
        contract="workflow",
        node_category="run_contract",
        summary="Published workflow fragment-run contract metadata",
        metadata=model["workflow"]["run_contract"],
    )
    for field in model["workflow"]["run_contract"].get("call_fields", []):
        add_node(
            f"workflow.run.{field['name']}",
            contract="workflow",
            node_category="run_field",
            summary="Published workflow fragment-run call field metadata",
            metadata=field,
        )
    add_node(
        "workflow.value_expression_root.args",
        contract="workflow",
        node_category="expression_root",
        summary="Published included-fragment argument expression root metadata",
        metadata={
            "name": "args",
            "surface": "value_expression",
            "access_surface": model["workflow"]["include_contract"].get("fragment_argument_access_surface"),
            "state_scope": model["workflow"]["include_contract"].get("state_scope"),
            "step_scope": model["workflow"]["include_contract"].get("step_scope"),
        },
    )
    add_node(
        "workflow.local_expression.adapter_seam",
        contract="workflow",
        node_category="adapter_seam",
        summary="Published shared representation-adapter seam metadata",
        metadata=model["representation_adapters"]["shared_seam"],
    )
    add_node(
        "workflow.local_expression.adapter_binding",
        contract="workflow",
        node_category="adapter_binding",
        summary="Published outer representation-adapter binding metadata",
        metadata={
            "outer_binding_form": model["representation_adapters"]["shared_seam"]["outer_binding_form"],
            "host_binding_rules": model["representation_adapters"]["shared_seam"]["host_binding_rules"],
        },
    )
    add_node(
        "workflow.local_expression.filter_surface",
        contract="workflow",
        node_category="filter_surface",
        summary="Published local-expression pipeline filter metadata",
        metadata=model["local_expressions"],
    )
    for filter_spec in model["local_expressions"]["pipeline_filters"]:
        add_node(
            f"workflow.local_expression.filter.{filter_spec['name']}",
            contract="workflow",
            node_category="filter",
            summary="Published local-expression pipeline filter metadata",
            metadata=filter_spec,
        )
    for adapter in model["representation_adapters"]["families"]:
        add_node(
            f"workflow.local_expression.adapter.{adapter['name']}",
            contract="workflow",
            node_category="adapter_family",
            summary="Published representation-adapter family metadata",
            metadata=adapter,
        )
    for form in model["workflow"]["step_forms"]:
        add_node(
            f"workflow.step_forms.{form['name']}",
            contract="workflow",
            node_category="step_form",
            summary="Published workflow step-form metadata",
            metadata=form,
        )
        for field_name in form.get("required_fields", []):
            add_node(
                f"workflow.step.{field_name}",
                contract="workflow",
                node_category="step_field",
                summary="Published workflow step field metadata",
                metadata={"name": field_name, "required_in_forms": [form["name"]]},
            )
        for field_name in form.get("optional_fields", []):
            existing = lookup.get(f"workflow.step.{field_name}")
            if existing is not None:
                existing["metadata"].setdefault("optional_in_forms", []).append(form["name"])
                continue
            add_node(
                f"workflow.step.{field_name}",
                contract="workflow",
                node_category="step_field",
                summary="Published workflow step field metadata",
                metadata={"name": field_name, "optional_in_forms": [form["name"]]},
            )
    for field in model["profile"]["top_level_fields"]:
        add_node(f"profile.{field['name']}", contract="profile", node_category="field", summary="Published profile field metadata", metadata=field)
    for field in model["profile"]["override_fields"]:
        add_node(f"profile.overrides.{field['name']}", contract="profile", node_category="override_field", summary="Published profile override field metadata", metadata=field)
    for field in model["routine_contract"]["top_level_fields"]:
        add_node(
            f"routine_contract.{field['name']}",
            contract="routine_contract",
            node_category="field",
            summary="Published routine-registry top-level field metadata",
            metadata=field,
        )
    for field in model["routine_contract"]["routine_entry_fields"]:
        add_node(
            f"routine_contract.entry.{field['name']}",
            contract="routine_contract",
            node_category="routine_entry_field",
            summary="Published routine entry field metadata",
            metadata=field,
        )
    for field in model["routine_contract"].get("workflow_call_surface", {}).get("fields", []):
        add_node(
            f"routine_contract.workflow_call.{field['name']}",
            contract="routine_contract",
            node_category="routine_call_field",
            summary="Published routine workflow-call field metadata",
            metadata=field,
        )
    add_node(
        "routine_contract.workflow_call_surface",
        contract="routine_contract",
        node_category="routine_call_surface",
        summary="Published routine workflow-call surface metadata",
        metadata=model["routine_contract"].get("workflow_call_surface", {}),
    )
    for field in model["routine_contract"].get("implementation_fields", []):
        add_node(
            f"routine_contract.implementation.{field['name']}",
            contract="routine_contract",
            node_category="routine_implementation_field",
            summary="Published routine implementation field metadata",
            metadata=field,
        )
    for field in model["playbook"]["top_level_fields"]:
        add_node(f"playbook.{field['name']}", contract="playbook", node_category="field", summary="Published playbook field metadata", metadata=field)
    if "pre_run" in model["playbook"].get("activation_semantics", {}):
        add_node(
            "playbook.pre_run_contract",
            contract="playbook",
            node_category="pre_run_contract",
            summary="Published playbook pre-run contract metadata",
            metadata=model["playbook"]["activation_semantics"]["pre_run"],
        )
    for field in model["playbook"].get("pre_run_entry_fields", []):
        add_node(
            f"playbook.pre_run.{field['name']}",
            contract="playbook",
            node_category="pre_run_entry_field",
            summary="Published playbook pre-run entry field metadata",
            metadata=field,
        )
    for field in model["playbook"]["defaults_fields"]:
        add_node(f"playbook.defaults.{field['name']}", contract="playbook", node_category="default_field", summary="Published playbook default field metadata", metadata=field)
    for field in model["playbook"]["workflow_entry_fields"]:
        add_node(f"playbook.workflows.{field['name']}", contract="playbook", node_category="workflow_entry_field", summary="Published playbook workflow-entry field metadata", metadata=field)
    for field in model["playbook"]["profile_entry_fields"]:
        add_node(f"playbook.profiles.{field['name']}", contract="playbook", node_category="profile_entry_field", summary="Published playbook profile-entry field metadata", metadata=field)
    for field in model["playbook"]["state_entry_fields"]:
        add_node(f"playbook.states.{field['name']}", contract="playbook", node_category="state_entry_field", summary="Published playbook state-entry field metadata", metadata=field)

    for connector in model["connectors"]:
        add_node(
            f"connector.{connector['namespace']}",
            contract="connectors",
            node_category="connector_family",
            summary=f"Published connector family metadata for the {connector['namespace']} namespace",
            metadata=connector,
        )
        for operation in connector["operations"]:
            add_node(
                f"connector.{connector['namespace']}.{operation['name']}",
                contract="connectors",
                node_category="connector_operation",
                summary=f"Published connector operation metadata for {connector['namespace']}.{operation['name']}",
                metadata=operation,
            )

    for field_name, value in model["state"]["workflow_surface"].items():
        add_node(
            f"state.workflow_surface.{field_name}",
            contract="state",
            node_category="workflow_surface_field",
            summary="Published state workflow-surface metadata",
            metadata={"name": field_name, "value": value},
        )
    return lookup


def _build_command_line_node_lookup() -> dict[str, JSONObject]:
    payload = build_command_line_response()
    lookup: dict[str, JSONObject] = {}

    for command in payload["commands"]:
        command_name = command["name"]
        lookup[f"command-line.{command_name}"] = {
            "document_kind": "command_line_node",
            "node_kind": "command",
            "name": f"command-line.{command_name}",
            "summary": "Published command-line command metadata",
            "metadata": command,
        }
        for flag in command.get("flags", []):
            normalized = flag["name"].lstrip("-").replace("-", "_")
            lookup[f"command-line.{command_name}.flag.{normalized}"] = {
                "document_kind": "command_line_node",
                "node_kind": "flag",
                "name": f"command-line.{command_name}.flag.{normalized}",
                "summary": "Published command-line flag metadata",
                "metadata": flag,
            }
    return lookup


def build_search_response(query: str) -> JSONObject:
    """Return search results across public topics and operation references."""

    lowered_query = query.strip().lower()
    operation_results = []
    for connector in describe_operations()["connectors"]:
        namespace = connector["namespace"]
        for operation in connector["operations"]:
            reference = f"{namespace}.{operation['name']}"
            search_record = _operation_search_record(reference=reference, operation=operation)
            if _query_matches(lowered_query, search_record["all"]):
                operation_results.append(
                    {
                        "_score": _operation_search_score(lowered_query, search_record),
                        "reference": reference,
                        "summary": operation.get("summary"),
                        "command": f"ordo-help operation {reference} --json",
                    }
                )
    operation_results.sort(key=lambda item: (-int(item["_score"]), str(item["reference"])))
    for item in operation_results:
        item.pop("_score", None)

    topic_results = []
    for topic in PUBLIC_TOPICS:
        searchable = f"{topic['name']} {topic['summary']}".lower()
        if _query_matches(lowered_query, searchable):
            command = f"ordo-help {topic['name']} --json"
            if topic["name"] == "operation":
                command = "ordo-help operation <reference> --json"
            elif topic["name"] == "describe":
                command = "ordo-help describe <topic> --json"
            elif topic["name"] == "search":
                command = "ordo-help search <query> --json"
            topic_results.append(
                {
                    "name": topic["name"],
                    "summary": topic["summary"],
                    "command": command,
                }
            )

    fact_results = []
    for capability in describe_capabilities()["capabilities"]:
        searchable = " ".join([capability["name"], capability["scope"], capability["status"]]).lower()
        if _query_matches(lowered_query, searchable):
            fact_results.append(
                {
                    "kind": "capability",
                    "name": capability["name"],
                    "summary": f"Capability in scope '{capability['scope']}' is {capability['status']}",
                    "topic": "capabilities",
                    "command": f"ordo-help describe {capability['name']} --json",
                }
            )

    for rule in describe_capabilities()["negative_rules"]:
        searchable = " ".join([rule["name"], rule["surface"], rule["rule"], rule["reason"]]).lower()
        if _query_matches(lowered_query, searchable):
            fact_results.append(
                {
                    "kind": "negative_rule",
                    "name": rule["name"],
                    "summary": rule["rule"],
                    "topic": "capabilities",
                    "command": f"ordo-help describe {rule['name']} --json",
                }
            )

    for node_name, node in _build_model_node_lookup().items():
        searchable = f"{node_name} {json.dumps(node['metadata'], sort_keys=True)} {node['summary']}".lower()
        if _query_matches(lowered_query, searchable):
            fact_results.append(
                {
                    "kind": "model_field",
                    "name": node_name,
                    "summary": node["summary"],
                    "topic": "model",
                    "command": f"ordo-help describe {node_name} --json",
                }
            )

    for node_name, node in _build_command_line_node_lookup().items():
        searchable = f"{node_name} {json.dumps(node['metadata'], sort_keys=True)} {node['summary']}".lower()
        if _query_matches(lowered_query, searchable):
            fact_results.append(
                {
                    "kind": "command_line_field",
                    "name": node_name,
                    "summary": node["summary"],
                    "topic": "command-line",
                    "command": f"ordo-help describe {node_name} --json",
                }
            )

    for example in describe_examples_catalog()["examples"]:
        searchable = " ".join([example["name"], example["path"], *example["shows"], *example["related_topics"]]).lower()
        if _query_matches(lowered_query, searchable):
            fact_results.append(
                {
                    "kind": "example",
                    "name": example["name"],
                    "summary": f"Verified example at {example['path']}",
                    "topic": "examples",
                    "command": "ordo-help examples --json",
                }
            )

    workflow_authoring = build_workflow_authoring_response()
    for rule in workflow_authoring["rules"]:
        searchable = " ".join(
            [
                rule["name"],
                rule["priority"],
                rule["guidance_level"],
                rule["rule"],
                *rule.get("why", []),
                *rule.get("prefer", []),
                *rule.get("avoid", []),
            ]
        ).lower()
        if _query_matches(lowered_query, searchable):
            fact_results.append(
                {
                    "kind": "workflow_authoring_rule",
                    "name": f"workflow-authoring.{rule['name']}",
                    "summary": rule["rule"],
                    "topic": "workflow-authoring",
                    "command": "ordo-help workflow-authoring --json",
                }
            )

    return {
        "document_kind": "search_results",
        "query": query,
        "topics": topic_results,
        "facts": fact_results,
        "operations": operation_results,
    }


def _operation_search_record(*, reference: str, operation: JSONObject) -> dict[str, str]:
    reference_text = reference.lower()
    name_text = str(operation["name"]).lower()
    summary_text = str(operation.get("summary") or "").lower()
    inputs_text = json.dumps(operation.get("inputs") or {}, sort_keys=True).lower()
    outputs_text = json.dumps(operation.get("outputs") or {}, sort_keys=True).lower()
    failure_text = json.dumps(operation.get("failure_modes") or [], sort_keys=True).lower()
    examples_text = json.dumps(operation.get("examples") or [], sort_keys=True).lower()
    kind_text = str(operation["kind"]).lower()
    return {
        "reference": reference_text,
        "name": name_text,
        "summary": summary_text,
        "inputs": inputs_text,
        "outputs": outputs_text,
        "failure_modes": failure_text,
        "examples": examples_text,
        "kind": kind_text,
        "all": " ".join(
            [reference_text, name_text, kind_text, summary_text, inputs_text, outputs_text, failure_text, examples_text]
        ),
    }


def _operation_search_score(query: str, record: dict[str, str]) -> int:
    score = 0
    tokens = _search_tokens(query)
    if query in record["reference"]:
        score += 200
    if query in record["name"]:
        score += 160
    if query in record["summary"]:
        score += 120
    if query in record["outputs"]:
        score += 100
    if query in record["inputs"]:
        score += 90
    if query in record["examples"]:
        score += 70
    if query in record["failure_modes"]:
        score += 50
    if query in record["all"]:
        score += 20
    for token in tokens:
        if token in record["reference"]:
            score += 20
        if token in record["name"]:
            score += 18
        if token in record["summary"]:
            score += 14
        if token in record["outputs"]:
            score += 12
        if token in record["inputs"]:
            score += 10
        if token in record["examples"]:
            score += 8
        if token in record["failure_modes"]:
            score += 6
    return score


def _query_matches(query: str, searchable: str) -> bool:
    if not query:
        return False
    if query in searchable:
        return True
    tokens = _search_tokens(query)
    if not tokens:
        return False
    return all(token in searchable for token in tokens)


def _search_tokens(text: str) -> list[str]:
    return _SEARCH_TOKEN_RE.findall(text.lower())


def render_root_text() -> str:
    """Return the human-readable bootstrap screen."""

    lines = [
        "ordo-help",
        "Self-describing discovery CLI for Ordo.",
        "",
        "Output modes:",
        "- text",
        "- json (--json)",
        "",
        "Topics:",
    ]
    for topic in PUBLIC_TOPICS:
        lines.append(f"- {topic['name']}: {topic['summary']}")
    lines.extend(
        [
            "",
            "Recommended first calls:",
            "1. ordo-help overview --json",
            "2. ordo-help model --json",
            "3. ordo-help workflow-authoring --json",
            "4. ordo-help capabilities --json",
            "5. ordo-help command-line --json",
            "6. ordo-help operations --json",
            "7. ordo-help examples --json",
            "",
            "Next command examples:",
            "- ordo-help overview --json",
            "- ordo-help model --json",
            "- ordo-help workflow-authoring --json",
            "- ordo-help capabilities --json",
            "- ordo-help command-line --json",
            "- ordo-help operations --json",
            "- ordo-help examples --json",
        ]
    )
    return "\n".join(lines)


def render_overview_text(payload: JSONObject) -> str:
    """Return the text overview surface."""

    lines = [
        "overview",
        payload["purpose"],
        "",
        "Document kinds:",
    ]
    lines.extend(f"- {item}" for item in payload["document_kinds"])
    lines.extend(
        [
            "",
            "Execution concepts:",
            f"- modes: {', '.join(payload['execution_concepts']['modes'])}",
            f"- statuses: {', '.join(payload['execution_concepts']['statuses'])}",
            "",
            "Workflow authoring passes:",
            f"- rule: {payload['workflow_authoring_passes']['rule']}",
            *[f"- {item['command']}: {item['purpose']}" for item in payload['workflow_authoring_passes']['passes']],
            "",
            "Connector namespaces:",
        ]
    )
    lines.extend(f"- {namespace}" for namespace in payload["connector_namespaces"])
    return "\n".join(lines)


def render_capabilities_text(payload: JSONObject) -> str:
    """Return the text capabilities surface."""

    capabilities = payload["capabilities"]
    lines = ["capabilities", "Supported and unsupported runtime surfaces.", "", "Capability states:"]
    for capability in capabilities:
        summary = f"- {capability['name']}: {capability['status']}"
        related = capability.get("related_capabilities") or []
        if related:
            summary = f"{summary} (related: {', '.join(related)})"
        must_not_infer = capability.get("must_not_infer") or []
        if must_not_infer:
            summary = f"{summary} (must not infer: {', '.join(must_not_infer)})"
        lines.append(summary)
    return "\n".join(lines)


def render_model_text(payload: JSONObject) -> str:
    """Return the text model surface."""

    lines = [
        "model",
        "Main authoring contracts exposed by Ordo.",
        "",
        "Contracts:",
        f"- workflow: {payload['workflow']['document_kind']}",
        f"- profile: {payload['profile']['document_kind']}",
        f"- playbook: {payload['playbook']['document_kind']}",
        f"- state: {payload['state']['document_kind']}",
        "",
        "Connectors:",
        f"- published namespaces: {', '.join(item['namespace'] for item in payload['connectors'])}",
        "",
        "Local-expression pipeline filters:",
        f"- published filters: {', '.join(item['name'] for item in payload['local_expressions']['pipeline_filters'])}",
        "",
        "Representation adapters:",
        f"- outer binding form: {payload['representation_adapters']['shared_seam']['outer_binding_form']}",
    ]
    for family in payload["representation_adapters"]["families"]:
        lines.append(f"- {family['name']}: selectors={', '.join(family['selectors'])}; actions={', '.join(family['actions'])}")
    return "\n".join(lines)


def render_workflow_authoring_text(payload: JSONObject) -> str:
    """Return the text workflow-authoring surface."""

    lines = ["workflow-authoring", payload["purpose"], "", "Authoring heuristic:"]
    lines.extend(f"- {item}" for item in payload["authoring_heuristic"])
    examples = payload.get("bounded_fan_out_examples")
    if isinstance(examples, list) and examples:
        lines.extend(["", "Bounded fan-out examples:"])
        for example in examples:
            if not isinstance(example, dict):
                continue
            lines.append(f"- {example['name']}: {example['summary']}")
    routine_env_examples = payload.get("routine_env_examples")
    if isinstance(routine_env_examples, list) and routine_env_examples:
        lines.extend(["", "Routine with.env examples:"])
        for example in routine_env_examples:
            if not isinstance(example, dict):
                continue
            lines.append(f"- {example['name']}: {example['summary']}")
            for generated in example.get("generated_env", []):
                lines.append(f"  generated env: {generated}")
            for reason in example.get("why_invalid", []):
                lines.append(f"  invalid because: {reason}")
    lines.extend(["", "Rules:"])
    for rule in payload["rules"]:
        lines.append(f"- {rule['name']} [{rule['priority']}]: {rule['rule']}")
        for reason in rule.get("why", []):
            lines.append(f"  why: {reason}")
        for preferred in rule.get("prefer", []):
            lines.append(f"  prefer: {preferred}")
        for avoided in rule.get("avoid", []):
            lines.append(f"  avoid: {avoided}")
        for stop_condition in rule.get("stop_when", []):
            lines.append(f"  stop when: {stop_condition}")
        for forbidden_inference in rule.get("must_not_infer", []):
            lines.append(f"  must not infer: {forbidden_inference}")
    return "\n".join(lines)


def render_command_line_text(payload: JSONObject) -> str:
    """Return the text command-line surface."""

    lines = ["command-line", "Public launch commands and stable flags.", ""]
    for command in payload["commands"]:
        lines.extend(
            [
                command["name"],
                command["purpose"],
                f"usage: {command['usage']}",
                f"modes: {', '.join(item['name'] for item in command['modes'])}",
            ]
        )
        authoring_passes = command.get("authoring_passes")
        if isinstance(authoring_passes, dict):
            lines.extend(["", "workflow authoring passes:", f"- rule: {authoring_passes['rule']}"])
            for item in authoring_passes.get("passes", []):
                lines.append(f"- {item['mode']}: {item['purpose']} ({item['question']})")
        lines.extend(["", "flags:"])
        for flag in command["flags"]:
            suffix = f" {flag.get('value_shape', '')}".rstrip()
            lines.append(f"- {flag['name']}{suffix}: {flag['summary']}")
        lines.extend(["", "input override precedence:"])
        lines.extend(f"- {item}" for item in command["input_override_precedence"])
    return "\n".join(lines)


def render_operations_text(payload: JSONObject) -> str:
    """Return the text operations surface."""

    lines = ["operations", "Public connector namespaces and operations.", ""]
    for connector in payload["connectors"]:
        operation_names = ", ".join(operation["name"] for operation in connector["operations"])
        lines.append(f"- {connector['namespace']}: {operation_names}")
    return "\n".join(lines)


def render_examples_text(payload: JSONObject) -> str:
    """Return the text verified-examples surface."""

    lines = ["examples", "Verified repository examples published for discovery.", ""]
    for example in payload["examples"]:
        shows = ", ".join(example["shows"])
        lines.append(f"- {example['name']}: {example['path']} ({shows})")
    return "\n".join(lines)


def render_operation_text(payload: JSONObject) -> str:
    """Return the text single-operation surface."""

    operation = payload["operation"]
    lines = [
        payload["reference"],
        operation["summary"] or "No summary published.",
        "",
        f"kind: {operation['kind']}",
        f"namespace: {payload['namespace']}",
        f"maturity: {operation['maturity']}",
    ]
    if operation["inputs"]:
        lines.extend(["", "inputs:"])
        for name, shape in operation["inputs"].items():
            lines.append(f"- {name}: {shape}")
    if operation["outputs"]:
        lines.extend(["", "outputs:"])
        for name, shape in operation["outputs"].items():
            lines.append(f"- {name}: {shape}")
    if operation["failure_modes"]:
        lines.extend(["", "failure modes:"])
        for mode in operation["failure_modes"]:
            lines.append(f"- {mode}")
    return "\n".join(lines)


def render_capability_node_text(payload: JSONObject) -> str:
    """Return the text capability-node surface."""

    lines = [payload["name"], payload["node_kind"]]
    if payload["node_kind"] == "capability":
        lines.extend([f"status: {payload['status']}", f"scope: {payload['scope']}"])
    else:
        lines.extend([f"surface: {payload['surface']}", payload["rule"]])
    return "\n".join(lines)


def render_model_node_text(payload: JSONObject) -> str:
    """Return the text model-node surface."""

    lines = [payload["name"], payload["summary"], "", f"contract: {payload['contract']}", f"node kind: {payload['node_kind']}"]
    return "\n".join(lines)


def render_command_line_node_text(payload: JSONObject) -> str:
    """Return the text command-line-node surface."""

    return "\n".join([payload["name"], payload["summary"], "", f"node kind: {payload['node_kind']}"])


def render_search_text(payload: JSONObject) -> str:
    """Return the text search surface."""

    lines = [f"search: {payload['query']}"]
    if payload["topics"]:
        lines.extend(["", "Topic matches:"])
        for topic in payload["topics"]:
            lines.append(f"- {topic['name']}: {topic['command']}")
    if payload["facts"]:
        lines.extend(["", "Fact matches:"])
        for fact in payload["facts"]:
            lines.append(f"- {fact['name']} ({fact['kind']}): {fact['command']}")
    if payload["operations"]:
        lines.extend(["", "Operation matches:"])
        for operation in payload["operations"]:
            lines.append(f"- {operation['reference']}: {operation['command']}")
    if not payload["topics"] and not payload["facts"] and not payload["operations"]:
        lines.extend(["", "No topic, fact, or operation matches found."])
    return "\n".join(lines)


def _emit_payload(payload: JSONObject, *, as_json: bool, renderer) -> int:
    """Emit one discovery payload in JSON or text mode."""

    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(renderer(payload))
    sys.stdout.write("\n")
    return 0


def _emit_unknown_operation(reference: str, *, as_json: bool) -> int:
    """Emit a focused unknown-operation error."""

    payload = {
        "document_kind": "operation_error",
        "reference": reference,
        "status": "unknown_operation",
        "message": f"Unknown public operation reference '{reference}'",
    }
    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stderr.write(payload["message"])
        sys.stderr.write("\n")
    return 1


def _emit_unknown_topic(topic: str, *, as_json: bool) -> int:
    """Emit a focused unknown-topic error."""

    payload = {
        "document_kind": "topic_error",
        "topic": topic,
        "status": "unknown_topic",
        "message": f"Unsupported public topic or node '{topic}'",
        "supported_topics": list(DESCRIBABLE_TOPICS),
        "supported_node_kinds": ["capability", "negative_rule", "model_node"],
    }
    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stderr.write(payload["message"])
        sys.stderr.write("\n")
    return 1


def _resolve_public_topic(topic: str) -> tuple[JSONObject, object] | None:
    """Resolve one describable public topic to its payload and renderer."""

    if topic == "overview":
        return build_overview_response(), render_overview_text
    if topic == "model":
        return build_model_response(), render_model_text
    if topic == "workflow-authoring":
        return build_workflow_authoring_response(), render_workflow_authoring_text
    if topic == "capabilities":
        return describe_capabilities(), render_capabilities_text
    if topic == "command-line":
        return build_command_line_response(), render_command_line_text
    if topic == "operations":
        return describe_operations(), render_operations_text
    if topic == "examples":
        return describe_examples_catalog(), render_examples_text
    capability_node = _build_capability_lookup().get(topic)
    if capability_node is not None:
        return capability_node, render_capability_node_text
    model_node = _build_model_node_lookup().get(topic)
    if model_node is not None:
        return model_node, render_model_node_text
    command_line_node = _build_command_line_node_lookup().get(topic)
    if command_line_node is not None:
        return command_line_node, render_command_line_node_text
    return None


def main(argv: list[str] | None = None) -> int:
    """Run the ordo-help CLI."""

    parser = argparse.ArgumentParser(prog="ordo-help", add_help=False)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("-h", "--help", action="store_true", dest="show_help")
    subparsers = parser.add_subparsers(dest="command")

    overview_parser = subparsers.add_parser("overview", add_help=False)
    overview_parser.add_argument("--json", action="store_true", dest="as_json")

    capabilities_parser = subparsers.add_parser("capabilities", add_help=False)
    capabilities_parser.add_argument("--json", action="store_true", dest="as_json")

    model_parser = subparsers.add_parser("model", add_help=False)
    model_parser.add_argument("--json", action="store_true", dest="as_json")

    workflow_authoring_parser = subparsers.add_parser("workflow-authoring", add_help=False)
    workflow_authoring_parser.add_argument("--json", action="store_true", dest="as_json")

    command_line_parser = subparsers.add_parser("command-line", add_help=False)
    command_line_parser.add_argument("--json", action="store_true", dest="as_json")

    operations_parser = subparsers.add_parser("operations", add_help=False)
    operations_parser.add_argument("--json", action="store_true", dest="as_json")

    examples_parser = subparsers.add_parser("examples", add_help=False)
    examples_parser.add_argument("--json", action="store_true", dest="as_json")

    operation_parser = subparsers.add_parser("operation", add_help=False)
    operation_parser.add_argument("reference")
    operation_parser.add_argument("--json", action="store_true", dest="as_json")

    describe_parser = subparsers.add_parser("describe", add_help=False)
    describe_parser.add_argument("topic")
    describe_parser.add_argument("--json", action="store_true", dest="as_json")

    search_parser = subparsers.add_parser("search", add_help=False)
    search_parser.add_argument("query")
    search_parser.add_argument("--json", action="store_true", dest="as_json")

    parsed = parser.parse_args(argv)
    as_json = bool(getattr(parsed, "as_json", False))

    if parsed.command is None:
        if as_json:
            json.dump(build_root_response(), sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
            return 0

        sys.stdout.write(render_root_text())
        sys.stdout.write("\n")
        return 0

    if parsed.command == "overview":
        return _emit_payload(build_overview_response(), as_json=as_json, renderer=render_overview_text)
    if parsed.command == "capabilities":
        return _emit_payload(describe_capabilities(), as_json=as_json, renderer=render_capabilities_text)
    if parsed.command == "model":
        return _emit_payload(build_model_response(), as_json=as_json, renderer=render_model_text)
    if parsed.command == "workflow-authoring":
        return _emit_payload(build_workflow_authoring_response(), as_json=as_json, renderer=render_workflow_authoring_text)
    if parsed.command == "command-line":
        return _emit_payload(build_command_line_response(), as_json=as_json, renderer=render_command_line_text)
    if parsed.command == "operations":
        return _emit_payload(describe_operations(), as_json=as_json, renderer=render_operations_text)
    if parsed.command == "examples":
        return _emit_payload(describe_examples_catalog(), as_json=as_json, renderer=render_examples_text)
    if parsed.command == "operation":
        payload = build_operation_response(parsed.reference)
        if payload is None:
            return _emit_unknown_operation(parsed.reference, as_json=as_json)
        return _emit_payload(payload, as_json=as_json, renderer=render_operation_text)
    if parsed.command == "describe":
        resolved = _resolve_public_topic(parsed.topic)
        if resolved is None:
            return _emit_unknown_topic(parsed.topic, as_json=as_json)
        payload, renderer = resolved
        return _emit_payload(payload, as_json=as_json, renderer=renderer)
    if parsed.command == "search":
        return _emit_payload(build_search_response(parsed.query), as_json=as_json, renderer=render_search_text)

    parser.error(f"Unsupported command: {parsed.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
