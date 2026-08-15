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
from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS
from ordo.model.help_snippets import describe_help_snippets
from ordo.model.runtime import Mode, RuntimeStatus
from ordo.model.json import JSONObject


PUBLIC_TOPICS: tuple[dict[str, str], ...] = (
    {"name": "features", "summary": "Inspect workflow authoring features, named surfaces, and when to use them"},
    {"name": "overview", "summary": "Start with the Ordo world map"},
    {"name": "model", "summary": "Inspect the main authoring contracts"},
    {"name": "workflow-authoring", "summary": "Inspect preferred workflow authoring patterns, paired check/review passes, routine cautions, early guards, and let usage"},
    {"name": "capabilities", "summary": "Inspect supported and unsupported surfaces"},
    {"name": "command-line", "summary": "Inspect the public command-line launch surface, including distinct check and review roles"},
    {"name": "operations", "summary": "Inspect the public connector catalog"},
    {"name": "examples", "summary": "Inspect verified repository examples"},
    {"name": "snippet-coverage", "summary": "Inspect which public handles do and do not publish canonical verified snippets"},
    {"name": "operation", "summary": "Inspect one public operation by reference"},
    {"name": "describe", "summary": "Resolve a supported public topic"},
    {"name": "search", "summary": "Search topics, contract facts, and operation references"},
)

_SEARCH_TOKEN_RE = re.compile(r"[a-z0-9_.#:/-]+")

DESCRIBABLE_TOPICS: tuple[str, ...] = ("features", "overview", "model", "workflow-authoring", "capabilities", "command-line", "operations", "examples", "snippet-coverage")

RECOMMENDED_FIRST_CALLS: tuple[dict[str, str], ...] = (
    {"command": "ordo-help features", "purpose": "Scan workflow authoring features, named surfaces, and when to use them"},
    {"command": "ordo-help overview", "purpose": "Get the Ordo world map"},
    {"command": "ordo-help model", "purpose": "Learn the main DSL surfaces"},
    {"command": "ordo-help workflow-authoring", "purpose": "Learn preferred workflow authoring patterns, including paired check/review passes"},
    {"command": "ordo-help capabilities", "purpose": "Learn capability boundaries"},
    {"command": "ordo-help command-line", "purpose": "Inspect public launch commands, flags, and distinct check/review roles"},
    {"command": "ordo-help operations", "purpose": "Inspect the public operation catalog"},
    {"command": "ordo-help examples", "purpose": "Inspect verified repository examples"},
    {"command": "ordo-help snippet-coverage", "purpose": "Inspect which public handles do and do not publish canonical verified snippets"},
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
        "name": "workflow_profile_binding_is_project_local",
        "priority": "strong_recommendation",
        "guidance_level": "recommended",
        "rule": "Use top-level workflow.profile only when one workflow is intentionally bound to one project-local execution profile. Treat it as a restrictive local binding, not as the default reusable pattern.",
        "why": [
            "workflow.profile binds execution context before guards and therefore changes the workflow's activation contract",
            "hard-binding one workflow to one named profile reduces portability across playbooks and projects",
            "the binding scopes to the current workflow subtree, so it is appropriate only when that local execution contract is intentional",
        ],
        "prefer": [
            "prefer playbook-owned or caller-selected profile activation for portable workflows",
            "use workflow.profile only for internal or project-bound workflows whose meaning depends on one execution profile",
            "treat descendant workflow.profile declarations as subtree-local overrides rather than as caller-wide mutations",
        ],
        "avoid": [
            "using workflow.profile merely as a convenience default for otherwise reusable workflows",
            "assuming workflow.profile should leak upward into the caller workflow after a nested run returns",
            "treating workflow.profile and profile_switch as the same authoring surface",
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
        "rule": "Use each conditional surface for its own job: guards for workflow applicability and early rejection, gates for whether a path or step may run at all, configuration for stable context variation, and if: when one local step or local branch is optional inside an already-valid path.",
        "why": [
            "mixing these roles makes workflows harder to read and harder to explain",
            "hidden applicability inside step conditions weakens workflow selection and safety",
            "using if: as a substitute for guards, gates, configuration, or workflow structure leads to brittle branching logic",
        ],
        "prefer": [
            "use guards for conditions that determine whether the workflow should run at all or should narrow applicability early",
            "use gates when the real question is whether a path or step may execute at all",
            "use inputs, profiles, and reusable fragments for stable context-specific variation",
            "use if: only when one local step or local branch is optional inside an already applicable workflow",
        ],
        "avoid": [
            "hiding workflow inapplicability inside late step-level if: conditions",
            "using if: for admission, readiness, or coarse path routing when guards or gates carry that meaning more honestly",
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
        "rule": "Prefer bare expressions in native and expression-first value contexts such as let:, with:, value:, publish:, result:, and for_each. For bare step if:, use either a compact expression or an equal-authority structured all/any/not form. When a step condition compares more than three predicates, require structured condition form instead of one long boolean string. Quote literal strings explicitly. Do not rely on expression-looking bare values silently falling back to literal text when evaluation fails.",
        "why": [
            "bare expressions reduce visual noise across the workflow surfaces that are usually expression-driven",
            "quoted literals make string intent explicit without forcing the common expression case through an extra envelope",
            "using one bare-first value model across with, value, publish, result, and for_each keeps authored workflow dataflow easier to scan",
            "fail-closed expression evaluation keeps author intent visible instead of silently reinterpreting a broken expression as plain text",
            "structured step conditions stay reviewable once predicate count grows beyond a small compact expression",
        ],
        "prefer": [
            "write let bindings as bare expressions",
            "write short step if conditions without ${...}",
            "rewrite step if conditions into structured all/any/not form when more than three predicates are being compared",
            "write with, value, publish, result, and for_each entries as bare expressions when they are meant to evaluate",
            "quote literal strings explicitly when a value-bearing field should preserve raw text",
            "treat runtime evaluation failure in a bare expression as a real error to fix rather than a cue to keep the bare form as text",
            "keep ${...} only for YAML-hostile expressions that are not viable as bare plain scalars",
        ],
        "avoid": [
            "wrapping native expression contexts in ${...} just by habit",
            "using ${...} in value-bearing fields that now prefer bare expressions",
            "packing more than three step-condition predicates into one boolean string",
            "leaving intended string literals unquoted in expression-first value-bearing fields",
            "depending on a broken bare expression to degrade into a literal string at runtime",
        ],
    },
)


AUTHORING_CLUSTER_SPECS: tuple[dict[str, object], ...] = (
    {
        "name": "playbook",
        "summary": "Project-local launch catalog for named workflows, profile selection, pre_run orchestration, and static activation inputs.",
        "keywords": ["workflows", "pre_run", "defaults", "profiles", "with", "working_directory", "state_bindings"],
        "appropriate_when": [
            "A project needs one stable launch surface that selects workflows by name instead of by raw file path.",
            "Static entry-owned inputs, pre_run preparation, profile defaults, or launch-time working-directory policy belong to the wrapper rather than to one workflow body.",
        ],
        "inappropriate_when": [
            "The logic is workflow-internal sequencing, validation, or branching that should live inside one workflow file.",
            "The value belongs to workflow-declared inputs or step-local dataflow rather than to launch-time orchestration.",
        ],
        "inspect_next": ["command-line.ordo-playbook", "playbook.workflows.file", "playbook.workflows.with", "playbook.pre_run_contract", "playbook.defaults.profile"],
        "related_rules": ["paired_authoring_passes"],
        "related_examples": ["examples.playbook-pre-run"],
        "published_names_kind": "playbook",
    },
    {
        "name": "profile",
        "summary": "Reusable runtime context for missing-input defaults, execution working directory, and profile-scoped launch metadata.",
        "keywords": ["profile", "inputs", "working_directory", "checks", "overrides", "launchers", "deprecated", "routines"],
        "appropriate_when": [
            "Several runs need the same missing-input defaults or execution context without copying them into every workflow entry.",
            "Selection among project modes belongs to launch context rather than to workflow-authored branching.",
        ],
        "inappropriate_when": [
            "The behavior changes workflow semantics and should be made explicit in guards, steps, or playbook workflow-entry inputs.",
            "The value is only relevant to one workflow body and does not justify reusable launch context.",
        ],
        "inspect_next": ["profile.inputs", "profile.working_directory", "profile.overrides.with", "profile.launchers", "playbook.defaults.profile", "command-line.ordo-playbook"],
        "related_rules": ["explicit_execution_context", "local_artifacts_are_context"],
        "related_examples": ["examples.playbook-pre-run", "examples.launcher-step"],
        "published_names_kind": "profile",
    },
    {
        "name": "workflow",
        "summary": "One executable authoring unit with declared inputs, let bindings, state needs, blocks, and typed step forms.",
        "keywords": ["workflow", "inputs", "let", "state_needs", "blocks", "step forms", "profile_switch"],
        "appropriate_when": [
            "The task needs one explicit executable contract with declared activation inputs and reviewable runtime structure.",
            "The logic belongs to one workflow body rather than to playbook launch policy or reusable fragment definition only.",
            "One intentionally project-local workflow subtree must bind itself to one fixed execution profile through workflow.profile.",
        ],
        "inappropriate_when": [
            "You only need launch-time catalog metadata or reusable fragment expansion rather than a standalone executable workflow.",
            "You are trying to hide multiple unrelated concerns instead of exposing clear inputs, guards, and step forms.",
            "You only want a soft reusable launch default; prefer playbook or caller-selected profile activation instead of workflow.profile.",
        ],
        "inspect_next": ["workflow.inputs_contract", "workflow.profile", "workflow.step.profile_switch", "workflow.step_forms.operation_call", "workflow.step.value", "workflow.step.publish", "workflow.run_contract"],
        "related_rules": ["early_let", "value_register_before_result", "publish_outputs", "workflow_profile_binding_is_project_local"],
        "related_examples": ["examples.minimal", "examples.inspect-issue"],
        "published_names_kind": "workflow",
    },
    {
        "name": "state",
        "summary": "Declared runtime state surface for bound locations, state-keyed storage, and explicit state mutation steps.",
        "keywords": ["state", "state_needs", "state_bindings", "states", "state_set", "state_delete", "bound locations"],
        "appropriate_when": [
            "Workflow data must survive across step boundaries or across runs through declared state locations rather than through implicit files or ambient context.",
            "State reads, writes, and deletions should be explicit in the workflow contract and step surface.",
        ],
        "inappropriate_when": [
            "The data is purely step-local, transient, or better expressed as direct step outputs or ordinary workflow values.",
            "State is being used as a vague catch-all context channel instead of a declared bound storage surface.",
        ],
        "inspect_next": ["state.workflow_surface.state_needs_field", "state.workflow_surface.state_binding_field", "state.workflow_surface.step_state_set_field", "state.workflow_surface.step_state_delete_field", "workflow.step.state_set", "workflow.step.state_delete"],
        "related_rules": ["local_artifacts_are_context", "publish_outputs"],
        "related_examples": [],
        "published_names_kind": "state",
    },
    {
        "name": "include",
        "summary": "Source-time fragment reuse through include expansion with fragment-local args and assembled-workflow validation.",
        "keywords": ["include", "with", "args", "fragment", "reuse", "expansion"],
        "appropriate_when": [
            "The same authored structure should be reused by expansion into the assembled workflow before validation and execution.",
            "Fragment-local args improve reuse more honestly than cloning the same block into multiple workflows.",
        ],
        "inappropriate_when": [
            "You need runtime invocation semantics, isolated callee scope, or per-item fan-out rather than source-time expansion.",
            "The fragment is a one-off body that does not justify reusable include structure.",
        ],
        "inspect_next": ["workflow.include_contract", "workflow.include.include", "workflow.include.with", "workflow.fragment.args", "examples.include-plain", "examples.include-args"],
        "related_rules": ["bounded_fan_out_is_structured_invocation"],
        "related_examples": ["examples.include-plain", "examples.include-args"],
        "published_names_kind": "include",
    },
    {
        "name": "run",
        "summary": "Runtime fragment invocation surface for named targets and bounded fan-out, including inline repeated step bodies.",
        "keywords": ["run", "for_each", "steps", "with", "register", "named target", "fan-out"],
        "appropriate_when": [
            "A reusable fragment should be invoked at runtime, optionally once per item in a bounded collection.",
            "A short repeated body fits inline fan-out better than a cloned step block.",
        ],
        "inappropriate_when": [
            "The body is ordinary top-level workflow structure rather than runtime invocation or bounded repetition.",
            "Inline repeated steps are growing long enough that a named run target would be clearer.",
        ],
        "inspect_next": ["workflow.run_contract", "workflow.run.run", "workflow.run.for_each", "workflow.step_forms.run_invocation", "workflow.step_forms.inline_fan_out_invocation", "workflow-authoring.run_target_vs_inline_fan_out"],
        "related_rules": ["bounded_fan_out_is_structured_invocation", "run_target_vs_inline_fan_out", "fan_out_scope_and_conditions", "inline_fan_out_invalid_shapes"],
        "related_examples": ["workflow-authoring.example.named_run_target_fan_out", "workflow-authoring.example.inline_fan_out_local_steps", "workflow-authoring.example.inline_fan_out_inner_if"],
        "published_names_kind": "run",
    },
    {
        "name": "guards",
        "summary": "Workflow-level applicability surface for early rejection, narrowing, and deciding whether the workflow should run before effectful steps start.",
        "keywords": ["guards", "applicability", "validation", "probe", "boolean result"],
        "appropriate_when": [
            "Applicability, input validation, or observable preconditions should be declared near the start of the workflow.",
            "The workflow must reject inapplicable situations before mutating steps or fallback logic start.",
        ],
        "inappropriate_when": [
            "The condition is step-local admission rather than whole-workflow applicability.",
            "The condition is only changing local behavior inside a path that is already valid.",
            "You are relying on downstream action failure instead of declaring a reviewable workflow-level precondition.",
        ],
        "inspect_next": ["workflow-authoring.early_guards", "workflow-authoring.input_validation_default", "workflow-authoring.delegated_applicability", "workflow.local_expression.filter", "workflow.local_expression.builtin.is_missing"],
        "related_rules": ["early_guards", "input_validation_default", "delegated_applicability", "guard_result_contract"],
        "related_examples": ["examples.inspect-issue"],
        "published_names_kind": "guards",
    },
    {
        "name": "gates",
        "summary": "Step-admission surface that decides whether a path or step may run at all after earlier reads but before the protected work executes.",
        "keywords": ["gate", "on_fail", "admission", "step checkpoint", "blocked step"],
        "appropriate_when": [
            "A step should be admitted or blocked based on earlier observed or computed facts without redefining whole-workflow applicability.",
            "The real question is whether the protected path may execute at all, not how one valid path should branch locally.",
            "Failure-focused gate context should be emitted through structured on_fail metadata instead of broad register dumps.",
        ],
        "inappropriate_when": [
            "The decision really belongs in workflow guards near the start of the workflow.",
            "The condition is only local behavioral variation inside an already-valid path; use if instead.",
            "You are trying to mix gate admission with register publication or current-step output reads; split the gate into a standalone checkpoint step before the registered step.",
        ],
        "inspect_next": ["workflow.step.gate", "workflow.step_forms.gate_checkpoint", "workflow.run.gate", "workflow-authoring.separate_control_surfaces", "workflow-authoring.guard_result_contract"],
        "related_rules": ["separate_control_surfaces", "guard_result_contract"],
        "related_examples": ["workflow-authoring.example.inline_fan_out_inner_if"],
        "published_names_kind": "gates",
    },
    {
        "name": "conditions",
        "summary": "Boolean condition-authoring surface shared by step if and gate, with if for optional local branching and gate for admission decisions.",
        "keywords": ["if", "gate", "all", "any", "not", "structured condition", "implicit_all"],
        "appropriate_when": [
            "Branching or admission logic needs an explicit boolean condition surface with readable operator structure.",
            "More than a few predicates benefit from structured all/any/not rather than one dense boolean string.",
        ],
        "inappropriate_when": [
            "The authored value is data shaping or payload construction rather than a boolean decision.",
            "You are using if as a catch-all control mechanism instead of separating workflow applicability, admission, and local branching.",
            "You are using control-surface syntax where workflow-level guards or local-expression value fields would be clearer.",
        ],
        "inspect_next": ["workflow.step.if", "workflow.step.gate", "workflow-authoring.native_expression_contexts", "workflow-authoring.fan_out_scope_and_conditions"],
        "related_rules": ["guard_result_contract", "fan_out_scope_and_conditions", "native_expression_contexts"],
        "related_examples": ["workflow-authoring.example.inline_fan_out_inner_if"],
        "published_names_kind": "conditions",
    },
    {
        "name": "local-expressions",
        "summary": "Built-in expression surface for reads, checks, comparisons, and short transformations inside workflow-owned fields.",
        "keywords": ["roots", "filters", "builtins", "pipeline", "bare expression", "structured condition"],
        "appropriate_when": [
            "A workflow-owned field needs a short inline expression for guards, if, gate, let, with, value, publish, result, or for_each.",
            "Type checks, membership checks, equality checks, or small value projections are enough without another surface.",
        ],
        "inappropriate_when": [
            "The expression is becoming long, repetitive, or difficult to review as inline logic.",
            "Representation shaping would be clearer through an adapter family or another more explicit surface.",
        ],
        "inspect_next": ["workflow.local_expression.filter", "workflow.local_expression.builtin", "workflow.local_expression.builtin.is_missing", "workflow.local_expression.filter.lookup", "workflow.local_expression.filter.only", "workflow-authoring.native_expression_contexts", "workflow.local_expression.adapter_seam"],
        "related_rules": ["native_expression_contexts", "guard_result_contract", "representation_adapters"],
        "related_examples": ["examples.local-expression-filters"],
        "published_names_kind": "local-expressions",
    },
    {
        "name": "connectors",
        "summary": "Published operation catalog for external probes and actions, grouped by stable namespaces.",
        "keywords": ["connectors", "operations", "namespace", "probe", "action", "public surface"],
        "appropriate_when": [
            "The workflow needs one published external operation instead of a repository-local helper or opaque fallback.",
            "Typed public operations express product intent better than broad execution surfaces.",
            "Users need connector-backed runtime failures to identify the external tool or remote system rather than looking like generic workflow mistakes.",
        ],
        "inappropriate_when": [
            "You are treating a missing public capability as permission to improvise local semantics silently.",
            "The behavior belongs to launch metadata or pure workflow-local transformation instead of an external operation.",
        ],
        "inspect_next": ["operations", "connector.gh", "connector.fs", "command-line.ordo-playbook", "workflow-authoring.decision_order", "workflow-authoring.structured_surface_bias"],
        "related_rules": ["decision_order", "structured_surface_bias", "routine.*", "local_artifacts_are_context"],
        "related_examples": ["examples.minimal", "examples.inspect-pr"],
        "published_names_kind": "connectors",
    },
    {
        "name": "routines",
        "summary": "Bounded opaque local-automation fallback surface. This is an exception path, not a normal extension mechanism, and repeated routine use is a design smell.",
        "keywords": ["routine.*", "fallback", "bounded automation", "local automation", "with.env", "opaque exception path"],
        "appropriate_when": [
            "Published connector operations and clean composition have already been exhausted, and the remaining gap is mechanical or intentionally project-local rather than semantic.",
            "A narrowly bounded local automation step must run through one published routine entry with explicit scalar caller context instead of a broader ad hoc shell surface.",
        ],
        "inappropriate_when": [
            "The remaining gap is semantic, unclear, or being preserved silently through a nearby local helper.",
            "Routine use is becoming the default implementation path, a convenience shortcut, or a way to avoid publishing better connector surface.",
        ],
        "inspect_next": ["routine_contract", "routine_contract.workflow_call_surface", "routine_contract.workflow_call.env", "workflow-authoring.routine.*", "workflow-authoring.explicit_execution_context", "workflow-authoring.decision_order"],
        "related_rules": ["routine.*", "decision_order", "explicit_execution_context", "local_artifacts_are_context", "semantic_ambiguity"],
        "related_examples": [],
        "published_names_kind": "routines",
    },
    {
        "name": "adapters",
        "summary": "Family-based representation transforms over workflow values, including projection-oriented selectors and family-specific actions.",
        "keywords": ["json", "key_value", "markdown", "text", "yaml", "selectors", "actions", "shortcuts", "with{...}"],
        "appropriate_when": [
            "A guard, condition, or published value would be clearer after family-owned representation shaping than after ad hoc inline rewrites.",
            "The published adapter family already matches the projection or mutation style you need.",
        ],
        "inappropriate_when": [
            "A plain local expression is already clearer than an adapter invocation.",
            "Guard logic would need adapter write-path behavior rather than read-only projection.",
        ],
        "inspect_next": ["workflow.local_expression.adapter_seam", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter.json", "workflow.local_expression.adapter.text", "workflow.local_expression.adapter.yaml", "workflow-authoring.representation_adapters"],
        "related_rules": ["representation_adapters", "native_expression_contexts"],
        "related_examples": ["examples.text-adapter"],
        "published_names_kind": "adapters",
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
            "ordo-help features",
            "ordo-help overview",
            "ordo-help model",
            "ordo-help workflow-authoring",
            "ordo-help capabilities",
            "ordo-help command-line",
            "ordo-help operations",
            "ordo-help examples",
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
    snippet_coverage = build_snippet_coverage_response()
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
        "conditional_roles": {
            "rule": "Use each conditional surface for its own job: guards handle applicability and early rejection, gates handle whether a path or step may run at all, and if handles local behavioral variation inside an already-valid path.",
            "avoid": [
                "Do not use if as a catch-all control mechanism.",
                "If a condition is really deciding applicability, admission, or routing, move it into guards, gates, or a higher structural choice instead.",
            ],
        },
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
        "failure_diagnostics": {
            "rule": "When runtime has external command or remote-system context, user-facing diagnostics should distinguish that external cause from workflow or engine logic failures.",
            "external_payload_fields": [
                "kind",
                "classification",
                "tool",
                "system",
                "argv_summary",
                "stderr_excerpt",
                "suggested_checks",
            ],
        },
        "connector_namespaces": [connector["namespace"] for connector in operations["connectors"]],
        "published_topics": [topic["name"] for topic in PUBLIC_TOPICS],
        "snippet_coverage_summary": snippet_coverage["summary"],
        "recommended_next_calls": [dict(item) for item in RECOMMENDED_FIRST_CALLS if item["command"] != "ordo-help overview"],
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


def _snippet_surface_for_handle(handle: str) -> JSONObject:
    snippets = describe_help_snippets().get(handle)
    if not isinstance(snippets, dict):
        return {"snippet_coverage": "none", "canonical_examples": []}
    return {
        "snippet_coverage": str(snippets.get("snippet_coverage", "none")),
        "canonical_examples": list(snippets.get("canonical_examples", [])),
    }


def build_features_response() -> JSONObject:
    """Return the compact feature map for workflow authoring discovery."""

    model = build_model_response()
    workflow_authoring = build_workflow_authoring_response()
    examples = describe_examples_catalog()
    rule_lookup = {str(rule["name"]): rule for rule in workflow_authoring["rules"] if isinstance(rule, dict)}

    clusters = []
    for spec in AUTHORING_CLUSTER_SPECS:
        clusters.append(
            {
                "name": spec["name"],
                "summary": spec["summary"],
                "published_names": _build_cluster_published_names(str(spec["published_names_kind"]), model=model),
                "keywords": list(spec["keywords"]),
                "appropriate_when": list(spec["appropriate_when"]),
                "inappropriate_when": list(spec["inappropriate_when"]),
                "inspect_next": [_build_public_handle_reference(str(handle)) for handle in spec["inspect_next"]],
                "related_rules": [_build_workflow_authoring_rule_reference(str(name), rule_lookup=rule_lookup) for name in spec["related_rules"]],
                "related_examples": [_build_example_reference(str(name), examples=examples) for name in spec["related_examples"]],
            }
        )

    return {
        "document_kind": "features",
        "purpose": "Compact workflow authoring feature map for authors and agents, with named handles for deeper discovery.",
        "clusters": clusters,
    }


def _names_from_fields(entries: list[JSONObject]) -> list[str]:
    return [str(item["name"]) for item in entries if isinstance(item, dict) and isinstance(item.get("name"), str)]


def _workflow_step_field_names(step_forms: list[JSONObject]) -> list[str]:
    names: list[str] = []
    for form in step_forms:
        if not isinstance(form, dict):
            continue
        for field_name in [*form.get("required_fields", []), *form.get("optional_fields", [])]:
            if isinstance(field_name, str) and field_name not in names:
                names.append(field_name)
    return names


def _step_forms_with_field(step_forms: list[JSONObject], field_name: str) -> list[str]:
    matches: list[str] = []
    for form in step_forms:
        if not isinstance(form, dict) or not isinstance(form.get("name"), str):
            continue
        if field_name in form.get("required_fields", []) or field_name in form.get("optional_fields", []):
            current_name = str(form["name"])
            if current_name not in matches:
                matches.append(current_name)
    return matches


def _build_cluster_published_names(kind: str, *, model: JSONObject) -> JSONObject:
    workflow = model["workflow"]
    playbook = model["playbook"]
    profile = model["profile"]
    local_expressions = model["local_expressions"]
    adapters = model["representation_adapters"]
    step_forms = workflow["step_forms"]
    authored_surfaces = workflow["surface_constraints"]["authored_surfaces"]

    if kind == "playbook":
        return {
            "top_level_fields": _names_from_fields(playbook["top_level_fields"]),
            "workflow_entry_fields": _names_from_fields(playbook["workflow_entry_fields"]),
            "pre_run_entry_fields": _names_from_fields(playbook["pre_run_entry_fields"]),
            "defaults_fields": _names_from_fields(playbook["defaults_fields"]),
        }
    if kind == "profile":
        return {
            "top_level_fields": _names_from_fields(profile["top_level_fields"]),
            "override_fields": _names_from_fields(profile["override_fields"]),
            "deprecated_launcher_fields": _names_from_fields(profile.get("launcher_fields", [])),
        }
    if kind == "workflow":
        return {
            "top_level_fields": _names_from_fields(workflow["top_level_fields"]),
            "block_forms": [str(item["name"]) for item in workflow["block_forms"] if isinstance(item, dict) and isinstance(item.get("name"), str)],
            "step_forms": [str(item["name"]) for item in step_forms if isinstance(item, dict) and isinstance(item.get("name"), str)],
            "step_fields": _workflow_step_field_names(step_forms),
            "profile_switch_step_forms": _step_forms_with_field(step_forms, "profile_switch"),
        }
    if kind == "state":
        state = model["state"]
        return {
            "workflow_surface": list(state["workflow_surface"].values()),
            "path_root": [str(state["path_forms"]["root"])],
            "path_shape": [str(state["path_forms"]["shape"])],
            "runtime_rules": [str(item["name"]) for item in state["runtime_rules"] if isinstance(item, dict) and isinstance(item.get("name"), str)],
        }
    if kind == "include":
        return {
            "call_fields": _names_from_fields(workflow["include_contract"]["call_fields"]),
            "fragment_metadata_fields": _names_from_fields(workflow["include_contract"]["fragment_metadata_fields"]),
            "fragment_argument_forms": [str(item["name"]) for item in workflow["include_contract"]["fragment_argument_declaration_forms"] if isinstance(item, dict) and isinstance(item.get("name"), str)],
        }
    if kind == "run":
        run_step_forms: list[str] = []
        for current_name in [*_step_forms_with_field(step_forms, "run"), *_step_forms_with_field(step_forms, "for_each")]:
            if current_name not in run_step_forms:
                run_step_forms.append(current_name)
        return {
            "call_fields": _names_from_fields(workflow["run_contract"]["call_fields"]),
            "body_forms": list(workflow["run_contract"]["body_forms"]),
            "step_forms": run_step_forms,
            "fan_out_fields": ["item_binding", "outer_if_scope", "inner_if_scope", "outer_register_scope"],
        }
    if kind == "guards":
        return {
            "workflow_fields": ["guards"],
            "guard_forms": [str(item["name"]) for item in workflow["guard_forms"] if isinstance(item, dict) and isinstance(item.get("name"), str)],
            "allowed_roots": list(workflow["surface_constraints"]["guard_expression"]["allowed_roots"]),
            "allowed_filters": list(workflow["surface_constraints"]["guard_expression"]["allowed_filters"]),
            "allowed_builtins": list(workflow["surface_constraints"]["guard_expression"]["allowed_builtins"]),
        }
    if kind == "gates":
        gate_fields = [item for item in workflow["run_contract"]["call_fields"] if isinstance(item, dict) and item.get("name") == "gate"]
        structured_optional_fields = []
        if gate_fields:
            structured_optional_fields = [str(item["name"]) for item in gate_fields[0].get("structured_optional_fields", []) if isinstance(item, dict) and isinstance(item.get("name"), str)]
        return {
            "step_field": ["gate"],
            "step_forms": _step_forms_with_field(step_forms, "gate"),
            "structured_operators": list(authored_surfaces["condition_field_forms"]["structured_object_operators"]),
            "structured_optional_fields": structured_optional_fields,
        }
    if kind == "conditions":
        return {
            "condition_fields": list(authored_surfaces["native_condition_fields"]),
            "structured_operators": list(local_expressions["condition_structures"]["structured_operators"]),
            "list_semantics": [str(local_expressions["condition_structures"]["list_semantics"])],
            "boolean_operators": list(workflow["surface_constraints"]["runtime_value_surface"]["boolean_operators"]),
        }
    if kind == "local-expressions":
        return {
            "roots": sorted(
                {
                    *workflow["surface_constraints"]["guard_expression"]["allowed_roots"],
                    *workflow["surface_constraints"]["runtime_value_surface"]["allowed_roots"],
                    "probe",
                }
            ),
            "filters": [str(item["name"]) for item in local_expressions["pipeline_filters"] if isinstance(item, dict) and isinstance(item.get("name"), str)],
            "builtins": list(workflow["surface_constraints"]["runtime_value_surface"]["allowed_builtins"]),
            "structured_condition_operators": list(local_expressions["condition_structures"]["structured_operators"]),
            "comparison_operators": ["==", "!=", "in", "not in"],
        }
    if kind == "connectors":
        return {
            "namespaces": [str(item["namespace"]) for item in model["connectors"] if isinstance(item, dict) and isinstance(item.get("namespace"), str)],
        }
    if kind == "routines":
        routine_contract = model["routine_contract"]
        return {
            "top_level_fields": _names_from_fields(routine_contract["top_level_fields"]),
            "routine_entry_fields": _names_from_fields(routine_contract["routine_entry_fields"]),
            "workflow_call_fields": _names_from_fields(routine_contract.get("workflow_call_surface", {}).get("fields", [])),
            "implementation_fields": _names_from_fields(routine_contract.get("implementation_fields", [])),
            "generated_env_name_examples": list(routine_contract.get("workflow_call_surface", {}).get("generated_env_name_examples", {}).keys()),
        }
    if kind == "adapters":
        return {
            "families": [str(item["name"]) for item in adapters["families"] if isinstance(item, dict) and isinstance(item.get("name"), str)],
            "selectors": {str(item["name"]): list(item["selectors"]) for item in adapters["families"] if isinstance(item, dict) and isinstance(item.get("name"), str)},
            "actions": {str(item["name"]): list(item["actions"]) for item in adapters["families"] if isinstance(item, dict) and isinstance(item.get("name"), str)},
            "shortcuts": {str(item["name"]): list(item["shortcuts"]) for item in adapters["families"] if isinstance(item, dict) and isinstance(item.get("name"), str)},
        }
    return {}


def describe_local_expression_surface() -> JSONObject:
    """Return the published local-expression discovery surface."""

    allowed_roots = sorted(
        {
            *describe_workflow_contract()["surface_constraints"]["guard_expression"]["allowed_roots"],
            *describe_workflow_contract()["surface_constraints"]["runtime_value_surface"]["allowed_roots"],
            "probe",
        }
    )
    return {
        "pipeline_filters": [spec.to_contract() for spec in VALUE_EXPRESSION_FILTERS.values()],
        "builtins": [
            {
                **spec.to_contract(),
                "summary": "Published local-expression builtin for inline workflow expressions.",
                "allowed_roots": allowed_roots,
            }
            for spec in VALUE_EXPRESSION_BUILTINS.values()
        ],
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
            "use each conditional surface for its own job: guards for applicability and early rejection, gates for whether a path or step may run at all, and if: only when one local step or local branch is optional inside an already-valid path",
            "when the first effectful action is skipped by an if that depends only on pre-step facts, treat that as a strong signal to consider guards instead",
            "distinguish authored probe intent from successful probe materialization: a guard may already express the right probe shape even when the observation could not be completed from the currently available pre-step facts",
            "prefer bare expressions in let, with, value, publish, result, and for_each; for step if, use either a bare expression or a structured all/any/not form; when comparing more than three predicates, require structured if; quote literal strings explicitly; do not rely on broken bare expressions silently falling back to literal text",
            "do not use with{root: ...} if the same adapter binding can be expressed with pipe-style syntax; use with{root: ...} only as a fallback when the pipe-style form is not valid in the current construct",
            "stage reusable payloads with value + register before emitting them through result or publish",
            "keep bounded fan-out bodies short, structured, and explicit about scope boundaries",
            "use ordo-playbook check <workflow> during authoring to catch guard and explicit probe-coverage gaps early",
            "for applicability decisions, prefer guard probes first; use read-only probe steps mainly when the observed fact must be reused later",
            "treat 'observation' in runtime metadata as the internal term for the result of an explicit probe",
            "use ordo-playbook review <workflow> during authoring to catch workflow authoring-quality findings early",
            "after adding or changing a workflow, run both check and review before calling the work complete",
            "keep publish payloads minimal and follow stricter local agent or project output rules when they exist",
            "use top-level workflow.profile only for intentionally project-local workflows that truly need one fixed execution profile subtree",
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
                "definition": "Public launch command for discovering playbook workflows and running one named workflow in a selected runtime mode.",
                "purpose": "Browse playbook workflows or launch one named workflow into one runtime mode",
                "use_when": [
                    "You need to discover which named workflows the current playbook publishes before choosing one.",
                    "You need to run one workflow through check, review, plan, explain, run, or next.",
                    "You need one-run launch overrides such as --profile, --input, or --input-file without editing the workflow or playbook.",
                ],
                "do_not_use_for": [
                    "Teaching workflow-body semantics that belong to workflow, playbook, or workflow-authoring discovery surfaces.",
                    "Treating check as complete workflow sign-off; review is still required for authoring-quality findings.",
                    "Encoding durable project logic in launch flags instead of declared workflow inputs, playbook metadata, or workflow structure.",
                ],
                "nearest_surfaces": [
                    {
                        "handle": "command-line",
                        "summary": "Top-level catalog of public launch commands and stable flags",
                    },
                    {
                        "handle": "playbook.workflows.file",
                        "summary": "Playbook workflow-entry field that binds one published workflow name to one workflow file",
                    },
                    {
                        "handle": "workflow-authoring.paired_authoring_passes",
                        "summary": "Why check and review are complementary authoring passes rather than substitutes",
                    },
                ],
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
                "run_failure_surface": {
                    "rule": "When a run failure has normalized external context, the public failure payload should identify that external cause instead of surfacing only a generic wrapper message.",
                    "external_payload_fields": [
                        "kind",
                        "classification",
                        "tool",
                        "system",
                        "argv_summary",
                        "stderr_excerpt",
                        "suggested_checks",
                    ],
                },
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
                "inspect_next": [
                    "command-line.ordo-playbook.flag.profile",
                    "command-line.ordo-playbook.flag.input",
                    "command-line.ordo-playbook.flag.input_file",
                    "playbook.workflows.file",
                    "workflow-authoring.paired_authoring_passes",
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

    capability_overrides: dict[str, JSONObject] = {
        "workflow.local_expressions": {
            "definition": "Workflow capability for short inline local expressions that only read and reshape already-available input data through workflow roots, pipeline filters, function-style builtins, and representation adapters.",
            "use_when": [
                "A workflow-owned field needs a concise inline read, check, comparison, or small transformation without escalating to a heavier execution surface.",
                "Authoring intent is still local expression shaping rather than external operations, step orchestration, or long opaque helper logic.",
                "The expression may transform input data in subtle ways, but it still stays inside pure local value-shaping rather than changing the outside world.",
            ],
            "do_not_use_for": [
                "Long, repetitive, or representation-heavy logic that would be clearer through adapters, dedicated workflow structure, or another typed public surface.",
                "Treating local expressions as a catch-all substitute for guards, gates, state surfaces, or other explicit workflow contracts.",
                "Anything that mutates the outside world, performs execution steps, or encodes workflow control flow such as branching, admission, or orchestration.",
            ],
        },
        "workflow.include_fragments": {
            "definition": "Workflow capability for source-time fragment reuse through include expansion with fragment-local args resolved before assembled-workflow validation.",
            "use_when": [
                "The same authored structure should be reused by expansion into the assembled workflow before execution rather than invoked as a runtime step.",
            ],
            "do_not_use_for": [
                "Runtime invocation, isolated callee scope, or repeated execution per item; use run surfaces for those runtime behaviors.",
                "Treating include as a hidden control-flow mechanism after execution has already started; include is source-time assembly, not runtime branching.",
            ],
        },
        "workflow.local_expression.adapter": {
            "definition": "Workflow capability for representation-adapter families that project or transform values after a source has already been interpreted as json, yaml, markdown, text, or key-value data.",
            "use_when": [
                "Inline workflow logic first needs family-owned parsing or structured selection that would be awkward as plain local-expression filters alone.",
            ],
            "do_not_use_for": [
                "Simple root reads, comparisons, or short pipeline shaping that are already clear with ordinary local-expression filters or builtins.",
                "Implicit host binding inside adapter-owned syntax; use the published adapter binding seam when host references must enter the adapter body.",
            ],
        }
    }
    for capability in payload["capabilities"]:
        snippet_surface = _snippet_surface_for_handle(str(capability["name"]))
        effective_capability = dict(capability)
        overrides = capability_overrides.get(str(capability["name"]))
        if isinstance(overrides, dict):
            effective_capability.update(overrides)
        lookup[capability["name"]] = {
            "document_kind": "capability_node",
            "node_kind": "capability",
            **effective_capability,
            "snippet_coverage": snippet_surface["snippet_coverage"],
            "canonical_examples": snippet_surface["canonical_examples"],
        }
    for rule in payload["negative_rules"]:
        snippet_surface = _snippet_surface_for_handle(str(rule["name"]))
        lookup[rule["name"]] = {
            "document_kind": "capability_node",
            "node_kind": "negative_rule",
            **rule,
            "snippet_coverage": snippet_surface["snippet_coverage"],
            "canonical_examples": snippet_surface["canonical_examples"],
        }
    return lookup


def _build_model_node_lookup() -> dict[str, JSONObject]:
    model = build_model_response()
    lookup: dict[str, JSONObject] = {}

    connector_family_overrides: dict[str, JSONObject] = {
        "runtime": {
            "definition": "Published runtime connector family for legacy execution-context actions that affect the current run itself.",
            "use_when": [
                "You are inspecting or maintaining a legacy runtime action surface that predates the dedicated workflow profile-switch step form.",
            ],
            "do_not_use_for": [
                "New workflow authoring when workflow.step.profile_switch can express the intent directly and more honestly.",
                "External system operations; this family changes local Ordo runtime context rather than calling a remote tool or service.",
            ],
            "nearest_surfaces": [
                {"handle": "connectors", "summary": "Top-level published connector namespace catalog"},
                {"handle": "operations", "summary": "Flat public operation catalog across all connector namespaces"},
                {"handle": "connector.runtime.profile.use", "summary": "Legacy runtime action for switching the active execution profile in the current run"},
                {"handle": "workflow.step.profile_switch", "summary": "Preferred workflow-native step surface for profile switching"},
            ],
            "inspect_next": ["connector.runtime.profile.use", "workflow.step.profile_switch", "profile"],
        },
        "fs": {
            "definition": "Published filesystem connector family for probing one filesystem path as a readable file snapshot.",
            "use_when": [
                "You need one typed filesystem probe instead of a broader shell command just to inspect a file.",
            ],
            "do_not_use_for": [
                "Writing, mutating, or deleting files; this family currently publishes observation only.",
                "Repository-local parsing logic when one file snapshot is enough and later workflow logic can inspect its outputs directly.",
            ],
            "nearest_surfaces": [
                {"handle": "connectors", "summary": "Top-level published connector namespace catalog"},
                {"handle": "operations", "summary": "Flat public operation catalog across all connector namespaces"},
                {"handle": "connector.fs.file", "summary": "Probe one filesystem path as one file snapshot"},
                {"handle": "connector.shell.command", "summary": "Broader shell surface for cases that are not covered by published filesystem probes"},
            ],
            "inspect_next": ["connector.fs.file", "operations", "connector.shell.command"],
        },
        "compose": {
            "definition": "Published Docker Compose connector family for observing one Compose project or service and for starting, stopping, or removing service runtime instances.",
            "use_when": [
                "You need published Compose-aware project or service operations instead of shelling out to ad hoc docker compose commands.",
                "You want one shared family surface that separates observation from lifecycle-changing actions.",
            ],
            "do_not_use_for": [
                "Pure workflow-local branching or value shaping that does not need an external orchestrator call.",
                "Repository-local helper scripts when the published Compose operations already express the intent directly.",
            ],
            "nearest_surfaces": [
                {"handle": "connectors", "summary": "Top-level published connector namespace catalog"},
                {"handle": "operations", "summary": "Flat public operation catalog across all connector namespaces"},
                {"handle": "profile.connectors", "summary": "Profile field where family-specific connector context such as compose.directory or compose.file can be authored"},
                {"handle": "connector.compose.project", "summary": "Probe one whole Compose project"},
                {"handle": "connector.compose.service", "summary": "Probe one declared Compose service"},
                {"handle": "connector.compose.start", "summary": "Start one Compose project or one declared service"},
            ],
            "authored_context_fields": [
                {"name": "directory", "summary": "working directory for docker compose commands"},
                {"name": "file", "summary": "explicit Compose file path, resolved relative to directory when needed"},
                {"name": "project_name", "summary": "explicit Compose project name override"},
            ],
            "inspect_next": [
                "connector.compose.project",
                "connector.compose.service",
                "connector.compose.start",
                "connector.compose.stop",
                "connector.compose.remove",
            ],
        }
    }

    connector_operation_overrides: dict[tuple[str, str], JSONObject] = {
        ("runtime", "profile.use"): {
            "definition": "Legacy runtime action for switching later execution in the current run to another declared profile.",
            "use_when": [
                "You are reading or migrating older workflow logic that still invokes runtime.profile.use directly.",
            ],
            "do_not_use_for": [
                "New profile-switch authoring; use workflow.step.profile_switch instead of a legacy runtime action call.",
                "Declaring a fixed workflow-owned profile binding; use workflow.profile when the subtree should always start under one profile.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.runtime", "summary": "Parent runtime connector family"},
                {"handle": "workflow.step.profile_switch", "summary": "Preferred workflow-native step surface that replaces this legacy action"},
                {"handle": "workflow.profile", "summary": "Workflow field for fixed project-local profile binding before guards run"},
            ],
            "examples": [
                {"inputs": {"profile": "frontend"}, "reference": "runtime.profile.use"},
            ],
            "inspect_next": ["workflow.step.profile_switch", "workflow.profile", "profile"],
        },
        ("fs", "file"): {
            "definition": "Probe one filesystem path as one UTF-8 file snapshot with canonical content and file metadata.",
            "use_when": [
                "You need one file's content and metadata inside workflow logic, guards, or later adapters.",
            ],
            "do_not_use_for": [
                "Directory inspection or generic filesystem traversal; this probe requires one regular file path.",
                "Binary or non-UTF-8 content when canonical text content cannot be produced reliably.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.fs", "summary": "Parent filesystem connector family"},
                {"handle": "connector.shell.command", "summary": "Fallback shell surface when you need broader filesystem behavior than one published file snapshot"},
                {"handle": "workflow.local_expression.adapter.key_value", "summary": "One downstream adapter family that can project structured values from fs.file content"},
            ],
            "examples": [
                {"inputs": {"path": "/workspace/app.env"}, "reference": "fs.file"},
            ],
            "inspect_next": ["workflow.local_expression.adapter.key_value", "connector.shell.command", "operations"],
        },
        ("compose", "project"): {
            "definition": "Probe one Compose project as a single orchestration unit.",
            "use_when": [
                "You need project-level runtime state before deciding whether to start, stop, or inspect one service.",
            ],
            "do_not_use_for": [
                "Service-specific health or container details; use connector.compose.service for that narrower observation.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.compose", "summary": "Parent Compose connector family"},
                {"handle": "connector.compose.service", "summary": "Sibling probe for one declared service"},
                {"handle": "connector.compose.start", "summary": "Lifecycle action that commonly follows a project-level observation"},
            ],
            "examples": [
                {"inputs": {}, "reference": "compose.project"},
            ],
            "inspect_next": ["connector.compose.service", "connector.compose.start", "operations"],
        },
        ("compose", "service"): {
            "definition": "Probe one declared Compose service as a single orchestration unit.",
            "use_when": [
                "You need service-specific declared/running/healthy state before acting on that service.",
            ],
            "do_not_use_for": [
                "Whole-project state; use connector.compose.project when the decision is about the project as a whole.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.compose", "summary": "Parent Compose connector family"},
                {"handle": "connector.compose.project", "summary": "Sibling probe for project-level state"},
                {"handle": "connector.compose.remove", "summary": "Lifecycle action that targets one stopped service instance"},
            ],
            "examples": [
                {"inputs": {"service": "api"}, "reference": "compose.service"},
            ],
            "inspect_next": ["connector.compose.remove", "connector.compose.start", "connector.compose.stop"],
        },
        ("compose", "start"): {
            "definition": "Start one Compose project or one declared Compose service.",
            "use_when": [
                "You need the requested Compose target running before later workflow steps continue.",
            ],
            "do_not_use_for": [
                "Pure observation; use connector.compose.project or connector.compose.service when you only need state.",
                "Removing stopped runtime instances; use connector.compose.remove for that cleanup action.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.compose", "summary": "Parent Compose connector family"},
                {"handle": "connector.compose.project", "summary": "Project-level observation that can precede a start decision"},
                {"handle": "connector.compose.stop", "summary": "Sibling lifecycle action for bringing a running target down"},
            ],
            "examples": [
                {"inputs": {}, "reference": "compose.start"},
                {"inputs": {"service": "api"}, "reference": "compose.start"},
            ],
            "inspect_next": ["connector.compose.stop", "connector.compose.project", "operations"],
        },
        ("compose", "stop"): {
            "definition": "Stop one Compose project or one declared Compose service.",
            "use_when": [
                "You need a running Compose target quiesced before cleanup, mutation, or another orchestration phase.",
            ],
            "do_not_use_for": [
                "Removing stopped runtime instances; use connector.compose.remove when the intent is cleanup rather than stop.",
                "Pure observation; use connector.compose.project or connector.compose.service when you only need state.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.compose", "summary": "Parent Compose connector family"},
                {"handle": "connector.compose.start", "summary": "Sibling lifecycle action for bringing a target up"},
                {"handle": "connector.compose.remove", "summary": "Cleanup action that often follows a successful stop"},
            ],
            "examples": [
                {"inputs": {}, "reference": "compose.stop"},
                {"inputs": {"service": "api"}, "reference": "compose.stop"},
            ],
            "inspect_next": ["connector.compose.remove", "connector.compose.start", "connector.compose.service"],
        },
        ("compose", "remove"): {
            "definition": "Remove one stopped materialized Compose service instance.",
            "use_when": [
                "You need cleanup of one stopped service instance after it is no longer needed.",
            ],
            "do_not_use_for": [
                "Stopping a still-running target; use connector.compose.stop first when runtime is still active.",
                "Whole-project lifecycle changes; use connector.compose.start or connector.compose.stop when the intent is project/service runtime state rather than removal.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.compose", "summary": "Parent Compose connector family"},
                {"handle": "connector.compose.service", "summary": "Service-level observation that can confirm stopped state before removal"},
                {"handle": "connector.compose.stop", "summary": "Sibling lifecycle action often needed before removal"},
            ],
            "examples": [
                {"inputs": {"service": "api"}, "reference": "compose.remove"},
            ],
            "inspect_next": ["connector.compose.stop", "connector.compose.service", "operations"],
        },
    }

    model_node_overrides: dict[str, JSONObject] = {
        "workflow.step.profile_switch": {
            "definition": "Workflow step field for switching later execution in the current workflow subtree to another declared profile.",
            "use_when": [
                "A later part of the workflow must continue under another declared profile based on workflow-owned logic.",
                "The profile change is a mid-workflow context switch rather than a fixed whole-workflow binding from the start.",
            ],
            "do_not_use_for": [
                "A fixed workflow-local profile that should apply before guards run; use workflow.profile for that contract.",
                "Legacy runtime connector migration targets; prefer this field instead of connector.runtime.profile.use for new authoring.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step_forms.profile_switch", "summary": "Step form that requires name + profile_switch and optionally allows if/gate"},
                {"handle": "workflow.profile", "summary": "Top-level workflow field for fixed project-local profile binding before guards run"},
                {"handle": "connector.runtime.profile.use", "summary": "Legacy runtime action replaced by this workflow-native field"},
            ],
            "inspect_next": ["workflow.step_forms.profile_switch", "workflow.profile", "profile"],
        },
        "workflow.step_forms.profile_switch": {
            "definition": "Workflow step form for one explicit profile-switch checkpoint inside the current workflow path.",
            "use_when": [
                "The workflow needs one named step whose only primary job is switching later execution to another declared profile.",
            ],
            "do_not_use_for": [
                "Ordinary operation calls or value-producing steps; this form is context-only rather than an external action or payload step.",
                "Whole-workflow fixed profile binding; use workflow.profile when the subtree should start under one profile from the beginning.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.profile_switch", "summary": "Field that carries the target profile expression or literal"},
                {"handle": "workflow.profile", "summary": "Top-level workflow field for fixed project-local profile binding before guards run"},
                {"handle": "workflow.step.gate", "summary": "Optional admission field that may guard this step form before the profile switch executes"},
            ],
            "inspect_next": ["workflow.step.profile_switch", "workflow.profile", "workflow.step.gate"],
        },
        "workflow.local_expression.filter": {
            "definition": "Overview of pipeline-style local-expression filters that transform, project, or check one value after an expression root has already been selected.",
            "use_when": [
                "You need short inline value shaping such as projection, normalization, comparison, type checks, or collection helpers in one expression pipeline.",
            ],
            "do_not_use_for": [
                "Function-style helpers such as is_present(...) or format(...); those belong to workflow.local_expression.builtin.",
                "Representation-owned parsing or structural selection across text families; use adapter families when the value first needs json/yaml/markdown/text interpretation.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.local_expressions", "summary": "Top-level workflow capability for local expressions across roots, builtins, filters, and conditions"},
                {"handle": "workflow.local_expression.builtin", "summary": "Overview of function-style local-expression helpers rather than pipeline filters"},
                {"handle": "workflow.local_expression.filter.lookup", "summary": "Representative pipeline filter for selecting one mapping value by key"},
            ],
            "inspect_next": ["workflow.local_expression.filter.lookup", "workflow.local_expression.filter.only", "workflow.local_expression.builtin"],
        },
        "workflow.local_expression.builtin": {
            "definition": "Overview of function-style local-expression builtins that perform special checks or formatting outside the pipeline filter chain.",
            "use_when": [
                "You need one helper such as presence checks or formatting that reads more honestly as a builtin call than as a pipeline stage.",
            ],
            "do_not_use_for": [
                "Ordinary pipeline shaping after one root value; prefer workflow.local_expression.filter for those transformations.",
                "Representation parsing or structured selection from text families; use adapter surfaces when the source first needs format-aware interpretation.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.local_expressions", "summary": "Top-level workflow capability for local expressions across roots, builtins, filters, and conditions"},
                {"handle": "workflow.local_expression.filter", "summary": "Overview of pipeline-style filters rather than function-style builtins"},
                {"handle": "workflow.local_expression.builtin.is_present", "summary": "Representative builtin for checking whether a referenced value is present"},
            ],
            "inspect_next": ["workflow.local_expression.builtin.is_present", "workflow.local_expression.builtin.is_missing", "workflow.local_expression.filter"],
        },
        "workflow.local_expression.adapter_binding": {
            "definition": "Outer adapter-binding form for passing host workflow references into adapter-owned body syntax explicitly through `with{...}`.",
            "use_when": [
                "An adapter family needs host workflow values bound explicitly before the adapter-owned selector or action body runs.",
            ],
            "do_not_use_for": [
                "Ordinary pipeline filters or builtins that already read the host value directly without an adapter-owned body.",
                "Bare host references inside adapter-owned syntax; the binding seam exists specifically to prevent that ambiguity.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.local_expression.adapter", "summary": "Overview for representation-adapter families"},
                {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared read/write seam and host-binding rules for adapters"},
                {"handle": "workflow.local_expression.adapter.json", "summary": "One adapter family that may consume host values through the outer binding form"},
            ],
            "inspect_next": ["workflow.local_expression.adapter_seam", "workflow.local_expression.adapter.json", "workflow.local_expression.adapter"],
        },
        "workflow.local_expression.adapter_seam": {
            "definition": "Shared adapter seam that separates host workflow references from family-owned adapter syntax and distinguishes read projections from write updates.",
            "use_when": [
                "You need to understand the common host-binding and read/write boundary that all representation-adapter families share.",
            ],
            "do_not_use_for": [
                "Pretending each adapter family invents its own host-binding rules from scratch; this seam is shared across families.",
                "Using write-path semantics in contexts that only admit read projections, such as guard logic.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.local_expression.adapter", "summary": "Overview for representation-adapter families"},
                {"handle": "workflow.local_expression.adapter_binding", "summary": "Outer binding form that introduces host references into adapter-owned syntax"},
                {"handle": "workflow-authoring.representation_adapters", "summary": "Authoring guidance for when adapters are preferable to ad hoc inline shaping"},
            ],
            "inspect_next": ["workflow.local_expression.adapter_binding", "workflow.local_expression.adapter.json", "workflow-authoring.representation_adapters"],
        },
        "workflow.local_expression.adapter.json": {
            "definition": "Representation-adapter family for selecting or updating strict JSON text through exact structural selectors and JSON-owned actions.",
            "use_when": [
                "The source value is JSON text and workflow logic needs structural selection or update semantics that are clearer than ad hoc inline parsing.",
            ],
            "do_not_use_for": [
                "Markdown, plain text, yaml, or key-value representations; use the family that matches the source format instead of treating every source as JSON.",
                "Simple root comparisons that do not need representation-aware parsing or structural selection.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.local_expression.adapter", "summary": "Overview for representation-adapter families"},
                {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared host-binding and read/write seam across adapter families"},
                {"handle": "workflow.local_expression.adapter.yaml", "summary": "Sibling structured-text family for yaml rather than JSON text"},
            ],
            "inspect_next": ["workflow.local_expression.adapter.yaml", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
        },
        "workflow.local_expression.adapter.key_value": {
            "definition": "Representation-adapter family for key-value text where selectors and shortcuts are intentionally minimal and the primary surface is the family match itself.",
            "use_when": [
                "The source value is key-value style text and workflow logic needs that family-specific interpretation instead of generic line parsing.",
            ],
            "do_not_use_for": [
                "Structured JSON/YAML documents or markdown block/list semantics; use the matching adapter family for those representations.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.local_expression.adapter", "summary": "Overview for representation-adapter families"},
                {"handle": "workflow.local_expression.adapter.text", "summary": "Sibling family for plain text line-oriented selection"},
                {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared host-binding and read/write seam across adapter families"},
            ],
            "inspect_next": ["workflow.local_expression.adapter.text", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
        },
        "workflow.local_expression.adapter.markdown": {
            "definition": "Representation-adapter family for selecting or transforming markdown sections, blocks, lists, and task-list structures through markdown-owned selectors and actions.",
            "use_when": [
                "The source value is markdown and workflow logic needs heading, block, list, or task-list semantics rather than plain string slicing.",
            ],
            "do_not_use_for": [
                "Strict structural JSON/YAML access or plain text line slicing; use the family that matches the representation instead of flattening markdown semantics.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.local_expression.adapter", "summary": "Overview for representation-adapter families"},
                {"handle": "workflow.local_expression.adapter.text", "summary": "Sibling family for plain text selectors without markdown-aware structure"},
                {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared host-binding and read/write seam across adapter families"},
            ],
            "inspect_next": ["workflow.local_expression.adapter.text", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
        },
        "workflow.local_expression.adapter.text": {
            "definition": "Representation-adapter family for plain text line-oriented selectors and simple text-owned update actions.",
            "use_when": [
                "The source value is plain text and line/substring-oriented selection is clearer than treating it as markdown or a structured data format.",
            ],
            "do_not_use_for": [
                "Markdown section/list semantics or strict structured JSON/YAML traversal; use the family that matches the representation shape.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.local_expression.adapter", "summary": "Overview for representation-adapter families"},
                {"handle": "workflow.local_expression.adapter.markdown", "summary": "Sibling family for markdown-aware selectors and actions"},
                {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared host-binding and read/write seam across adapter families"},
            ],
            "inspect_next": ["workflow.local_expression.adapter.markdown", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
        },
        "workflow.local_expression.adapter.yaml": {
            "definition": "Representation-adapter family for selecting structured YAML values through YAML-owned selectors while preserving YAML-specific interpretation rather than treating the source as raw text.",
            "use_when": [
                "The source value is YAML text and workflow logic needs structural selection that should respect YAML interpretation.",
            ],
            "do_not_use_for": [
                "Strict JSON parsing or markdown/text families; use the family that matches the representation instead of assuming YAML and JSON are interchangeable authoring surfaces.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.local_expression.adapter", "summary": "Overview for representation-adapter families"},
                {"handle": "workflow.local_expression.adapter.json", "summary": "Sibling structured-text family for JSON rather than YAML"},
                {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared host-binding and read/write seam across adapter families"},
            ],
            "inspect_next": ["workflow.local_expression.adapter.json", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
        },
        "workflow.include_contract": {
            "definition": "Workflow include contract for resolving fragment files, binding fragment-local args, and validating the assembled workflow only after include expansion finishes.",
            "use_when": [
                "You need the execution boundary and resolution rules for source-time include expansion rather than runtime invocation semantics.",
            ],
            "do_not_use_for": [
                "Assuming include runs as an isolated runtime call; include replaces source structure before validation and execution start.",
                "Guessing fragment argument rules from ordinary workflow inputs; fragment args have their own declaration and default semantics.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.include_fragments", "summary": "Capability overview for source-time include fragment reuse"},
                {"handle": "workflow.include.include", "summary": "Call field that points at the fragment file to expand"},
                {"handle": "workflow.include.with", "summary": "Call field for binding fragment-local args into the included fragment"},
            ],
            "required_fields": ["include"],
            "optional_fields": ["with"],
            "inspect_next": ["workflow.include.include", "workflow.include.with", "workflow.fragment.args"],
        },
        "workflow.include.include": {
            "definition": "Included-fragment call field that names the fragment file to resolve and expand at source time.",
            "use_when": [
                "A workflow block should be replaced by reusable fragment content loaded from a fragment file before validation begins.",
            ],
            "do_not_use_for": [
                "Selecting a runtime workflow to invoke later; use run or playbook workflow-entry surfaces for runtime selection instead of source-time expansion.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.include_contract", "summary": "Contract that requires include and resolves fragment files before assembled-workflow validation"},
                {"handle": "workflow.include.with", "summary": "Sibling field for binding fragment-local args during include expansion"},
                {"handle": "workflow.fragment.description", "summary": "Fragment metadata field inside the included fragment file itself"},
            ],
            "examples": [
                {"reference": "workflow.include.include", "inputs": {"include": "fragments/check_issue.yaml"}},
            ],
            "inspect_next": ["workflow.include.with", "workflow.fragment.args", "examples.include-plain"],
        },
        "workflow.include.with": {
            "definition": "Included-fragment call field for binding fragment-local args into the included fragment during source-time expansion.",
            "use_when": [
                "The included fragment declares args and the caller needs to provide concrete values before the assembled workflow is validated.",
            ],
            "do_not_use_for": [
                "Runtime step with-binding or ordinary workflow input activation; this field only feeds fragment-local args during include expansion.",
                "Host-side arbitrary expressions that should be delayed until runtime invocation; include.with is part of source-time fragment assembly.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.include_contract", "summary": "Contract that defines fragment argument binding and validation semantics"},
                {"handle": "workflow.fragment.args", "summary": "Fragment metadata field that declares which args may be bound"},
                {"handle": "workflow.run.with", "summary": "Runtime invocation binding surface rather than source-time include arg binding"},
            ],
            "examples": [
                {"reference": "workflow.include.with", "inputs": {"issue_number": "${inputs.issue_number}"}},
            ],
            "inspect_next": ["workflow.fragment.args", "examples.include-args", "workflow.run.with"],
        },
        "workflow.fragment.args": {
            "definition": "Included-fragment metadata field that declares fragment-local args available through args.name inside the expanded fragment body.",
            "use_when": [
                "A reusable fragment needs a small explicit local input contract rather than reading all caller context implicitly.",
            ],
            "do_not_use_for": [
                "Ordinary top-level workflow activation inputs; use workflow.inputs for the executable workflow contract rather than fragment-local include args.",
                "Implicitly assuming any caller value is available inside the fragment without declaration.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.include.with", "summary": "Call field that binds declared fragment args during include expansion"},
                {"handle": "workflow.include_contract", "summary": "Contract that defines allowed fragment arg declaration forms and defaults"},
                {"handle": "workflow.inputs", "summary": "Executable workflow activation-input contract rather than fragment-local reuse metadata"},
            ],
            "inspect_next": ["workflow.include.with", "workflow.include_contract", "examples.include-args"],
        },
        "workflow.fragment.description": {
            "definition": "Included-fragment metadata field for documenting the reusable fragment's purpose without changing the assembled workflow contract.",
            "use_when": [
                "A reusable fragment benefits from a short human-facing description so authors can discover why it exists before expanding it.",
            ],
            "do_not_use_for": [
                "Executable workflow semantics or activation inputs; description is documentation, not contract shape.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.include.include", "summary": "Call field that selects the fragment file to expand"},
                {"handle": "workflow.fragment.args", "summary": "Sibling fragment metadata field for declaring local args"},
                {"handle": "examples.include-plain", "summary": "Verified example that shows a simple include fragment call shape"},
            ],
            "inspect_next": ["workflow.fragment.args", "examples.include-plain", "workflow.include.include"],
        },
        "workflow.inputs": {
            "definition": "Top-level workflow field for declaring the named activation inputs that the caller must provide before the workflow may run.",
            "use_when": [
                "The workflow needs a declared external request shape instead of reading undeclared caller values implicitly.",
                "Guards, steps, or result logic should be able to reference activation inputs through one explicit contract surface.",
            ],
            "do_not_use_for": [
                "Fragment-local include args; use workflow.fragment.args when the values belong only to source-time fragment reuse.",
                "Playbook entry-owned static launch inputs; use playbook.workflows.with when the values belong to one named launch entry rather than to the workflow contract itself.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.inputs_contract", "summary": "Contract surface for declaration shape, access path, and activation rules"},
                {"handle": "playbook.workflows.with", "summary": "Launch-time entry surface that supplies concrete values for declared workflow inputs"},
                {"handle": "command-line.ordo-playbook.flag.input", "summary": "One-run caller override for declared workflow input values"},
            ],
            "inspect_next": ["workflow.inputs_contract", "playbook.workflows.with", "command-line.ordo-playbook.flag.input"],
        },
        "workflow.inputs_contract": {
            "definition": "Workflow activation-input contract for how inputs are declared, accessed, validated, and rejected at runtime.",
            "use_when": [
                "You need to understand what declaring workflow inputs means at activation time, including required-key and unknown-input rules.",
            ],
            "do_not_use_for": [
                "Assuming undeclared caller keys are tolerated; unknown activation inputs are rejected by contract.",
                "Treating input declaration as sufficient validation guidance; authoring still needs explicit input validation guards when semantics require them.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.inputs", "summary": "Top-level field that declares the workflow activation-input catalog"},
                {"handle": "workflow-authoring.input_validation_default", "summary": "Authoring guidance for validating newly introduced or changed workflow inputs"},
                {"handle": "command-line.ordo-playbook.flag.input", "summary": "Launch-time surface that supplies one concrete value for a declared workflow input"},
            ],
            "inspect_next": ["workflow.inputs", "workflow-authoring.input_validation_default", "command-line.ordo-playbook.flag.input"],
        },
        "workflow.profile": {
            "definition": "Top-level workflow field for binding the current workflow subtree to one fixed declared execution profile before guards run.",
            "use_when": [
                "The workflow is intentionally project-local and should always start under one fixed profile binding.",
                "Guard evaluation and later steps must both see the same fixed profile-owned context from the start of this workflow subtree.",
            ],
            "do_not_use_for": [
                "Portable workflows that should let the caller, playbook, or launch context choose the active profile.",
                "Mid-workflow context switches; use workflow.step.profile_switch when the profile changes later in the path instead of at workflow start.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.profile_switch", "summary": "Step-local profile change for later execution inside an already-started workflow path"},
                {"handle": "workflow-authoring.workflow_profile_binding_is_project_local", "summary": "Authoring guidance that explains why workflow.profile is intentionally restrictive"},
                {"handle": "profile", "summary": "Profile contract surface for declared execution-context data that a binding selects"},
            ],
            "inspect_next": ["workflow.step.profile_switch", "workflow-authoring.workflow_profile_binding_is_project_local", "profile"],
        },
        "playbook.defaults": {
            "definition": "Playbook field for declaring launch-time defaults that apply when the caller and workflow entry did not choose a value explicitly.",
            "use_when": [
                "Several published workflows should share one soft default profile or working-directory policy without hard-binding each workflow body.",
            ],
            "do_not_use_for": [
                "Workflow-local semantics that must be fixed inside one workflow contract; use workflow.profile or workflow-owned fields for those.",
                "Per-workflow-entry overrides; use playbook.workflows.* fields when one published workflow needs a different launch contract.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.defaults.profile", "summary": "Child field for one soft default active profile selection"},
                {"handle": "playbook.defaults.working_directory", "summary": "Child field for one soft default execution working directory"},
                {"handle": "workflow.profile", "summary": "Workflow-owned fixed profile binding rather than a soft playbook launch default"},
            ],
            "examples": [
                {"reference": "playbook.defaults", "inputs": {"profile": "review", "working_directory": "${inputs.repo_dir}"}},
            ],
            "inspect_next": ["playbook.defaults.profile", "playbook.defaults.working_directory", "playbook.workflows"],
        },
        "playbook.defaults.profile": {
            "definition": "Playbook default field for selecting the active profile when a run did not already choose one explicitly.",
            "use_when": [
                "Most published workflows in this playbook should start under one reusable profile unless the caller or entry overrides it.",
            ],
            "do_not_use_for": [
                "A fixed workflow-local profile contract; use workflow.profile when the workflow itself must always bind one profile before guards run.",
                "One-run operator overrides; use --profile when the caller wants to override the default at launch time.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.defaults", "summary": "Parent playbook defaults object"},
                {"handle": "command-line.ordo-playbook.flag.profile", "summary": "Launch-time override that wins over soft playbook defaults for one invocation"},
                {"handle": "workflow.profile", "summary": "Workflow-owned fixed binding instead of a soft playbook launch default"},
            ],
            "examples": [
                {"reference": "playbook.defaults.profile", "inputs": {"profile": "review"}},
            ],
            "inspect_next": ["command-line.ordo-playbook.flag.profile", "workflow.profile", "profile"],
        },
        "playbook.defaults.working_directory": {
            "definition": "Playbook default field for setting the execution working directory when no narrower launch surface already provided one.",
            "use_when": [
                "Most published workflows in this playbook should resolve relative paths from one shared default directory.",
                "The default directory depends only on activation inputs and should be computed before workflow execution starts.",
            ],
            "do_not_use_for": [
                "Workflow-entry-specific directory overrides; use playbook.workflows.working_directory when one published workflow needs a narrower default.",
                "Step-local directory shifts after the workflow has already started; use a narrower execution surface for that kind of local behavior.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.defaults", "summary": "Parent playbook defaults object"},
                {"handle": "playbook.workflows.working_directory", "summary": "Per-workflow-entry override for the default execution directory"},
                {"handle": "profile.working_directory", "summary": "Reusable profile-owned execution directory context instead of a playbook-wide soft default"},
            ],
            "examples": [
                {"reference": "playbook.defaults.working_directory", "inputs": {"working_directory": "${inputs.repo_dir}"}},
            ],
            "inspect_next": ["playbook.workflows.working_directory", "profile.working_directory", "playbook.defaults"],
        },
        "playbook.pre_run": {
            "definition": "Playbook field for declaring one or more playbook-owned workflows that run before the requested published workflow in the same runtime session.",
            "use_when": [
                "The project needs shared launch-time preparation, validation, or state setup before whichever published workflow the caller selected.",
            ],
            "do_not_use_for": [
                "Workflow-internal sequencing that belongs inside one workflow body rather than in the playbook wrapper.",
                "Per-workflow-entry preparation that should only happen for one published workflow; keep that logic closer to the workflow entry or workflow body instead.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.pre_run_contract", "summary": "Contract surface for what a pre_run entry may declare and what boundaries it must respect"},
                {"handle": "playbook.pre_run.file", "summary": "Child field that selects the workflow file to run before the requested workflow"},
                {"handle": "playbook.workflows.with", "summary": "Sibling launch-time input surface for the requested workflow entry rather than for pre_run setup"},
            ],
            "examples": [
                {"reference": "playbook.pre_run", "inputs": {"file": ".ordo/workflows/bootstrap.yaml", "with": {"repo": "acme/app"}, "state_bindings": {"shared_state": "global"}}},
            ],
            "inspect_next": ["playbook.pre_run_contract", "playbook.pre_run.file", "playbook.pre_run.with"],
        },
        "playbook.pre_run_contract": {
            "definition": "Playbook contract for pre_run entries that execute before the requested workflow in the same runtime session with playbook-owned launch context.",
            "use_when": [
                "You need to understand the execution boundary, allowed fields, and state-scope limits for playbook pre_run orchestration.",
            ],
            "do_not_use_for": [
                "Ordinary workflow-entry invocation rules; use playbook.workflows.* when describing the requested workflow launch itself.",
                "Assuming pre_run may silently widen the main workflow's declared state contract; that boundary is intentionally restricted.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.pre_run", "summary": "Parent playbook field that lists pre_run entries"},
                {"handle": "playbook.pre_run.state_bindings", "summary": "Entry field for explicitly binding state locations into the pre_run workflow only"},
                {"handle": "playbook.workflows.with", "summary": "Requested-workflow launch inputs rather than playbook-owned pre_run inputs"},
            ],
            "required_fields": ["file"],
            "optional_fields": ["with", "state_bindings"],
            "inspect_next": ["playbook.pre_run.file", "playbook.pre_run.with", "playbook.pre_run.state_bindings"],
        },
        "playbook.pre_run.file": {
            "definition": "Pre-run entry field that selects which workflow file executes before the requested workflow.",
            "use_when": [
                "A specific bootstrap workflow should always run first when this playbook is used.",
            ],
            "do_not_use_for": [
                "Selecting the requested published workflow by name; that belongs to playbook.workflows entries and ordo-playbook commands.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.pre_run", "summary": "Parent pre_run list surface"},
                {"handle": "playbook.pre_run_contract", "summary": "Contract that requires file on every pre_run entry"},
                {"handle": "playbook.workflows.file", "summary": "Sibling field for the requested workflow entry rather than pre_run setup"},
            ],
            "examples": [
                {"reference": "playbook.pre_run.file", "inputs": {"file": ".ordo/workflows/bootstrap.yaml"}},
            ],
            "inspect_next": ["playbook.pre_run.with", "playbook.pre_run_contract", "playbook.workflows.file"],
        },
        "playbook.pre_run.with": {
            "definition": "Pre-run entry field for static playbook-owned invocation inputs passed only to the pre_run workflow.",
            "use_when": [
                "The bootstrap workflow needs fixed launch-time values owned by the playbook rather than by the caller.",
            ],
            "do_not_use_for": [
                "Caller-supplied activation inputs for the requested workflow; use playbook.workflows.with or command-line overrides for those.",
                "Dynamic workflow expressions; this surface is static YAML values only.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.pre_run", "summary": "Parent pre_run list surface"},
                {"handle": "playbook.workflows.with", "summary": "Sibling launch-time input surface for the requested workflow entry"},
                {"handle": "command-line.ordo-playbook.flag.input", "summary": "One-run caller override surface instead of playbook-owned static pre_run inputs"},
            ],
            "examples": [
                {"reference": "playbook.pre_run.with", "inputs": {"repo": "acme/app", "strict": True}},
            ],
            "inspect_next": ["playbook.workflows.with", "command-line.ordo-playbook.flag.input", "playbook.pre_run.state_bindings"],
        },
        "playbook.pre_run.state_bindings": {
            "definition": "Pre-run entry field for explicit state-location bindings that the pre_run workflow may use without widening the requested workflow's own state contract.",
            "use_when": [
                "The bootstrap workflow needs declared state access, but that access should stay explicit and scoped to pre_run setup.",
            ],
            "do_not_use_for": [
                "Sneaking extra state requirements into the main requested workflow; state widening is explicitly disallowed here.",
                "Ordinary requested-workflow state bindings; use playbook.workflows.state_bindings for those entry-specific bindings.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.pre_run_contract", "summary": "Contract that explains the pre_run state-scope boundary"},
                {"handle": "playbook.workflows.state_bindings", "summary": "Sibling binding surface for the requested workflow entry rather than pre_run setup"},
                {"handle": "state.workflow_surface.state_binding_field", "summary": "State contract surface for what one state binding means"},
            ],
            "examples": [
                {"reference": "playbook.pre_run.state_bindings", "inputs": {"shared_state": "global"}},
            ],
            "inspect_next": ["playbook.workflows.state_bindings", "state.workflow_surface.state_binding_field", "playbook.pre_run_contract"],
        },
        "playbook.profiles": {
            "definition": "Playbook field for declaring the reusable named profiles that this playbook may activate by default, by entry policy, or by caller override.",
            "use_when": [
                "The project needs a playbook-local catalog of named execution contexts instead of hard-coding one profile inside each workflow body.",
            ],
            "do_not_use_for": [
                "Choosing which profile wins for one invocation; use defaults, workflow entry policy, or command-line selection for that decision.",
                "Encoding one workflow-owned fixed profile contract; use workflow.profile when the workflow itself must bind one profile before guards run.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.profiles.file", "summary": "Child field for loading one declared profile from a separate file"},
                {"handle": "playbook.defaults.profile", "summary": "Soft default active profile choice drawn from the profiles catalog"},
                {"handle": "workflow.profile", "summary": "Workflow-owned fixed binding rather than a reusable playbook profile declaration"},
            ],
            "examples": [
                {"reference": "playbook.profiles", "inputs": {"backend": {"file": "backend.yml"}, "review": {"file": "review.yml"}}},
            ],
            "inspect_next": ["playbook.profiles.file", "playbook.defaults.profile", "profile"],
        },
        "playbook.profiles.file": {
            "definition": "Playbook profile-entry field that points one declared profile name at the profile file to load for that catalog entry.",
            "use_when": [
                "A named playbook profile should load its reusable runtime context from a separate profile document.",
            ],
            "do_not_use_for": [
                "Selecting the active profile for the current run; use playbook defaults or caller/entry selection surfaces for that choice.",
                "Pointing at a workflow file; use playbook.workflows.file or playbook.pre_run.file for workflow launch surfaces.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.profiles", "summary": "Parent playbook profile catalog surface"},
                {"handle": "profile.name", "summary": "Profile-owned internal name field inside the loaded profile document"},
                {"handle": "playbook.workflows.file", "summary": "Sibling field that selects a workflow file rather than a profile file"},
            ],
            "examples": [
                {"reference": "playbook.profiles.file", "inputs": {"file": "backend.yml"}},
            ],
            "inspect_next": ["profile.name", "playbook.defaults.profile", "playbook.workflows.file"],
        },
        "playbook.states": {
            "definition": "Playbook field for declaring the named state storage locations that workflows and playbook entries may bind explicitly.",
            "use_when": [
                "The project needs durable named storage targets that workflows may read, write, or delete through explicit state contracts instead of implicit files.",
            ],
            "do_not_use_for": [
                "Workflow-local transient dataflow; keep short-lived values in workflow values, step outputs, or direct inputs instead of declared state storage.",
                "Binding a workflow to one state location; use workflow.state_bindings or playbook entry state_bindings for the binding step rather than editing the catalog itself.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.states.path", "summary": "Child field that maps one declared state name to its storage path"},
                {"handle": "workflow.state_bindings", "summary": "Capability surface for binding declared state names into a workflow or entry"},
                {"handle": "state.workflow_surface.state_binding_field", "summary": "State-binding surface that consumes declared playbook state names"},
            ],
            "examples": [
                {"reference": "playbook.states", "inputs": {"shared_state": {"path": "repo.json"}, "cache": {"path": ".ordo/cache.json"}}},
            ],
            "inspect_next": ["playbook.states.path", "workflow.state_bindings", "state.workflow_surface.state_binding_field"],
        },
        "playbook.states.path": {
            "definition": "Playbook state-entry field that assigns one declared state location name to the filesystem path where that durable state is stored.",
            "use_when": [
                "A declared state location needs one concrete storage target so workflows can bind and resolve it explicitly.",
            ],
            "do_not_use_for": [
                "Binding a workflow role to a declared state location name; use workflow.state_bindings or entry state_bindings for that authoring step.",
                "Ordinary working-directory defaults or workflow file selection; this field declares state storage, not execution context.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.states", "summary": "Parent playbook state-location catalog"},
                {"handle": "workflow.state_bindings", "summary": "Binding surface that references declared state location names"},
                {"handle": "profile.working_directory", "summary": "Execution-directory context surface rather than a durable state storage declaration"},
            ],
            "examples": [
                {"reference": "playbook.states.path", "inputs": {"path": "repo.json"}},
            ],
            "inspect_next": ["workflow.state_bindings", "state.workflow_surface.state_binding_field", "playbook.states"],
        },
        "profile.connectors": {
            "definition": "Profile field for supplying family-keyed connector context objects to runs that activate this profile.",
            "use_when": [
                "Several runs under one profile need the same connector context, such as Compose directory/file/project settings, without repeating it in every workflow call.",
            ],
            "do_not_use_for": [
                "Publishing connector operations themselves; use connector.* handles to learn the public operation surface.",
                "Workflow business inputs that belong in declared workflow inputs rather than connector bootstrap context.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.connectors", "summary": "Playbook-level connector context before profile-specific overrides"},
                {"handle": "connector.compose", "summary": "One connector family that reads concrete context fields such as directory, file, and project_name"},
                {"handle": "connectors", "summary": "Top-level published connector namespace catalog"},
            ],
            "examples": [
                {
                    "reference": "profile.connectors",
                    "inputs": {
                        "compose.directory": "./deploy",
                        "compose.file": "compose.prod.yaml",
                        "compose.project_name": "orders-prod",
                    },
                }
            ],
            "inspect_next": ["playbook.connectors", "connector.compose", "operations"],
        },
        "playbook.connectors": {
            "definition": "Playbook field for supplying default family-keyed connector context objects across published workflows in this playbook.",
            "use_when": [
                "One repository-wide connector context default should apply before any profile-specific connector overrides are considered.",
            ],
            "do_not_use_for": [
                "Per-profile connector context variation; use profile.connectors for that narrower launch context.",
                "Publishing connector operations themselves; use connector.* handles to inspect the public connector surface.",
            ],
            "nearest_surfaces": [
                {"handle": "profile.connectors", "summary": "Profile-level connector context that can narrow or override playbook defaults"},
                {"handle": "connector.compose", "summary": "One connector family that reads concrete context fields such as directory, file, and project_name"},
                {"handle": "connectors", "summary": "Top-level published connector namespace catalog"},
            ],
            "examples": [
                {
                    "reference": "playbook.connectors",
                    "inputs": {
                        "compose.directory": "./deploy",
                    },
                }
            ],
            "inspect_next": ["profile.connectors", "connector.compose", "operations"],
        },
    }

    def add_node(name: str, *, contract: str, node_category: str, summary: str, metadata: JSONObject) -> None:
        snippet_surface = _snippet_surface_for_handle(name)
        effective_metadata = dict(metadata)
        overrides = model_node_overrides.get(name)
        if isinstance(overrides, dict):
            effective_metadata.update(overrides)
        lookup[name] = {
            "document_kind": "model_node",
            "node_kind": node_category,
            "name": name,
            "contract": contract,
            "summary": summary,
            "metadata": effective_metadata,
            "snippet_coverage": snippet_surface["snippet_coverage"],
            "canonical_examples": snippet_surface["canonical_examples"],
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
        "workflow.local_expression.filter",
        contract="workflow",
        node_category="overview",
        summary="Published local-expression pipeline filter metadata",
        metadata=model["local_expressions"],
    )
    add_node(
        "workflow.local_expression.builtin",
        contract="workflow",
        node_category="overview",
        summary="Published local-expression builtin metadata",
        metadata={"builtins": model["local_expressions"]["builtins"]},
    )
    for filter_spec in model["local_expressions"]["pipeline_filters"]:
        filter_metadata = dict(filter_spec)
        filter_name = filter_spec["name"]
        filter_metadata.setdefault(
            "definition",
            f"Pipeline-style local-expression filter `{filter_name}` for transforming, projecting, or checking one value after an expression root has already been selected.",
        )
        filter_metadata.setdefault(
            "use_when",
            [
                f"You need `{filter_name}` as one short pipeline stage inside an inline local expression rather than a function-style builtin call.",
            ],
        )
        filter_metadata.setdefault(
            "do_not_use_for",
            [
                "Function-style helper calls such as is_present(...) or format(...); those belong to workflow.local_expression.builtin.*.",
                "Representation parsing across text families before projection; use adapter families when the source first needs json/yaml/markdown/text interpretation.",
            ],
        )
        filter_metadata.setdefault(
            "nearest_surfaces",
            [
                {"handle": "workflow.local_expression.filter", "summary": "Overview of the pipeline filter family"},
                {"handle": "workflow.local_expressions", "summary": "Top-level workflow capability for local expressions"},
                {"handle": "workflow.local_expression.builtin", "summary": "Overview of function-style local-expression builtins"},
            ],
        )
        filter_metadata.setdefault(
            "inspect_next",
            ["workflow.local_expression.filter", "workflow.local_expression.builtin", "workflow.local_expressions"],
        )
        add_node(
            f"workflow.local_expression.filter.{filter_spec['name']}",
            contract="workflow",
            node_category="filter",
            summary="Published local-expression pipeline filter metadata",
            metadata=filter_metadata,
        )
    for builtin_spec in model["local_expressions"]["builtins"]:
        builtin_metadata = dict(builtin_spec)
        builtin_name = builtin_spec["name"]
        builtin_metadata.setdefault(
            "definition",
            f"Function-style local-expression builtin `{builtin_name}(...)` for special checks or formatting that read more honestly as a helper call than as a pipeline stage.",
        )
        builtin_metadata.setdefault(
            "use_when",
            [
                f"You need `{builtin_name}(...)` as a short helper call inside a workflow-owned expression.",
            ],
        )
        builtin_metadata.setdefault(
            "do_not_use_for",
            [
                "Ordinary pipeline shaping after one root value; prefer workflow.local_expression.filter.* for those transformations.",
                "Representation-aware parsing or projection from text families; use adapter families when the source first needs format-aware interpretation.",
            ],
        )
        builtin_metadata.setdefault(
            "nearest_surfaces",
            [
                {"handle": "workflow.local_expression.builtin", "summary": "Overview of function-style local-expression builtins"},
                {"handle": "workflow.local_expressions", "summary": "Top-level workflow capability for local expressions"},
                {"handle": "workflow.local_expression.filter", "summary": "Overview of pipeline-style local-expression filters"},
            ],
        )
        builtin_metadata.setdefault(
            "inspect_next",
            ["workflow.local_expression.builtin", "workflow.local_expression.filter", "workflow.local_expressions"],
        )
        add_node(
            f"workflow.local_expression.builtin.{builtin_spec['name']}",
            contract="workflow",
            node_category="builtin",
            summary="Published local-expression builtin metadata",
            metadata=builtin_metadata,
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
    if "workflow.step.if" in lookup:
        lookup["workflow.step.if"]["summary"] = "Local step-branching field for an optional step or local branch inside an already-valid path"
        lookup["workflow.step.if"]["metadata"]["role"] = "local_behavioral_variation"
        lookup["workflow.step.if"]["metadata"]["use_when"] = [
            "one local step is optional inside a path that is already valid",
            "a valid path needs one small local branch rather than a new applicability or admission decision",
            "the condition changes one step's behavior without deciding workflow applicability or step admission",
        ]
        lookup["workflow.step.if"]["metadata"]["do_not_use_for"] = [
            "workflow applicability or early rejection",
            "whether a path or step may run at all",
            "catch-all routing or policy admission",
        ]
    if "workflow.step.gate" in lookup:
        lookup["workflow.step.gate"]["summary"] = "Step-admission field for deciding whether a path or step may run at all"
        lookup["workflow.step.gate"]["metadata"]["role"] = "step_admission"
        lookup["workflow.step.gate"]["metadata"]["use_when"] = [
            "the real question is whether the protected path or step may execute at all",
            "admission depends on facts observed or computed earlier in the workflow",
        ]
        lookup["workflow.step.gate"]["metadata"]["do_not_use_for"] = [
            "whole-workflow applicability; use guards instead",
            "local behavioral variation inside an already-valid path; use if instead",
        ]
    for field in model["profile"]["top_level_fields"]:
        add_node(f"profile.{field['name']}", contract="profile", node_category="field", summary="Published profile field metadata", metadata=field)
    for field in model["profile"]["override_fields"]:
        add_node(f"profile.overrides.{field['name']}", contract="profile", node_category="override_field", summary="Published profile override field metadata", metadata=field)
    add_node(
        "routine_contract",
        contract="routine_contract",
        node_category="contract",
        summary="Published routine-registry contract metadata",
        metadata=model["routine_contract"],
    )
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
        connector_metadata = dict(connector)
        overrides = connector_family_overrides.get(connector["namespace"])
        if isinstance(overrides, dict):
            connector_metadata.update(overrides)
        add_node(
            f"connector.{connector['namespace']}",
            contract="connectors",
            node_category="connector_family",
            summary=f"Published connector family metadata for the {connector['namespace']} namespace",
            metadata=connector_metadata,
        )
        for operation in connector["operations"]:
            operation_metadata = dict(operation)
            operation_metadata.setdefault("namespace", connector["namespace"])
            operation_metadata.setdefault("reference", f"{connector['namespace']}.{operation['name']}")
            operation_overrides = connector_operation_overrides.get((connector["namespace"], operation["name"]))
            if isinstance(operation_overrides, dict):
                operation_metadata.update(operation_overrides)
            add_node(
                f"connector.{connector['namespace']}.{operation['name']}",
                contract="connectors",
                node_category="connector_operation",
                summary=f"Published connector operation metadata for {connector['namespace']}.{operation['name']}",
                metadata=operation_metadata,
            )

    for field_name, value in model["state"]["workflow_surface"].items():
        add_node(
            f"state.workflow_surface.{field_name}",
            contract="state",
            node_category="workflow_surface_field",
            summary="Published state workflow-surface metadata",
            metadata={"name": field_name, "value": value},
        )
    add_node(
        "state",
        contract="state",
        node_category="state_contract",
        summary="Published state contract metadata",
        metadata={
            **model["state"],
            "search_aliases": [
                "state key expression",
                "state key path",
                "bound state role",
                "declared state location",
            ],
        },
    )
    return lookup


def _build_workflow_authoring_node_lookup() -> dict[str, JSONObject]:
    payload = build_workflow_authoring_response()
    lookup: dict[str, JSONObject] = {}

    for rule in payload["rules"]:
        if not isinstance(rule, dict) or not isinstance(rule.get("name"), str):
            continue
        handle = f"workflow-authoring.{rule['name']}"
        lookup[handle] = {
            "document_kind": "workflow_authoring_node",
            "node_kind": "rule",
            "name": handle,
            "summary": rule["rule"],
            "metadata": rule,
            "snippet_coverage": "none",
            "canonical_examples": [],
        }

    for example_group in ("bounded_fan_out_examples", "routine_env_examples"):
        for example in payload.get(example_group, []):
            if not isinstance(example, dict) or not isinstance(example.get("name"), str):
                continue
            handle = f"workflow-authoring.example.{example['name']}"
            lookup[handle] = {
                "document_kind": "workflow_authoring_node",
                "node_kind": "example",
                "name": handle,
                "summary": str(example.get("summary") or "Published workflow-authoring example"),
                "metadata": {"group": example_group, **example},
                "snippet_coverage": "none",
                "canonical_examples": [],
            }

    return lookup


def _build_examples_node_lookup() -> dict[str, JSONObject]:
    payload = describe_examples_catalog()
    lookup: dict[str, JSONObject] = {}
    for example in payload["examples"]:
        if not isinstance(example, dict) or not isinstance(example.get("name"), str):
            continue
        handle = f"examples.{example['name']}"
        lookup[handle] = {
            "document_kind": "example_node",
            "node_kind": "example",
            "name": handle,
            "summary": f"Verified example at {example['path']}",
            "metadata": example,
            "snippet_coverage": "none",
            "canonical_examples": [],
        }
    return lookup


def _build_command_line_node_lookup() -> dict[str, JSONObject]:
    payload = build_command_line_response()
    lookup: dict[str, JSONObject] = {}

    flag_overrides: dict[tuple[str, str], JSONObject] = {
        (
            "ordo-playbook",
            "--file",
        ): {
            "definition": "Use one explicit playbook file for this invocation instead of the default playbook discovery path.",
            "use_when": [
                "You need to point this run at a different playbook file without changing repository defaults.",
            ],
            "do_not_use_for": [
                "Selecting a workflow profile; use --profile for that.",
                "Passing business inputs into the workflow; use --input or --input-file for those values.",
            ],
            "nearest_surfaces": [
                {"handle": "command-line.ordo-playbook", "summary": "Parent command surface for ordo-playbook"},
                {"handle": "playbook.workflows.file", "summary": "Playbook field that binds a published workflow name to a workflow file inside a playbook"},
            ],
        },
        (
            "ordo-playbook",
            "--profile",
        ): {
            "definition": "Select one named execution profile for this run.",
            "use_when": [
                "You need one project-local profile override for this invocation.",
            ],
            "do_not_use_for": [
                "Passing workflow business inputs; use --input or --input-file for those.",
                "Changing the playbook file itself; use --file for that.",
            ],
            "nearest_surfaces": [
                {"handle": "command-line.ordo-playbook", "summary": "Parent command surface for ordo-playbook"},
                {"handle": "workflow.profile", "summary": "Workflow-declared fixed profile binding inside authored workflow source"},
                {"handle": "profile.inputs", "summary": "Profile-owned input defaults that may supply declared workflow inputs"},
            ],
        },
        (
            "ordo-playbook",
            "--input",
        ): {
            "definition": "Set one top-level workflow input from inline command-line text for this run.",
            "use_when": [
                "You need a quick one-run workflow input override that fits naturally on the command line.",
            ],
            "do_not_use_for": [
                "Large text bodies or file-backed content; use --input-file when the value already lives in a file.",
                "Selecting a profile or playbook file; use --profile or --file for those launch concerns.",
            ],
            "nearest_surfaces": [
                {"handle": "command-line.ordo-playbook", "summary": "Parent command surface for ordo-playbook"},
                {"handle": "command-line.ordo-playbook.flag.input_file", "summary": "Sibling flag for loading one workflow input value from a file"},
                {"handle": "workflow.inputs_contract", "summary": "Workflow contract that defines which activation inputs are allowed and required"},
            ],
        },
        (
            "ordo-playbook",
            "--input-file",
        ): {
            "definition": "Set one top-level workflow input by reading its raw UTF-8 value from a file for this run.",
            "use_when": [
                "You need to pass longer text or file-backed content into one workflow input without shell quoting it inline.",
            ],
            "do_not_use_for": [
                "Short inline values that are clearer directly on the command line; use --input for those.",
                "Selecting a profile or playbook file; use --profile or --file for those launch concerns.",
            ],
            "nearest_surfaces": [
                {"handle": "command-line.ordo-playbook", "summary": "Parent command surface for ordo-playbook"},
                {"handle": "command-line.ordo-playbook.flag.input", "summary": "Sibling flag for setting one workflow input inline on the command line"},
                {"handle": "workflow.inputs_contract", "summary": "Workflow contract that defines which activation inputs are allowed and required"},
            ],
        },
        (
            "ordo-playbook",
            "--json",
        ): {
            "definition": "Emit machine-readable JSON for this invocation instead of the default text rendering.",
            "use_when": [
                "You need stable machine-readable output for automation, tooling, or precise inspection.",
            ],
            "do_not_use_for": [
                "Changing workflow behavior; this flag changes output format, not execution semantics.",
            ],
            "nearest_surfaces": [
                {"handle": "command-line.ordo-playbook", "summary": "Parent command surface for ordo-playbook"},
                {"handle": "overview", "summary": "Public discovery overview that teaches the main JSON-capable help surfaces"},
            ],
        },
    }

    for command in payload["commands"]:
        command_name = command["name"]
        lookup[f"command-line.{command_name}"] = {
            "document_kind": "command_line_node",
            "node_kind": "command",
            "name": f"command-line.{command_name}",
            "summary": "Published command-line command metadata",
            "metadata": command,
            "snippet_coverage": "none",
            "canonical_examples": [],
        }
        for flag in command.get("flags", []):
            normalized = flag["name"].lstrip("-").replace("-", "_")
            flag_metadata = dict(flag)
            flag_metadata.setdefault(
                "definition",
                f"Stable launch flag for {command_name} that changes one invocation property without editing workflow or playbook source.",
            )
            flag_metadata.setdefault(
                "use_when",
                [
                    f"You need a one-run override for {command_name} instead of changing project-local source files.",
                ],
            )
            flag_metadata.setdefault(
                "do_not_use_for",
                [
                    "Encoding durable workflow semantics that should be declared in playbook or workflow source.",
                ],
            )
            flag_metadata.setdefault(
                "nearest_surfaces",
                [
                    {
                        "handle": f"command-line.{command_name}",
                        "summary": f"Parent command surface for {command_name}",
                    }
                ],
            )
            flag_metadata.setdefault(
                "examples",
                [
                    example
                    for example in command.get("examples", [])
                    if isinstance(example, str) and f"{flag['name']} " in example
                ],
            )
            flag_metadata.setdefault(
                "inspect_next",
                [f"command-line.{command_name}", "command-line"],
            )
            overrides = flag_overrides.get((command_name, flag["name"]))
            if isinstance(overrides, dict):
                flag_metadata.update(overrides)
            lookup[f"command-line.{command_name}.flag.{normalized}"] = {
                "document_kind": "command_line_node",
                "node_kind": "flag",
                "name": f"command-line.{command_name}.flag.{normalized}",
                "summary": "Published command-line flag metadata",
                "metadata": flag_metadata,
                "snippet_coverage": "none",
                "canonical_examples": [],
            }
    return lookup


def _build_public_handle_reference(handle: str) -> JSONObject:
    topic = next((item for item in PUBLIC_TOPICS if item["name"] == handle), None)
    if topic is not None:
        return {
            "handle": handle,
            "kind": "topic",
            "summary": topic["summary"],
            "command": f"ordo-help {handle} --json",
        }

    for lookup, topic_name in (
        (_build_workflow_authoring_node_lookup(), "workflow-authoring"),
        (_build_examples_node_lookup(), "examples"),
        (_build_model_node_lookup(), "model"),
        (_build_command_line_node_lookup(), "command-line"),
        (_build_capability_lookup(), "capabilities"),
    ):
        node = lookup.get(handle)
        if node is None:
            continue
        return {
            "handle": handle,
            "kind": str(node["node_kind"]),
            "summary": str(node["summary"]),
            "command": f"ordo-help describe {handle} --json",
            "topic": topic_name,
        }

    return {"handle": handle, "kind": "unknown", "summary": "Unresolved public handle", "command": f"ordo-help describe {handle} --json"}


def _build_workflow_authoring_rule_reference(rule_name: str, *, rule_lookup: dict[str, JSONObject]) -> JSONObject:
    handle = f"workflow-authoring.{rule_name}"
    node = _build_workflow_authoring_node_lookup().get(handle)
    rule = rule_lookup.get(rule_name)
    summary = str(rule["rule"]) if isinstance(rule, dict) and isinstance(rule.get("rule"), str) else str(node["summary"]) if node is not None else rule_name
    return {
        "name": rule_name,
        "handle": handle,
        "summary": summary,
        "command": f"ordo-help describe {handle} --json",
    }


def _build_example_reference(handle: str, *, examples: JSONObject) -> JSONObject:
    if handle.startswith("workflow-authoring.example."):
        node = _build_workflow_authoring_node_lookup().get(handle)
        if node is not None:
            return {
                "name": str(node["metadata"]["name"]),
                "handle": handle,
                "summary": str(node["summary"]),
                "command": f"ordo-help describe {handle} --json",
            }

    node = _build_examples_node_lookup().get(handle)
    if node is not None:
        return {
            "name": str(node["metadata"]["name"]),
            "handle": handle,
            "summary": str(node["summary"]),
            "command": f"ordo-help describe {handle} --json",
        }

    if isinstance(examples, dict):
        for example in examples.get("examples", []):
            if isinstance(example, dict) and f"examples.{example.get('name')}" == handle:
                return {
                    "name": str(example["name"]),
                    "handle": handle,
                    "summary": f"Verified example at {example['path']}",
                    "command": f"ordo-help describe {handle} --json",
                }

    return {"name": handle, "handle": handle, "summary": "Unresolved related example", "command": f"ordo-help describe {handle} --json"}


def build_snippet_coverage_response() -> JSONObject:
    """Return snippet-coverage metadata for public describable handles."""

    handles: list[JSONObject] = []
    lookup_groups = (
        ("capabilities", _build_capability_lookup()),
        ("model", _build_model_node_lookup()),
        ("command-line", _build_command_line_node_lookup()),
        ("workflow-authoring", _build_workflow_authoring_node_lookup()),
        ("examples", _build_examples_node_lookup()),
    )
    seen_handles: set[str] = set()
    for topic_name, lookup in lookup_groups:
        for handle, payload in lookup.items():
            if handle in seen_handles:
                continue
            seen_handles.add(handle)
            handles.append(
                {
                    "handle": handle,
                    "topic": topic_name,
                    "document_kind": payload["document_kind"],
                    "node_kind": payload["node_kind"],
                    "snippet_coverage": payload.get("snippet_coverage", "none"),
                    "canonical_example_count": len(payload.get("canonical_examples", [])),
                }
            )
    handles.sort(key=lambda item: str(item["handle"]))
    coverage_counts: dict[str, int] = {}
    for item in handles:
        coverage = str(item["snippet_coverage"])
        coverage_counts[coverage] = coverage_counts.get(coverage, 0) + 1
    return {
        "document_kind": "snippet_coverage",
        "purpose": "Coverage map for canonical verified snippets published through ordo-help describe.",
        "coverage_levels": ["none", "excerpt_verified", "harness_verified"],
        "summary": {
            "total_handles": len(handles),
            "coverage_counts": coverage_counts,
        },
        "handles": handles,
    }


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
                    "command": f"ordo-help describe examples.{example['name']} --json",
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
                    "command": f"ordo-help describe workflow-authoring.{rule['name']} --json",
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


def _expand_search_tokens(text: str) -> list[str]:
    expanded: list[str] = []
    for token in _search_tokens(text):
        if token not in expanded:
            expanded.append(token)
        for segment in re.split(r"[._:/#-]+", token):
            if len(segment) < 2:
                continue
            if segment not in expanded:
                expanded.append(segment)
    return expanded


def _query_matches(query: str, searchable: str) -> bool:
    if not query:
        return False
    if query in searchable:
        return True
    tokens = _expand_search_tokens(query)
    if not tokens:
        return False
    return all(token in searchable for token in tokens if token not in {query})


def _search_tokens(text: str) -> list[str]:
    return _SEARCH_TOKEN_RE.findall(text.lower())


def _resolve_example_topic_alias(topic: str) -> str | None:
    lowered = topic.strip().lower()
    if not lowered.startswith("examples/"):
        return None
    for example in describe_examples_catalog()["examples"]:
        path = str(example.get("path") or "")
        if lowered == path.lower():
            return f"examples.{example['name']}"
    return None


def _resolve_describe_topic_alias(topic: str) -> str:
    example_alias = _resolve_example_topic_alias(topic)
    if example_alias is not None:
        return example_alias
    if topic.startswith("operation."):
        candidate = f"connector.{topic.removeprefix('operation.')}"
        if candidate in _build_model_node_lookup():
            return candidate
    return topic


def _build_unknown_topic_suggestions(topic: str) -> list[JSONObject]:
    suggestions: list[JSONObject] = []
    example_alias = _resolve_example_topic_alias(topic)
    if example_alias is not None:
        suggestions.append(
            {
                "kind": "canonical_topic",
                "topic": example_alias,
                "command": f"ordo-help describe {example_alias} --json",
                "reason": "Example paths resolve to canonical examples.<name> handles.",
            }
        )
    if topic.startswith("operation."):
        operation_reference = topic.removeprefix("operation.")
        connector_topic = f"connector.{operation_reference}"
        suggestions.append(
            {
                "kind": "operation_command",
                "topic": operation_reference,
                "command": f"ordo-help operation {operation_reference} --json",
                "reason": "Operation references are described with the dedicated operation command.",
            }
        )
        if connector_topic in _build_model_node_lookup():
            suggestions.append(
                {
                    "kind": "connector_topic",
                    "topic": connector_topic,
                    "command": f"ordo-help describe {connector_topic} --json",
                    "reason": "Connector operation metadata is also available as a model node.",
                }
            )
    if topic.startswith("examples/") and example_alias is None:
        suggestions.append(
            {
                "kind": "examples_catalog",
                "topic": "examples",
                "command": "ordo-help examples --json",
                "reason": "List published examples to find the canonical examples.<name> handle.",
            }
        )
    if topic == "state":
        suggestions.append(
            {
                "kind": "canonical_topic",
                "topic": "state",
                "command": "ordo-help describe state --json",
                "reason": "State discovery is published as a describable state model node.",
            }
        )
    suggestions.append(
        {
            "kind": "search",
            "topic": topic,
            "command": f"ordo-help search {json.dumps(topic)} --json",
            "reason": "Search can reveal nearby public topics, facts, or operations.",
        }
    )
    return suggestions


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
            "1. ordo-help features",
            "2. ordo-help overview",
            "3. ordo-help model",
            "4. ordo-help workflow-authoring",
            "5. ordo-help capabilities",
            "6. ordo-help command-line",
            "7. ordo-help operations",
            "8. ordo-help examples",
            "",
            "Add --json for machine-readable output.",
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
    conditional_roles = payload.get("conditional_roles")
    if isinstance(conditional_roles, dict):
        lines.extend(
            [
                "",
                "Conditional roles:",
                f"- rule: {conditional_roles['rule']}",
                *[f"- avoid: {item}" for item in conditional_roles.get("avoid", [])],
            ]
        )
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
            "Failure diagnostics:",
            f"- rule: {payload['failure_diagnostics']['rule']}",
            f"- external payload fields: {', '.join(payload['failure_diagnostics']['external_payload_fields'])}",
            "",
            "Connector namespaces:",
        ]
    )
    lines.extend(f"- {namespace}" for namespace in payload["connector_namespaces"])
    summary = payload.get("snippet_coverage_summary")
    if isinstance(summary, dict):
        coverage_counts = summary.get("coverage_counts", {})
        lines.extend(
            [
                "",
                "Snippet coverage:",
                f"- total handles: {summary.get('total_handles', 0)}",
                f"- none: {coverage_counts.get('none', 0)}",
                f"- excerpt_verified: {coverage_counts.get('excerpt_verified', 0)}",
                f"- harness_verified: {coverage_counts.get('harness_verified', 0)}",
            ]
        )
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


def render_features_text(payload: JSONObject) -> str:
    """Return the text features surface."""

    lines = ["features", payload["purpose"]]
    for cluster in payload["clusters"]:
        lines.extend(["", cluster["name"], f"what: {cluster['summary']}"])
        published_names = cluster.get("published_names", {})
        if isinstance(published_names, dict):
            lines.append("published names:")
            for group_name, values in published_names.items():
                if isinstance(values, dict):
                    rendered = "; ".join(f"{key}={', '.join(map(str, item_values))}" for key, item_values in values.items())
                    lines.append(f"- {group_name}: {rendered}")
                    continue
                if isinstance(values, list):
                    lines.append(f"- {group_name}: {', '.join(map(str, values))}")
        lines.append(f"keywords: {', '.join(cluster['keywords'])}")
        lines.append("when appropriate:")
        lines.extend(f"- {item}" for item in cluster["appropriate_when"])
        lines.append("when inappropriate:")
        lines.extend(f"- {item}" for item in cluster["inappropriate_when"])
        lines.append("inspect next:")
        for item in cluster["inspect_next"]:
            lines.append(f"- {item['handle']}: {item['summary']}")
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
        run_failure_surface = command.get("run_failure_surface")
        if isinstance(run_failure_surface, dict):
            lines.extend(
                [
                    "",
                    "run failure surface:",
                    f"- rule: {run_failure_surface['rule']}",
                    f"- external payload fields: {', '.join(run_failure_surface['external_payload_fields'])}",
                ]
            )
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


def _append_text_canonical_examples(lines: list[str], examples: list[JSONObject]) -> None:
    if not examples:
        return
    lines.extend(["", "canonical examples:"])
    for example in examples:
        lines.append(f"- {example['name']}: {example['summary']}")
        if isinstance(example.get("form"), str):
            lines.append(f"  example_for: {example['form']}")
        yaml_text = example.get("yaml")
        if isinstance(yaml_text, str) and yaml_text:
            lines.append("  yaml:")
            for snippet_line in yaml_text.splitlines():
                lines.append(f"    {snippet_line}")


def render_capability_node_text(payload: JSONObject) -> str:
    """Return the text capability-node surface."""

    definition = payload.get("definition") or payload["node_kind"]
    lines = [payload["name"], str(definition), "", f"node kind: {payload['node_kind']}", f"snippet coverage: {payload.get('snippet_coverage', 'none')}"]
    if payload["node_kind"] == "capability":
        lines.extend(["", f"status: {payload['status']}", f"scope: {payload['scope']}"])
        use_when = payload.get("use_when", [])
        if isinstance(use_when, list) and use_when:
            lines.extend(["", "use when:"])
            lines.extend(f"- {item}" for item in use_when if isinstance(item, str))
        do_not_use_for = payload.get("do_not_use_for", [])
        if isinstance(do_not_use_for, list) and do_not_use_for:
            lines.extend(["", "do not use for:"])
            lines.extend(f"- {item}" for item in do_not_use_for if isinstance(item, str))
        related_capabilities = payload.get("related_capabilities", [])
        related_model_nodes = payload.get("related_model_nodes", [])
        if related_capabilities or related_model_nodes:
            lines.extend(["", "related surfaces:"])
            lines.extend(f"- {item}" for item in related_capabilities if isinstance(item, str))
            lines.extend(f"- {item}" for item in related_model_nodes if isinstance(item, str))
        for item in payload.get("must_not_infer", []):
            lines.append(f"must not infer: {item}")
    else:
        lines.extend([f"surface: {payload['surface']}", payload["rule"]])
    _append_text_canonical_examples(lines, payload.get("canonical_examples", []))
    return "\n".join(lines)


def render_model_node_text(payload: JSONObject) -> str:
    """Return the text model-node surface."""

    def _render_arg_value(value: object) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    lines = [payload["name"]]
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        lines.append(payload["summary"])
        _append_text_canonical_examples(lines, payload.get("canonical_examples", []))
        return "\n".join(lines)

    definition = metadata.get("definition") or payload["summary"]
    lines.extend([
        str(definition),
        "",
        f"node kind: {payload['node_kind']}",
        f"snippet coverage: {payload.get('snippet_coverage', 'none')}",
    ])

    use_when = metadata.get("use_when", [])
    if isinstance(use_when, list) and use_when:
        lines.extend(["", "use when:"])
        lines.extend(f"- {item}" for item in use_when if isinstance(item, str))

    do_not_use_for = metadata.get("do_not_use_for", [])
    if isinstance(do_not_use_for, list) and do_not_use_for:
        lines.extend(["", "do not use for:"])
        lines.extend(f"- {item}" for item in do_not_use_for if isinstance(item, str))

    nearest_surfaces = metadata.get("nearest_surfaces", [])
    if isinstance(nearest_surfaces, list) and nearest_surfaces:
        lines.extend(["", "nearest surfaces:"])
        for item in nearest_surfaces:
            if isinstance(item, dict):
                lines.append(f"- {item['handle']}: {item['summary']}")

    namespace = metadata.get("namespace")
    kind = metadata.get("kind")
    maturity = metadata.get("maturity")
    deprecated = metadata.get("deprecated")
    if any(isinstance(item, str) for item in (namespace, kind, maturity)):
        lines.extend(["", "published contract:"])
        if isinstance(namespace, str):
            lines.append(f"- namespace: {namespace}")
        if isinstance(kind, str):
            lines.append(f"- kind: {kind}")
        if isinstance(maturity, str):
            lines.append(f"- maturity: {maturity}")
        if isinstance(deprecated, bool):
            lines.append(f"- deprecated: {'yes' if deprecated else 'no'}")

    operations = metadata.get("operations", [])
    if isinstance(operations, list) and operations:
        lines.extend(["", "published operations:"])
        for item in operations:
            if isinstance(item, dict):
                lines.append(f"- {item['name']}: {item['summary']}")

    bootstrap = metadata.get("bootstrap")
    if isinstance(bootstrap, dict):
        prerequisites = bootstrap.get("prerequisites", [])
        context_fields = bootstrap.get("context_fields", [])
        if isinstance(prerequisites, list) and prerequisites:
            lines.extend(["", "bootstrap prerequisites:"])
            lines.extend(f"- {item}" for item in prerequisites if isinstance(item, str))
        if isinstance(context_fields, list) and context_fields:
            lines.extend(["", "bootstrap context:"])
            lines.extend(f"- {item}" for item in context_fields if isinstance(item, str))

    authored_context_fields = metadata.get("authored_context_fields", [])
    if isinstance(authored_context_fields, list) and authored_context_fields:
        lines.extend(["", "authored connector context fields:"])
        for item in authored_context_fields:
            if isinstance(item, dict):
                lines.append(f"- {item['name']}: {item['summary']}")

    inputs = metadata.get("inputs")
    if isinstance(inputs, dict) and inputs:
        lines.extend(["", "inputs:"])
        for name, shape in inputs.items():
            lines.append(f"- {name}: {shape}")

    required_in_forms = metadata.get("required_in_forms", [])
    if isinstance(required_in_forms, list) and required_in_forms:
        lines.extend(["", "required in forms:"])
        lines.extend(f"- {item}" for item in required_in_forms if isinstance(item, str))

    optional_in_forms = metadata.get("optional_in_forms", [])
    if isinstance(optional_in_forms, list) and optional_in_forms:
        lines.extend(["", "optional in forms:"])
        lines.extend(f"- {item}" for item in optional_in_forms if isinstance(item, str))

    required_fields = metadata.get("required_fields", [])
    if isinstance(required_fields, list) and required_fields:
        lines.extend(["", "required fields:"])
        lines.extend(f"- {item}" for item in required_fields if isinstance(item, str))

    optional_fields = metadata.get("optional_fields", [])
    if isinstance(optional_fields, list) and optional_fields:
        lines.extend(["", "optional fields:"])
        lines.extend(f"- {item}" for item in optional_fields if isinstance(item, str))

    access_surface = metadata.get("access_surface")
    declaration_shape = metadata.get("declaration_shape")
    activation_requirement = metadata.get("activation_requirement")
    unknown_input_policy = metadata.get("unknown_input_policy")
    declared_keys_required_at_activation = metadata.get("declared_keys_required_at_activation")
    rejects_unknown_activation_inputs = metadata.get("rejects_unknown_activation_inputs")
    validated_by = metadata.get("validated_by")
    if any(
        [
            isinstance(access_surface, str),
            isinstance(declaration_shape, str),
            isinstance(activation_requirement, str),
            isinstance(unknown_input_policy, str),
            isinstance(declared_keys_required_at_activation, bool),
            isinstance(rejects_unknown_activation_inputs, bool),
            isinstance(validated_by, str),
        ]
    ):
        lines.extend(["", "activation contract:"])
        if isinstance(declaration_shape, str):
            lines.append(f"- declaration shape: {declaration_shape}")
        if isinstance(access_surface, str):
            lines.append(f"- access surface: {access_surface}")
        if isinstance(activation_requirement, str):
            lines.append(f"- activation requirement: {activation_requirement}")
        if isinstance(unknown_input_policy, str):
            lines.append(f"- unknown input policy: {unknown_input_policy}")
        if isinstance(declared_keys_required_at_activation, bool):
            lines.append(f"- declared keys required at activation: {'yes' if declared_keys_required_at_activation else 'no'}")
        if isinstance(rejects_unknown_activation_inputs, bool):
            lines.append(f"- rejects unknown activation inputs: {'yes' if rejects_unknown_activation_inputs else 'no'}")
        if isinstance(validated_by, str):
            lines.append(f"- validated by: {validated_by}")

    declaration_fields = metadata.get("declaration_fields", [])
    if isinstance(declaration_fields, list) and declaration_fields:
        lines.extend(["", "declaration fields:"])
        for item in declaration_fields:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            type_name = item.get("type")
            required = item.get("required")
            role = item.get("authoring_role")
            parts = []
            if isinstance(type_name, str):
                parts.append(f"type={type_name}")
            if isinstance(required, bool):
                parts.append(f"required={'yes' if required else 'no'}")
            if isinstance(role, str):
                parts.append(f"role={role}")
            suffix = f" ({', '.join(parts)})" if parts else ""
            if isinstance(name, str):
                lines.append(f"- {name}{suffix}")

    outputs = metadata.get("outputs")
    if isinstance(outputs, dict) and outputs:
        lines.extend(["", "outputs:"])
        for name, shape in outputs.items():
            lines.append(f"- {name}: {shape}")

    input_type = metadata.get("input_type")
    output_type = metadata.get("output_type")
    argument_count = metadata.get("argument_count")
    authored_form = metadata.get("authored_form")
    allowed_roots = metadata.get("allowed_roots", [])
    if any(
        [
            isinstance(input_type, str),
            isinstance(output_type, str),
            isinstance(argument_count, int),
            isinstance(authored_form, str),
            isinstance(allowed_roots, list) and bool(allowed_roots),
        ]
    ):
        lines.extend(["", "expression contract:"])
        if isinstance(input_type, str):
            lines.append(f"- input type: {input_type}")
        if isinstance(output_type, str):
            lines.append(f"- output type: {output_type}")
        if isinstance(argument_count, int):
            lines.append(f"- argument count: {argument_count}")
        if isinstance(authored_form, str):
            lines.append(f"- authored form: {authored_form}")
        if isinstance(allowed_roots, list) and allowed_roots:
            lines.append(f"- allowed roots: {', '.join(str(item) for item in allowed_roots)}")

    preflight_observations = metadata.get("preflight_observations", [])
    if isinstance(preflight_observations, list) and preflight_observations:
        lines.extend(["", "preflight observations:"])
        for item in preflight_observations:
            if not isinstance(item, dict):
                continue
            probe = item.get("probe")
            with_payload = item.get("with")
            if isinstance(probe, str) and isinstance(with_payload, dict) and with_payload:
                rendered_args = ", ".join(f"{key}={_render_arg_value(value)}" for key, value in with_payload.items())
                lines.append(f"- {probe}({rendered_args})")
            elif isinstance(probe, str):
                lines.append(f"- {probe}")

    pipeline_filters = metadata.get("pipeline_filters", [])
    if isinstance(pipeline_filters, list) and pipeline_filters:
        lines.extend(["", "pipeline filters:"])
        for item in pipeline_filters:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            input_type = item.get("input_type")
            output_type = item.get("output_type")
            argument_count = item.get("argument_count")
            if isinstance(name, str):
                detail = []
                if isinstance(input_type, str):
                    detail.append(f"in={input_type}")
                if isinstance(output_type, str):
                    detail.append(f"out={output_type}")
                if isinstance(argument_count, int):
                    detail.append(f"args={argument_count}")
                suffix = f" ({', '.join(detail)})" if detail else ""
                lines.append(f"- {name}{suffix}")

    builtins = metadata.get("builtins", [])
    if isinstance(builtins, list) and builtins:
        lines.extend(["", "builtins:"])
        for item in builtins:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            summary = item.get("summary")
            if isinstance(name, str):
                if isinstance(summary, str) and summary:
                    lines.append(f"- {name}: {summary}")
                else:
                    lines.append(f"- {name}")

    selectors = metadata.get("selectors", [])
    if isinstance(selectors, list) and selectors:
        lines.extend(["", "selectors:"])
        lines.extend(f"- {item}" for item in selectors if isinstance(item, str))

    actions = metadata.get("actions", [])
    if isinstance(actions, list) and actions:
        lines.extend(["", "actions:"])
        lines.extend(f"- {item}" for item in actions if isinstance(item, str))

    shortcuts = metadata.get("shortcuts", [])
    if isinstance(shortcuts, list) and shortcuts:
        lines.extend(["", "shortcuts:"])
        lines.extend(f"- {item}" for item in shortcuts if isinstance(item, str))

    outer_binding_form = metadata.get("outer_binding_form")
    host_binding_rules = metadata.get("host_binding_rules", [])
    family_owned_body = metadata.get("family_owned_body")
    read_write_boundary = metadata.get("read_write_boundary")
    if any([
        isinstance(outer_binding_form, str),
        isinstance(host_binding_rules, list) and bool(host_binding_rules),
        isinstance(family_owned_body, bool),
        isinstance(read_write_boundary, dict) and bool(read_write_boundary),
    ]):
        lines.extend(["", "adapter seam:"])
        if isinstance(outer_binding_form, str):
            lines.append(f"- outer binding form: {outer_binding_form}")
        if isinstance(family_owned_body, bool):
            lines.append(f"- family-owned body: {'yes' if family_owned_body else 'no'}")
        if isinstance(host_binding_rules, list) and host_binding_rules:
            lines.append("- host binding rules:")
            lines.extend(f"  - {item}" for item in host_binding_rules if isinstance(item, str))
        if isinstance(read_write_boundary, dict) and read_write_boundary:
            read_value = read_write_boundary.get("read")
            write_value = read_write_boundary.get("write")
            if isinstance(read_value, str):
                lines.append(f"- read path returns: {read_value}")
            if isinstance(write_value, str):
                lines.append(f"- write path returns: {write_value}")

    invalidates = metadata.get("invalidates_observations", [])
    if isinstance(invalidates, list) and invalidates:
        lines.extend(["", "invalidates observations:"])
        lines.extend(f"- {item}" for item in invalidates if isinstance(item, str))

    failure_modes = metadata.get("failure_modes", [])
    if isinstance(failure_modes, list) and failure_modes:
        lines.extend(["", "failure modes:"])
        lines.extend(f"- {item}" for item in failure_modes if isinstance(item, str))

    effects = metadata.get("effects", [])
    if isinstance(effects, list) and effects:
        lines.extend(["", "effects:"])
        lines.extend(f"- {item}" for item in effects if isinstance(item, str))

    replaced_by = metadata.get("replaced_by", [])
    if isinstance(replaced_by, list) and replaced_by:
        lines.extend(["", "replaced by:"])
        lines.extend(f"- {item}" for item in replaced_by if isinstance(item, str))

    related_examples = metadata.get("related_examples")
    examples = related_examples if isinstance(related_examples, list) else metadata.get("examples", [])
    if isinstance(examples, list) and examples:
        lines.extend(["", "related examples:"])
        for item in examples:
            if not isinstance(item, dict):
                continue
            reference = item.get("reference")
            inputs = item.get("inputs")
            if isinstance(reference, str) and isinstance(inputs, dict) and inputs:
                rendered_args = ", ".join(f"{key}={_render_arg_value(value)}" for key, value in inputs.items())
                lines.append(f"- {reference}({rendered_args})")
            elif isinstance(reference, str):
                lines.append(f"- {reference}")

    inspect_next = metadata.get("inspect_next", [])
    if isinstance(inspect_next, list) and inspect_next:
        lines.extend(["", "inspect next:"])
        lines.extend(f"- {item}" for item in inspect_next if isinstance(item, str))

    _append_text_canonical_examples(lines, payload.get("canonical_examples", []))
    return "\n".join(lines)


def render_command_line_node_text(payload: JSONObject) -> str:
    """Return the text command-line-node surface."""

    lines = [payload["name"]]
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        lines.extend([payload["summary"], "", f"node kind: {payload['node_kind']}"])
        return "\n".join(lines)

    definition = metadata.get("definition") or payload["summary"]
    lines.extend([
        str(definition),
        "",
        f"node kind: {payload['node_kind']}",
        f"snippet coverage: {payload.get('snippet_coverage', 'none')}",
    ])

    use_when = metadata.get("use_when", [])
    if isinstance(use_when, list) and use_when:
        lines.extend(["", "use when:"])
        lines.extend(f"- {item}" for item in use_when)

    do_not_use_for = metadata.get("do_not_use_for", [])
    if isinstance(do_not_use_for, list) and do_not_use_for:
        lines.extend(["", "do not use for:"])
        lines.extend(f"- {item}" for item in do_not_use_for)

    nearest_surfaces = metadata.get("nearest_surfaces", [])
    if isinstance(nearest_surfaces, list) and nearest_surfaces:
        lines.extend(["", "nearest surfaces:"])
        for item in nearest_surfaces:
            if isinstance(item, dict):
                lines.append(f"- {item['handle']}: {item['summary']}")

    usage = metadata.get("usage")
    if isinstance(usage, str) and usage:
        lines.extend(["", f"usage: {usage}"])

    discovery_commands = metadata.get("discovery_commands", [])
    if isinstance(discovery_commands, list) and discovery_commands:
        lines.extend(["", "start with:"])
        for item in discovery_commands:
            if isinstance(item, dict):
                lines.append(f"- {item['name']}: {item['summary']}")

    modes = metadata.get("modes", [])
    if isinstance(modes, list) and modes:
        lines.extend(["", "runtime modes:"])
        for item in modes:
            if isinstance(item, dict):
                mode_name = item.get("name")
                summary = item.get("summary")
                lines.append(f"- {mode_name}: {summary}")

    authoring_passes = metadata.get("authoring_passes")
    if isinstance(authoring_passes, dict):
        lines.extend(["", "workflow authoring passes:", f"- rule: {authoring_passes['rule']}"])
        for item in authoring_passes.get("passes", []):
            if isinstance(item, dict):
                lines.append(f"- {item['mode']}: {item['purpose']} ({item['question']})")

    flags = metadata.get("flags", [])
    if isinstance(flags, list) and flags:
        lines.extend(["", "stable flags:"])
        for flag in flags:
            if isinstance(flag, dict):
                suffix = f" {flag.get('value_shape', '')}".rstrip()
                repeatable = " (repeatable)" if flag.get("repeatable") else ""
                lines.append(f"- {flag['name']}{suffix}{repeatable}: {flag['summary']}")

    examples = metadata.get("examples", [])
    if isinstance(examples, list) and examples:
        lines.extend(["", "examples:"])
        seen_examples: set[str] = set()
        for item in examples:
            if not isinstance(item, str) or item in seen_examples:
                continue
            seen_examples.add(item)
            lines.append(f"- {item}")

    run_success_surface = metadata.get("run_success_surface")
    if isinstance(run_success_surface, str) and run_success_surface:
        lines.extend(["", "run success surface:", f"- {run_success_surface}"])

    run_failure_surface = metadata.get("run_failure_surface")
    if isinstance(run_failure_surface, dict):
        lines.extend(["", "run failure surface:", f"- rule: {run_failure_surface['rule']}"])
        fields = run_failure_surface.get("external_payload_fields", [])
        if isinstance(fields, list) and fields:
            lines.append(f"- external payload fields: {', '.join(str(item) for item in fields)}")

    input_override_precedence = metadata.get("input_override_precedence", [])
    if isinstance(input_override_precedence, list) and input_override_precedence:
        lines.extend(["", "input override precedence:"])
        lines.extend(f"- {item}" for item in input_override_precedence if isinstance(item, str))

    inspect_next = metadata.get("inspect_next", [])
    if isinstance(inspect_next, list) and inspect_next:
        lines.extend(["", "inspect next:"])
        lines.extend(f"- {item}" for item in inspect_next if isinstance(item, str))

    _append_text_canonical_examples(lines, payload.get("canonical_examples", []))
    return "\n".join(lines)


def render_workflow_authoring_node_text(payload: JSONObject) -> str:
    """Return the text workflow-authoring-node surface."""

    lines = [payload["name"], payload["summary"], "", f"node kind: {payload['node_kind']}", f"snippet coverage: {payload.get('snippet_coverage', 'none')}"]

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return "\n".join(lines)

    guidance_level = metadata.get("guidance_level")
    priority = metadata.get("priority")
    if isinstance(guidance_level, str) or isinstance(priority, str):
        lines.append("")
        if isinstance(guidance_level, str):
            lines.append(f"guidance level: {guidance_level}")
        if isinstance(priority, str):
            lines.append(f"priority: {priority}")

    why = metadata.get("why")
    if isinstance(why, list) and why:
        lines.extend(["", "why:"])
        lines.extend(f"- {item}" for item in why if isinstance(item, str))

    prefer = metadata.get("prefer")
    if isinstance(prefer, list) and prefer:
        lines.extend(["", "prefer:"])
        lines.extend(f"- {item}" for item in prefer if isinstance(item, str))

    avoid = metadata.get("avoid")
    if isinstance(avoid, list) and avoid:
        lines.extend(["", "avoid:"])
        lines.extend(f"- {item}" for item in avoid if isinstance(item, str))

    stop_when = metadata.get("stop_when")
    if isinstance(stop_when, list) and stop_when:
        lines.extend(["", "stop when:"])
        lines.extend(f"- {item}" for item in stop_when if isinstance(item, str))

    examples = metadata.get("examples")
    if isinstance(examples, list) and examples:
        lines.extend(["", "examples:"])
        lines.extend(f"- {item}" for item in examples if isinstance(item, str))

    why_invalid = metadata.get("why_invalid")
    if isinstance(why_invalid, str) and why_invalid:
        lines.extend(["", f"why invalid: {why_invalid}"])

    generated_env = metadata.get("generated_env")
    if isinstance(generated_env, list) and generated_env:
        lines.extend(["", "generated env:"])
        lines.extend(f"- {item}" for item in generated_env if isinstance(item, str))

    recommended = metadata.get("recommended")
    if isinstance(recommended, str) and recommended:
        lines.extend(["", f"recommended: {recommended}"])

    invalid = metadata.get("invalid")
    if isinstance(invalid, str) and invalid:
        lines.extend(["", f"invalid: {invalid}"])

    yaml = metadata.get("yaml")
    if isinstance(yaml, str) and yaml:
        lines.extend(["", "yaml:"])
        lines.extend(f"  {line}" for line in yaml.splitlines())

    return "\n".join(lines)


def render_example_node_text(payload: JSONObject) -> str:
    """Return the text example-node surface."""

    return "\n".join([payload["name"], payload["summary"], "", f"node kind: {payload['node_kind']}"])


def render_snippet_coverage_text(payload: JSONObject) -> str:
    """Return the text snippet-coverage surface."""

    lines = ["snippet-coverage", payload["purpose"], "", "Coverage summary:"]
    coverage_counts = payload["summary"]["coverage_counts"]
    lines.append(f"- total handles: {payload['summary']['total_handles']}")
    for coverage in payload["coverage_levels"]:
        lines.append(f"- {coverage}: {coverage_counts.get(coverage, 0)}")
    lines.extend(["", "Handles:"])
    for item in payload["handles"]:
        lines.append(f"- {item['handle']}: {item['snippet_coverage']}")
    return "\n".join(lines)


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
        "supported_node_kinds": ["capability", "negative_rule", "model_node", "workflow_authoring_node", "example_node", "command_line_node"],
        "suggestions": _build_unknown_topic_suggestions(topic),
    }
    if as_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stderr.write(payload["message"])
        sys.stderr.write("\n")
        for suggestion in payload["suggestions"]:
            sys.stderr.write(f"- {suggestion['command']}\n")
    return 1


def _resolve_public_topic(topic: str) -> tuple[JSONObject, object] | None:
    """Resolve one describable public topic to its payload and renderer."""

    if topic == "overview":
        return build_overview_response(), render_overview_text
    if topic == "model":
        return build_model_response(), render_model_text
    if topic == "features":
        return build_features_response(), render_features_text
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
    if topic == "snippet-coverage":
        return build_snippet_coverage_response(), render_snippet_coverage_text
    capability_node = _build_capability_lookup().get(topic)
    if capability_node is not None:
        return capability_node, render_capability_node_text
    model_node = _build_model_node_lookup().get(topic)
    if model_node is not None:
        return model_node, render_model_node_text
    command_line_node = _build_command_line_node_lookup().get(topic)
    if command_line_node is not None:
        return command_line_node, render_command_line_node_text
    workflow_authoring_node = _build_workflow_authoring_node_lookup().get(topic)
    if workflow_authoring_node is not None:
        return workflow_authoring_node, render_workflow_authoring_node_text
    example_node = _build_examples_node_lookup().get(topic)
    if example_node is not None:
        return example_node, render_example_node_text
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

    features_parser = subparsers.add_parser("features", add_help=False)
    features_parser.add_argument("--json", action="store_true", dest="as_json")

    workflow_authoring_parser = subparsers.add_parser("workflow-authoring", add_help=False)
    workflow_authoring_parser.add_argument("--json", action="store_true", dest="as_json")

    command_line_parser = subparsers.add_parser("command-line", add_help=False)
    command_line_parser.add_argument("--json", action="store_true", dest="as_json")

    operations_parser = subparsers.add_parser("operations", add_help=False)
    operations_parser.add_argument("--json", action="store_true", dest="as_json")

    examples_parser = subparsers.add_parser("examples", add_help=False)
    examples_parser.add_argument("--json", action="store_true", dest="as_json")

    snippet_coverage_parser = subparsers.add_parser("snippet-coverage", add_help=False)
    snippet_coverage_parser.add_argument("--json", action="store_true", dest="as_json")

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
    if parsed.command == "features":
        return _emit_payload(build_features_response(), as_json=as_json, renderer=render_features_text)
    if parsed.command == "workflow-authoring":
        return _emit_payload(build_workflow_authoring_response(), as_json=as_json, renderer=render_workflow_authoring_text)
    if parsed.command == "command-line":
        return _emit_payload(build_command_line_response(), as_json=as_json, renderer=render_command_line_text)
    if parsed.command == "operations":
        return _emit_payload(describe_operations(), as_json=as_json, renderer=render_operations_text)
    if parsed.command == "examples":
        return _emit_payload(describe_examples_catalog(), as_json=as_json, renderer=render_examples_text)
    if parsed.command == "snippet-coverage":
        return _emit_payload(build_snippet_coverage_response(), as_json=as_json, renderer=render_snippet_coverage_text)
    if parsed.command == "operation":
        payload = build_operation_response(parsed.reference)
        if payload is None:
            return _emit_unknown_operation(parsed.reference, as_json=as_json)
        return _emit_payload(payload, as_json=as_json, renderer=render_operation_text)
    if parsed.command == "describe":
        resolved_topic = _resolve_describe_topic_alias(parsed.topic)
        resolved = _resolve_public_topic(resolved_topic)
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
