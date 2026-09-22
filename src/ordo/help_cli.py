"""Public CLI entrypoint for ordo-help discovery."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy

import yaml

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
    {"name": "features", "summary": "Inspect workflow features, named surfaces, and when to use them"},
    {"name": "overview", "summary": "Start with the Ordo world map"},
    {"name": "model", "summary": "Inspect the main workflow contracts"},
    {"name": "workflow-rules", "summary": "Inspect preferred workflow rules, paired check/review passes, routine cautions, early guards, and let usage"},
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

DESCRIBABLE_TOPICS: tuple[str, ...] = ("features", "overview", "model", "workflow-rules", "capabilities", "command-line", "operations", "examples", "snippet-coverage")

RECOMMENDED_FIRST_CALLS: tuple[dict[str, str], ...] = (
    {"command": "ordo-help features", "purpose": "Scan workflow features, named surfaces, and when to use them"},
    {"command": "ordo-help overview", "purpose": "Get the Ordo world map"},
    {"command": "ordo-help model", "purpose": "Learn the main DSL surfaces"},
    {"command": "ordo-help workflow-rules", "purpose": "Learn preferred workflow rules, including paired check/review passes"},
    {"command": "ordo-help capabilities", "purpose": "Learn capability boundaries"},
    {"command": "ordo-help command-line", "purpose": "Inspect public launch commands, flags, and distinct check/review roles"},
    {"command": "ordo-help operations", "purpose": "Inspect the public operation catalog"},
    {"command": "ordo-help examples", "purpose": "Inspect verified repository examples"},
    {"command": "ordo-help snippet-coverage", "purpose": "Inspect which public handles do and do not publish canonical verified snippets"},
)

WORKFLOW_AUTHORING_RULES: tuple[dict[str, object], ...] = (
    {
        "name": "paired_check_review_passes",
        "priority": "critical_check_review_loop",
        "guidance_level": "required_default",
        "rule": "After adding or changing a workflow, run both ordo-playbook check <workflow> and ordo-playbook review <workflow>. Treat them as complementary check/review passes, not substitutes.",
        "why": [
            "check answers whether the workflow is applicable and execution-ready now",
            "review answers whether the workflow still has workflow-quality findings",
            "using both makes it harder to mistake execution readiness for workflow completeness",
        ],
        "prefer": [
            "use check to surface guard, explicit probe-coverage, and applicability gaps",
            "use review to surface workflow-quality findings",
            "report both results when presenting workflow changes as complete",
        ],
        "avoid": [
            "treating check as sufficient workflow sign-off",
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
        "related_rules": ["paired_check_review_passes"],
        "related_examples": ["examples.playbook-workflows", "examples.playbook-pre-run"],
        "published_names_kind": "playbook",
    },
    {
        "name": "profile",
        "summary": "Reusable runtime context for missing-input defaults, execution working directory, explicit override metadata, and profile-scoped launch metadata.",
        "keywords": ["profile", "inputs", "working_directory", "checks", "overrides", "launchers", "deprecated", "routines"],
        "appropriate_when": [
            "Several runs need the same missing-input defaults or execution context without copying them into every workflow entry.",
            "Selection among project modes belongs to launch context rather than to workflow-authored branching.",
            "Static graph resolves declared fixed profiles and known literal/input/let switches without activation. Declared workflow defaults and protected bindings survive; explicit CLI profile authority applies to pre_run. Unknown selections remain symbolic rather than reading remembered state.",
        ],
        "inappropriate_when": [
            "The behavior changes workflow semantics and should be made explicit in guards, steps, or playbook workflow-entry inputs.",
            "The value is only relevant to one workflow body and does not justify reusable launch context.",
        ],
        "inspect_next": ["profile.inputs", "profile.working_directory", "profile.overrides", "profile.launchers", "playbook.defaults.profile", "command-line.ordo-playbook"],
        "related_rules": ["explicit_execution_context", "local_artifacts_are_context"],
        "related_examples": ["examples.playbook-pre-run", "examples.launcher-step"],
        "published_names_kind": "profile",
    },
    {
        "name": "workflow",
        "summary": "One executable workflow unit with declared inputs, let bindings, state needs, blocks, and typed step forms.",
        "keywords": ["workflow", "inputs", "let", "state_needs", "blocks", "step forms", "profile_switch"],
        "appropriate_when": [
            "The task needs one explicit executable contract with declared activation inputs and reviewable runtime structure.",
            "The logic belongs to one workflow body rather than to playbook launch policy or reusable fragment definition only.",
            "One intentionally project-local workflow subtree must bind itself to one fixed execution profile through workflow.profile.",
            "Document every root input with a non-blank description and expose inputs without a default, selected launch-profile value, or entry binding through playbook with caller slots: x: for required inputs, x?: for optional inputs. Review reports input_authoring warnings; CLI overrides do not suppress them or change activation errors.",
            "Plain workflows show omits top-level launch_profile entirely and removes caller_slot, sources, and coverage from retained inputs; other record fields are preserved except required, which reports caller-slot obligation: true for a required slot, false for an optional slot, not workflow declaration requiredness. No optional field is added. --json keeps all fields unchanged, including original normalized required, caller_slot, the launch_profile source label and initial activation name and source, not the final bound workflow profile.",
            "Inspect the main caller interface with ordo-playbook workflows show <workflow>: plain output keeps the JSON-shaped serialized envelope but filters the inputs mapping to caller_slot required or optional, hides caller_slot none, and retains inputs: {} when no caller slots exist. --json retains the unchanged full declaration contract with normalized required, caller_slot, sources, and coverage. Coverage reports source presence, not execution readiness; required caller slots still require caller input. Launch-profile values are not exposed, and CLI input overrides or runtime profile switches do not count as authored sources.",
            "Plain workflows show adds top-level warnings only for required workflow inputs with coverage missing, including declarations hidden from inputs. Each warning has code discovery.workflow.input_source_missing, input, message, and hint: no workflow default, not supplied by the selected launch profile (or no profile selected), no concrete playbook binding, and no caller slot; expose a caller slot or supply a source. Optional missing declarations do not warn, and warnings is omitted when none qualify. --json is unchanged. This uses authored source presence without readiness or state analysis; check, review, plan, run, explain, and next are unchanged.",
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
        "keywords": ["state", "state_needs", "state_bindings", "states", "state_set", "state_delete", "bound locations", "graph", "possible processes"],
        "appropriate_when": [
            "Workflow data must survive across runs through declared state locations rather than through implicit files or ambient context.",
            "State reads, writes, and deletions should be explicit in the workflow contract and step surface.",
            "Use ordo-playbook graph to see how workflows connect through persistent state, where shared data is written, and where it is removed. No active task is required.",
            "Shared context: writers → readers, not execution order. Free alternative reader roots are marked (data use; alternative sources). Read +field as writes, −field as deletes, and ? as a conditional change. Distinct data sources can show the same operation on several branches: ↔ (reference) leaves never repeat its subtree or execution. Alternative writers of the same data are not expanded. also reads from keeps extra sources visible; reads from: name? marks conditional/fallback data use separately from +field?. Guards and check determine applicability; alternative ends are not sequential steps.",
            "parameter stands for a key that has not been selected; relationships apply to a matching context instance. Graph does not read saved state or run probes. A missing edge does not prove independence in external systems. Use graph --json for dependencies, conditions, and unresolved relationships.",
            "After exploring graph, use workflows show <workflow> for inputs, check or explain <workflow> for readiness, and next for a recommendation in the current environment. See docs/static-graph.md for the technical reference.",
            "Write or delete only after the final read of the same actual file, regardless of roles or profiles; use value + register for per-run dataflow.",
            "Before binding, authoring validation retains the same-role rule. After binding, relative paths resolve in each access context: aliases count as one file, while the same role may access different files and be valid.",
            "Bound validation reports state_storage.write_before_last_read for proven violations, or state_storage.identity_unresolved for conservative early rejection of relevant uncertain write/later-read pairs, not a proven violation. Both codes have the validation.workflow. prefix.",
            "Top-level check defers effectful state mutations after conditions and gates, then continues to independent guards without mutation, simulation, outputs, registers, or reuse. Plan retains the nodes; run executes admitted mutations once in order.",
            "Aggregate runtime.value.state_missing diagnostics group emitted failures for the same resolved target, reporting occurrence_count (emitted events) and reported_at (unique effective structural locations of emitted diagnostic events, not all dependent uses) with references. This changes reporting only; operation results stay unchanged and next keeps groups candidate-local. Inspect state for identity and counting boundaries.",
        ],
        "inappropriate_when": [
            "The data is purely step-local, transient, or better expressed as direct step outputs or ordinary workflow values.",
            "State is being used as a vague catch-all context channel instead of a declared bound storage surface.",
            "Nested state deferral or full composed-run proof: a reached run/loop after deferral halts with state_deferral_invocation_barrier, which profiles cannot resume. Cross-invocation and cross-iteration guarantees remain deferred.",
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
        "inspect_next": ["workflow.run_contract", "workflow.run.run", "workflow.run.for_each", "workflow.step_forms.run_invocation", "workflow.step_forms.inline_fan_out_invocation", "workflow-rules.run_target_vs_inline_fan_out"],
        "related_rules": ["bounded_fan_out_is_structured_invocation", "run_target_vs_inline_fan_out", "fan_out_scope_and_conditions", "inline_fan_out_invalid_shapes"],
        "related_examples": ["workflow-rules.example.named_run_target_fan_out", "workflow-rules.example.inline_fan_out_local_steps", "workflow-rules.example.inline_fan_out_inner_if"],
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
        "inspect_next": ["workflow-rules.early_guards", "workflow-rules.input_validation_default", "workflow-rules.delegated_applicability", "workflow.local_expression.filter", "workflow.local_expression.builtin.is_missing"],
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
        "inspect_next": ["workflow.step.gate", "workflow.step_forms.gate_checkpoint", "workflow.run.gate", "workflow-rules.separate_control_surfaces", "workflow-rules.guard_result_contract"],
        "related_rules": ["separate_control_surfaces", "guard_result_contract"],
        "related_examples": ["workflow-rules.example.inline_fan_out_inner_if"],
        "published_names_kind": "gates",
    },
    {
        "name": "conditions",
        "summary": "Boolean condition surface shared by step if and gate, with if for optional local branching and gate for admission decisions.",
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
        "inspect_next": ["workflow.step.if", "workflow.step.gate", "workflow-rules.native_expression_contexts", "workflow-rules.fan_out_scope_and_conditions"],
        "related_rules": ["guard_result_contract", "fan_out_scope_and_conditions", "native_expression_contexts"],
        "related_examples": ["workflow-rules.example.inline_fan_out_inner_if"],
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
        "inspect_next": ["workflow.local_expression.filter", "workflow.local_expression.builtin", "workflow.local_expression.builtin.is_missing", "workflow.local_expression.filter.lookup", "workflow.local_expression.filter.only", "workflow-rules.native_expression_contexts", "workflow.local_expression.adapter_seam"],
        "related_rules": ["native_expression_contexts", "guard_result_contract", "representation_adapters"],
        "related_examples": ["examples.local-expression-filters"],
        "published_names_kind": "local-expressions",
    },
    {
        "name": "connectors",
        "summary": "Published operation catalog for external probes and actions, grouped by stable namespaces.",
        "keywords": ["connectors", "operations", "namespace", "probe", "action", "public surface", "async merge", "expected_head_sha", "test_merge", "standalone", "request_id", "Actions", "run_attempt", "check_suite_id", "check_run_id"],
        "appropriate_when": [
            "The workflow needs one published external operation instead of a repository-local helper or opaque fallback.",
            "Typed public operations express product intent better than broad execution surfaces.",
            "Use gh.actions.run with exactly one of run_id or check_suite_id; omitted/null attempt observes latest then pins that numbered attempt. Pass returned run_id and run_attempt as gh.actions.run.jobs inputs run_id and explicit attempt. gh.pr.checks check_suite_id bridges check runs to the direct GraphQL Actions association; null association is found=false. Jobs are complete read-only observations, not tested-SHA attestation or merge policy. gh.actions is a namespace segment, not an executable operation.",
            "Use gh.pr.list with head, head_owner, base and explicit state: all to distinguish no matches, one open PR, multiple open PRs, and closed history; unknown facts block dependent decisions. gh.pr.create is a separate action with its own mandatory open check. One existing open PR including draft is non-OK already_exists, not successful reuse; uncertain submission leaves created=null. No atomic uniqueness or exactly-once guarantee is provided.",
            "Connector authors use ctx.call(name, inputs=...) for same-family probe dependencies with already-resolved values, never reevaluated expressions. Full and local dotted names work; omitted inputs/None preserve legacy behavior. Cross-family calls and probe-to-action hidden mutation are rejected; no new action composition. Inspect connector.authoring.",
            "For GitHub async merge, inspect gh.pr identity and stack_state, accept gh.pr.checks evidence, submit gh.pr.merge with expected_head_sha from the accepted CI head, then save request_id for gh.pr.merge.request. Acceptance is not completion.",
            "For gh.pr.merge and gh.pr.merge.request, repository is optional: a valid explicit OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error.",
            "Use fs.file for UTF-8 content and metadata from the same opened regular file; safe-open requires nonzero O_NOFOLLOW and O_NONBLOCK, with no unsafe fallback or atomic snapshot guarantee.",
            "GitHub repository inputs and connector_contexts.gh.repository use literal ASCII OWNER/REPO operands, not URLs; the context is a default, not an authorization allowlist.",
            "Users need connector-backed runtime failures to identify the external tool or remote system rather than looking like generic workflow mistakes.",
            "Use git.upstream to detect the exact configured remote, including nested names such as team/origin, and its local tracking-tail remote_branch. git.sync.push can use this remote when omitted or null; explicit names keep fetch/push targets clear. Run alone validates exact remote-inventory membership before transport.",
            "Use git.branch.delete for local cleanup: optional strictly boolean force defaults to false (git branch -d); force: true uses -D after the caller has established cleanup eligibility, including squash-merged work. Default-branch protection via origin/HEAD and current/worktree checkout restrictions still apply. Inspect connector.git.branch.delete.",
            "Use git.remote with a configured remote name to observe effective fetch_urls, push_urls, and mirror locally. Git applies URL rewrites; literal observed URLs are preserved without normalization or redaction. Missing remote is exists=false with empty URL lists and mirror=null; an existing remote without a mirror setting is mirror=false. The caller chooses acceptable destinations. Use git.repo for repository facts, git.upstream for branch tracking, and git.sync.push for publication.",
        ],
        "inappropriate_when": [
            "You are treating a missing public capability as permission to improvise local semantics silently.",
            "The behavior belongs to launch metadata or pure workflow-local transformation instead of an external operation.",
            "Do not replace accepted CI head evidence with a freshly fetched head. Checks on test-merge candidate M bind expected head H, not M. First-version merge rejects stacked and unknown scope; no atomic base or stack guarantee, polling, queue administration, or admin bypass is provided.",
            "Git sync remote inputs are configured identifiers, not ad-hoc URLs, paths, or options. Configured URLs and helpers remain trusted; this is not a protocol sandbox.",
        ],
        "inspect_next": ["operations", "connector.authoring", "connector.git.remote", "connector.git.repo", "connector.git.upstream", "connector.git.sync.push", "connector.gh", "connector.gh.actions.run", "connector.gh.actions.run.jobs", "connector.gh.pr.list", "connector.gh.pr.create", "connector.gh.pr", "connector.gh.pr.checks", "connector.gh.pr.merge", "connector.gh.pr.merge.request", "connector.fs", "command-line.ordo-playbook", "workflow-rules.decision_order", "workflow-rules.structured_surface_bias"],
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
        "inspect_next": ["routine_contract", "routine_contract.workflow_call_surface", "routine_contract.workflow_call.env", "workflow-rules.routine.*", "workflow-rules.explicit_execution_context", "workflow-rules.decision_order"],
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
        "inspect_next": ["workflow.local_expression.adapter_seam", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter.json", "workflow.local_expression.adapter.text", "workflow.local_expression.adapter.yaml", "workflow-rules.representation_adapters"],
        "related_rules": ["representation_adapters", "native_expression_contexts"],
        "related_examples": ["examples.text-adapter"],
        "published_names_kind": "adapters",
    },
)


GH_PR_LIST_GUIDANCE = (
    "GitHub candidate discovery: gh.pr.list observes a full filtered REST pull-request collection, not the search index. "
    "repository is optional with the standard connector_contexts.gh.repository default and explicit OWNER/REPO override. "
    "state is required: open|closed|all. Prefer state: all for find/create-oriented inspection, optionally narrowed by head/head_owner/base. "
    "head_owner is the head repository owner (user or organization), not PR author, and requires head; owner plus branch is not exact repository identity. "
    "Compare returned head_repository for exact fork matching. Internal pagination has no public page/cursor/limit; incomplete traversal fails. "
    "head with head_owner composes server owner:branch; bare head is matched exactly locally across all state/base pages because GitHub does not guarantee bare-head filtering. Missing head_ref for local filtering fails. The 100-page ceiling applies before local filtering. GitHub.com only, matching bootstrap authentication. "
    "Full traversal is not an atomic snapshot or a total remote count guarantee. "
    "Empty success means no matches within the supplied filters; one result is a candidate, not automatically the correct PR. "
    "Workflow rules classify none, one open, multiple open, and closed history; unknown facts block dependent decisions. "
    "Closed/merged history may require additional workflow rules. Listing does not authorize creation, reopening, or merge. "
    "gh.pr reads detailed facts by pull_number; gh.pr.create is a separate action with its own mandatory open check. Inspect connector.gh.pr.list for canonical filtered classification fragments."
)


GH_PR_CREATE_GUIDANCE = (
    "GitHub creation: gh.pr.create requires head, base, title, and an explicit boolean draft; body defaults to empty. "
    "repository is optional: valid explicit OWNER/REPO overrides connector_contexts.gh.repository; omitted or null uses context, malformed explicit input fails without fallback. "
    "head_repository is a full source OWNER/REPO, default target repository; explicit cross-repository intent requires it, with no fork guessing. "
    "head_owner is an optional consistency assertion, otherwise derived from the exact source repository. Same-organization head_repo API argument is derived repository NAME. Reject same-branch/same-repository requests. "
    "The action uses ctx.call('gh.pr.list', inputs=...) with resolved repository/head/head_owner/base and state: open; require complete traversal and exact case-insensitive head_repository_key identity. "
    "One exact open match including draft returns non-OK already_exists with pull_number, url, created=false and no POST; multiple matches return ambiguous; unknown identity and list failure return precheck_failed. "
    "No existing match permits one POST. Only validated HTTP 201 means created=true; malformed 201, timeout, or server failure returns creation_unknown with created=null. "
    "HTTP 422 is generic create_refused, not universal duplicate evidence; preserve API errors. No POST retry or automatic readback reconciliation. "
    "This is not find-or-reuse or closed-history policy: workflow-owned gh.pr.list state: all classification precedes create's separate open check. "
    "Concurrent duplicates can race the check: no atomic uniqueness or exactly-once guarantee. No CI waiting, merge, push, fork, branch cleanup, or extra issue/project operations. Inspect connector.gh.pr.create."
)

SDK_CALL_GUIDANCE = (
    "Connector-author SDK: ctx.call(name, *, inputs=None) supports nonempty already-resolved inputs only for same-family probe dependencies. "
    "Full references (gh.pr.list) and local dotted names (pr.list) work; values are not reevaluated as expressions or templates. "
    "Omitted inputs or None preserve legacy no-input behavior. Cross-family calls and probe-to-action hidden mutation are rejected; no new action composition. "
    "Inspect connector.authoring for dependency boundaries and verified examples."
)


GH_PR_MERGE_GUIDANCE = (
    "GitHub async merge: gh.pr observes head/base/test-merge identity and stack_state "
    "(standalone/stacked/unknown) plus stack; gh.pr.checks observes CI evidence. "
    "gh.pr.merge requires expected_head_sha from the accepted CI head, never a freshly fetched replacement. "
    "For gh.pr.merge and gh.pr.merge.request, repository is optional: a valid explicit OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error. "
    "For checks on candidate M with verified base B and head H, submit expected_head_sha=H, not M. "
    "The first version rejects stacked PRs and unknown scope before submission; there is no atomic base or stack guarantee. "
    "Save the action result request_id UUID for gh.pr.merge.request: accepted submission is not completion. "
    "Observe pending/merged/failed/enqueued once; unavailable is not failed and enqueued is not merged. "
    "Only an exact matching existing request is reusable. No polling, queue administration, or admin bypass is provided. "
    "GitHub automatic issue closing and branch configuration effects are outside this action. "
    "Inspect connector.gh.pr.merge and connector.gh.pr.merge.request for the verified canonical workflow example."
)


GRAPH_GUIDANCE = (
    "Show how workflows connect through persistent state. Use ordo-playbook graph to explore related workflows, "
    "where they write shared data, and where that data is removed. No active task is required."
)


GRAPH_PRESENTATION = (
    "Read +field as a write, −field as a deletion, and ? as a conditional change. "
    "A write need not be the first write; −context removes the selected context."
)


GRAPH_SOURCE_PLACEMENT = (
    "Shared context: writers → readers, not execution order. A free reader root is marked "
    "(data use; alternative sources) because it uses data without mutating the context. "
    "This shows shared data, not a mandatory sequence: guards and check determine applicability, "
    "and alternative ends are not sequential steps. Playbook order helps arrange workflows when their "
    "relationships leave a choice. Writers and deletions can also be branches. When sources already form "
    "a chain, the deepest source is the parent; also reads from keeps other sources visible. Distinct data from "
    "incomparable sources is shown under each source: the first source in display order holds the full "
    "occurrence, and ↔ (reference) leaves show the same operation without repeating its subtree. "
    "Alternative writers of the same data stay together. reads from: name? marks known conditional or fallback "
    "data use, separately from +field?. Fallback reads still count as data use. "
    "A missing graph edge does not prove independence in external systems."
)


GRAPH_CONTEXT_GUIDANCE = (
    "Graph does not read saved state, run probes, or recommend what to do next. Use workflows show <workflow> "
    "for inputs, check <workflow> to check whether it can run, explain <workflow> to understand why, "
    "and next for a recommendation in the current environment."
)


GRAPH_ROLE_GUIDANCE = (
    "↔ marks the same workflow: state/kind identifies another role; (reference) is a leaf sighting, not another execution. A deletion appears near the "
    "related data's users; this does not require running every reader before deleting the data."
)


GRAPH_PARAMETER_GUIDANCE = (
    "parameter stands for a key that has not been selected; the relationship applies to a matching context instance. "
    "Use graph --json for detailed dependencies, conditions, and unresolved relationships. "
    "Technical reference: docs/static-graph.md and meta/model/runtime/graph-v1.md."
)


def build_capabilities_response() -> JSONObject:
    return {**describe_capabilities(), "gh_pr_merge_guidance": GH_PR_MERGE_GUIDANCE,
            "gh_pr_create_guidance": GH_PR_CREATE_GUIDANCE, "connector_authoring_guidance": SDK_CALL_GUIDANCE,
            "graph_guidance": GRAPH_GUIDANCE, "graph_presentation": GRAPH_PRESENTATION,
            "graph_source_placement": GRAPH_SOURCE_PLACEMENT, "graph_context": GRAPH_CONTEXT_GUIDANCE,
            "graph_parameters": GRAPH_PARAMETER_GUIDANCE, "graph_roles": GRAPH_ROLE_GUIDANCE}


def build_operations_response() -> JSONObject:
    return {**describe_operations(), "gh_pr_merge_guidance": GH_PR_MERGE_GUIDANCE,
            "gh_pr_create_guidance": GH_PR_CREATE_GUIDANCE, "connector_authoring_guidance": SDK_CALL_GUIDANCE}


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
            "ordo-help workflow-rules",
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
        "graph_roles": GRAPH_ROLE_GUIDANCE,
        "graph_parameters": GRAPH_PARAMETER_GUIDANCE,
        "graph_context": GRAPH_CONTEXT_GUIDANCE,
        "graph_guidance": GRAPH_GUIDANCE,
        "graph_presentation": GRAPH_PRESENTATION,
        "graph_source_placement": GRAPH_SOURCE_PLACEMENT,
        "purpose": "World map for Ordo discovery and authoring bootstrap",
        "gh_pr_list_guidance": GH_PR_LIST_GUIDANCE,
        "gh_pr_create_guidance": GH_PR_CREATE_GUIDANCE,
        "connector_authoring_guidance": SDK_CALL_GUIDANCE,
        "gh_pr_merge_guidance": GH_PR_MERGE_GUIDANCE,
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
            "state_deferral": "Top-level check defers effectful state writes/deletes after conditions and gates and continues to independent guards, without mutation, simulation, outputs, registers, or reuse. Plan retains ordered non-reusable nodes; run executes admitted mutations once.",
            "state_boundary": "Nested analysis does not defer state. A reached run/loop after deferral halts with state_deferral_invocation_barrier; profiles cannot resume it. Cross-invocation and cross-iteration guarantees remain deferred.",
            "check_unknown": "Inspect allowed_state, analysis_complete, incomplete_reasons, and unevaluated_relevant_guards. allowed false can mean unknown, not blocked; missing_facts is not inferred from unevaluated expressions.",
        },
        "workflow_check_review_passes": {
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
        "graph_roles": GRAPH_ROLE_GUIDANCE,
        "graph_parameters": GRAPH_PARAMETER_GUIDANCE,
        "graph_context": GRAPH_CONTEXT_GUIDANCE,
        "graph_guidance": GRAPH_GUIDANCE,
        "graph_presentation": GRAPH_PRESENTATION,
        "graph_source_placement": GRAPH_SOURCE_PLACEMENT,
        "gh_pr_create_guidance": GH_PR_CREATE_GUIDANCE,
        "connector_authoring_guidance": SDK_CALL_GUIDANCE,
        "gh_pr_merge_guidance": GH_PR_MERGE_GUIDANCE,
        "workflow": describe_workflow_contract(),
        "profile": describe_profile_contract(),
        "routine_contract": describe_routine_contract(),
        "playbook": describe_playbook_contract(),
        "state": describe_state_contract(),
        "connectors": describe_operations()["connectors"],
        "local_expressions": describe_local_expression_surface(),
        "representation_adapters": describe_representation_adapter_surface(),
    }


class _HelpResponseContext:
    """Own snippet and lookup reuse for one response, never across requests."""

    def __init__(self) -> None:
        self.snippets: dict[str, JSONObject] | None = None
        self.lookups: dict[str, dict[str, JSONObject]] = {}

    def snippet_surface(self, handle: str) -> JSONObject:
        # Load at the first existing snippet access, preserving earlier failures.
        if self.snippets is None:
            self.snippets = describe_help_snippets()
        return _snippet_surface_for_handle(handle, snippets=self.snippets)

    def lookup(self, topic: str) -> dict[str, JSONObject]:
        if topic not in self.lookups:
            if topic == "workflow-rules":
                lookup = _build_workflow_rules_node_lookup()
            else:
                builder = {
                    "examples": _build_examples_node_lookup,
                    "model": _build_model_node_lookup,
                    "command-line": _build_command_line_node_lookup,
                    "capabilities": _build_capability_lookup,
                }[topic]
                lookup = builder(context=self)
            # Publish only completed tables; builder exceptions still propagate.
            self.lookups[topic] = lookup
        return self.lookups[topic]


def _snippet_surface_for_handle(handle: str, *, snippets: dict[str, JSONObject] | None = None) -> JSONObject:
    if snippets is None:
        snippets = describe_help_snippets()
    entry = snippets.get(handle)
    if not isinstance(entry, dict):
        return {"snippet_coverage": "none", "canonical_examples": []}
    return {
        "snippet_coverage": str(entry.get("snippet_coverage", "none")),
        # Nodes may share a catalog entry, but must not share mutable examples.
        "canonical_examples": deepcopy(list(entry.get("canonical_examples", []))),
    }


def build_features_response() -> JSONObject:
    """Return the compact feature map for workflow discovery."""

    context = _HelpResponseContext()
    model = build_model_response()
    workflow_rules = build_workflow_rules_response()
    examples = describe_examples_catalog()
    rule_lookup = {str(rule["name"]): rule for rule in workflow_rules["rules"] if isinstance(rule, dict)}

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
                "inspect_next": [_build_public_handle_reference(str(handle), context=context) for handle in spec["inspect_next"]],
                "related_rules": [_build_workflow_rule_reference(str(name), rule_lookup=rule_lookup, context=context) for name in spec["related_rules"]],
                "related_examples": [_build_example_reference(str(name), examples=examples, context=context) for name in spec["related_examples"]],
            }
        )

    return {
        "document_kind": "features",
        "purpose": "Compact workflow feature map for authors and agents, with named handles for deeper discovery.",
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


def build_workflow_rules_response() -> JSONObject:
    """Return the published workflow rules surface."""

    return {
        "document_kind": "workflow_rules",
        "purpose": "Preferred workflow rules and discouraged design choices for Ordo authors and agents",
        "audience": ["workflow_authors", "agents"],
        "disclaimer": "This guidance complements the validation contract. It does not replace the formal runtime model.",
        "heuristic": [
            GH_PR_CREATE_GUIDANCE,
            SDK_CALL_GUIDANCE,
            GH_PR_LIST_GUIDANCE,
            GH_PR_MERGE_GUIDANCE,
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
        {"name": "--progress-steps", "required": False, "effect": "emit_run_step_progress_to_stderr", "summary": "During run, emit each step name to stderr right before execution"},
        {"name": "--json", "required": False, "effect": "emit_json", "summary": "Emit the full JSON payload, including detailed diagnostics"},
    ]
    return {
        "document_kind": "command_line",
        "commands": [
            {
                "name": "ordo-playbook",
                "definition": "Public launch command for discovering playbook workflows, asking which workflow fits next, inspecting inferred workflow topology, and running one named workflow in a selected runtime mode.",
                "purpose": "Browse playbook workflows, ask which workflow should run next, inspect inferred workflow topology, or launch one named workflow into one runtime mode",
                "use_when": [
                    GRAPH_GUIDANCE,
                    GRAPH_PRESENTATION,
                    GRAPH_SOURCE_PLACEMENT,
                    GRAPH_CONTEXT_GUIDANCE,
                    GRAPH_PARAMETER_GUIDANCE,
                    GRAPH_ROLE_GUIDANCE,
                    "You need to discover which named workflows the current playbook publishes before choosing one.",
                    "Use workflows show <workflow> for the main caller interface without activating the workflow. Plain output keeps the JSON-shaped serialized envelope but filters the inputs mapping to caller_slot required or optional, hides caller_slot none, and retains inputs: {} when no caller slots exist. Plain output omits top-level launch_profile entirely and removes caller_slot, sources, and coverage from retained inputs; other record fields are preserved except required, which reports caller-slot obligation: true for a required slot, false for an optional slot, not workflow declaration requiredness. No optional field is added. --json retains the unchanged complete declared inputs mapping and top-level launch_profile, including all input fields with original normalized required and caller_slot. Each visible input preserves description and hint when provided. There are no separate declared_inputs, caller_inputs, or optional_caller_inputs fields; other envelope fields are unchanged except conditional plain warnings.",
                    "Plain workflows show adds top-level warnings only for required workflow declarations with coverage missing, evaluated before filtering inputs. Each warning contains code discovery.workflow.input_source_missing, the input name, a message explaining no workflow default, not supplied by the selected launch profile (or no profile selected), no concrete playbook binding, and no caller slot, plus a hint to expose a caller slot or supply a source. Missing declarations stay hidden from inputs. Optional missing declarations do not warn; either caller-slot form or any present source suppresses the warning. Omit warnings entirely when none qualify. --json gains no warnings and remains unchanged. No readiness or state analysis is performed; check, review, plan, run, explain, and next remain unchanged.",
                    "In --json only, input sources list every present workflow_default, launch_profile, and entry_binding in that order, and coverage is provided when any source exists, caller_slot when only a slot exists, or missing when neither exists, using the same source-presence rule as review.playbook.input_caller_slot_missing. In both outputs, default appears only when declared, including null; binding appears only for a concrete static entry binding. Selected profile values are never exposed.",
                    "In --json only, top-level launch_profile reports the initial activation name and source, not the final bound workflow profile: default for defaults.profile, explicit_cli for --profile, or both null when no launch profile is selected. The launch_profile input source label is also JSON-only. Only the selected profile is loaded. Coverage is not value validity or execution readiness: null, false, and zero count as present sources; required caller slots still require explicit caller input even with provided coverage. --input, --input-file, and runtime profile switches do not contribute authored source coverage.",
                    "You need to ask which workflow should run next, or run one named workflow through check, review, plan, explain, or run.",
                    "You need one-run launch overrides such as --profile, --input, or --input-file without editing the workflow or playbook.",
                    "Inspect check's allowed_state, analysis_complete, incomplete_reasons, and unevaluated_relevant_guards: allowed false may mean unknown rather than blocked, and missing_facts is not inferred from unevaluated expressions.",
                    "Check may defer top-level state mutations after conditions and gates to inspect later independent guards without simulating writes. Plan keeps non-reusable nodes; run executes admitted mutations once in order.",
                ],
                "do_not_use_for": [
                    "Teaching workflow-body semantics that belong to workflow, playbook, or workflow-rules surfaces.",
                    "Treating CLI command examples as executable verified snippets: the current snippet harness cannot validate CLI activation examples. Authored YAML excerpts verify source parity only, not CLI discovery or activation output.",
                    "Treating check as complete workflow sign-off; review is still required for authoring-quality findings.",
                    "Encoding durable project logic in launch flags instead of declared workflow inputs, playbook metadata, or workflow structure.",
                    "Assuming nested state deferral or full composed-run proof: a reached run/loop after deferral halts with state_deferral_invocation_barrier, and profile switches cannot resume it. Cross-invocation and cross-iteration guarantees remain deferred.",
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
                        "handle": "workflow-rules.paired_check_review_passes",
                        "summary": "Why check and review are complementary authoring passes rather than substitutes",
                    },
                ],
                "usage": "ordo-playbook [--file PATH] [--profile NAME] [--input KEY=VALUE] [--input-file KEY=PATH] [--progress-steps] [--json] <command>",
                "discovery_commands": [
                    {"name": "workflows list", "summary": "list declared playbook workflows with project-local descriptions"},
                    {"name": "workflows show <workflow>", "summary": "show one workflow entry: plain inputs expose caller slots with top-level warnings only for required declarations missing source coverage; --json retains the unchanged full declaration contract"},
                ],
                "modes": [
                    {"name": "review <workflow>", "summary": "review workflow-quality findings without making changes"},
                    {"name": "check <workflow>", "summary": "check whether the workflow can be run now, without making changes"},
                    {"name": "plan <workflow>", "summary": "show what the workflow would do, without making changes"},
                    {"name": "explain <workflow>", "summary": "explain why the workflow can or cannot be run right now"},
                    {"name": "run <workflow>", "summary": "run the workflow and do the real work"},
                    {"name": "next", "summary": "suggest which workflow should run next from the current playbook context, preferring state-connected continuation over world-blocked or unrelated options"},
                    {"name": "graph", "summary": "Show how workflows connect through persistent state."},
                ],
                "next_priority": [
                    "prefer workflows tied to the active state-backed work context over unrelated utility workflows",
                    "prefer workflows blocked only by execution-only operator input over workflows blocked by world-state mismatch",
                    "keep inspection-only workflows below continuation-capable workflows when both are otherwise credible",
                ],
                "check_review_passes": {
                    "rule": "When adding or changing workflows, run both check and review. Neither replaces the other.",
                    "passes": [
                        {
                            "mode": "check <workflow>",
                            "question": "Can this workflow run now?",
                            "purpose": "Validate applicability, explicit probe coverage, and execution readiness",
                        },
                        {
                            "mode": "review <workflow>",
                            "question": "Is this workflow well-authored?",
                            "purpose": "Surface workflow-quality findings, including input_authoring warnings for missing root input descriptions and missing playbook caller slots. CLI overrides do not suppress these advisories; available static findings remain visible when review_status is unavailable, without changing activation errors or other modes.",
                        },
                    ],
                },
                "run_success_surface": "successful run emits workflow-local results, may also surface global published values, and may synthesize one top-level fallback result when neither results nor published output were produced",
                "review_findings_surface": "Plain review includes all available findings in order under top_findings, with compact details, including when review_status is unavailable; --json retains full finding details.",
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
                    "workflow.inputs declares the allowed activation keys; each declared key may be required, optional, or defaulted by its own declaration",
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
                    "ordo-playbook next",
                    "ordo-playbook graph",
                    "ordo-playbook plan inspect-issue",
                    "ordo-playbook --profile review plan inspect-issue",
                    "ordo-playbook --input enabled=true plan inspect-issue",
                    "ordo-playbook --input-file body=./prompt.md plan inspect-issue",
                    "ordo-playbook --progress-steps run inspect-issue",
                ],
                "inspect_next": [
                    "command-line.ordo-playbook.flag.profile",
                    "command-line.ordo-playbook.flag.input",
                    "command-line.ordo-playbook.flag.input_file",
                    "command-line.ordo-playbook.flag.progress_steps",
                    "playbook.workflows.file",
                    "workflow-rules.paired_check_review_passes",
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


def _build_capability_lookup(*, context: _HelpResponseContext | None = None) -> dict[str, JSONObject]:
    if context is None:
        context = _HelpResponseContext()
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
        "workflow.state_bindings": {
            "definition": "Workflow capability for binding declared playbook state locations into workflow roles so steps may read, write, or delete durable state explicitly.",
            "use_when": [
                "A workflow needs durable named storage that persists across runs instead of relying on implicit files or transient outputs.",
                "The workflow has already declared state_needs and now must connect those workflow roles to concrete named playbook state locations.",
                "After binding, final-read ordering compares actual files in each access context, including normalized paths, symlinks, and existing hardlinks, regardless of roles or profiles. Relative paths retain runtime resolution; the same role may access distinct files and be valid.",
                "Inspect the state_bundle examples for explicit bindings to real temporary world files, including a rejected alias read. Bundle verification checks bound validity, not execution or profile-switch contexts.",
            ],
            "do_not_use_for": [
                "Short-lived local values that belong in step outputs, workflow values, or direct inputs rather than declared state storage.",
                "Writing state directly without first binding a declared location into the workflow's explicit state contract.",
                "Assuming different roles or profiles isolate aliases. Proven violations report validation.workflow.state_storage.write_before_last_read; relevant unresolved write/later-read pairs are conservatively rejected early with validation.workflow.state_storage.identity_unresolved, not a proven violation.",
                "Treating separate child validation as flattened caller-child analysis: cross-invocation and cross-iteration guarantees remain deferred.",
            ],
        },
        "workflow.state_needs": {
            "definition": "Workflow capability for declaring which state roles and storage targets the workflow requires before durable state reads, writes, or deletions are valid.",
            "use_when": [
                "A workflow intends to interact with durable state and must declare that need explicitly before step-level state surfaces become legitimate.",
            ],
            "do_not_use_for": [
                "Binding one concrete role to one declared playbook state location; that next step belongs to workflow.state_bindings.",
                "Implicitly relying on state availability just because a later step mentions state.*; durable state access still needs an explicit workflow need declaration.",
            ],
        },
        "workflow.step.state_delete": {
            "definition": "Workflow step capability for deleting one explicit bound state target as a deliberate durable state mutation.",
            "use_when": [
                "The workflow must remove a bound durable state value for future runs, after the final read of the same actual file, regardless of role or profile.",
                "Top-level check evaluates conditions and gates first, then records deferred without mutation, simulation, outputs, registers, or reuse, and continues to independent guards. Plan retains a not_reusable node with planned_probe_result null; run executes admitted deletion once in order.",
                "Before binding, authoring validation retains the same-role rule. Bound validation resolves relative paths in each access context, recognizes normalized paths, symlinks, and existing hardlinks, and permits the same role to access different files.",
            ],
            "do_not_use_for": [
                "Local ephemeral data cleanup that should stay in step-local values instead of altering durable state.",
                "Deleting before a later read of the same actual file, even through another role, profile, key, or field: validation.workflow.state_storage.write_before_last_read reports proven violations.",
                "Treating validation.workflow.state_storage.identity_unresolved as a proven violation: it conservatively rejects only relevant uncertain write/later-read pairs before observations or effects, not all uncertain contexts.",
                "Writing or reshaping durable state; use workflow.step.state_set when the intent is persistence rather than deletion.",
                "Nested deferral or full composed-run proof: a reached run/loop after deferral halts with state_deferral_invocation_barrier, which profile switches cannot resume. Cross-invocation and cross-iteration guarantees remain deferred.",
            ],
        },
        "workflow.step.value": {
            "definition": "Workflow step capability for computing one explicit ephemeral value inside the workflow and optionally registering it for later local reuse.",
            "use_when": [
                "A step should produce one derived value for later guards, publishes, results, or step-local dataflow without mutating durable state or calling an external operation.",
            ],
            "do_not_use_for": [
                "Durable persistence; use workflow.step.state_set when the value must survive beyond local workflow dataflow.",
                "Outward-facing final result or publication surfaces when the main intent is emitting contract output rather than computing an intermediate value.",
            ],
        },
        "workflow.step.register": {
            "definition": "Workflow step capability for binding one step result to a reusable step-local name so later steps may read that result explicitly.",
            "use_when": [
                "A later step still needs the current step's result through one stable explicit read path such as step.<register>.outputs.value.",
                "The workflow is staging reusable local dataflow rather than emitting one final outward-facing result through publish or result.",
            ],
            "do_not_use_for": [
                "Outward-facing final result emission; use workflow.step.publish or workflow.step.result when the main intent is final output rather than reuse.",
                "Implicit result reuse without a concrete step-local binding name; register exists to make that reuse path explicit and reviewable.",
            ],
        },
        "workflow.step.condition": {
            "definition": "Workflow step capability for authoring explicit boolean control decisions through step-level if and gate surfaces, where a failed gate blocks the protected execution path.",
            "use_when": [
                "A workflow path needs one explicit step-scoped boolean decision and the real question is whether the step is optional or admitted.",
                "Several predicates should remain reviewable as one declared control surface instead of being hidden inside payload-building expressions.",
            ],
            "do_not_use_for": [
                "Treating if and gate as interchangeable; if is for optional local branching while gate is for admission decisions.",
                "Whole-workflow applicability or early rejection; that meaning belongs to workflow guards rather than to step-scoped condition surfaces.",
            ],
        },
        "workflow.step.outputs": {
            "definition": "Workflow step capability for reading the explicit output surface of a previously registered step through step.<register>.outputs... paths.",
            "use_when": [
                "A later step, condition, or publication needs one earlier step result through an explicit readable path such as step.issue.outputs.title or step.prepare.outputs.value.",
                "Workflow-local dataflow should stay transient and reviewable instead of being copied into state only to be read again immediately.",
            ],
            "do_not_use_for": [
                "Pretending every prior step is readable without an explicit register binding; the workflow needs a registered step result to create a durable read path.",
                "Long-term persistence across runs; use declared state surfaces when the data must survive beyond current workflow-local execution.",
            ],
        },
        "workflow.step.state_set": {
            "definition": "Workflow step capability for writing one explicit value into one bound state target as a deliberate durable state mutation.",
            "use_when": [
                "The workflow must persist one value for future runs, after the final read of the same actual file, regardless of role or profile.",
                "Top-level check evaluates conditions and gates first, then records deferred without mutation, simulation, outputs, registers, or reuse, and continues to independent guards. Plan retains a not_reusable node with planned_probe_result null; run executes admitted writing once in order.",
                "Before binding, authoring validation retains the same-role rule. Bound validation resolves relative paths in each access context, recognizes normalized paths, symlinks, and existing hardlinks, and permits the same role to access different files.",
            ],
            "do_not_use_for": [
                "Ordinary local dataflow that should stay in step outputs or workflow values instead of becoming durable state.",
                "Writing before a later read of the same actual file, even through another role, profile, key, or field: validation.workflow.state_storage.write_before_last_read reports proven violations. Use value + register for per-run reuse.",
                "Treating validation.workflow.state_storage.identity_unresolved as a proven violation: it conservatively rejects only relevant uncertain write/later-read pairs before observations or effects, not all uncertain contexts.",
                "Writing several unrelated state targets in one step; each state_set step writes exactly one resolved target entry.",
                "Nested deferral or full composed-run proof: a reached run/loop after deferral halts with state_deferral_invocation_barrier, which profile switches cannot resume. Cross-invocation and cross-iteration guarantees remain deferred.",
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
        },
        "runtime.launchers": {
            "definition": "Deprecated runtime capability for honoring legacy launcher-based execution setup when older workflows still reference launcher names at runtime.",
            "use_when": [
                "You are reading or maintaining an older workflow path that still resolves a named launcher through profile.launchers and workflow.step.launcher.",
                "A migration discussion needs to distinguish current compatibility support from the preferred routines-based path for new work.",
            ],
            "do_not_use_for": [
                "Treating launcher support as approval for new launcher-centric workflow authoring; the capability exists for compatibility, not as the preferred path.",
                "Assuming a runtime capability automatically provides the authored syntax you should introduce next; prefer routines or explicit profile context for new execution setup.",
            ],
        },
        "workflow.step.launcher": {
            "definition": "Deprecated workflow-step capability for selecting one named legacy launcher record on an operation-shaped step when an older workflow still depends on launcher-based execution setup.",
            "use_when": [
                "You are reading or maintaining an existing workflow that already references one named launcher and need to understand that legacy step surface honestly.",
                "A migration discussion needs to explain how one step-level launcher reference relates to profile.launchers and why routines are now preferred for new local automation.",
            ],
            "do_not_use_for": [
                "New workflow authoring when a routine or another structured execution-context surface can express the behavior more honestly.",
                "Treating step-level launcher selection as the preferred way to attach execution setup to a step; this capability is deprecated and retained for compatibility only.",
            ],
        },
        "workflow.version": {
            "definition": "Required top-level workflow format marker that declares which published workflow document shape this file is written against.",
            "use_when": [
                "Every workflow document must start by declaring the required published workflow format version before workflow, inputs, blocks, or other top-level workflow fields.",
            ],
            "do_not_use_for": [
                "Publishing a domain, release, or business-process version for the workflow itself; this field is only the workflow document-format marker.",
                "Declaring playbook or routine registry document formats; use playbook.version or routine_contract.version for those separate documents.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.version", "summary": "Required version marker for one playbook launch-catalog document rather than for one workflow file"},
                {"handle": "routine_contract.version", "summary": "Required version marker for the routine registry document"},
                {"handle": "workflow.workflow", "summary": "The top-level workflow identity field that the version marker makes safe to interpret"},
            ],
            "examples": [
                {"reference": "workflow.version", "inputs": {"version": 0}},
            ],
            "inspect_next": ["workflow.workflow", "playbook.version", "routine_contract.version"],
        }
    }
    for capability in payload["capabilities"]:
        snippet_surface = context.snippet_surface(str(capability["name"]))
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
        snippet_surface = context.snippet_surface(str(rule["name"]))
        lookup[rule["name"]] = {
            "document_kind": "capability_node",
            "node_kind": "negative_rule",
            **rule,
            "snippet_coverage": snippet_surface["snippet_coverage"],
            "canonical_examples": snippet_surface["canonical_examples"],
        }
    return lookup


_GH_REPOSITORY_INPUT_GUIDANCE = (
    "repository inputs and connector_contexts.gh.repository accept literal OWNER/REPO: strip ASCII spaces only, "
    "then full-match [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+. Neither part may be '.' or '..'; the owner must not start with '-'. "
    "Repository names '.github', '-demo', and '-' remain syntactically route-safe. Case is preserved; this is not length, account-registry, or existence validation. "
    "Controls, non-ASCII whitespace, ?, #, %, backslashes, and URLs are rejected, not decoded or encoded into arbitrary URLs. "
    "Invalid context fails before authentication; explicit input validation precedes repository API requests but may follow existing authentication bootstrap. "
    "Existing failure codes remain, with a clear format diagnostic. Context is a default, not an authorization allowlist: a valid explicit other repository remains allowed with an override warning. "
    "API-response nameWithOwner and composite content_refs parsing retain separate unchanged trust contracts; this input rule does not validate all API responses or demonstrate SSRF or authentication bypass."
)


def _build_model_node_lookup(*, context: _HelpResponseContext | None = None) -> dict[str, JSONObject]:
    if context is None:
        context = _HelpResponseContext()
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
        "shell": {
            "definition": "Published shell connector family for one coarse legacy command-execution action that runs arbitrary shell text inside the current working directory context.",
            "use_when": [
                "You are inspecting, migrating, or containing older workflow logic that still depends on shell.command as a compatibility surface.",
                "You need to understand the broad fallback namespace that exists when no narrower published connector operation yet expresses the required external behavior.",
            ],
            "do_not_use_for": [
                "New workflow authoring when a narrower published connector surface, a composed public workflow, or a bounded routine can express the intent more honestly.",
                "Treating arbitrary shell execution as a normal first-choice operation family; this namespace is intentionally coarse and high-risk.",
            ],
            "nearest_surfaces": [
                {"handle": "connectors", "summary": "Top-level published connector namespace catalog"},
                {"handle": "operations", "summary": "Flat public operation catalog across all connector namespaces"},
                {"handle": "connector.shell.command", "summary": "The one coarse shell action published in this family"},
                {"handle": "workflow-rules.shell.command", "summary": "Authoring rule that explains why shell.command is forbidden for new workflow work"},
                {"handle": "routines", "summary": "Bounded opaque local-automation fallback surface that is preferred over new shell.command authoring when structured public surfaces are exhausted"},
            ],
            "inspect_next": ["connector.shell.command", "workflow-rules.shell.command", "routines", "operations"],
        },
        "fs": {
            "definition": "Published filesystem connector family for observing UTF-8 content and metadata from the same opened regular file, not an atomic snapshot.",
            "use_when": [
                "You need one typed filesystem probe instead of a broader shell command just to inspect a file.",
            ],
            "do_not_use_for": [
                "Writing, mutating, or deleting files; this family currently publishes observation only.",
                "Atomic snapshots or workspace confinement; parent symlinks and hardlinks remain allowed. Safe-open requires nonzero O_NOFOLLOW and O_NONBLOCK with no unsafe fallback.",
            ],
            "nearest_surfaces": [
                {"handle": "connectors", "summary": "Top-level published connector namespace catalog"},
                {"handle": "operations", "summary": "Flat public operation catalog across all connector namespaces"},
                {"handle": "connector.fs.file", "summary": "Observe content and metadata from one opened regular file"},
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
        },
        "gh": {
            "definition": "Published GitHub connector family for typed repository, issue, pull-request, Actions run, and project operations backed by GitHub CLI authentication rather than ad hoc shell calls.",
            "use_when": [
                "The workflow needs one published GitHub probe or action whose outputs and failure modes stay stable across repositories.",
                "Repository-targeted GitHub probes and actions should normally inherit connector_contexts.gh.repository instead of repeating the same repository argument on every step, and review warns when an explicit repository overrides that default.",
                "You want separate public surfaces for repository sync, issue snapshots, pull-request review surfaces, and GitHub Project membership instead of one coarse GitHub command wrapper.",
                "The published operations list includes read-only probes and effectful actions. gh.pr and gh.pr.checks observe facts; gh.pr.merge submits a mutation, while gh.pr.merge.request observes its saved UUID. The project-membership example also includes actions and is not a read-only recipe.",
                "Bootstrap requires an available authenticated gh CLI with repository access. gh.actions.run observes one attempt by run_id or check_suite_id (exactly one); omitted/null attempt reads latest then pins it. gh.actions.run.jobs requires explicit attempt, normally the returned run_attempt. Optional/null repository uses connector_contexts.gh.repository; explicit valid OWNER/REPO overrides it, invalid explicit input fails without fallback, and no resolved target is input_error.",
                "A gh.pr.checks check-run item supplies nullable check_suite_id for direct GraphQL CheckSuite.workflowRun lookup. A validated null association returns found=false. Jobs expose check_run_id only from a validated official API URL, not logs. Complete jobs retrieval and pinned attempts remain non-atomic API observations, not tested-SHA attestation or immutable PR event snapshots. Run failures are actions_run_unavailable; jobs failures, including incomplete pagination, are actions_jobs_unavailable.",
                GH_PR_LIST_GUIDANCE,
                GH_PR_MERGE_GUIDANCE,
                GH_PR_CREATE_GUIDANCE,
            ],
            "do_not_use_for": [
                "Repository-local helper scripts or opaque gh invocations when an existing published GitHub operation already expresses the intent more directly.",
                "Non-GitHub repository state such as local branches, commits, or worktrees; use the git connector family for repository-local facts.",
                "Async merge is not polling, queue administration, admin bypass, or an atomic base/stack transaction. GitHub automatic issue closing and branch configuration effects remain outside the action.",
                "Actions run probes do not trigger, rerun, cancel, poll, download logs, select required jobs, or apply merge policy. gh.actions is a namespace segment, not an executable operation.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.authoring", "summary": "Connector-author SDK and explicit same-family probe dependency contract"},
                {"handle": "operations", "summary": "Flat public operation catalog across all connector namespaces"},
                {"handle": "connector.gh.repo", "summary": "Repository identity and fork probe for repo-level GitHub workflows"},
                {"handle": "connector.gh.repo.actions.permissions", "summary": "Repository Actions permissions probe for workflows that need to inspect or guard hosted Actions policy"},
                {"handle": "connector.gh.actions.run", "summary": "Observe one numbered Actions attempt by run or check suite"},
                {"handle": "connector.gh.actions.run.jobs", "summary": "Observe all jobs for an explicitly pinned attempt"},
                {"handle": "connector.gh.pr", "summary": "Pull-request metadata probe that anchors the PR inspection subgroup"},
                {"handle": "connector.gh.pr.list", "summary": "Full filtered candidate collection before detailed by-number inspection; workflow owns selection"},
                {"handle": "connector.gh.pr.create", "summary": "Create one PR with a mandatory exact open-duplicate check"},
                {"handle": "connector.gh.pr.checks", "summary": "Observe head or verified test-merge CI evidence before accepting a head"},
                {"handle": "connector.gh.pr.merge", "summary": "Submit a standalone PR merge bound to the accepted CI head"},
                {"handle": "connector.gh.pr.merge.request", "summary": "Observe a saved async merge request UUID once"},
                {"handle": "connector.gh.issue", "summary": "Issue snapshot probe for issue maintenance and routing workflows"},
                {"handle": "connector.gh.project", "summary": "Project identity probe that anchors the GitHub Project field and membership subgroup"},
                {"handle": "connector.gh.project.items", "summary": "Project membership probe when the workflow needs GitHub Project item collections"},
            ],
            "examples": [
                {"reference": "gh.repo", "inputs": {}},
                {"reference": "gh.repo.actions.permissions", "inputs": {}},
                {"reference": "gh.pr", "inputs": {"pull_number": 42}},
                {"reference": "gh.issue", "inputs": {"issue_number": 17}},
                {"reference": "gh.project", "inputs": {"project_id": "PVT_kwDOExample"}},
            ],
            "inspect_next": ["connector.gh.repo", "connector.gh.repo.actions.permissions", "connector.gh.actions.run", "connector.gh.actions.run.jobs", "connector.gh.pr", "connector.gh.pr.checks", "connector.gh.pr.merge", "connector.gh.pr.merge.request", "connector.gh.issue", "connector.gh.project", "connector.gh.project.items", "operations"],
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
        ("shell", "command"): {
            "definition": "Execute one arbitrary shell command string through bash -lc and return its exit code together with captured stdout and stderr.",
            "use_when": [
                "You are reading, debugging, or migrating legacy workflow logic that already depends on shell.command and must understand its coarse runtime contract accurately.",
                "A compatibility or containment scenario still needs one broad shell escape hatch, and narrower published connector surfaces or bounded routines have already been ruled out explicitly.",
            ],
            "do_not_use_for": [
                "New workflow authoring as a default mechanism; prefer narrower published connector operations, composed public workflows, or routines before falling back here.",
                "Pretending this surface carries typed domain semantics; shell.command only runs raw shell text and leaves parsing, safety, and intent outside the public contract.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.shell", "summary": "Parent shell connector family for this coarse legacy execution action"},
                {"handle": "workflow-rules.shell.command", "summary": "Authoring rule that marks shell.command as forbidden for new workflow authoring"},
                {"handle": "routines", "summary": "Preferred bounded fallback surface when local automation is still necessary after structured public options are exhausted"},
                {"handle": "operations", "summary": "Flat connector catalog to check whether a narrower published operation already exists before using shell.command"},
            ],
            "examples": [
                {"reference": "shell.command", "inputs": {"command": "printf 'legacy check'"}},
            ],
            "inspect_next": ["workflow-rules.shell.command", "routines", "operations", "connector.shell"],
        },
        ("fs", "file"): {
            "definition": "Observe UTF-8 content and metadata from the same opened regular file. The initial no-follow stat preserves diagnostics; nonzero O_NOFOLLOW and O_NONBLOCK are required before opening, then fstat verifies a regular file before reading that descriptor.",
            "use_when": [
                "You need one file's content and metadata inside workflow logic, guards, or later adapters.",
                "Supply a required path explicitly. Relative and absolute textual Path projections are retained, not resolved to the opened object's identity. Publish basename, size, or line_count rather than full content by default; later adapters can consume the registered content.",
                "Initial missing paths return path_not_found; initial final symlinks or nonregular entries and opened FIFO/directory objects return not_a_file. Missing secure flags return content_unavailable with probe.fs_file.secure_open_unavailable and no fallback. Open errors including ELOOP return content_unavailable without guessing kind; fstat failure returns probe_failed with probe.fs_file.stat_failed.",
            ],
            "do_not_use_for": [
                "Directory inspection or generic filesystem traversal; this probe requires one regular file path.",
                "Binary or non-UTF-8 content when canonical text content cannot be produced reliably.",
                "Atomic snapshots under concurrent writes, workspace confinement, device-open sandboxing, or same-UID isolation. Parent symlinks and hardlinks remain allowed; POSIX race tests do not establish Windows support.",
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
        ("gh", "issue"): {
            "definition": "Probe one GitHub issue as a typed snapshot of its current metadata, body, labels, assignees, and project-item context. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and workflow logic now needs one issue snapshot from that repository by issue number.",
                "Workflow logic needs to inspect one issue before deciding whether to comment, edit the body, close it, or publish a summary.",
                "A guard or later step needs typed issue facts such as state, title, labels, or body rather than a coarse shell response.",
            ],
            "do_not_use_for": [
                "Listing the issue's comment thread only; use connector.gh.issue.comments for that narrower conversation surface.",
                "Mutating the issue; use connector.gh.issue.create, connector.gh.issue.comment.add, connector.gh.issue.body.append, connector.gh.issue.body.replace, or connector.gh.issue.close for effectful changes.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh", "summary": "Parent GitHub connector family for issue, pull request, and project operations"},
                {"handle": "connector.gh.issue.comments", "summary": "Sibling probe for the issue comment thread rather than the issue snapshot itself"},
                {"handle": "connector.gh.issue.comment.add", "summary": "Action for adding one new issue comment after inspection"},
                {"handle": "connector.gh.issue.close", "summary": "Action for closing the issue after inspection or cleanup"},
            ],
            "inspect_next": ["connector.gh.issue.comments", "connector.gh.issue.comment.add", "connector.gh.issue.body.replace", "connector.gh.issue.close"],
        },
        ("gh", "issue.create"): {
            "definition": "Create one new GitHub issue in one repository and return its canonical reference, number, title, and URL for later workflow steps. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow must open a new issue there.",
                "The workflow must open a new issue and then reuse the returned issue number or URL in later steps.",
            ],
            "do_not_use_for": [
                "Editing or commenting on an already existing issue; use the narrower body or comment actions for that follow-up work.",
                "Reading current issue metadata before deciding whether creation is necessary; use connector.gh.issue or other probe surfaces first when the issue already exists.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.issue", "summary": "Probe the created issue later when you need its full current snapshot"},
                {"handle": "connector.gh.issue.comment.add", "summary": "Add a follow-up comment to an existing issue instead of creating a new one"},
                {"handle": "connector.gh.issue.body.replace", "summary": "Rewrite the body of an existing issue instead of creating a fresh issue"},
            ],
            "inspect_next": ["connector.gh.issue", "connector.gh.issue.comment.add", "connector.gh.issue.body.append"],
        },
        ("gh", "issue.close"): {
            "definition": "Close one existing GitHub issue by repository and issue number. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow now needs to close one issue there by issue number.",
                "A workflow has already decided that the issue should be closed and needs one typed action result instead of a shell-level command.",
            ],
            "do_not_use_for": [
                "Explaining the closure in conversation text; add a comment first when the workflow should leave a human-facing note.",
                "Closing a pull request; use the pull-request connector family for PR-specific lifecycle actions.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.issue", "summary": "Probe the issue first when closure depends on current issue state or metadata"},
                {"handle": "connector.gh.issue.comment.add", "summary": "Leave one final note on the issue before or instead of closing it"},
                {"handle": "connector.gh.issue.body.append", "summary": "Append a closing note to the body when the workflow needs body mutation rather than state transition"},
            ],
            "inspect_next": ["connector.gh.issue", "connector.gh.issue.comment.add", "connector.gh.issue.body.append"],
        },
        ("gh", "issue.comments"): {
            "definition": "Probe the comment thread of one GitHub issue as a typed list of recent comments plus total count metadata. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and workflow logic now needs prior discussion for one issue there.",
                "Workflow logic needs to inspect prior discussion, count comments, or publish a compact conversation summary before taking another step.",
            ],
            "do_not_use_for": [
                "Reading the issue's main body, labels, or state; use connector.gh.issue for the broader issue snapshot.",
                "Posting a new comment; use connector.gh.issue.comment.add for that effectful change.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.issue", "summary": "Sibling probe for the issue snapshot rather than its comment list"},
                {"handle": "connector.gh.issue.comment.add", "summary": "Action for appending one new comment to the same thread"},
                {"handle": "connector.gh.issue.body.append", "summary": "Issue-body mutation surface when the update belongs in the issue body rather than the comment thread"},
            ],
            "inspect_next": ["connector.gh.issue", "connector.gh.issue.comment.add", "connector.gh.issue.body.append"],
        },
        ("gh", "issue.comment.add"): {
            "definition": "Add one new comment to an existing GitHub issue and return the created comment id, URL, and body. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow should leave one comment on one issue there.",
                "The workflow should leave a human-facing note in the issue conversation without rewriting the issue body.",
            ],
            "do_not_use_for": [
                "Updating the canonical issue description; use connector.gh.issue.body.append or connector.gh.issue.body.replace when the change belongs in the body itself.",
                "Reading prior comments; use connector.gh.issue.comments when the workflow needs observation rather than mutation.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.issue.comments", "summary": "Probe the existing comment thread before or after adding a new comment"},
                {"handle": "connector.gh.issue.body.append", "summary": "Append durable text to the issue body instead of the comment thread"},
                {"handle": "connector.gh.issue.body.replace", "summary": "Rewrite the full issue body when the workflow owns the canonical description"},
            ],
            "inspect_next": ["connector.gh.issue.comments", "connector.gh.issue.body.append", "connector.gh.issue.close"],
        },
        ("gh", "issue.body.append"): {
            "definition": "Append one text fragment to the end of an existing GitHub issue body, optionally separated from the prior body by one explicit separator. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow should append one note to one issue body there.",
                "The workflow should preserve the current issue body and add one extra section, note, or footer to it.",
            ],
            "do_not_use_for": [
                "Regenerating the whole canonical body from scratch; use connector.gh.issue.body.replace for a full rewrite.",
                "Adding conversational discussion that belongs in the comment thread instead of the issue body; use connector.gh.issue.comment.add.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.issue.body.replace", "summary": "Rewrite the full body instead of appending one trailing fragment"},
                {"handle": "connector.gh.issue.comment.add", "summary": "Write a discussion comment instead of mutating the issue body"},
                {"handle": "connector.gh.issue", "summary": "Probe the current body first when the append decision depends on existing issue metadata"},
            ],
            "inspect_next": ["connector.gh.issue.body.replace", "connector.gh.issue.comment.add", "connector.gh.issue"],
        },
        ("gh", "issue.body.replace"): {
            "definition": "Replace the entire GitHub issue body with one new body string and report whether the resulting body changed. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow should rewrite one issue body there by issue number.",
                "The workflow owns the canonical issue description and should rewrite the full body deterministically.",
            ],
            "do_not_use_for": [
                "Preserving the current body and merely adding one extra section; use connector.gh.issue.body.append for that narrower update.",
                "Thread-style follow-up notes; use connector.gh.issue.comment.add when the update belongs in conversation history rather than the body.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.issue.body.append", "summary": "Append one extra fragment while preserving the rest of the current body"},
                {"handle": "connector.gh.issue.comment.add", "summary": "Add a conversational note instead of rewriting the body"},
                {"handle": "connector.gh.issue", "summary": "Probe the current issue body before deciding whether a full rewrite is appropriate"},
            ],
            "inspect_next": ["connector.gh.issue.body.append", "connector.gh.issue.comment.add", "connector.gh.issue"],
        },
        ("gh", "repo"): {
            "definition": "Probe one GitHub repository as a normalized identity and fork snapshot, including its default branch, fork status, parent repository, and archived flag. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs one repository-level fact probe before deciding whether repo.sync can apply cleanly.",
                "Later logic needs the repository's canonical name, default branch, or parent fork relationship rather than issue-, PR-, or project-level facts.",
            ],
            "do_not_use_for": [
                "Syncing the repository's default branch; use connector.gh.repo.sync for that effectful fork-sync operation.",
                "Inspecting pull requests, issues, or GitHub Project membership; those remain separate narrower GitHub surfaces.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh", "summary": "Parent GitHub connector family for repository, issue, pull-request, and project operations"},
                {"handle": "connector.gh.repo.sync", "summary": "Sibling action for syncing one fork repository default branch after this probe confirms fork facts"},
                {"handle": "connector.git.repo", "summary": "Sibling local Git repository probe for checkout-root and worktree facts rather than remote GitHub repository identity"},
                {"handle": "connector.gh.pr", "summary": "Sibling GitHub probe for pull-request facts once the workflow moves from repository-level to PR-level logic"},
            ],
            "examples": [
                {"reference": "gh.repo", "inputs": {}},
            ],
            "inspect_next": ["connector.gh.repo.sync", "connector.git.repo", "connector.gh.pr"],
        },
        ("gh", "repo.sync"): {
            "definition": "Sync one GitHub fork repository's default branch from its parent repository and return the synced branch together with the resolved upstream repository name. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override; review warns when it differs from the current gh context repository.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal fork target and the workflow needs to keep its canonical default branch current with the parent repository.",
                "The authored intent is the GitHub-native fork sync operation itself, not a local git fetch/merge sequence or a repository-settings mutation helper.",
            ],
            "do_not_use_for": [
                "Inspecting whether the repository is a fork or what its default branch is; use connector.gh.repo for that read-only fact surface first or separately.",
                "Local checkout synchronization or worktree mutation; use connector.git.* when the real target is the local repository rather than GitHub-hosted fork state.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.repo", "summary": "Parent repository probe for fork identity and default-branch facts before or after sync"},
                {"handle": "connector.git.sync.fetch", "summary": "Sibling local Git action for fetching refs into a local clone rather than syncing a hosted GitHub fork"},
                {"handle": "connector.git.repo", "summary": "Sibling local Git probe when later workflow logic needs local repository state after remote fork sync"},
                {"handle": "connector.gh.pr", "summary": "Sibling GitHub probe for PR-level follow-up work once repository sync is complete"},
            ],
            "examples": [
                {"reference": "gh.repo.sync", "inputs": {}},
            ],
            "inspect_next": ["connector.gh.repo", "connector.git.sync.fetch", "connector.git.repo"],
        },
        ("gh", "repo.actions.permissions"): {
            "definition": "Probe GitHub Actions permissions for one repository, including whether Actions are enabled and the current hosted Actions policy shape. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs to decide whether GitHub Actions are currently enabled before repo.sync or another hosted mutation proceeds.",
                "Later logic needs one typed snapshot of repository Actions policy instead of an opaque gh api response.",
            ],
            "do_not_use_for": [
                "Changing the repository Actions enabled state; use connector.gh.repo.actions.permissions.set for that effectful update.",
                "Inspecting local checkout automation state or workflow-run history; this surface is only the repository Actions permissions snapshot.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh", "summary": "Parent GitHub connector family for repository, issue, pull-request, project, and repository-Actions operations"},
                {"handle": "connector.gh.repo", "summary": "Sibling repository identity probe for fork and default-branch facts"},
                {"handle": "connector.gh.repo.actions.permissions.set", "summary": "Sibling action for setting the repository Actions enabled state after reading the current policy"},
                {"handle": "connector.gh.repo.sync", "summary": "Sibling repository sync action that workflows may guard with the current Actions policy"},
            ],
            "examples": [
                {"reference": "gh.repo.actions.permissions", "inputs": {}},
            ],
            "inspect_next": ["connector.gh.repo.actions.permissions.set", "connector.gh.repo", "connector.gh.repo.sync"],
        },
        ("gh", "repo.actions.permissions.set"): {
            "definition": "Set the GitHub Actions enabled state for one repository and report the resulting enabled flag together with whether the repository policy changed. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs to disable or re-enable hosted GitHub Actions there as an explicit step before later repo-level work.",
                "The authored intent is one narrow repository Actions policy mutation, not a hidden multi-step sync helper.",
            ],
            "do_not_use_for": [
                "Reading the current repository Actions policy without changing it; use connector.gh.repo.actions.permissions for that probe.",
                "Composing a temporary disable-sync-restore sequence inside one action; keep those steps explicit in the workflow instead of hiding orchestration inside this leaf action.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.repo.actions.permissions", "summary": "Sibling probe for the current repository Actions policy before or after mutation"},
                {"handle": "connector.gh.repo.sync", "summary": "Sibling repository sync action that can appear between explicit disable and restore steps"},
                {"handle": "connector.gh.repo", "summary": "Sibling repository identity probe for repo-level targeting facts"},
                {"handle": "connector.git.sync.fetch", "summary": "Local Git sync action when the real target is a local clone rather than hosted Actions policy"},
            ],
            "examples": [
                {"reference": "gh.repo.actions.permissions.set", "inputs": {"enabled": False}},
            ],
            "inspect_next": ["connector.gh.repo.actions.permissions", "connector.gh.repo.sync", "connector.gh.repo"],
        },
        ("gh", "project"): {
            "definition": "Probe one GitHub Project by its stable project id and return a typed existence snapshot with the canonical id and title.",
            "use_when": [
                "A workflow first needs to confirm that one GitHub Project exists before inspecting its fields, issue membership, or item collections.",
                "Later steps need the project's canonical title or want a narrow project-identity probe instead of jumping straight to field or membership surfaces.",
            ],
            "do_not_use_for": [
                "Inspecting one named field or its selectable values; use connector.gh.project.field or connector.gh.project.field.option for that narrower field story.",
                "Enumerating project items or checking whether one issue is already attached to the project; use connector.gh.project.items or connector.gh.project.issue for membership questions.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh", "summary": "Parent GitHub connector family for issue, pull-request, and project operations"},
                {"handle": "connector.gh.project.field", "summary": "Sibling probe for one named project field rather than the project identity itself"},
                {"handle": "connector.gh.project.items", "summary": "Sibling probe for project membership collections rather than top-level project identity"},
                {"handle": "connector.gh.project.issue", "summary": "Sibling probe for whether one repository issue is already in the project"},
            ],
            "examples": [
                {"reference": "gh.project", "inputs": {"project_id": "PVT_kwDOExample"}},
            ],
            "inspect_next": ["connector.gh.project.field", "connector.gh.project.items", "connector.gh.project.issue"],
        },
        ("gh", "project.field"): {
            "definition": "Probe one named field in one GitHub Project and return whether it exists, what field kind it is, and which selectable option names it exposes when applicable.",
            "use_when": [
                "A workflow needs to confirm that a field such as Status or Priority exists before publishing, validating, or mutating project-backed issue data.",
                "Later logic needs field metadata such as kind or allowed option names instead of only a yes/no answer about one candidate option.",
            ],
            "do_not_use_for": [
                "Checking only whether one named allowed value exists; use connector.gh.project.field.option for that narrower yes/no probe.",
                "Setting a field value on a project item; use the relevant connector.gh.project.issue.field_* action surface for mutation rather than this read-only metadata probe.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.project", "summary": "Parent project probe for confirming the project identity before field-specific inspection"},
                {"handle": "connector.gh.project.field.option", "summary": "Sibling probe for one candidate selectable value rather than the whole field metadata surface"},
                {"handle": "connector.gh.project.issue.field_single_select.set", "summary": "Action for writing one selectable field value after field inspection confirms the target field"},
                {"handle": "connector.gh.project.issue.field_number.set", "summary": "Action for writing one numeric field value after field inspection confirms the target field"},
            ],
            "examples": [
                {"reference": "gh.project.field", "inputs": {"project_id": "PVT_kwDOExample", "field": "Status"}},
            ],
            "inspect_next": ["connector.gh.project.field.option", "connector.gh.project.issue.field_single_select.set", "connector.gh.project.issue.field_number.set"],
        },
        ("gh", "project.field.option"): {
            "definition": "Probe whether one named selectable value exists inside one GitHub Project field when that field publishes an allowed-value set.",
            "use_when": [
                "A workflow needs one explicit yes/no check that a candidate value such as Done is valid before publishing or applying it elsewhere.",
                "A guard or preparatory step should fail early when one expected project field option is missing but the full field metadata is not otherwise needed later.",
            ],
            "do_not_use_for": [
                "Inspecting the field's broader metadata such as kind or the full option list; use connector.gh.project.field for the parent field surface.",
                "Mutating an issue's project field value; use connector.gh.project.issue.field_single_select.set when the workflow should actually set the value after validation.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.project.field", "summary": "Parent field probe that returns the field kind and full option list instead of only one boolean option check"},
                {"handle": "connector.gh.project.issue.field_single_select.set", "summary": "Action for setting one single-select project field value after the option check succeeds"},
                {"handle": "connector.gh.project.issue.field_iteration.set", "summary": "Action for setting one iteration field value when the project field is iteration-backed rather than free-form"},
            ],
            "examples": [
                {"reference": "gh.project.field.option", "inputs": {"project_id": "PVT_kwDOExample", "field": "Status", "option": "Done"}},
            ],
            "inspect_next": ["connector.gh.project.field", "connector.gh.project.issue.field_single_select.set", "connector.gh.project.issue.field_iteration.set"],
        },
        ("gh", "project.issue"): {
            "definition": "Probe whether one GitHub issue is already attached to one GitHub Project and return the normalized membership item id plus the common project field values that Ordo reads from that membership. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs project membership for one issue there.",
                "A workflow needs to know whether one issue is already in the target project before deciding to add it or update its project fields.",
                "Later logic needs one compact project-membership snapshot such as Status, Type, Priority, Iteration, Size, or Estimate for one issue in one project.",
            ],
            "do_not_use_for": [
                "Scanning many project items or filtering project membership collections; use connector.gh.project.items or connector.gh.project.items.details for collection-shaped project inspection.",
                "Adding the issue to the project or mutating project field values; use connector.gh.project.issue.add or the connector.gh.project.issue.field_* setters for those effectful changes.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.project", "summary": "Parent project probe for confirming the target project identity before issue-membership inspection"},
                {"handle": "connector.gh.project.issue.add", "summary": "Sibling action for attaching the issue to the project when this probe reports exists=false"},
                {"handle": "connector.gh.project.items", "summary": "Sibling probe for project-wide membership scans instead of one issue-specific membership lookup"},
                {"handle": "connector.gh.project.issue.field_single_select.set", "summary": "Sibling action for mutating one project field after membership inspection confirms the target issue context"},
            ],
            "examples": [
                {"reference": "gh.project.issue", "inputs": {"issue_number": 42, "project_id": "PVT_kwDOExample"}},
            ],
            "inspect_next": ["connector.gh.project.issue.add", "connector.gh.project.issue.field_single_select.set", "connector.gh.project.items"],
        },
        ("gh", "project.issue.add"): {
            "definition": "Add one GitHub issue to one GitHub Project and return the project item id, while staying idempotent when the issue is already attached. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs to ensure one issue there becomes a project item.",
                "A workflow has one concrete issue and one target project and needs to ensure that the issue becomes a project item before later project-field updates.",
                "The workflow wants one typed membership-creation result instead of shelling out to ad hoc gh project mutations.",
            ],
            "do_not_use_for": [
                "Checking membership without changing anything; use connector.gh.project.issue when the real question is whether the issue is already in the project.",
                "Updating Status, Estimate, Iteration, or another project-backed field after membership exists; use the narrower connector.gh.project.issue.field_* setters for those follow-up mutations.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.project.issue", "summary": "Sibling probe for membership inspection before or after this action"},
                {"handle": "connector.gh.project.issue.field_single_select.set", "summary": "Follow-up action for setting one selectable project field after membership is ensured"},
                {"handle": "connector.gh.project.issue.field_number.set", "summary": "Follow-up action for setting one numeric project field after membership is ensured"},
                {"handle": "connector.gh.project.items", "summary": "Project-wide collection probe when the workflow needs many project items rather than attaching one issue"},
            ],
            "examples": [
                {"reference": "gh.project.issue.add", "inputs": {"issue_number": 42, "project_id": "PVT_kwDOExample"}},
            ],
            "inspect_next": ["connector.gh.project.issue", "connector.gh.project.issue.field_single_select.set", "connector.gh.project.issue.field_number.set"],
        },
        ("gh", "project.issue.field_iteration.set"): {
            "definition": "Set one iteration-valued GitHub Project field on one issue's project item by field name and human iteration title. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs to move one project-backed issue there into a named iteration.",
                "A workflow needs to move one project-backed issue into a named iteration such as Sprint 12 after membership already exists or can be resolved.",
                "The caller knows the field by its project-visible name and wants Ordo to resolve the underlying iteration id and item id automatically.",
            ],
            "do_not_use_for": [
                "Attaching the issue to the project in the first place; use connector.gh.project.issue.add when membership may still be missing.",
                "Updating numeric or single-select fields; use connector.gh.project.issue.field_number.set or connector.gh.project.issue.field_single_select.set for those different field kinds.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.project.issue", "summary": "Parent issue-membership probe for reading current project field values before or after mutation"},
                {"handle": "connector.gh.project.field", "summary": "Sibling probe for confirming the project field exists and is iteration-backed before mutation"},
                {"handle": "connector.gh.project.issue.add", "summary": "Sibling action for ensuring the issue is a project item before setting iteration"},
                {"handle": "connector.gh.project.issue.field_single_select.set", "summary": "Sibling setter for selectable fields rather than iteration-backed fields"},
            ],
            "examples": [
                {"reference": "gh.project.issue.field_iteration.set", "inputs": {"issue_number": 42, "project_id": "PVT_kwDOExample", "field": "Iteration", "iteration": "Sprint 12"}},
            ],
            "inspect_next": ["connector.gh.project.issue", "connector.gh.project.field", "connector.gh.project.issue.add"],
        },
        ("gh", "project.issue.field_number.set"): {
            "definition": "Set one number-valued GitHub Project field on one issue's project item by field name and numeric value. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs to write one numeric project field for one issue there.",
                "A workflow needs to write one numeric project field such as Estimate to a project-backed issue item after membership and field resolution succeed.",
                "The caller wants Ordo to reject non-numeric values early instead of discovering that mismatch only inside a raw project mutation.",
            ],
            "do_not_use_for": [
                "Writing selectable or iteration-backed project fields; use connector.gh.project.issue.field_single_select.set or connector.gh.project.issue.field_iteration.set for those different field kinds.",
                "Reading the current field value without changing it; use connector.gh.project.issue when the workflow only needs the observed membership snapshot.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.project.issue", "summary": "Parent issue-membership probe for inspecting current project field values before or after mutation"},
                {"handle": "connector.gh.project.field", "summary": "Sibling probe for confirming the target project field exists before mutation"},
                {"handle": "connector.gh.project.issue.field_single_select.set", "summary": "Sibling setter for selectable fields rather than numeric fields"},
                {"handle": "connector.gh.project.issue.field_iteration.set", "summary": "Sibling setter for iteration-backed fields rather than numeric fields"},
            ],
            "examples": [
                {"reference": "gh.project.issue.field_number.set", "inputs": {"issue_number": 42, "project_id": "PVT_kwDOExample", "field": "Estimate", "value": 3}},
            ],
            "inspect_next": ["connector.gh.project.issue", "connector.gh.project.field", "connector.gh.project.issue.field_single_select.set"],
        },
        ("gh", "project.issue.field_single_select.set"): {
            "definition": "Set one single-select GitHub Project field on one issue's project item by field name and visible option name. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs to assign one selectable project value for one issue there.",
                "A workflow needs to assign one selectable project value such as Status or Priority after membership and field-option validation succeed.",
                "The caller knows the human-facing option label and wants Ordo to resolve the underlying option id automatically.",
            ],
            "do_not_use_for": [
                "Writing iteration-backed or numeric project fields; use connector.gh.project.issue.field_iteration.set or connector.gh.project.issue.field_number.set for those different field kinds.",
                "Checking whether the requested option exists without mutating anything; use connector.gh.project.field.option when the workflow only needs a yes/no option probe.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.project.issue", "summary": "Parent issue-membership probe for reading current project field values before or after mutation"},
                {"handle": "connector.gh.project.field.option", "summary": "Sibling probe for validating one candidate selectable value before mutation"},
                {"handle": "connector.gh.project.issue.add", "summary": "Sibling action for ensuring the issue is a project item before setting a selectable field"},
                {"handle": "connector.gh.project.issue.field_number.set", "summary": "Sibling setter for numeric fields rather than selectable fields"},
            ],
            "examples": [
                {"reference": "gh.project.issue.field_single_select.set", "inputs": {"issue_number": 42, "project_id": "PVT_kwDOExample", "field": "Status", "option": "In review"}},
            ],
            "inspect_next": ["connector.gh.project.field.option", "connector.gh.project.issue", "connector.gh.project.issue.add"],
        },
        ("gh", "project.items"): {
            "definition": "Probe one GitHub Project as a collection of normalized project items, with optional narrowing by content kind, project field filters, and explicit GitHub content references.",
            "use_when": [
                "A workflow needs one project-scoped membership scan across many items rather than one issue-specific membership lookup.",
                "Later logic only needs stable collection facts such as repository, number, title, url, and content kind without loading richer content details like issue state and labels.",
            ],
            "do_not_use_for": [
                "Inspecting one specific issue's membership or project field values; use connector.gh.project.issue for the one-issue membership surface.",
                "Loading richer content details such as issue state and label_names for the matched items; use connector.gh.project.items.details for that heavier collection probe.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.project", "summary": "Parent project probe for confirming the target project identity before collection scans"},
                {"handle": "connector.gh.project.items.details", "summary": "Sibling probe for the same collection scan with richer issue and pull-request details"},
                {"handle": "connector.gh.project.issue", "summary": "Sibling probe for one issue-specific membership snapshot instead of a collection scan"},
                {"handle": "connector.gh.project.field", "summary": "Sibling probe for one project field definition when the workflow needs field metadata rather than matched items"},
            ],
            "examples": [
                {"reference": "gh.project.items", "inputs": {"project_id": "PVT_demo"}},
                {"reference": "gh.project.items", "inputs": {"project_id": "PVT_demo", "content_kind": "Issue", "filters": [{"field": "Status", "value": "Ready"}]}},
                {"reference": "gh.project.items", "inputs": {"project_id": "PVT_demo", "content_kind": "Issue", "filters": [{"field": "Type", "value": "Task"}], "content_refs": ["owner/repo#7", "owner/repo#8"]}},
            ],
            "inspect_next": ["connector.gh.project.items.details", "connector.gh.project.issue", "connector.gh.project.field"],
        },
        ("gh", "project.items.details"): {
            "definition": "Probe one GitHub Project as a normalized item collection with stable content details such as issue state and label names in addition to the base membership facts.",
            "use_when": [
                "A workflow needs project-scoped item matching plus richer content details that are not present on connector.gh.project.items alone.",
                "Later branching or publishing depends on issue or pull-request state, or on label_names for the matched project-backed content.",
            ],
            "do_not_use_for": [
                "Cheap project membership scans where repository, number, title, and url are already enough; use connector.gh.project.items for the lighter collection probe.",
                "Checking or mutating one specific issue membership; use connector.gh.project.issue or connector.gh.project.issue.* for the one-item membership family.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.project.items", "summary": "Parent collection probe for lighter normalized project items without extra content details"},
                {"handle": "connector.gh.project.issue", "summary": "Sibling probe for one issue-specific membership snapshot instead of a collection result set"},
                {"handle": "connector.gh.issue", "summary": "Sibling probe for one repository issue snapshot outside the project-collection context"},
                {"handle": "connector.gh.project.field", "summary": "Sibling probe for project field metadata rather than matched item details"},
            ],
            "examples": [
                {"reference": "gh.project.items.details", "inputs": {"project_id": "PVT_demo", "content_kind": "Issue"}},
                {"reference": "gh.project.items.details", "inputs": {"project_id": "PVT_demo", "content_kind": "Issue", "filters": [{"field": "Type", "value": "Task"}], "content_refs": ["owner/repo#7", "owner/repo#8"]}},
            ],
            "inspect_next": ["connector.gh.project.items", "connector.gh.project.issue", "connector.gh.issue"],
        },
        ("git", "branch"): {
            "definition": "Probe the currently checked out local Git branch and report whether the repository is on a named branch or in detached HEAD state.",
            "use_when": [
                "A workflow needs one cheap checkout-context probe before deciding whether branch-specific actions or branch guards are appropriate.",
                "Later logic only needs the current branch name, ref, or detached flag rather than a full branch inventory.",
            ],
            "do_not_use_for": [
                "Listing many local and remote branches; use connector.git.branches for the inventory surface.",
                "Creating, deleting, or switching branches; use the narrower connector.git.branch.create, connector.git.branch.delete, or connector.git.branch.switch actions for mutation.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.branches", "summary": "Sibling probe for the full branch inventory instead of only the current checkout context"},
                {"handle": "connector.git.branch.switch", "summary": "Sibling action for changing the current checkout after this probe confirms the current branch context"},
                {"handle": "connector.git.repo", "summary": "Sibling probe for repository-level facts such as root path and default branch"},
                {"handle": "connector.git.state", "summary": "Sibling probe for broader worktree state when branch name alone is not enough"},
            ],
            "examples": [
                {"reference": "git.branch", "inputs": {}},
            ],
            "inspect_next": ["connector.git.branches", "connector.git.branch.switch", "connector.git.state"],
        },
        ("git", "branch.create"): {
            "definition": "Create one new local Git branch, optionally from an explicit start point, without switching the current checkout automatically.",
            "use_when": [
                "A workflow needs to create a local working branch before switching to it or using it in later Git operations.",
                "The authored intent is branch creation itself, not a broader repository clone, fetch, or checkout workflow.",
            ],
            "do_not_use_for": [
                "Switching the current checkout to the new or existing branch; use connector.git.branch.switch for that mutation.",
                "Inspecting whether a branch already exists; use connector.git.branches or connector.git.ref when the workflow only needs a read path.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.branch", "summary": "Parent current-branch probe for reading checkout context before or after branch creation"},
                {"handle": "connector.git.branch.switch", "summary": "Typical follow-up action for moving the current checkout onto the created branch"},
                {"handle": "connector.git.branches", "summary": "Sibling probe for inspecting branch inventory before or after creation"},
                {"handle": "connector.git.ref", "summary": "Sibling probe for one explicit ref existence check when a full branch inventory is unnecessary"},
            ],
            "examples": [
                {"reference": "git.branch.create", "inputs": {"branch": "feature/demo", "start_point": "HEAD"}},
            ],
            "inspect_next": ["connector.git.branch.switch", "connector.git.branches", "connector.git.branch"],
        },
        ("git", "branch.delete"): {
            "definition": "Delete one local non-default Git branch. Optional strictly boolean force defaults to false: omitted or false uses git branch -d and its merged-branch check; true uses git branch -D to bypass that check.",
            "use_when": [
                "A workflow is intentionally cleaning up one stale local branch rather than switching branches or resetting repository state broadly.",
                "Use the default merged-branch check for ordinary cleanup. Use force: true only after the caller establishes cleanup eligibility, for example after independently verifying a squash-merged PR; this action does not verify remote merge status.",
                "Both modes preserve default-branch protection discovered through git.repo from origin/HEAD, and reject branches checked out here or in another worktree. If origin/HEAD is absent, no default branch is inferred by name.",
                "Null, strings, numbers, arrays, and objects are invalid force values and return input_error. Missing branches return branch_not_found; checkout conflicts return branch_checked_out; protected defaults return default_branch_protected; an unmerged branch under -d returns branch_not_merged. The existing delete_blocked command mapping is retained; unclassified command failures are normalized by the shared Git handler to action_failed with action.git.command_failed and raw Git evidence.",
                "Only run performs deletion and validates the force value at the action boundary. check, review, plan, explain, and next retain their non-mutating analysis behavior; their readiness result does not prove that Git will permit deletion.",
            ],
            "do_not_use_for": [
                "Switching away from the current branch before deletion; use connector.git.branch.switch first when the current checkout must move.",
                "Deleting tags, remote refs, or arbitrary refs; this surface only covers local branch cleanup.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.branch", "summary": "Parent current-branch probe for checking whether the target branch is currently active"},
                {"handle": "connector.git.branches", "summary": "Sibling probe for reviewing local and remote branch inventory before deletion"},
                {"handle": "connector.git.branch.switch", "summary": "Sibling action for moving off the target branch before deletion if needed"},
                {"handle": "connector.git.repo", "summary": "Sibling probe for repository-level facts such as the protected default branch"},
            ],
            "examples": [
                {"reference": "git.branch.delete", "inputs": {"branch": "stale/demo"}},
                {"reference": "git.branch.delete", "inputs": {"branch": "squash/demo", "force": True}},
            ],
            "inspect_next": ["connector.git.branches", "connector.git.branch.switch", "connector.git.branch"],
        },
        ("git", "branch.switch"): {
            "definition": "Switch the current Git checkout to one existing local branch and report whether the checkout actually changed.",
            "use_when": [
                "A workflow needs to move the current checkout onto one known local branch before later repository actions run.",
                "The authored intent is checkout movement itself, with explicit reporting about whether the branch was already current.",
            ],
            "do_not_use_for": [
                "Creating a new branch before switching; use connector.git.branch.create first when the target branch may not exist yet.",
                "Inspecting current branch state without mutating checkout; use connector.git.branch for the read-only checkout probe.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.branch", "summary": "Parent current-branch probe for reading checkout context before or after switching"},
                {"handle": "connector.git.branch.create", "summary": "Sibling action for creating a branch before switching to it"},
                {"handle": "connector.git.worktree", "summary": "Sibling probe for broader worktree cleanliness when switch safety depends on local changes"},
                {"handle": "connector.git.state", "summary": "Sibling probe for broader repository state when branch switching is only part of the decision"},
            ],
            "examples": [
                {"reference": "git.branch.switch", "inputs": {"branch": "feature/demo"}},
            ],
            "inspect_next": ["connector.git.branch", "connector.git.worktree", "connector.git.state"],
        },
        ("git", "branches"): {
            "definition": "Probe the Git branch inventory and return a normalized list of local and remote branches together with the current branch marker.",
            "use_when": [
                "A workflow needs one branch inventory scan before choosing, creating, deleting, or publishing branch-related state.",
                "Later logic needs to compare the current branch against the available local or remote branch set, not just read one current branch name.",
            ],
            "do_not_use_for": [
                "Reading only the current checkout context; use connector.git.branch for the cheaper current-branch probe.",
                "Mutating branch state; use connector.git.branch.create, connector.git.branch.delete, or connector.git.branch.switch for those actions.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.branch", "summary": "Sibling probe for only the current checkout branch instead of the full inventory"},
                {"handle": "connector.git.branch.create", "summary": "Sibling action for adding one new local branch after inventory review"},
                {"handle": "connector.git.branch.delete", "summary": "Sibling action for removing one local branch after inventory review"},
                {"handle": "connector.git.ref", "summary": "Sibling probe for one explicit ref check when a full inventory is broader than needed"},
            ],
            "examples": [
                {"reference": "git.branches", "inputs": {}},
            ],
            "inspect_next": ["connector.git.branch", "connector.git.branch.create", "connector.git.branch.delete"],
        },
        ("git", "commit.create"): {
            "definition": "Create one new Git commit from the current index with one non-empty commit message and return the new commit id plus the current branch context.",
            "use_when": [
                "A workflow has already staged the intended changes and now needs one normal commit creation step rather than history rewriting.",
                "The authored intent is to capture the current index as one new commit and publish the resulting commit id for later steps.",
            ],
            "do_not_use_for": [
                "Rewriting the current HEAD commit; use connector.git.commit.amend for amend-style history rewriting.",
                "Undoing one existing commit with a compensating revert commit; use connector.git.commit.revert for that distinct history-preserving action.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.commit.amend", "summary": "Sibling action for rewriting the current HEAD commit instead of creating a fresh one"},
                {"handle": "connector.git.commit.revert", "summary": "Sibling action for creating a compensating revert commit instead of recording newly staged changes"},
                {"handle": "connector.git.commits", "summary": "Sibling probe for reading recent commit texts before or after commit creation"},
                {"handle": "connector.git.worktree", "summary": "Sibling probe for broader worktree state when commit readiness depends on unstaged or staged changes"},
            ],
            "examples": [
                {"reference": "git.commit.create", "inputs": {"message": "Record release notes update"}},
            ],
            "inspect_next": ["connector.git.commits", "connector.git.commit.amend", "connector.git.worktree"],
        },
        ("git", "commit.amend"): {
            "definition": "Rewrite the current HEAD commit, optionally replacing its message, and return both the new commit id and the previous commit id.",
            "use_when": [
                "A workflow intentionally needs amend semantics for the current HEAD commit rather than creating another follow-up commit.",
                "Later logic needs both the rewritten commit id and the previous HEAD id to describe what changed in history.",
            ],
            "do_not_use_for": [
                "Creating an ordinary new commit from staged changes; use connector.git.commit.create when history should advance without rewriting HEAD.",
                "Undoing an older commit through a new compensating commit; use connector.git.commit.revert for that history-preserving action.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.commit.create", "summary": "Sibling action for ordinary new commit creation instead of rewriting HEAD"},
                {"handle": "connector.git.commit.revert", "summary": "Sibling action for reverting one target commit instead of rewriting the current one"},
                {"handle": "connector.git.commits", "summary": "Sibling probe for reading recent commit texts around the commit that was amended"},
                {"handle": "connector.git.branch", "summary": "Sibling probe for current branch context before or after the amend"},
            ],
            "examples": [
                {"reference": "git.commit.amend", "inputs": {"message": "Tighten commit message wording"}},
                {"reference": "git.commit.amend", "inputs": {"message": None}},
            ],
            "inspect_next": ["connector.git.commits", "connector.git.commit.create", "connector.git.branch"],
        },
        ("git", "commit.revert"): {
            "definition": "Create one new Git commit that reverts one target commit while preserving history, and return both the reverted commit id and the new revert commit id.",
            "use_when": [
                "A workflow needs to undo one existing commit through an explicit compensating commit instead of rewriting shared history.",
                "Later steps need the new revert commit id and the resolved target commit id for publication or follow-up review.",
            ],
            "do_not_use_for": [
                "Rewriting the current HEAD commit; use connector.git.commit.amend when the real intent is an amend.",
                "Creating a normal new commit from currently staged work; use connector.git.commit.create for standard commit creation.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.commit.create", "summary": "Sibling action for recording staged work instead of undoing an older commit"},
                {"handle": "connector.git.commit.amend", "summary": "Sibling action for rewriting HEAD instead of preserving history with a revert commit"},
                {"handle": "connector.git.commits", "summary": "Sibling probe for loading recent commit texts before choosing one to revert or after recording the revert"},
                {"handle": "connector.git.ref", "summary": "Sibling probe for explicit ref resolution when the workflow needs a narrower commit-ref read path"},
            ],
            "examples": [
                {"reference": "git.commit.revert", "inputs": {"commit": "HEAD~1"}},
            ],
            "inspect_next": ["connector.git.commits", "connector.git.commit.create", "connector.git.ref"],
        },
        ("git", "commits"): {
            "definition": "Probe a bounded readable slice of Git commit history from one revision scope and return normalized commit texts with only minimal metadata.",
            "use_when": [
                "A workflow needs a short reviewable commit-history slice for prompting, decision-making, or publication without diff text or graph decoration.",
                "Later logic needs subjects, bodies, authors, and commit times from one bounded revision scope rather than arbitrary git log formatting.",
            ],
            "do_not_use_for": [
                "Passing Git options through rev: revisions and ranges such as HEAD~10..HEAD are supported, but rev must not start with '-' after trimming whitespace. Option-shaped values fail with probe.git_commits.invalid_rev before git log runs, including during guard and preflight observations in inspection modes.",
                "Loading patch text, changed files, diff stats, or graph decoration; this probe intentionally stays narrower than a full git log surface.",
                "Mutating history through creation, amend, or revert actions; use connector.git.commit.create, connector.git.commit.amend, or connector.git.commit.revert for those effectful steps.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.commit.create", "summary": "Sibling action for recording a new commit after or before reading commit history"},
                {"handle": "connector.git.commit.amend", "summary": "Sibling action for rewriting HEAD when the workflow needs mutation instead of history inspection"},
                {"handle": "connector.git.commit.revert", "summary": "Sibling action for undoing one commit with a new revert commit"},
                {"handle": "connector.git.range", "summary": "Sibling probe for narrower revision-range facts when one readable commit-text list is broader than needed"},
            ],
            "examples": [
                {"reference": "git.commits", "inputs": {"limit": 5, "rev": "HEAD"}},
                {"reference": "git.commits", "inputs": {"limit": 3, "rev": "HEAD~10..HEAD"}},
            ],
            "inspect_next": ["connector.git.commit.create", "connector.git.commit.revert", "connector.git.range"],
        },
        ("git", "tag"): {
            "definition": "Probe one named Git tag and report whether it exists, which ref it occupies, and whether the stored object is an annotated tag object or a lightweight commit ref.",
            "use_when": [
                "A workflow needs to confirm one specific tag such as v1.2.3 before branching on release presence or publishing tag metadata.",
                "Later logic needs the single-tag existence result plus the raw tag ref and object identity, not a broader tag inventory.",
            ],
            "do_not_use_for": [
                "Listing or pattern-matching many tags; use connector.git.tags for the inventory surface.",
                "Inferring the newest tag by version ordering across many candidates; use connector.git.tags and its latest output for that collection-oriented question.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.tags", "summary": "Sibling probe for inventory-wide tag inspection instead of one named tag lookup"},
                {"handle": "connector.git.ref", "summary": "Sibling probe for narrower ref-oriented checks when the workflow cares about refs broadly rather than Git tag semantics specifically"},
                {"handle": "connector.git.commits", "summary": "Sibling probe for readable commit history when one tag lookup alone is not enough context"},
                {"handle": "connector.git.range", "summary": "Sibling probe for revision-scope inspection when the question is broader than one named tag"},
            ],
            "examples": [
                {"reference": "git.tag", "inputs": {"name": "v1.2.3"}},
                {"reference": "git.tag", "inputs": {"name": "release-2026-07"}},
            ],
            "inspect_next": ["connector.git.tags", "connector.git.ref", "connector.git.commits"],
        },
        ("git", "tags"): {
            "definition": "Probe the Git tag inventory as a version-sorted collection, optionally narrowed by glob or regex matching, and return matching tags plus the first match as latest in that sorted order.",
            "use_when": [
                "A workflow needs to inspect several tags at once, optionally narrowing them by release naming conventions such as v* or one semantic-version regex.",
                "Later logic needs both the full matching tag list and the first version-sorted match, not just one named tag existence check.",
            ],
            "do_not_use_for": [
                "Checking only one specific tag by exact name; use connector.git.tag for that simpler single-tag probe.",
                "Treating latest as newest by creation date; this surface orders by descending version refname, not by tag creation time.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.tag", "summary": "Sibling probe for one exact tag lookup instead of an inventory scan"},
                {"handle": "connector.git.range", "summary": "Sibling probe for revision-range facts when tag inventory is broader than needed"},
                {"handle": "connector.git.commits", "summary": "Sibling probe for readable commit history after a tag inventory decision chooses a revision scope"},
                {"handle": "connector.git.ref", "summary": "Sibling probe for explicit ref-oriented checks when the workflow does not need tag-specific inventory semantics"},
            ],
            "examples": [
                {"reference": "git.tags", "inputs": {"match": "v*", "match_kind": "glob"}},
                {"reference": "git.tags", "inputs": {"match": "^v?[0-9]+\\.[0-9]+\\.[0-9]+$", "match_kind": "regex"}},
            ],
            "inspect_next": ["connector.git.tag", "connector.git.range", "connector.git.commits"],
        },
        ("git", "ref"): {
            "definition": "Probe one named Git ref and report whether it resolves, which object id it names, and whether it is a symbolic ref with a separate target.",
            "use_when": [
                "A workflow needs one exact ref existence check such as HEAD, refs/heads/main, or origin/main before making a narrower branch, tag, or sync decision.",
                "Later logic needs one ref's oid or symbolic-target facts without comparing two revisions or listing an inventory.",
            ],
            "do_not_use_for": [
                "Comparing two revision endpoints for ahead/behind or merge-base facts; use connector.git.range for that relationship probe.",
                "Reading tag-specific semantics or tag inventories; use connector.git.tag or connector.git.tags when the workflow is really about Git tags rather than generic refs.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.range", "summary": "Sibling probe for comparing two revision endpoints rather than resolving one exact ref"},
                {"handle": "connector.git.tag", "summary": "Sibling probe for one exact Git tag when tag semantics matter more than generic ref resolution"},
                {"handle": "connector.git.branch", "summary": "Sibling probe for current checkout branch context rather than one arbitrary named ref"},
                {"handle": "connector.git.tags", "summary": "Sibling probe for tag inventory scans instead of one exact ref lookup"},
            ],
            "examples": [
                {"reference": "git.ref", "inputs": {"ref": "HEAD"}},
                {"reference": "git.ref", "inputs": {"ref": "refs/heads/main"}},
            ],
            "inspect_next": ["connector.git.range", "connector.git.tag", "connector.git.branch"],
        },
        ("git", "range"): {
            "definition": "Probe the relationship between two Git revision endpoints and return their resolved object ids, merge base, and ahead/behind counts.",
            "use_when": [
                "A workflow needs to compare two endpoints such as main and HEAD before deciding whether a branch is ahead, behind, or diverged.",
                "Later logic needs one merge-base-aware relationship summary instead of a readable commit list or one exact ref lookup.",
            ],
            "do_not_use_for": [
                "Checking only whether one exact ref resolves; use connector.git.ref for the simpler single-ref probe.",
                "Reading commit subjects or bodies across a revision slice; use connector.git.commits when the workflow needs readable history rather than ahead/behind math.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.ref", "summary": "Sibling probe for resolving one exact ref instead of comparing two revision endpoints"},
                {"handle": "connector.git.commits", "summary": "Sibling probe for readable commit-history slices after the workflow chooses a revision scope"},
                {"handle": "connector.git.branch", "summary": "Sibling probe for current checkout branch context before choosing base and head endpoints"},
                {"handle": "connector.git.upstream", "summary": "Sibling probe for upstream-tracking context when the workflow first needs to choose a comparison target"},
            ],
            "examples": [
                {"reference": "git.range", "inputs": {"base": "main", "head": "HEAD"}},
                {"reference": "git.range", "inputs": {"base": "origin/main", "head": "feature/demo"}},
            ],
            "inspect_next": ["connector.git.ref", "connector.git.commits", "connector.git.upstream"],
        },
        ("git", "integrate.merge"): {
            "definition": "Integrate one target Git ref into the current checkout by creating a merge commit with ordinary merge semantics, even when a fast-forward would have been possible.",
            "use_when": [
                "A workflow intentionally wants one merge commit that preserves the integration event instead of silently linearizing history.",
                "The integration target is one ref such as feature/demo or origin/main, not one standalone commit transplant or one branch-range rewrite.",
            ],
            "do_not_use_for": [
                "Requiring a linear-history-only fast-forward update; use connector.git.integrate.merge_ff_only when creating a merge commit would be the wrong outcome.",
                "Replaying one commit or rewriting a topic branch onto a new base; use connector.git.integrate.cherry_pick or connector.git.integrate.rebase_onto for those narrower rewrite semantics.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.integrate.merge_ff_only", "summary": "Sibling action for integrating one target ref only when the current checkout can fast-forward without creating a merge commit"},
                {"handle": "connector.git.integrate.cherry_pick", "summary": "Sibling action for copying one commit onto the current checkout without merging a whole target ref"},
                {"handle": "connector.git.integrate.rebase_onto", "summary": "Sibling action for rewriting one branch range onto a new base instead of integrating into the current checkout by merge"},
                {"handle": "connector.git.range", "summary": "Sibling probe for checking ahead/behind or merge-base facts before choosing an integration strategy"},
            ],
            "examples": [
                {"reference": "git.integrate.merge", "inputs": {"ref": "feature/demo"}},
            ],
            "inspect_next": ["connector.git.integrate.merge_ff_only", "connector.git.range", "connector.git.integrate.cherry_pick"],
        },
        ("git", "integrate.merge_ff_only"): {
            "definition": "Integrate one target Git ref into the current checkout only if the update can fast-forward, refusing to create a merge commit when histories have diverged.",
            "use_when": [
                "A workflow wants linear-history integration and should fail cleanly rather than synthesize a merge commit for the target ref.",
                "The authored decision is specifically about advancing the current checkout to one descendant ref, not about copying one commit or rewriting a topic branch range.",
            ],
            "do_not_use_for": [
                "Preserving an explicit integration commit even when fast-forward would be possible; use connector.git.integrate.merge for ordinary merge semantics.",
                "Branch-range rewrites or single-commit transplants; use connector.git.integrate.rebase_onto or connector.git.integrate.cherry_pick for those rewrite-oriented surfaces.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.integrate.merge", "summary": "Sibling action for integrating the same target ref through an explicit merge commit instead of fast-forward-only admission"},
                {"handle": "connector.git.range", "summary": "Sibling probe for confirming whether two endpoints are already in a fast-forward relationship before this action runs"},
                {"handle": "connector.git.upstream", "summary": "Sibling probe for current-branch upstream context when the workflow first needs to choose which target ref should fast-forward"},
                {"handle": "connector.git.integrate.rebase_onto", "summary": "Sibling action for rewriting branch history when linear movement requires replay rather than pure fast-forward integration"},
            ],
            "examples": [
                {"reference": "git.integrate.merge_ff_only", "inputs": {"ref": "origin/main"}},
            ],
            "inspect_next": ["connector.git.range", "connector.git.integrate.merge", "connector.git.upstream"],
        },
        ("git", "integrate.cherry_pick"): {
            "definition": "Apply one existing non-merge Git commit onto the current checkout as a new commit, without integrating the whole source ref history.",
            "use_when": [
                "A workflow needs one targeted commit transplant such as backporting one fix without merging or rebasing the larger branch that originally contained it.",
                "The authored decision is about one chosen commit identity, not about integrating a whole ref tip or replaying a branch range onto a new base.",
            ],
            "do_not_use_for": [
                "Integrating a whole branch tip or preserving branch topology; use connector.git.integrate.merge or connector.git.integrate.merge_ff_only when the unit of integration is one ref rather than one commit.",
                "Cherry-picking merge commits or rewriting one topic branch onto a new base; this surface rejects merge commits and is narrower than connector.git.integrate.rebase_onto.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.integrate.merge", "summary": "Sibling action for integrating a whole target ref instead of transplanting one selected commit"},
                {"handle": "connector.git.integrate.rebase_onto", "summary": "Sibling action for replaying a branch range onto a new base rather than copying one chosen commit"},
                {"handle": "connector.git.commits", "summary": "Sibling probe for loading readable commit history before choosing which commit to cherry-pick"},
                {"handle": "connector.git.ref", "summary": "Sibling probe for exact ref resolution when the workflow still needs to identify the source commit or source branch first"},
            ],
            "examples": [
                {"reference": "git.integrate.cherry_pick", "inputs": {"commit": "abc1234"}},
            ],
            "inspect_next": ["connector.git.commits", "connector.git.integrate.merge", "connector.git.integrate.rebase_onto"],
        },
        ("git", "integrate.rebase_onto"): {
            "definition": "Rewrite one non-default Git branch by replaying the commits after one upstream boundary onto a new base with rebase --onto semantics.",
            "use_when": [
                "A workflow needs to move a topic branch onto a new base while preserving only the branch-local commit range after one upstream split point.",
                "The authored decision is branch-range rewriting itself, not whole-ref integration into the current checkout and not a one-commit transplant.",
            ],
            "do_not_use_for": [
                "Integrating a target ref into the current checkout without rewriting branch history; use connector.git.integrate.merge or connector.git.integrate.merge_ff_only for those integration semantics.",
                "Rebasing the repository default branch or copying only one selected commit; this surface protects the default branch and is broader than connector.git.integrate.cherry_pick.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.integrate.merge", "summary": "Sibling action for integrating by merge instead of rewriting one branch range onto a new base"},
                {"handle": "connector.git.integrate.cherry_pick", "summary": "Sibling action for replaying one chosen commit instead of rebasing an entire branch-local range"},
                {"handle": "connector.git.range", "summary": "Sibling probe for inspecting base/head relationships before choosing onto and upstream boundaries"},
                {"handle": "connector.git.branch", "summary": "Sibling probe for current checkout branch identity when the workflow first needs to confirm which branch is being rewritten"},
            ],
            "examples": [
                {"reference": "git.integrate.rebase_onto", "inputs": {"onto": "origin/main", "upstream": "main", "branch": "feature/demo"}},
            ],
            "inspect_next": ["connector.git.range", "connector.git.branch", "connector.git.integrate.cherry_pick"],
        },
        ("git", "sync.fetch"): {
            "definition": "Fetch refs from one Git remote configured in the local repository so later probes and decisions can see updated remote-tracking state without publishing any local branch back outward.",
            "use_when": [
                "A workflow first needs fresh remote-tracking refs, tags, or branch comparisons before deciding whether merging, rebasing, or pushing is safe.",
                "The authored intent is inbound synchronization from one named remote, not publishing a local branch to collaborators.",
                "Supply a nonempty remote name without whitespace or a leading '-'. During run, the name must exactly match the local git remote inventory; team/origin is valid when configured. Any accepted spelling in that inventory is an identifier, not a direct transport destination.",
                "During run, malformed or unknown names return remote_not_found with action.git.invalid_remote or action.git.remote_not_found respectively. Local inventory failure returns fetch_blocked with action.git.remote_inventory_failed; none of these validation failures starts transport. Inspection modes do not perform this action-time validation.",
            ],
            "do_not_use_for": [
                "Publishing local commits to a remote; use connector.git.sync.push when the workflow needs outbound branch publication rather than remote refresh.",
                "Comparing branch divergence itself; use connector.git.range after fetch when the workflow actually needs ahead/behind facts rather than the refresh action.",
                "Ad-hoc URLs, paths, or options instead of configured names. Configured Git URLs and helpers remain trusted; this validation is not a protocol sandbox.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.sync.push", "summary": "Sibling action for publishing one local branch outward after remote state has been refreshed or confirmed"},
                {"handle": "connector.git.range", "summary": "Sibling probe for comparing local and remote revision endpoints after fetch updates remote-tracking refs"},
                {"handle": "connector.git.tags", "summary": "Sibling probe for reading fetched tag inventory when the workflow cares about release refs after refresh"},
                {"handle": "connector.git.upstream", "summary": "Sibling probe for current-branch tracking context before deciding which remote should be fetched or pushed"},
            ],
            "examples": [
                {"reference": "git.sync.fetch", "inputs": {"remote": "origin"}},
                {"reference": "git.sync.fetch", "inputs": {"remote": "team/origin"}},
            ],
            "inspect_next": ["connector.git.range", "connector.git.sync.push", "connector.git.tags"],
        },
        ("git", "sync.push"): {
            "definition": "Push one local Git branch to a configured remote name, supplied explicitly or derived by the current upstream resolver when remote is omitted or null, then validated against configured names.",
            "use_when": [
                "A workflow is ready to publish one local branch outward after local validation, range checks, or remote refresh have already justified the push decision.",
                "The authored intent is outbound branch publication itself, not merely refreshing remote-tracking refs or inspecting divergence.",
                "Supply a nonempty remote name without whitespace or a leading '-'. During run, the name must exactly match the local git remote inventory; team/origin is valid when configured. Any accepted spelling in that inventory is an identifier, not a direct transport destination.",
                "Omitted or null remote uses git.upstream for the current branch, which must match the requested branch, then applies the same membership validation. The exact branch.<current>.remote name is supported, including nested names such as team/origin. Missing matching upstream context returns upstream_remote_missing; unsupported upstream configuration propagates probe_failed rather than guessing a remote.",
                "During run, malformed or unknown names return remote_not_found with action.git.invalid_remote or action.git.remote_not_found respectively. Local inventory failure returns push_blocked with action.git.remote_inventory_failed; none of these validation failures starts transport. Inspection modes do not perform this action-time validation. Branch, upstream, and range remain preflight observations; upstream now also reads local Git configuration and the canonical tracking ref, without network access.",
            ],
            "do_not_use_for": [
                "Refreshing local knowledge of remote refs; use connector.git.sync.fetch for inbound synchronization before or instead of publishing.",
                "Guessing whether a push would be fast-forward-safe without wanting to publish yet; use connector.git.range or connector.git.upstream for that read-only decision context first.",
                "Ad-hoc URLs, paths, or options instead of configured names. Configured Git URLs and helpers remain trusted; this validation is not a protocol sandbox.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.sync.fetch", "summary": "Sibling action for refreshing remote-tracking refs before a later push decision or rejection recovery"},
                {"handle": "connector.git.upstream", "summary": "Sibling probe for resolving the current branch's configured upstream remote when remote is omitted"},
                {"handle": "connector.git.range", "summary": "Sibling probe for ahead/behind facts when the workflow first needs to know whether the push should succeed as fast-forward"},
                {"handle": "connector.git.branch", "summary": "Sibling probe for current branch identity when the workflow first needs to confirm which branch should be published"},
            ],
            "examples": [
                {"reference": "git.sync.push", "inputs": {"branch": "feature/demo", "remote": "origin"}},
                {"reference": "git.sync.push", "inputs": {"branch": "feature/demo", "remote": "team/origin"}},
                {"reference": "git.sync.push", "inputs": {"branch": "feature/demo", "remote": None}},
            ],
            "inspect_next": ["connector.git.sync.fetch", "connector.git.upstream", "connector.git.range"],
        },
        ("git", "stash"): {
            "definition": "Probe the current Git stash inventory and return the ordered stash entries, their selectors, and the repository root they belong to.",
            "use_when": [
                "A workflow needs to know whether stash entries exist before switching branches, cleaning a worktree, or deciding whether hidden local work might need recovery.",
                "Later logic needs the explicit stash entry list itself rather than only one coarse repository-state summary flag.",
            ],
            "do_not_use_for": [
                "Reading only one combined repository snapshot with branch and worktree flags; use connector.git.state when stash count is just one part of a broader readiness summary.",
                "Inspecting unstaged or staged path details; use connector.git.worktree when the workflow is really about dirty files rather than saved stash entries.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.state", "summary": "Sibling probe for one broader branch-plus-worktree-plus-stash-count summary instead of the explicit stash entry list"},
                {"handle": "connector.git.worktree", "summary": "Sibling probe for current dirty-path details when the workflow needs live worktree changes rather than saved stash entries"},
                {"handle": "connector.git.branch.switch", "summary": "Sibling action often guarded by stash awareness when the workflow wants to avoid losing hidden local work during checkout changes"},
                {"handle": "connector.git.repo", "summary": "Sibling probe for repository-level context when the workflow first needs root and default-branch facts rather than stash inventory"},
            ],
            "examples": [
                {"reference": "git.stash", "inputs": {}},
            ],
            "inspect_next": ["connector.git.state", "connector.git.worktree", "connector.git.branch.switch"],
        },
        ("git", "worktrees"): {
            "definition": "Probe the repository's Git worktree inventory and return every attached worktree path together with its HEAD, branch or detached status, bare flag, and which path is current.",
            "use_when": [
                "A workflow needs to reason about multiple checkouts of the same repository, such as locating the current worktree, finding detached sibling worktrees, or checking whether another branch is already checked out elsewhere.",
                "Later logic needs the explicit multi-worktree topology itself rather than only the current checkout branch or current worktree cleanliness.",
            ],
            "do_not_use_for": [
                "Inspecting only the current checkout's dirty files or staging state; use connector.git.worktree for live path-level cleanliness details in one worktree.",
                "Reading only one repository snapshot for the current checkout; use connector.git.state or connector.git.branch when the workflow does not need sibling worktree inventory.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.worktree", "summary": "Sibling probe for current dirty-path details inside one worktree instead of the repository-wide worktree inventory"},
                {"handle": "connector.git.branch", "summary": "Sibling probe for current checkout branch identity when the workflow does not need multi-worktree topology"},
                {"handle": "connector.git.repo", "summary": "Sibling probe for repository root and default-branch context before or alongside multi-worktree inspection"},
                {"handle": "connector.git.state", "summary": "Sibling probe for one broader current-checkout summary instead of listing every attached worktree"},
            ],
            "examples": [
                {"reference": "git.worktrees", "inputs": {}},
            ],
            "inspect_next": ["connector.git.worktree", "connector.git.branch", "connector.git.repo"],
        },
        ("git", "repo"): {
            "definition": "Probe the current local Git repository context and return repository-root, git-dir, worktree, HEAD-ref, and default-branch facts for the repository discovered at the current root.",
            "use_when": [
                "A workflow first needs to confirm repository-level context such as root path, bare status, or default branch before making narrower branch or sync decisions.",
                "Later logic needs stable repository facts without yet asking about one specific ref, one branch inventory, or one upstream relationship.",
            ],
            "do_not_use_for": [
                "Reading the current branch's upstream-tracking configuration; use connector.git.upstream for that branch-specific tracking surface.",
                "Inspecting branch inventory or current checkout branch identity; use connector.git.branches or connector.git.branch when the workflow is really about branch-level context.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.upstream", "summary": "Sibling probe for current-branch upstream tracking after repository context is known"},
                {"handle": "connector.git.branch", "summary": "Sibling probe for current checkout branch identity rather than repository-level facts"},
                {"handle": "connector.git.worktree", "summary": "Sibling probe for broader worktree cleanliness and file-change context"},
                {"handle": "connector.git.ref", "summary": "Sibling probe for one exact ref lookup instead of repository-wide context"},
            ],
            "examples": [
                {"reference": "git.repo", "inputs": {}},
            ],
            "inspect_next": ["connector.git.upstream", "connector.git.branch", "connector.git.worktree"],
        },
        ("git", "remote"): {
            "definition": "Observe one configured Git remote's effective fetch and push URLs and mirror setting from local Git configuration without network access.",
            "use_when": [
                "Supply required remote: string as a nonempty configured name without whitespace, NUL, or a leading '-'; nested names such as team/origin are supported. Match the local git remote inventory exactly.",
                "Success returns name: string, exists: boolean, fetch_urls: array of strings, push_urls: array of strings, and mirror: boolean or null. A missing remote succeeds with exists=false, fetch_urls=[], push_urls=[], mirror=null, and the requested name preserved.",
                "For an existing remote, git remote get-url --all and git remote get-url --push --all supply effective URLs after Git insteadOf and pushInsteadOf rewrites and Git's push-URL fallback. Preserve every literal observed URL in order, including duplicates, without normalization, trimming, or redaction. Only LF delimits records; CR and Unicode line separators remain URL content.",
                "mirror reports git config --bool --get remote.<name>.mirror: true or false; an absent mirror setting on an existing remote means mirror=false, not null. Git config exit 1 represents the absent setting; other command failures fail the probe.",
                "All local failures use probe_failed. Diagnostic prefix probe.git_remote has invalid_input, inventory_failed, invalid_inventory, fetch_urls_failed, push_urls_failed, invalid_fetch_urls, invalid_push_urls, mirror_failed, and invalid_mirror. Duplicate or malformed inventory names, empty URL lists or records, and invalid mirror booleans fail rather than produce partial success. Raw command evidence supplements structured outputs.",
                "These read-only, non-atomic observations use ordinary probe evaluation in check, review, plan, run, explain, and next; no mode-specific policy or new engine semantics. Git availability and repository context remain shared family bootstrap prerequisites.",
            ],
            "do_not_use_for": [
                "URL safety, redaction, normalization, host/protocol allowlists, or remote policy: the caller chooses acceptable destinations from literal observations.",
                "Network reachability, authentication, remote repository identity, or proof of a later push destination: configuration can change between observation and transport.",
                "Repository-root facts, current-branch tracking, or publication itself; use connector.git.repo, connector.git.upstream, or connector.git.sync.push respectively.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.repo", "summary": "Local repository-root, git-dir, and default-branch facts"},
                {"handle": "connector.git.upstream", "summary": "Current branch's configured tracking remote and tracking ref"},
                {"handle": "connector.git.sync.push", "summary": "Publish a branch to a configured remote after the caller's decision"},
            ],
            "examples": [{"reference": "git.remote", "inputs": {"remote": "origin"}}],
            "inspect_next": ["connector.git.repo", "connector.git.upstream", "connector.git.sync.push"],
        },
        ("git", "upstream"): {
            "definition": "Probe the upstream-tracking configuration for the current local branch and return the exact configured remote and the branch tail of its conventional local remote-tracking ref.",
            "use_when": [
                "A workflow needs to know whether the current branch tracks one upstream before comparing ahead/behind state or deciding whether pushing makes sense.",
                "Later logic needs remote, remote_branch, or upstream_ref facts for the current branch rather than repository-root or branch-inventory facts.",
                "remote comes from branch.<current>.remote, so nested configured names such as team/origin are preserved. remote_branch is the local tracking tail under refs/remotes/<exactremote>/, not the source-side branch name from a fetch refspec.",
                "upstream_ref preserves Git's original abbreviated or full output. A separate canonical git rev-parse --symbolic-full-name lookup checks that spelling against the full tracking ref, avoiding misleading abbreviations.",
                "Detached HEAD and missing tracking return configured=false with null tracking fields; detached HEAD also has branch=null. Exit 128 from the initial upstream rev-parse retains this unconfigured result, rather than becoming a lookup failure.",
                "Unsupported remote names, including '.' for a local upstream, return probe_failed with probe.git_upstream.invalid_remote. A failed Git configuration lookup returns probe.git_upstream.remote_lookup_failed. Nonstandard tracking destinations or inconsistent ref spellings return probe.git_upstream.invalid_ref; a failed canonical ref lookup returns probe.git_upstream.ref_lookup_failed. These four diagnostics use probe_failed, never a guessed remote.",
                "These are local, read-only observations shared by runtime mode paths that evaluate the probe or its preflight observation: check, review, plan, run, explain, and next. Additional Git configuration and canonical-ref reads perform no network access. Reads are non-atomic; repository state can change between them.",
            ],
            "do_not_use_for": [
                "Reading repository-root, git-dir, or default-branch facts; use connector.git.repo for repository-level context.",
                "Comparing current branch divergence against its upstream; use connector.git.range when the workflow needs ahead/behind math after choosing base and head endpoints.",
                "Resolving source-side branch names from custom fetch mappings, local '.' upstreams, or tracking destinations outside refs/remotes/<exactremote>/. Unsupported shapes fail instead of being inferred.",
                "Validating transport destinations or proving push safety. Fetch/push remote-inventory membership checks remain run-only; configured URLs and helpers remain trusted, not a transport sandbox.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.repo", "summary": "Sibling probe for repository-level facts before or alongside upstream-tracking inspection"},
                {"handle": "connector.git.branch", "summary": "Sibling probe for current branch identity when the workflow first needs the branch name itself"},
                {"handle": "connector.git.range", "summary": "Sibling probe for ahead/behind and merge-base comparison after an upstream target is known"},
                {"handle": "connector.git.sync.push", "summary": "Sibling action surface for actually pushing once upstream-tracking context has been confirmed"},
            ],
            "examples": [
                {"reference": "git.upstream", "inputs": {}},
            ],
            "inspect_next": ["connector.git.range", "connector.git.sync.push", "connector.git.branch"],
        },
        ("git", "index.add_all"): {
            "definition": "Stage every currently changed, deleted, and untracked path from the current Git worktree into the index as one all-in staging action.",
            "use_when": [
                "A workflow has already decided that the whole current worktree batch should be staged before one later commit or review step.",
                "The authored intent is full-worktree staging itself, not selective per-path staging or read-only inspection.",
            ],
            "do_not_use_for": [
                "Inspecting which paths are dirty or whether the worktree is clean; use connector.git.worktree or connector.git.state for those read-only checks.",
                "Selecting only some paths for staging; this public surface intentionally stages the whole current worktree batch at once.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.worktree", "summary": "Sibling probe for the path-level dirty-worktree view before or after staging"},
                {"handle": "connector.git.state", "summary": "Sibling probe for a broader branch-plus-worktree-plus-stash summary after staging decisions"},
                {"handle": "connector.git.commit.create", "summary": "Typical follow-up action for recording the newly staged index as one ordinary commit"},
                {"handle": "connector.git.commit.amend", "summary": "Sibling follow-up action when the staged batch should rewrite HEAD instead of creating a new commit"},
            ],
            "examples": [
                {"reference": "git.index.add_all", "inputs": {}},
            ],
            "inspect_next": ["connector.git.worktree", "connector.git.state", "connector.git.commit.create"],
        },
        ("git", "worktree"): {
            "definition": "Probe the current Git worktree cleanliness and changed-path inventory, separating untracked, staged, and unstaged changes without mixing in branch or stash summary fields.",
            "use_when": [
                "A workflow needs the exact dirty-path list or needs to distinguish staged, unstaged, and untracked changes before a later Git action.",
                "Later logic is about worktree cleanliness itself rather than about the current branch name or stash inventory.",
            ],
            "do_not_use_for": [
                "One coarse repository-status snapshot that also includes current-branch and stash facts; use connector.git.state for that combined summary surface.",
                "Mutating the index by staging everything; use connector.git.index.add_all for the all-in staging action.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.state", "summary": "Sibling probe for one broader repository-status snapshot that includes branch and stash context"},
                {"handle": "connector.git.index.add_all", "summary": "Sibling action for staging the current worktree batch after this probe inspects it"},
                {"handle": "connector.git.branch.switch", "summary": "Sibling action for checkout movement when local cleanliness may decide whether switching is safe"},
                {"handle": "connector.git.commit.create", "summary": "Sibling action for committing once staged and unstaged worktree state has been reviewed"},
            ],
            "examples": [
                {"reference": "git.worktree", "inputs": {}},
            ],
            "inspect_next": ["connector.git.index.add_all", "connector.git.state", "connector.git.commit.create"],
        },
        ("git", "state"): {
            "definition": "Probe one combined Git repository-state snapshot by composing current-branch context, worktree cleanliness flags, and stash count into one higher-level summary surface.",
            "use_when": [
                "A workflow needs one compact readiness snapshot before deciding whether committing, switching, syncing, or publishing repository state makes sense.",
                "Later logic needs branch, detached, worktree-cleanliness, and stash-count facts together rather than one path-level worktree inventory alone.",
            ],
            "do_not_use_for": [
                "Inspecting the exact dirty path list or keeping staged-versus-unstaged file paths visible; use connector.git.worktree for that narrower path-level probe.",
                "Listing stash entries themselves or mutating staging state; use connector.git.stash for stash inventory and connector.git.index.add_all for full-worktree staging.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.git.worktree", "summary": "Sibling probe for path-level worktree details instead of one combined repository snapshot"},
                {"handle": "connector.git.branch", "summary": "Sibling probe for only the current checkout branch when broader cleanliness and stash context are unnecessary"},
                {"handle": "connector.git.stash", "summary": "Sibling probe for explicit stash-entry inventory instead of only the stash count summary"},
                {"handle": "connector.git.index.add_all", "summary": "Sibling action for staging the whole current worktree after this summary confirms the repository is ready"},
            ],
            "examples": [
                {"reference": "git.state", "inputs": {}},
            ],
            "inspect_next": ["connector.git.worktree", "connector.git.index.add_all", "connector.git.branch"],
        },
        ("gh", "pr"): {
            "definition": "Probe one GitHub pull request as a typed metadata snapshot with head/base identity, a verified test-merge candidate, and stack scope. Prefer connector_contexts.gh.repository as the normal repository target; review warns when an explicit repository overrides it.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and workflow logic now needs one PR snapshot there by pull number.",
                "Workflow logic needs the pull request's current headline facts before deciding which narrower PR surfaces to inspect next.",
                "A later step needs branch refs, draft/state flags, review decision, or change totals from one normalized PR snapshot.",
                "head_sha and base_sha identify head H and base B with their repositories. test_merge_state=verified means candidate M has the observed parents B then H; test_merge_sha, test_merge_head_sha, and test_merge_base_sha retain that identity. merge_commit_sha is the completed merge result only when merged=true.",
                "stack_state is standalone, stacked, or unknown; stack carries the observed stack data. The first-version gh.pr.merge action rejects stacked PRs and unknown scope before submission.",
            ],
            "do_not_use_for": [
                "Discovering candidates before a pull number is known; use gh.pr.list with explicit state filters, then apply workflow-owned identity and history rules.",
                "Conversation history, submitted reviews, line comments, checks, or lifecycle events; use the dedicated PR sibling surfaces for those narrower views.",
                "Mutating or merging the pull request; this published surface is observation only.",
                "A test-merge candidate is not a completed merge or proof of the CI worker checkout. Missing identity stays unavailable, not invented. A snapshot gives no atomic base or stack guarantee; never replace the accepted CI head with this probe's freshly fetched head when authoring expected_head_sha.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh", "summary": "Parent GitHub connector family for issue, pull-request, and project operations"},
                {"handle": "connector.gh.pr.list", "summary": "Discover filtered PR candidates; one item does not automatically identify the correct PR"},
                {"handle": "connector.gh.pr.create", "summary": "Create a PR before detailed by-number inspection; existing open identity refuses creation"},
                {"handle": "connector.gh.pr.diff", "summary": "Sibling probe for changed files and patch content rather than PR headline metadata"},
                {"handle": "connector.gh.pr.reviews", "summary": "Sibling probe for submitted review decisions rather than the PR snapshot"},
                {"handle": "connector.gh.pr.checks", "summary": "Observe CI attached to head H or verified candidate M"},
                {"handle": "connector.gh.pr.merge", "summary": "Submit a merge with expected_head_sha from accepted CI evidence"},
                {"handle": "connector.gh.pr.merge.request", "summary": "Observe completion using the saved request UUID"},
            ],
            "examples": [
                {"reference": "gh.pr", "inputs": {"pull_number": 42}},
            ],
            "inspect_next": ["connector.gh.pr.diff", "connector.gh.pr.comments", "connector.gh.pr.reviews", "connector.gh.pr.checks", "connector.gh.pr.merge", "connector.gh.pr.merge.request"],
        },
        ("gh", "pr.list"): {
            "definition": "Probe one full filtered GitHub pull-request collection through REST list PRs, with minimal lifecycle and head/base identity facts for workflow-owned candidate classification.",
            "use_when": [
                GH_PR_LIST_GUIDANCE,
                "The repository argument is optional: a valid explicit ASCII OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error.",
                "Supply required state explicitly as open, closed, or all. head is an optional branch filter, head_owner an optional user/org qualifier requiring head, and base an optional base branch filter. Narrowing head/base is workflow policy, not an operation requirement.",
                "Items expose number, url, state, draft, merged, merged_at, head_repository, head_repository_key, head_owner, head_ref, head_sha, base_repository, base_ref, base_sha, and pull_ref. Preserve these identities for exact fork matching before detailed gh.pr inspection.",
                "GitHub repository identity is case-insensitive. Raw head_repository preserves API case; nullable head_repository_key is the lowercase identity. Gate on a known nonnull key, then match with only(head_repository_key=inputs.head_repository | lower). Raw case-sensitive comparison could falsely report no PR when API/input case differs; unknown keys block dependent decisions.",
                "The list API supplies merged_at: a known merge timestamp derives merged=true, explicitly present null merged_at derives false, and missing or indeterminate evidence derives null. Never turn unknown into false or infer merged merely from closed state.",
                "An item with state: open and nonnull merged_at is contradictory and fails the observation.",
                "With head and head_owner, compose the server head filter as owner:branch. Without head_owner, send only state/base server filters and apply exact head matching locally across all pages; GitHub docs do not guarantee bare-head filtering. Missing head_ref when local filtering is required fails rather than silently discarding the item.",
                "Success requires full filtered traversal; transport, normalization, or pagination failure cannot publish partial success. A protective cap of 100 pages of 100 items applies to the traversed collection before local filtering and fails if more pages remain, even with few matches; it is not a public result limit.",
                "A subprocess timeout (subprocess.TimeoutExpired) returns pull_list_unavailable with no partial outputs.",
                "GitHub.com only, matching the bootstrap authentication host. Pagination accepts validated repository-name and numeric /repositories/id/pulls paths, validates repository IDs and pagination parameters, and constructs requests locally; never follow response URLs directly.",
            ],
            "do_not_use_for": [
                "A generic correct-PR selector, creation authorization, reopening, or merge decisions. gh.pr.create performs a separate mandatory open-duplicate check after workflow-owned history policy.",
                "Detailed facts for a known pull_number; use gh.pr. List facts are minimal and unavailable facts must remain unknown.",
                "PR author filtering: head_owner means head repository owner. One owner can own multiple repositories with the same branch; owner plus branch is not an exact repository guarantee.",
                "Public page, cursor, or limit controls, partial-success truncation, search-index completeness, atomic concurrency completeness, or a total remote count guarantee.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh", "summary": "Parent GitHub family and repository context rules"},
                {"handle": "connector.gh.pr", "summary": "Detailed pull-request snapshot by number after workflow-owned candidate classification"},
                {"handle": "connector.gh.pr.create", "summary": "Create after workflow-owned history policy, with a separate mandatory exact open-duplicate check"},
                {"handle": "workflow-rules", "summary": "Own identity, ambiguity, closed history, and unknown-fact decisions in workflow logic"},
            ],
            "examples": [
                {"reference": "gh.pr.list", "inputs": {"state": "all", "head": "feature/topic", "head_owner": "acme", "base": "main"}},
                {"reference": "gh.pr.list", "inputs": {"state": "all"}},
            ],
            "inspect_next": ["connector.gh.pr", "connector.gh", "workflow-rules"],
        },
        ("gh", "pr.create"): {
            "definition": "Create one GitHub pull request after a mandatory complete exact-identity open-duplicate precheck.",
            "use_when": [
                GH_PR_CREATE_GUIDANCE,
                "Workflow policy has authorized creation, including any closed-history decision. Register the action result and distinguish runtime status, diagnostic code, pull_number/url identity, and tri-state created; already_exists is non-OK rather than reuse.",
                "Outputs are repository, pull_number, pull_ref, url, created, head_repository, head_ref, head_sha, base_repository, base_ref, base_sha, draft, state, http_status, message, and errors. Unknown identity/response facts stay null. Failure statuses are input_error, precheck_failed, ambiguous, already_exists, api_failed, create_refused, and creation_unknown; validated creation is ok.",
                "check, review, plan, explain, and next retain action non-execution; run executes the admitted action. The internal probe does not make creation read-only or authorize POST in analysis modes.",
            ],
            "do_not_use_for": [
                "Find-or-reuse, reopening, or closed-history policy; use a separate gh.pr.list state: all observation and workflow rules.",
                "Atomic uniqueness, exactly-once effects, automatic retry or readback reconciliation after unknown creation results.",
                "Waiting for CI, merging, pushing, forking, branch cleanup, or extra issue/project mutations.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr.list", "summary": "Full candidate observation and workflow-owned closed-history classification"},
                {"handle": "connector.gh.pr", "summary": "Detailed by-number inspection after creation"},
                {"handle": "connector.gh.pr.merge", "summary": "Separate SHA-bound merge action after CI acceptance"},
                {"handle": "connector.authoring", "summary": "SDK same-family probe dependency calls with resolved inputs"},
            ],
            "examples": [{"reference": "gh.pr.create", "inputs": {"head": "feature/topic", "base": "main", "title": "Add topic", "draft": False}}],
            "inspect_next": ["connector.gh.pr.list", "connector.gh.pr", "connector.gh.pr.merge", "connector.authoring"],
        },
        ("gh", "pr.comments"): {
            "definition": "Probe the regular conversation thread on one GitHub pull request as top-level discussion comments plus total count metadata. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs top-level PR discussion there by pull number.",
                "The workflow needs human conversation on the PR itself before summarizing discussion or deciding whether follow-up is needed.",
            ],
            "do_not_use_for": [
                "Line-level review discussion attached to changed files; use connector.gh.pr.review_comments for code-anchored comments.",
                "Submitted review decisions such as APPROVED or CHANGES_REQUESTED; use connector.gh.pr.reviews for review verdicts.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr", "summary": "Parent PR snapshot probe that omits conversation thread details"},
                {"handle": "connector.gh.pr.review_comments", "summary": "Sibling probe for line-level code review comments instead of top-level conversation comments"},
                {"handle": "connector.gh.pr.reviews", "summary": "Sibling probe for submitted review decisions rather than free-form conversation comments"},
            ],
            "examples": [
                {"reference": "gh.pr.comments", "inputs": {"pull_number": 42, "limit": 20}},
            ],
            "inspect_next": ["connector.gh.pr.review_comments", "connector.gh.pr.reviews", "connector.gh.pr.timeline"],
        },
        ("gh", "pr.diff"): {
            "definition": "Probe one GitHub pull request diff as normalized changed-file summaries with patch excerpts, rename metadata, and binary/truncation signals. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs changed-file detail there for one PR number.",
                "The workflow needs to reason about which files changed or inspect bounded patch content without parsing raw git output itself.",
            ],
            "do_not_use_for": [
                "Overall PR headline facts such as title, branch refs, or review decision; use connector.gh.pr for that metadata snapshot.",
                "Conversation or review decision surfaces; use comments, review_comments, or reviews when the workflow is about discussion rather than code changes.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr", "summary": "Parent PR snapshot probe that reports change totals but not per-file diff content"},
                {"handle": "connector.gh.pr.review_comments", "summary": "Sibling probe for line-level reviewer feedback that may reference files from this diff"},
                {"handle": "connector.git.range", "summary": "Repository-local git diff surface when the workflow needs local git ranges instead of remote PR normalization"},
            ],
            "examples": [
                {"reference": "gh.pr.diff", "inputs": {"pull_number": 42, "limit": 20}},
            ],
            "inspect_next": ["connector.gh.pr.review_comments", "connector.git.range", "connector.gh.pr"],
        },
        ("gh", "pr.review_comments"): {
            "definition": "Probe line-level review comments on one GitHub pull request as typed code-anchored discussion records with path and line metadata. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs file-anchored PR review comments there by pull number.",
                "The workflow needs reviewer feedback tied to concrete files or lines rather than only top-level PR conversation.",
            ],
            "do_not_use_for": [
                "Top-level conversation comments on the PR body; use connector.gh.pr.comments for that broader discussion thread.",
                "Submitted review verdicts without line detail; use connector.gh.pr.reviews for the review-level decisions.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr.diff", "summary": "Sibling probe for changed-file context that these line comments often reference"},
                {"handle": "connector.gh.pr.comments", "summary": "Sibling probe for top-level conversation comments rather than file-anchored review remarks"},
                {"handle": "connector.gh.pr.reviews", "summary": "Sibling probe for submitted review verdicts rather than individual line comments"},
            ],
            "examples": [
                {"reference": "gh.pr.review_comments", "inputs": {"pull_number": 42, "limit": 20}},
            ],
            "inspect_next": ["connector.gh.pr.diff", "connector.gh.pr.reviews", "connector.gh.pr.comments"],
        },
        ("gh", "pr.reviews"): {
            "definition": "Probe submitted GitHub pull-request reviews as typed review records with verdict, author, timestamp, and optional reviewed commit id. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs submitted review records there by pull number.",
                "The workflow needs reviewer decisions such as APPROVED or CHANGES_REQUESTED without reconstructing them from comments or timeline events.",
            ],
            "do_not_use_for": [
                "Free-form top-level discussion; use connector.gh.pr.comments when the workflow needs ordinary PR conversation.",
                "Per-line feedback details; use connector.gh.pr.review_comments for code-anchored remarks.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr", "summary": "Parent PR snapshot that carries only aggregate review decision, not the individual submitted reviews"},
                {"handle": "connector.gh.pr.review_comments", "summary": "Sibling probe for detailed line-level review discussion"},
                {"handle": "connector.gh.pr.timeline", "summary": "Sibling probe for lifecycle events that may surround review activity"},
            ],
            "examples": [
                {"reference": "gh.pr.reviews", "inputs": {"pull_number": 42, "limit": 20}},
            ],
            "inspect_next": ["connector.gh.pr.review_comments", "connector.gh.pr.timeline", "connector.gh.pr"],
        },
        ("gh", "actions.run"): {
            "definition": "Observe one GitHub Actions run attempt, selected by a run ID or a check suite's direct Actions association.",
            "use_when": [
                "Supply exactly one non-null positive integer run_id or check_suite_id. Optional positive integer attempt selects that numbered attempt; omitted/null attempt reads the latest observed run_attempt, then retrieves the pinned numbered attempt. Booleans are not integer identifiers.",
                "repository is optional and nullable: explicit valid literal ASCII OWNER/REPO overrides bootstrapped connector_contexts.gh.repository; omitted/null uses context. Malformed explicit values fail without fallback; no resolved target is input_error. Bootstrap requires an available authenticated gh CLI with repository access on github.com. Context is a default, not an authorization allowlist.",
                "For check_suite_id, resolve the REST suite node then query GraphQL CheckSuite.workflowRun directly, validating repository, node type, suite identity and backreference. No repository-wide run scan is used. A validated null association returns found=false, requested check_suite_id, repository, pull_requests=[], and all other run fields null. Missing nodes/fields or GraphQL errors fail, not normal absence.",
                "On found=true, outputs include repository, run_id, check_suite_id, run_attempt, workflow_id, workflow_path, event, status, conclusion, head_sha, head_branch, url, created_at, updated_at, run_started_at, and pull_requests with number/head_sha/base_sha. Optional API facts remain null; missing pull_requests becomes []. Present SHAs are full hexadecimal values. Output run_attempt becomes the explicit attempt input to gh.actions.run.jobs.",
                "Invalid selectors, attempt or repository resolution produce input_error. API/transport failures, malformed responses and repository/run/attempt/suite mismatches produce actions_run_unavailable with reason diagnostics and raw request evidence. HTTP 404 is not found=false; shared bootstrap failures can precede operation execution.",
            ],
            "do_not_use_for": [
                "Run triggering, reruns, cancellation, polling, log retrieval, required-job selection, or merge policy. This is read-only observation.",
                "A tested-SHA attestation or immutable event snapshot: PR head/base SHAs are API observations, not proof of worker checkout. Latest-then-pinned retrieval is non-atomic and does not promise the newest attempt at return time.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.actions.run.jobs", "summary": "Full jobs traversal using the observed run_id and explicit attempt=run_attempt"},
                {"handle": "connector.gh.pr.checks", "summary": "PR-attached check runs expose nullable check_suite_id as the selector bridge"},
                {"handle": "connector.gh.repo.actions.permissions", "summary": "Repository Actions permission settings, not run observations"},
                {"handle": "connector.gh", "summary": "GitHub bootstrap and family operation boundaries"},
            ],
            "inspect_next": ["connector.gh.actions.run.jobs", "connector.gh.pr.checks", "connector.gh"],
            "examples": [
                {"reference": "gh.actions.run", "inputs": {"run_id": 123}},
                {"reference": "gh.actions.run", "inputs": {"check_suite_id": 456, "attempt": 2}},
            ],
        },
        ("gh", "actions.run.jobs"): {
            "definition": "Observe the complete job collection for one explicitly numbered GitHub Actions run attempt.",
            "use_when": [
                "Supply required positive integer run_id and explicit positive integer attempt, normally from gh.actions.run outputs run_id and run_attempt. There is no latest-attempt default or caller limit; booleans are invalid identifiers.",
                "repository is optional and nullable: explicit valid literal ASCII OWNER/REPO overrides bootstrapped connector_contexts.gh.repository; omitted/null uses context. Malformed explicit values fail without fallback; no resolved target is input_error. Bootstrap requires an available authenticated gh CLI with repository access on github.com. Context is a default, not an authorization allowlist.",
                "Outputs are repository, run_id, run_attempt, items, count and complete=true. Each item contains positive job_id, nullable check_run_id, and nullable name/status/conclusion/head_sha/url/started_at/completed_at. Present head_sha is a full hexadecimal SHA. Empty retrieval is items=[], count=0, complete=true, not successful CI.",
                "check_run_id is extracted only from a validated official https://api.github.com/repos/OWNER/REPO/check-runs/ID API check_run_url matching repository, not from logs or display URLs. Missing/null link gives null identity; malformed or mismatched links fail. Correlate this ID with gh.pr.checks check-run item id, whose check_suite_id supplies the suite-to-run bridge.",
                "Traverse attempt-scoped pages of 100 jobs, up to 100 pages, requiring stable total_count, exact page sizes, valid official API Link relations, unique job IDs and matching run/attempt per job. count equals len(items). Incomplete or inconsistent traversal fails rather than publishing partial success.",
                "Invalid repository/run_id/attempt is input_error. API/transport, malformed response, identity, invalid link, changing totals, duplicate IDs, missing pages or page-bound failures are actions_jobs_unavailable with reason diagnostics and raw evidence. Shared bootstrap failures can precede operation execution.",
            ],
            "do_not_use_for": [
                "Selecting the latest attempt implicitly, triggering, rerunning, cancelling, polling, downloading logs, choosing required jobs, or enforcing merge policy; this is read-only observation.",
                "Treating complete as an atomic snapshot, CI success, immutable event-time data, or tested-SHA attestation. Cross-page and cross-probe observations are non-atomic and do not prove worker checkout.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.actions.run", "summary": "Resolve a run or suite association and pin its observed run_attempt before reading jobs"},
                {"handle": "connector.gh.pr.checks", "summary": "PR-attached status/check evidence, not an Actions job collection"},
                {"handle": "connector.gh", "summary": "GitHub bootstrap and family operation boundaries"},
            ],
            "inspect_next": ["connector.gh.actions.run", "connector.gh.pr.checks", "connector.gh"],
            "examples": [
                {"reference": "gh.actions.run.jobs", "inputs": {"run_id": 123, "attempt": 2}},
            ],
        },
        ("gh", "pr.checks"): {
            "definition": "Probe one GitHub pull request head for normalized status contexts and check runs, or select a verified test-merge candidate. Paginated API-attached evidence preserves status fidelity and commit identity for workflow-owned CI acceptance policy.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs CI readiness for one PR there by pull number.",
                "The workflow needs CI readiness or status context outcomes before recommending merge, rerun, or escalation steps.",
                "target defaults to head; target=test_merge requires verified candidate M with base B and head H. commit_sha identifies the checked API commit; head_sha remains H. Optional expected_head_sha binds the observation to H and rejects a mismatch without silently switching targets.",
                "Inspect complete, statuses_complete, check_runs_complete, sha_evidence, and each check's name/context, app identity, SHA source, status, conclusion, and timestamps. Pending, failed, skipped, neutral, unknown, and empty evidence are not interchangeable with success; workflow policy must choose required checks and trusted producers explicitly.",
                "Preserve the head from accepted CI evidence for gh.pr.merge.expected_head_sha. Checks on candidate M authorize expected H, not M; never substitute a freshly fetched head after CI acceptance.",
                "Check-run items expose nullable check_suite_id from API check_suite.id; legacy commit statuses use null. Pass a known suite ID to gh.actions.run for direct GraphQL association lookup, then its run_id and run_attempt to gh.actions.run.jobs as run_id and explicit attempt. A validated null Actions association is found=false, not failed CI. Jobs' check_run_id comes from a validated official API URL and can correlate back to check-run item id; this bridge adds no tested-SHA or merge-policy claim.",
            ],
            "do_not_use_for": [
                "Review decisions from humans; use connector.gh.pr.reviews when the workflow cares about approvals or change requests.",
                "Branch or headline PR metadata unrelated to execution status; use connector.gh.pr for the broader snapshot.",
                "API-attached SHA evidence does not prove the CI worker checkout, branch-protection satisfaction, or an atomic base/stack snapshot. Pagination can drift; incomplete or unavailable evidence must not be treated as passing CI. No polling or merge submission occurs here.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr", "summary": "Parent PR snapshot that supplies the head SHA and mergeability context"},
                {"handle": "connector.gh.actions.run", "summary": "Resolve a check-run item's check_suite_id into one Actions attempt"},
                {"handle": "connector.gh.actions.run.jobs", "summary": "Complete job collection for that explicit run attempt"},
                {"handle": "connector.gh.pr.reviews", "summary": "Sibling probe for human review decisions rather than machine status results"},
                {"handle": "connector.gh.pr.timeline", "summary": "Sibling probe for lifecycle events that can explain why checks changed over time"},
                {"handle": "connector.gh.pr.merge", "summary": "Submit using the head identity retained from accepted CI evidence"},
                {"handle": "connector.gh.pr.merge.request", "summary": "Observe the saved merge request, not CI status"},
            ],
            "examples": [
                {"reference": "gh.pr.checks", "inputs": {"pull_number": 42}},
            ],
            "inspect_next": ["connector.gh.actions.run", "connector.gh.actions.run.jobs", "connector.gh.pr.reviews", "connector.gh.pr.timeline", "connector.gh.pr", "connector.gh.pr.merge", "connector.gh.pr.merge.request"],
        },
        ("gh", "pr.merge"): {
            "definition": "Submit one direct asynchronous GitHub merge request for a standalone PR, bound to the head accepted by CI policy.",
            "use_when": [
                "Supply pull_number, merge_method (merge/squash/rebase), and expected_head_sha as a full 40-digit hexadecimal SHA from the accepted CI head. The repository argument is optional: a valid explicit literal ASCII OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error. Repository context is a default, not an authorization allowlist. Explicit-repository examples supply repository as workflow policy, not as an operation requirement. The context example omits repository on merge and request; its comments show profile YAML supplying the context, not a workflow YAML context declaration.",
                "For accepted checks on verified test-merge candidate M with base B and head H, submit expected_head_sha=H, not M. Preserve that accepted head; a freshly fetched replacement defeats the CI-to-merge binding.",
                "The action rejects stacked PRs and unknown scope before submission; gh.pr exposes stack_state (standalone/stacked/unknown) plus stack for authoring guards and diagnostics.",
                "Register the action result and save its request_id UUID with repository and pull_number for gh.pr.merge.request. submission=accepted is not completion; pending and enqueued are not merged. Already merged is distinct from already enqueued.",
                "An existing request is reusable only when request_compatibility=exact: merge_method, direct_merge action, and expected_head_sha all match. Different or unknown parameters are not permission to reuse or blindly retry an uncertain submission.",
                "Before submission, unsupported_stack rejects stacked PRs, merge_scope_unknown rejects unavailable or malformed scope, and head_mismatch reports an observed head different from expected_head_sha. An already-merged PR can be reported without a new submission or stack/head admission.",
                "Distinguish merge_refused (HTTP 400 refusal) from merge_api_failed (scope-read failure or submission HTTP 403/404/422). HTTP 409 denotes an existing request, not a head-mismatch reason. merge_result_unknown preserves an uncertain submission outcome; do not blindly retry.",
            ],
            "do_not_use_for": [
                "No atomic base or stack guarantee is provided: the head guard does not freeze base B or prevent a later stack change. Stacked and unknown scope are rejected in this first version.",
                "No polling, merge queue administration, admin bypass, auto-merge configuration, or branch deletion is implemented. Spontaneous GitHub automatic issue closing and repository branch configuration effects are outside the action.",
                "GitHub evaluates repository rules for the authenticated actor. The action requests no bypass and changes no rules, but cannot remove that actor's server-configured bypass privileges.",
                "Submission success does not establish merge completion. Async failure carries a message, not a structured reason code; do not infer a strict head-mismatch classification from it.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr", "summary": "Observe PR identity and stack scope"},
                {"handle": "connector.gh.pr.checks", "summary": "Observe CI evidence whose accepted head must be retained"},
                {"handle": "connector.gh.pr.merge.request", "summary": "Observe the saved request UUID once after submission"},
            ],
            "inspect_next": ["connector.gh.pr.checks", "connector.gh.pr", "connector.gh.pr.merge.request"],
        },
        ("gh", "pr.merge.request"): {
            "definition": "Observe one saved asynchronous GitHub merge request UUID once and report its pending, merged, failed, or enqueued state.",
            "use_when": [
                "Supply pull_number and request_id from the stored gh.pr.merge action result; the UUID identifies the submitted request rather than a newly fetched PR head. The repository argument is optional: a valid explicit literal ASCII OWNER/REPO overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that context. Malformed explicit values fail without fallback, and no resolved repository is an error. The resolved repository input/context and pull_number must match the saved request's target. Explicit-repository examples supply repository as workflow policy, not as an operation requirement. The context example omits repository on merge and request; its comments show profile YAML supplying the context, not a workflow YAML context declaration.",
                "pending means unfinished; merged reports merge_sha; enqueued means queued, not merged. A successfully observed failed state is a successful probe observation of an unsuccessful merge, with GitHub's message preserved.",
                "Requests are retained for 24 hours. request_unavailable, including an expired or missing UUID (404), is unavailable evidence, not proof that the merge failed. Preserve uncertainty rather than blindly resubmitting.",
                "Use the request state and availability together; merged=false alone cannot distinguish pending, failed, enqueued, or unavailable evidence and is not proof of an unmerged PR. Confirm current PR completion with gh.pr when the workflow needs that fact.",
            ],
            "do_not_use_for": [
                "No polling, queue administration, admin bypass, or new submission occurs. Use gh.pr.merge only after CI acceptance and standalone scope admission; it rejects stacked and unknown scope and reuses only an exact matching existing request.",
                "The asynchronous failure message is not a structured reason code and cannot reliably establish a strict head-mismatch classification. This observation provides no atomic base or stack guarantee.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr.merge", "summary": "Submit with expected_head_sha from the accepted CI head and retain request_id"},
                {"handle": "connector.gh.pr", "summary": "Observe current PR facts rather than the saved request lifecycle"},
                {"handle": "connector.gh.pr.checks", "summary": "Inspect CI attached to head H or candidate M; candidate checks bind expected H, not M"},
            ],
            "inspect_next": ["connector.gh.pr.merge", "connector.gh.pr", "connector.gh.pr.checks"],
        },
        ("gh", "pr.timeline"): {
            "definition": "Probe one GitHub pull request timeline as normalized lifecycle events such as ready-for-review, review requests, and base-ref changes. Prefer connector_contexts.gh.repository as the normal repository target and use an explicit repository argument only as a one-off override.",
            "use_when": [
                "connector_contexts.gh.repository already names the normal repository target and the workflow needs lifecycle history there for one PR number.",
                "The workflow needs temporal PR lifecycle facts that are not equivalent to comments, checks, or the current PR snapshot alone.",
            ],
            "do_not_use_for": [
                "The current PR state only; use connector.gh.pr when timeline history is unnecessary.",
                "Top-level discussion or submitted review verdicts; use comments or reviews for those narrower surfaces.",
            ],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr", "summary": "Parent PR snapshot for the current state without event history"},
                {"handle": "connector.gh.pr.reviews", "summary": "Sibling probe for submitted review verdicts rather than timeline events"},
                {"handle": "connector.gh.pr.comments", "summary": "Sibling probe for conversation comments rather than lifecycle history"},
            ],
            "examples": [
                {"reference": "gh.pr.timeline", "inputs": {"pull_number": 42, "limit": 20}},
            ],
            "inspect_next": ["connector.gh.pr.reviews", "connector.gh.pr.comments", "connector.gh.pr"],
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
            "definition": "Start one Compose project or one declared Compose service, reconciling one transient nonzero compose start with a short post-start runtime observation window before declaring failure.",
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
        "state": {
            "definition": "Declared persistent storage for passing named values between workflow runs through bound logical roles.",
            "use_when": [
                GRAPH_GUIDANCE,
                GRAPH_PRESENTATION,
                GRAPH_SOURCE_PLACEMENT,
                GRAPH_CONTEXT_GUIDANCE,
                GRAPH_PARAMETER_GUIDANCE,
                GRAPH_ROLE_GUIDANCE,
                "A later run needs a remembered value. Declare state_needs and bind each role to a named playbook state location before access.",
                "Read through state.<role>[<key>], then use state_set or state_delete only after the final read of the same actual file, regardless of role, state name, profile, key, or field.",
                "Before binding, authoring validation retains the same-role rule. After binding, relative paths resolve in each access context; normalized paths, symlinks, and existing hardlinks can alias. The same role may access distinct files and be valid.",
                "validation.workflow.state_storage.write_before_last_read reports proven same-file violations. validation.workflow.state_storage.identity_unresolved conservatively rejects early only relevant uncertain write/later-read pairs, before observations or effects; it is not a proven violation.",
                "Top-level check checks conditions and gates first, then defers effectful mutations and continues to independent guards without mutation, simulation, outputs, registers, or reuse. Plan retains not_reusable nodes with planned_probe_result null; run executes admitted mutations once in order.",
                "Aggregate runtime.value.state_missing diagnostics group only emitted failures with the same private resolved absolute location path, text key, and field path. This conservative identity does not merge inode or symlink aliases and is not the write-order validation identity. Other errors and diagnostics without that private identity remain ungrouped.",
                "A repeated target adds occurrence_count (emitted events, not inferred reads) and reported_at (unique effective structural locations of emitted diagnostic events, not all dependent uses). Each site contains path and references: distinct expression/state pairs, with no separate workflow field. Caller prefixes locate child sites; paths are not source line numbers. Groups, sites, and references retain first-seen order. A singleton keeps existing details; a group retains the first event's details and uses the site path for one site or an empty path for multiple sites. Private target identity is not serialized.",
                "Grouping changes aggregate reporting only in check, review, plan, run, and explain: no evaluation, short-circuit, cache, status, or barrier changes, and no extra reads. Operation-result diagnostics remain unchanged; next keeps groups candidate-local without changing eligibility or selection. Existing verified snippets check authoring validation, not runtime grouping output.",
            ],
            "do_not_use_for": [
                "Passing newly computed values between steps in one run; use value + register and step.<register>.outputs.value instead.",
                "Assuming authored-order validation proves safety across loop iterations; cross-iteration state analysis remains a known verification gap.",
                "Treating uncertain context as a blanket ban: read-only, read-before-write, and known-disjoint access are not rejected for uncertainty alone. No new loop mutation ban is added.",
                "Nested deferral or full composed-run proof: a reached run/loop after deferral halts with state_deferral_invocation_barrier; profiles cannot resume it. Children validate individually, not as a flattened caller-child access stream. Cross-invocation and cross-iteration guarantees remain deferred.",
            ],
            "related_surfaces": [
                {"handle": "workflow.state_bindings", "summary": "Connect logical roles to declared storage locations"},
                {"handle": "workflow.step.state_set", "summary": "Read-before-write example with registered per-run reuse"},
                {"handle": "workflow.step.state_delete", "summary": "Read-before-delete example with registered per-run reuse"},
            ],
        },
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
        "workflow.step_forms.result": {
            "definition": "Workflow step form for one named result-emission checkpoint that appends one resolved value to the workflow's ordered result list.",
            "use_when": [
                "A step's primary job is emitting one final workflow-local result value rather than staging an intermediate reusable value or publishing an outward-facing named payload.",
            ],
            "do_not_use_for": [
                "Reusable intermediate payload staging; use workflow.step.value with register when later steps still need to read the computed value.",
                "Publishing one outward-facing named output bundle for callers; use workflow.step_forms.publish when the intent is published workflow output rather than the workflow result list.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.result", "summary": "Field that carries the value appended to the workflow result list"},
                {"handle": "workflow.step_forms.publish", "summary": "Sibling outward-output form for publishing named payloads instead of appending to the result list"},
                {"handle": "workflow.step_forms.value", "summary": "Sibling local-value form for staging ephemeral reusable data before any final emission"},
                {"handle": "workflow-rules.value_register_before_result", "summary": "Authoring rule for staging reusable payloads with value + register before emitting them through result or publish"},
            ],
            "inspect_next": ["workflow.step.result", "workflow.step_forms.publish", "workflow.step_forms.value", "workflow-rules.value_register_before_result"],
        },
        "workflow.step_forms.publish": {
            "definition": "Workflow step form for one named publish checkpoint that emits one outward-facing published output payload for the workflow.",
            "use_when": [
                "A step's primary job is communicating one caller-facing payload such as summary fields, identifiers, or URLs rather than only appending to the workflow's internal result list.",
            ],
            "do_not_use_for": [
                "Ephemeral payload staging for later steps; use workflow.step_forms.value when the value is still workflow-local and reusable before final emission.",
                "Appending one value to the workflow result list without treating it as the outward published payload surface; use workflow.step_forms.result for that narrower emission role.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.publish", "summary": "Field that carries the outward-facing payload emitted by this publish step form"},
                {"handle": "workflow.step_forms.result", "summary": "Sibling result-emission form for appending to the workflow result list instead of publishing named outward output"},
                {"handle": "workflow.step_forms.value", "summary": "Sibling local-value form for staging reusable workflow-local data before any final outward emission"},
                {"handle": "workflow-rules.publish_outputs", "summary": "Authoring rule that prefers explicit publish payloads for intentional outward-facing workflow results"},
            ],
            "inspect_next": ["workflow.step.publish", "workflow.step_forms.result", "workflow.step_forms.value", "workflow-rules.publish_outputs"],
        },
        "workflow.step_forms.operation_call": {
            "definition": "Workflow step form for one named published-operation invocation whose primary authored body is uses plus optional control, binding, and result fields.",
            "use_when": [
                "One step's main job is calling one published operation surface through uses rather than invoking a workflow fragment or repeating a short local body inline.",
            ],
            "do_not_use_for": [
                "Named workflow-fragment invocation; use workflow.step_forms.run_invocation when the callee should stay explicit as a run target.",
                "Legacy launcher-centric authoring as the preferred path; launcher remains deprecated optional compatibility metadata on this form.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.uses", "summary": "Primary field that selects the published operation surface invoked by this form"},
                {"handle": "workflow.step_forms.run_invocation", "summary": "Sibling step form for named workflow-fragment targets instead of published operations"},
                {"handle": "workflow.step.with", "summary": "Optional invocation-argument field commonly paired with uses on this form"},
            ],
            "inspect_next": ["workflow.step.uses", "workflow.step.with", "workflow.step_forms.run_invocation", "workflow.step.launcher"],
        },
        "workflow.step_forms.run_invocation": {
            "definition": "Workflow step form for one named workflow-fragment runtime invocation whose primary authored body is run plus optional caller bindings, fan-out, admission, and aggregate result fields.",
            "use_when": [
                "One step should invoke a named workflow fragment at runtime rather than call a published operation surface directly.",
                "A reusable repeated body should stay behind one named run target, optionally with bounded fan-out through for_each.",
            ],
            "do_not_use_for": [
                "Short local repeated work that is clearer as inline steps under workflow.step_forms.inline_fan_out_invocation.",
                "Source-time include expansion before validation; use include surfaces when the body should be assembled rather than invoked.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.run.run", "summary": "Primary named-target field carried by this form"},
                {"handle": "workflow.step_forms.inline_fan_out_invocation", "summary": "Sibling step form for short local repeated bodies instead of named targets"},
                {"handle": "workflow.step_forms.operation_call", "summary": "Sibling step form for published operations instead of named run targets"},
            ],
            "inspect_next": ["workflow.run.run", "workflow.run.with", "workflow.run.for_each", "workflow.step_forms.inline_fan_out_invocation"],
        },
        "workflow.step_forms.inline_fan_out_invocation": {
            "definition": "Workflow step form for one named bounded fan-out invocation whose primary authored body is for_each plus one short inline repeated steps list.",
            "use_when": [
                "A short workflow-local repeated body should run once per item without introducing a separate named run target.",
                "The repeated body is small enough to stay legible inline and does not need its own fragment-local guards or reuse identity.",
            ],
            "do_not_use_for": [
                "Large, reusable, or guard-bearing repeated bodies that deserve workflow.step_forms.run_invocation with a named target.",
                "General looping or nested repetition beyond the published bounded fan-out shape.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.run.for_each", "summary": "Primary repeated-item source field carried by this form"},
                {"handle": "workflow.run.steps", "summary": "Primary inline repeated-body field carried by this form"},
                {"handle": "workflow.step_forms.run_invocation", "summary": "Sibling step form for named targets instead of inline repeated local bodies"},
            ],
            "inspect_next": ["workflow.run.for_each", "workflow.run.steps", "workflow.step_forms.run_invocation", "workflow-rules.run_target_vs_inline_fan_out"],
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
                {"handle": "workflow-rules.representation_adapters", "summary": "Authoring guidance for when adapters are preferable to ad hoc inline shaping"},
            ],
            "inspect_next": ["workflow.local_expression.adapter_binding", "workflow.local_expression.adapter.json", "workflow-rules.representation_adapters"],
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
        "workflow.step_forms.state_delete": {
            "definition": "Workflow step form for one named state-deletion checkpoint that removes one explicit bound state target.",
            "use_when": [
                "A step's primary job is deleting durable state rather than calling an operation or only shaping ephemeral workflow data.",
            ],
            "do_not_use_for": [
                "Bundling deletion with a write or other unrelated step behavior; the public state_delete form exists for explicit durable removal.",
                "Purely local value cleanup that should not affect declared durable state storage.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.state_delete", "summary": "Field that carries the bound state target to delete"},
                {"handle": "state.workflow_surface.step_state_delete_field", "summary": "State contract surface for what the state_delete field means inside a workflow step"},
                {"handle": "workflow.step_forms.state_set", "summary": "Sibling state mutation form for explicit durable writes instead of deletion"},
            ],
            "inspect_next": ["workflow.step.state_delete", "state.workflow_surface.step_state_delete_field", "workflow.step_forms.state_set"],
        },
        "workflow.step_forms.value": {
            "definition": "Workflow step form for one named ephemeral value checkpoint that computes one workflow-local value and may optionally register it for later reuse.",
            "use_when": [
                "A step's primary job is producing one derived local value rather than calling an operation, mutating durable state, or emitting final outward contract output.",
            ],
            "do_not_use_for": [
                "Durable state writes or deletions; use state_set/state_delete forms when the intent is persistent mutation.",
                "Final publish/result emission when the step should communicate outward contract rather than stage an intermediate local value.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.value", "summary": "Field that carries the computed local value for this step form"},
                {"handle": "workflow.step.result", "summary": "Sibling field for final workflow result emission rather than local intermediate computation"},
                {"handle": "workflow.step.publish", "summary": "Sibling field for publishing outward contract data rather than staging a local step value"},
            ],
            "inspect_next": ["workflow.step.value", "workflow.step.result", "workflow.step.publish"],
        },
        "state.workflow_surface.step_state_delete_field": {
            "definition": "State workflow-surface field that marks `state_delete` as the explicit step-owned durable deletion surface inside workflow authoring.",
            "use_when": [
                "You need the contract meaning of the state_delete step field rather than only an example of removing state.",
            ],
            "do_not_use_for": [
                "Assuming durable state can be removed implicitly without the workflow's surrounding state-binding contract.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.state_delete", "summary": "Step capability for deleting one explicit bound state target"},
                {"handle": "workflow.step_forms.state_delete", "summary": "Named step form that requires state_delete as its primary field"},
                {"handle": "workflow.step.state_set", "summary": "Sibling durable state mutation capability for explicit writes instead of deletion"},
            ],
            "inspect_next": ["workflow.step.state_delete", "workflow.step_forms.state_delete", "workflow.step.state_set"],
        },
        "state.workflow_surface.state_needs_field": {
            "definition": "State workflow-surface field that marks `state_needs` as the top-level workflow contract surface for declaring durable state requirements before binding and mutation surfaces are used.",
            "use_when": [
                "You need the contract meaning of the workflow's state_needs declaration rather than only one example of a later bound state operation.",
            ],
            "do_not_use_for": [
                "Assuming a later state_set, state_delete, or state read implicitly declares workflow state requirements on its own.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.state_needs", "summary": "Workflow capability for declaring durable state requirements before binding and mutation"},
                {"handle": "workflow.state_bindings", "summary": "Capability for binding declared playbook state locations into workflow roles after state_needs exists"},
                {"handle": "playbook.states", "summary": "Playbook surface that declares the named durable state locations a workflow may later bind"},
            ],
            "inspect_next": ["workflow.state_needs", "workflow.state_bindings", "playbook.states"],
        },
        "state.workflow_surface.state_binding_field": {
            "definition": "State workflow-surface field that marks `state_bindings` as the workflow contract surface for connecting declared workflow state roles to named playbook state locations.",
            "use_when": [
                "You need the contract meaning of the workflow's state_bindings declaration rather than only one later step that reads or mutates state.",
            ],
            "do_not_use_for": [
                "Declaring state requirements in the abstract; that earlier declaration belongs to state_needs.",
                "Inventing undeclared playbook state locations on the fly; bindings connect to already-declared state catalog names.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.state_bindings", "summary": "Workflow capability for binding state roles to declared playbook locations"},
                {"handle": "workflow.state_needs", "summary": "Earlier workflow declaration of which state roles are needed before binding"},
                {"handle": "playbook.states", "summary": "Playbook catalog that declares the named durable state locations a binding may target"},
            ],
            "inspect_next": ["workflow.state_bindings", "workflow.state_needs", "playbook.states"],
        },
        "workflow.step_forms.state_set": {
            "definition": "Workflow step form for one named state-write checkpoint that stores one explicit value into one bound state target.",
            "use_when": [
                "A step's primary job is persisting one durable state update rather than calling an operation or producing only ephemeral workflow data.",
            ],
            "do_not_use_for": [
                "Bundling several state writes into one synthetic step; the public state_set form is intentionally one-target-at-a-time.",
                "Purely local value staging that should remain outside durable state surfaces.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.state_set", "summary": "Field that carries the single state target entry for this step form"},
                {"handle": "state.workflow_surface.step_state_set_field", "summary": "State contract surface for what the state_set field means inside a workflow step"},
                {"handle": "workflow.step_forms.state_delete", "summary": "Sibling state mutation form for explicit durable state deletion"},
            ],
            "inspect_next": ["workflow.step.state_set", "state.workflow_surface.step_state_set_field", "state_set.single_target_entry"],
        },
        "state.workflow_surface.step_state_set_field": {
            "definition": "State workflow-surface field that marks `state_set` as the explicit step-owned durable write surface inside workflow authoring.",
            "use_when": [
                "You need the contract meaning of the state_set step field rather than just one example of writing state.",
            ],
            "do_not_use_for": [
                "Assuming any state path write is valid without the surrounding workflow state-binding contract and single-target rule.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.state_set", "summary": "Step capability for writing one explicit value into one bound state target"},
                {"handle": "workflow.step_forms.state_set", "summary": "Named step form that requires state_set as its primary field"},
                {"handle": "state_set.single_target_entry", "summary": "Negative rule that forbids more than one target entry in a state_set step"},
            ],
            "inspect_next": ["workflow.step.state_set", "workflow.step_forms.state_set", "state_set.single_target_entry"],
        },
        "routine_contract.workflow_call_surface": {
            "definition": "Routine workflow-call surface for passing declared business args and a short explicit list of forwarded scalar context references into one routine call.",
            "use_when": [
                "A workflow step calls routine.* and must distinguish business arguments from forwarded ambient context explicitly.",
            ],
            "do_not_use_for": [
                "Broad implicit environment mirroring; routine calls forward context only through explicit env references.",
                "Treating routine call fields as ordinary workflow input declaration; this surface configures one routine invocation only.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.workflow_call.args", "summary": "Call field for declared routine business arguments"},
                {"handle": "routine_contract.workflow_call.env", "summary": "Call field for explicit forwarded scalar context references"},
                {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance for when routine.* is acceptable at all"},
            ],
            "related_examples": [
                {"reference": "with.args", "inputs": {"target": "inputs.issue_number"}},
                {"reference": "with.env", "inputs": {"refs": ["inputs.profile", "step.collect.outputs.value.path"]}},
            ],
            "inspect_next": ["routine_contract.workflow_call.args", "routine_contract.workflow_call.env", "workflow-rules.routine.*"],
        },
        "routine_contract.workflow_call.args": {
            "definition": "Routine workflow-call field for business arguments that satisfy the routine entry's declared args contract.",
            "use_when": [
                "The routine entry declares business args and the caller must supply concrete domain values to that call.",
            ],
            "do_not_use_for": [
                "Forwarding ambient caller context such as inputs.* or step outputs; use workflow_call.env for those scalar references.",
                "Declaring the routine entry's accepted arg schema; that belongs to routine_contract.entry.args on the registry side.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.workflow_call_surface", "summary": "Parent routine workflow-call surface"},
                {"handle": "routine_contract.workflow_call.env", "summary": "Sibling field for explicit forwarded scalar context references"},
                {"handle": "routine_contract.entry.args", "summary": "Registry-side declaration of which business args the routine accepts"},
            ],
            "related_examples": [
                {"reference": "with.args", "inputs": {"target": "inputs.issue_number"}},
            ],
            "inspect_next": ["routine_contract.workflow_call.env", "routine_contract.entry.args", "routine_contract.workflow_call_surface"],
        },
        "routine_contract.workflow_call.env": {
            "definition": "Routine workflow-call field for forwarding a short explicit list of scalar caller references as generated environment variables for the routine process.",
            "use_when": [
                "The routine truly needs ambient caller context and that context can be expressed as a short explicit list of scalar references.",
            ],
            "do_not_use_for": [
                "Business arguments that belong in with.args; env is for forwarded context references, not the main domain payload.",
                "Objects, arrays, or custom environment-variable naming; non-scalar forwarding errors and env names are generated mechanically.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.workflow_call_surface", "summary": "Parent routine workflow-call surface"},
                {"handle": "routine_contract.workflow_call.args", "summary": "Sibling field for declared business arguments"},
                {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that limits routine env forwarding to short explicit scalar lists"},
            ],
            "related_examples": [
                {"reference": "with.env", "inputs": {"refs": ["inputs.profile", "step.collect.outputs.value.path"]}},
            ],
            "inspect_next": ["routine_contract.workflow_call.args", "workflow-rules.routine.*", "routine_contract.workflow_call_surface"],
        },
        "routine_contract.entry.args": {
            "definition": "Routine registry-entry field for declaring which business arguments a routine accepts from workflow_call.args.",
            "use_when": [
                "A routine needs an explicit declaration of its accepted business payload instead of silently consuming arbitrary caller data.",
            ],
            "do_not_use_for": [
                "Forwarded ambient context references; those belong to workflow_call.env rather than to registry-side business arg declaration.",
                "Encoding the execution command itself; accepted business args are separate from the implementation envelope.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.workflow_call.args", "summary": "Call-side field that supplies concrete values for the declared business args"},
                {"handle": "routine_contract.entry.implementation", "summary": "Sibling registry field that defines the bounded execution envelope"},
                {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that treats routines as a narrow exception path"},
            ],
            "related_examples": [
                {"reference": "entry.args", "inputs": {"target": {"type": "string", "required": True}}},
            ],
            "inspect_next": ["routine_contract.workflow_call.args", "routine_contract.entry.implementation", "workflow-rules.routine.*"],
        },
        "routine_contract.entry.implementation": {
            "definition": "Routine registry-entry field for the bounded execution envelope that actually runs the project-local automation step.",
            "use_when": [
                "A routine entry must declare exactly how its bounded local automation is executed instead of hiding execution behavior in ambient conventions.",
            ],
            "do_not_use_for": [
                "Business semantics such as accepted args or failure class meaning; those belong to sibling registry fields.",
                "General free-form shell authoring; the implementation surface is intentionally narrow and bounded.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.implementation.argv", "summary": "Required bounded execution field that lists the concrete argv vector"},
                {"handle": "routine_contract.entry.args", "summary": "Sibling field that declares accepted business arguments"},
                {"handle": "routine_contract.entry.failure_modes", "summary": "Sibling field that declares expected failure classes for this implementation"},
            ],
            "related_examples": [
                {"reference": "entry.implementation", "inputs": {"argv": [".ordo/scripts/demo-check", "{target}"]}},
            ],
            "inspect_next": ["routine_contract.implementation.argv", "routine_contract.entry.failure_modes", "routine_contract.entry.args"],
        },
        "routine_contract.implementation.argv": {
            "definition": "Routine implementation field for the bounded argv vector that launches the local helper behind one routine entry.",
            "use_when": [
                "The routine's bounded execution step must state the exact command vector that runs the helper process.",
            ],
            "do_not_use_for": [
                "Inline shell-language authoring or broad command synthesis; argv is an explicit argument vector, not a generic script body.",
                "Routine business-argument declaration; argv consumes already-declared args rather than defining them.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.entry.implementation", "summary": "Parent implementation envelope that requires argv"},
                {"handle": "routine_contract.entry.args", "summary": "Registry-side declaration of business args that argv placeholders may consume"},
                {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that keeps routine execution bounded and exceptional"},
            ],
            "related_examples": [
                {"reference": "implementation.argv", "inputs": {"argv": [".ordo/scripts/demo-check", "{target}"]}},
            ],
            "inspect_next": ["routine_contract.entry.implementation", "routine_contract.entry.args", "workflow-rules.routine.*"],
        },
        "routine_contract.entry.failure_modes": {
            "definition": "Routine registry-entry field for declaring the expected named failure classes that this bounded local automation may report.",
            "use_when": [
                "A routine should expose reviewable failure semantics instead of collapsing every implementation problem into one opaque generic failure.",
            ],
            "do_not_use_for": [
                "Ad hoc debug notes or implementation detail dumps; failure_modes should stay as named outward-facing failure classes.",
                "Skipping failure declaration because the helper might fail unpredictably; opaque fallback becomes less reviewable without explicit failure classes.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.entry.implementation", "summary": "Sibling field that defines the bounded execution envelope whose failures are being classified"},
                {"handle": "routine_contract.entry.outputs", "summary": "Sibling outward contract field for successful routine result shape"},
                {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that treats routines as narrow, reviewable exception surfaces"},
            ],
            "related_examples": [
                {"reference": "entry.failure_modes", "inputs": {"failure_modes": ["check_failed", "helper_failed"]}},
            ],
            "inspect_next": ["routine_contract.entry.outputs", "routine_contract.entry.implementation", "workflow-rules.routine.*"],
        },
        "routine_contract.entry.kind": {
            "definition": "Routine registry-entry field for the narrow classification of a routine entry inside the routine exception surface.",
            "use_when": [
                "A routine entry needs its required kind marker so the registry records what bounded fallback shape this entry represents.",
            ],
            "do_not_use_for": [
                "Business semantics or user-facing purpose text; those belong to summary, args, outputs, and failure contract fields.",
                "Treating kind as a substitute for richer public connector modeling; routine kind still stays inside the exception-path registry.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.entry.summary", "summary": "Sibling field for the short human-facing purpose of the routine entry"},
                {"handle": "routine_contract.entry.implementation", "summary": "Sibling field for the bounded execution envelope that actually runs the helper"},
                {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that keeps routine publication narrow and exceptional"},
            ],
            "inspect_next": ["routine_contract.entry.summary", "routine_contract.entry.implementation", "workflow-rules.routine.*"],
        },
        "routine_contract.entry.summary": {
            "definition": "Routine registry-entry field for the short human-facing purpose statement that explains what one routine entry is for.",
            "use_when": [
                "A routine entry needs a concise reviewable explanation of its bounded local automation role.",
            ],
            "do_not_use_for": [
                "Full business semantics or execution details; summary should stay short and pair with args, implementation, outputs, and failure_modes.",
                "Replacing explicit output or failure contracts with prose alone.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.entry.kind", "summary": "Sibling field for the routine entry classification"},
                {"handle": "routine_contract.entry.outputs", "summary": "Sibling field for declared successful result shape"},
                {"handle": "routine_contract.entry.failure_modes", "summary": "Sibling field for declared outward-facing failure classes"},
            ],
            "inspect_next": ["routine_contract.entry.outputs", "routine_contract.entry.failure_modes", "routine_contract.entry.kind"],
        },
        "routine_contract.entry.outputs": {
            "definition": "Routine registry-entry field for declaring the successful outward result shape that the routine may return to the workflow.",
            "use_when": [
                "A routine returns structured success data and that outward contract should be reviewable instead of remaining implicit in helper behavior.",
            ],
            "do_not_use_for": [
                "Execution logs or debug-only helper chatter; outputs are the successful result contract, not generic process output.",
                "Failure classification; use failure_modes for named outward-facing failure classes.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.entry.failure_modes", "summary": "Sibling field for declared outward-facing failure classes"},
                {"handle": "routine_contract.entry.summary", "summary": "Sibling short purpose statement for the routine entry"},
                {"handle": "routine_contract.workflow_call_surface", "summary": "Call surface that feeds args and env into a routine that may later return declared outputs"},
            ],
            "inspect_next": ["routine_contract.entry.failure_modes", "routine_contract.workflow_call_surface", "routine_contract.entry.summary"],
        },
        "routine_contract.entry.log_hints": {
            "definition": "Routine registry-entry field for optional logging and observability hints that help explain helper execution without changing the business contract.",
            "use_when": [
                "A routine benefits from lightweight operator-facing log guidance beyond its summary and failure/output contracts.",
            ],
            "do_not_use_for": [
                "Business outputs or failure classes; log_hints should not become a second implicit contract surface.",
                "Replacing the required implementation or failure declaration with commentary alone.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.entry.summary", "summary": "Sibling field for the short human-facing purpose statement"},
                {"handle": "routine_contract.entry.outputs", "summary": "Sibling field for declared successful outward result shape"},
                {"handle": "routine_contract.entry.failure_modes", "summary": "Sibling field for declared failure classes"},
            ],
            "inspect_next": ["routine_contract.entry.summary", "routine_contract.entry.outputs", "routine_contract.entry.failure_modes"],
        },
        "routine_contract.routines": {
            "definition": "Routine-registry top-level field that contains the declared set of named routine entries for this project-local exception-path registry.",
            "use_when": [
                "The registry needs one top-level map of named routine entries that workflows may reference through routine.* uses surfaces.",
            ],
            "do_not_use_for": [
                "A connector family catalog or general extension registry; routines stay a bounded local exception surface.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.version", "summary": "Sibling top-level field for the routine registry schema version"},
                {"handle": "routine_contract.entry.summary", "summary": "Representative entry field inside the named routines map"},
                {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that treats the whole registry as an exception path"},
            ],
            "inspect_next": ["routine_contract.version", "routine_contract.entry.summary", "workflow-rules.routine.*"],
        },
        "routine_contract.version": {
            "definition": "Routine-registry top-level field for the schema version of the project-local routine contract document.",
            "use_when": [
                "The registry document needs an explicit contract version so tooling can validate it against the expected routine schema.",
            ],
            "do_not_use_for": [
                "Routine helper release numbering or business data versioning; this field versions the routine registry contract itself.",
            ],
            "nearest_surfaces": [
                {"handle": "routine_contract.routines", "summary": "Sibling top-level field that contains the named routine entry map"},
                {"handle": "routine_contract", "summary": "Top-level routine contract surface for the project-local registry"},
                {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance for when the routine registry should exist at all"},
            ],
            "inspect_next": ["routine_contract.routines", "routine_contract.entry.summary", "workflow-rules.routine.*"],
        },
        "workflow.inputs": {
            "definition": "Top-level workflow field for declaring the named activation inputs that the workflow may require, treat as optional, or prefill with defaults before the workflow may run.",
            "use_when": [
                "The workflow needs a declared external request shape instead of reading undeclared caller values implicitly.",
                "Plain workflows show adds top-level warnings only for required workflow declarations with coverage missing, even though those declarations are hidden from inputs. Each warning contains code discovery.workflow.input_source_missing, input, message, and hint: no workflow default, not supplied by the selected launch profile (or no profile selected), no concrete playbook binding, and no caller slot; expose a caller slot or supply a source. Optional missing declarations do not warn; warnings is omitted when none qualify. --json is unchanged. This performs no readiness or state analysis and changes none of check, review, plan, run, explain, or next.",
                "Plain output omits top-level launch_profile entirely and removes caller_slot, sources, and coverage from retained inputs; other record fields are preserved except required, which reports caller-slot obligation: true for a required slot, false for an optional slot, not workflow declaration requiredness. No optional field is added. --json keeps all fields unchanged, including original normalized required, caller_slot, the launch_profile source label and initial activation name and source, not the final bound workflow profile.",
                "Guards, steps, or result logic should be able to reference activation inputs through one explicit contract surface.",
                "Give every root input a non-blank description, including optional, defaulted, profile-supplied, and unused inputs. Review reports review.workflow.input_description_missing (warning, input_authoring; suggested_fix: add_input_description) for absent, null, empty, or whitespace-only descriptions.",
                "Inspect the main caller interface through ordo-playbook workflows show <workflow>: plain output keeps the JSON-shaped serialized envelope but filters inputs to caller_slot required or optional, hides caller_slot none, and retains inputs: {} when no caller slots exist. Use --json for the unchanged full declaration contract, including inputs not exposed to callers, sources, and coverage. Retained plain records preserve description/hint when provided and default only when declared (including null), while required reports caller-slot obligation. Static entry values appear as binding; selected profile values are not exposed. Authored source coverage is not execution readiness.",
            ],
            "do_not_use_for": [
                "Fragment-local include args; use workflow.fragment.args when the values belong only to source-time fragment reuse.",
                "Playbook entry-owned static launch inputs; use playbook.workflows.with when the values belong to one named launch entry rather than to the workflow contract itself.",
                "Treating documentation warnings as activation errors or as missing-validation advice. These advisories leave check, plan, run, explain, and next unchanged; available static findings remain visible even when review_status is unavailable.",
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
                "You need to understand what declaring workflow inputs means at activation time, including per-input required/default rules and unknown-input rejection.",
                "Plain workflows show adds top-level warnings only when a required workflow declaration has coverage missing, using declaration requiredness rather than displayed caller-slot requiredness. Each warning contains code discovery.workflow.input_source_missing, input, message, and hint: no workflow default, not supplied by the selected launch profile (or no profile selected), no concrete playbook binding, and no caller slot; expose a caller slot or supply a source. Optional missing declarations do not warn; warnings is omitted when none qualify. Filtering and --json remain unchanged. This is source discovery with no readiness or state analysis; all six runtime modes are unchanged.",
                "Plain output omits top-level launch_profile entirely and removes caller_slot, sources, and coverage from retained inputs; other record fields are preserved except required, which reports caller-slot obligation: true for a required slot, false for an optional slot, not workflow declaration requiredness. No optional field is added. --json keeps all fields unchanged, including original normalized required, caller_slot, the launch_profile source label and initial activation name and source, not the final bound workflow profile.",
                "Document every root declaration with a non-blank description. Review warns with review.workflow.input_description_missing (input_authoring; add_input_description) for absent, null, empty, or whitespace-only descriptions, independently of required/default rules or whether the input is used.",
                "workflows show <workflow> presents the main caller interface: plain output keeps the JSON-shaped serialized envelope but filters inputs to caller_slot required or optional, hides caller_slot none, and retains inputs: {} when no caller slots exist. --json retains the unchanged full declaration contract in one inputs mapping: description/hint when provided, normalized required, caller_slot (required/optional/none), sources (workflow_default/launch_profile/entry_binding), coverage (provided/caller_slot/missing), default only when declared including null, and binding only for a static entry value. Filtering uses caller_slot, not declaration requiredness or coverage. Profile values stay private. Source presence is not readiness; required caller slots still require caller input, and CLI overrides or runtime profile switches do not count as authored sources.",
            ],
            "do_not_use_for": [
                "Assuming undeclared caller keys are tolerated; unknown activation inputs are rejected by contract.",
                "Treating input declaration as sufficient validation guidance; authoring still needs explicit input validation guards when semantics require them.",
                "Treating input_authoring warnings as new activation requirements: existing errors and check, plan, run, explain, and next semantics are unchanged. Available static findings survive review_status unavailable.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.inputs", "summary": "Top-level field that declares the workflow activation-input catalog"},
                {"handle": "workflow-rules.input_validation_default", "summary": "Authoring guidance for validating newly introduced or changed workflow inputs"},
                {"handle": "command-line.ordo-playbook.flag.input", "summary": "Launch-time surface that supplies one concrete value for a declared workflow input"},
            ],
            "inspect_next": ["workflow.inputs", "workflow-rules.input_validation_default", "command-line.ordo-playbook.flag.input"],
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
                {"handle": "workflow-rules.workflow_profile_binding_is_project_local", "summary": "Authoring guidance that explains why workflow.profile is intentionally restrictive"},
                {"handle": "profile", "summary": "Profile contract surface for declared execution-context data that a binding selects"},
            ],
            "inspect_next": ["workflow.step.profile_switch", "workflow-rules.workflow_profile_binding_is_project_local", "profile"],
        },
        "workflow.version": {
            "definition": "Required top-level workflow format marker that declares which published workflow document shape this file is written against.",
            "use_when": [
                "Every workflow document must start by declaring the required published workflow format version before workflow, inputs, blocks, or other top-level workflow fields.",
            ],
            "do_not_use_for": [
                "Publishing a domain, release, or business-process version for the workflow itself; this field is only the workflow document-format marker.",
                "Declaring playbook or routine registry document formats; use playbook.version or routine_contract.version for those separate documents.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.version", "summary": "Required version marker for one playbook launch-catalog document rather than for one workflow file"},
                {"handle": "routine_contract.version", "summary": "Required version marker for the routine registry document"},
                {"handle": "workflow.workflow", "summary": "The top-level workflow identity field that the version marker makes safe to interpret"},
            ],
            "examples": [
                {"reference": "workflow.version", "inputs": {"version": 0}},
            ],
            "inspect_next": ["workflow.workflow", "playbook.version", "routine_contract.version"],
        },
        "workflow.workflow": {
            "definition": "Required top-level workflow identity field that declares the stable authored name of the workflow contract in this document.",
            "use_when": [
                "Every workflow document must publish the stable workflow name that diagnostics, explain/check surfaces, and launch wrappers refer to when identifying this contract.",
            ],
            "do_not_use_for": [
                "Naming one playbook entry, profile, or human-facing description; this field is the workflow document's own contract identity.",
                "Selecting a different workflow to run from inside this document; that belongs to playbook launch surfaces or runtime invocation surfaces, not to the top-level workflow name field.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.workflows.file", "summary": "Playbook workflow-entry field that points one launch entry at a workflow file rather than naming the workflow contract inside that file"},
                {"handle": "profile.name", "summary": "Profile document identity field for execution context, distinct from the workflow contract name"},
                {"handle": "workflow.version", "summary": "Top-level workflow format marker that makes the named workflow contract safe to interpret"},
            ],
            "examples": [
                {"reference": "workflow.workflow", "inputs": {"workflow": "set-active-task"}},
            ],
            "inspect_next": ["workflow.version", "playbook.workflows.file", "profile.name"],
        },
        "profile.inputs": {
            "definition": "Profile field for declaring default values for workflow-declared inputs when the caller did not supply those inputs explicitly.",
            "use_when": [
                "Several runs under one profile should reuse the same declared workflow input defaults without copying them into every playbook entry or command invocation.",
                "One execution mode such as review or backend should supply stable fallback input values while still allowing explicit caller overrides.",
            ],
            "do_not_use_for": [
                "Undeclared workflow inputs or arbitrary profile-local scratch data; this field only supplies values for workflow-declared activation inputs.",
                "Forcing one value even when the caller or playbook workflow entry already supplied it; profile.inputs is a missing-input default surface, not an unconditional override.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.inputs_contract", "summary": "Workflow contract that declares which activation inputs may be supplied or required"},
                {"handle": "playbook.workflows.with", "summary": "Playbook workflow-entry field for entry-owned launch inputs rather than reusable profile defaults"},
                {"handle": "profile.overrides", "summary": "Profile metadata records that do not feed workflow activation inputs directly"},
            ],
            "effects": [
                "profile-owned values fill only missing declared workflow inputs during activation",
                "explicit caller inputs and playbook entry-owned inputs remain higher-precedence than profile defaults",
            ],
            "examples": [
                {
                    "reference": "profile.inputs",
                    "inputs": {
                        "command": ".venv/bin/python -m unittest discover -s tests",
                        "issue": "kergma-lw/ordo-cli#1",
                    },
                }
            ],
            "inspect_next": ["workflow.inputs_contract", "playbook.workflows.with", "playbook.defaults.profile"],
        },
        "profile.working_directory": {
            "definition": "Profile field for declaring one reusable execution working-directory context that becomes active when this profile is selected.",
            "use_when": [
                "Several runs under one profile should execute from the same repository-relative directory without repeating that directory in every playbook workflow entry.",
                "One profile should derive its execution directory from activation inputs such as inputs.repo_dir while still remaining reusable across workflows.",
            ],
            "do_not_use_for": [
                "Per-workflow-entry directory overrides; use playbook.workflows.working_directory when one published workflow entry needs a narrower directory choice.",
                "Arbitrary runtime expressions over step or state data; this activation-time field only allows ${...} expressions rooted in inputs.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.defaults.working_directory", "summary": "Playbook-wide soft default execution directory when no profile-specific directory is needed"},
                {"handle": "playbook.workflows.working_directory", "summary": "Per-workflow-entry execution directory override that is narrower than one reusable profile context"},
                {"handle": "profile.inputs", "summary": "Profile-owned input defaults that may feed the working_directory expression through inputs.* values"},
            ],
            "effects": [
                "the resolved directory becomes the activated execution cwd for runs under this profile when no narrower workflow-entry override wins",
                "working_directory expressions resolve relative to the playbook directory and may read only inputs.* roots",
            ],
            "examples": [
                {
                    "reference": "profile.working_directory",
                    "inputs": {"working_directory": "${inputs.repo_dir}"},
                }
            ],
            "inspect_next": ["playbook.defaults.working_directory", "playbook.workflows.working_directory", "profile.inputs"],
        },
        "profile.overrides": {
            "definition": "Profile field for publishing one or more explicit override records, each with a consumer-owned target plus optional payload and reason text.",
            "use_when": [
                "Several runs under one profile should expose the same project-local adaptation metadata without pretending that the profile silently rewrites workflow behavior.",
                "A known consumer, compatibility seam, or local convention already understands one named override target and should read a stable record from the active profile.",
            ],
            "do_not_use_for": [
                "Workflow inputs, guards, or step branching that should be authored on the workflow or playbook surfaces that actually drive runtime behavior.",
                "Assuming the engine will infer behavior from the payload automatically; overrides are published metadata, not implicit workflow mutation.",
            ],
            "nearest_surfaces": [
                {"handle": "profile.inputs", "summary": "Profile field for missing-input defaults that do affect workflow activation data"},
                {"handle": "profile.overrides.target", "summary": "Required child field that names which consumer-owned override slot this record is for"},
                {"handle": "workflow.profile", "summary": "Workflow-owned fixed profile binding rather than profile-scoped adaptation metadata"},
            ],
            "fields": [
                {"name": "target", "type": "string", "required": True, "role": "consumer_owned_override_key"},
                {"name": "with", "type": "object", "required": False, "role": "opaque_override_payload"},
                {"name": "reason", "type": "string", "required": False, "role": "human_readable_override_explanation"},
            ],
            "effects": [
                "each active profile may publish at most one override record per target",
                "the override payload is preserved as published metadata rather than interpreted as workflow logic by the engine",
            ],
            "examples": [
                {
                    "reference": "profile.overrides",
                    "inputs": {
                        "overrides": [
                            {
                                "target": "local.issue-triage",
                                "with": {"default_label": "bug", "board": "intake"},
                                "reason": "Share one profile-scoped triage adaptation record.",
                            }
                        ]
                    },
                }
            ],
            "inspect_next": ["profile.overrides.target", "profile.overrides.with", "profile.overrides.reason"],
        },
        "profile.overrides.target": {
            "definition": "Required override field that names the consumer-owned target key for one override record.",
            "use_when": [
                "One consumer or local convention expects a stable target name so it can pick the right override record from the active profile.",
            ],
            "do_not_use_for": [
                "Workflow input names or connector context fields; this key selects one override record, not ordinary workflow data.",
            ],
            "nearest_surfaces": [
                {"handle": "profile.overrides", "summary": "Parent profile field that collects the override records"},
                {"handle": "profile.overrides.with", "summary": "Sibling field that carries the payload for the named target"},
                {"handle": "profile.overrides.reason", "summary": "Sibling field that explains why this target-specific record exists"},
            ],
            "effects": [
                "duplicate target names conflict when profiles are composed or when one profile repeats the same target",
            ],
            "inspect_next": ["profile.overrides.with", "profile.overrides.reason", "profile.overrides"],
        },
        "profile.overrides.with": {
            "definition": "Optional override field for the opaque object payload that a target-specific consumer may interpret.",
            "use_when": [
                "The named override target needs structured profile-scoped data in addition to the target key itself.",
            ],
            "do_not_use_for": [
                "Fields that the engine should validate as first-class workflow or playbook contract data; this payload is consumer-owned metadata.",
                "Free-form text explanation; use profile.overrides.reason for the human-facing why.",
            ],
            "nearest_surfaces": [
                {"handle": "profile.overrides", "summary": "Parent profile field that publishes override records"},
                {"handle": "profile.overrides.target", "summary": "Sibling field that names which consumer should read this payload"},
                {"handle": "profile.inputs", "summary": "Profile-owned input defaults that do change workflow activation data"},
            ],
            "effects": [
                "the engine preserves this object verbatim instead of interpreting its keys as built-in behavior",
            ],
            "inspect_next": ["profile.overrides.reason", "profile.overrides.target", "profile.overrides"],
        },
        "profile.overrides.reason": {
            "definition": "Optional override field for one short human-readable explanation of why the target-specific override record exists.",
            "use_when": [
                "Later readers would benefit from a short intent note instead of reverse-engineering the payload alone.",
            ],
            "do_not_use_for": [
                "Machine-readable override data that belongs in profile.overrides.with.",
                "The required target identifier itself; use profile.overrides.target for that.",
            ],
            "nearest_surfaces": [
                {"handle": "profile.overrides", "summary": "Parent profile field that groups the override record"},
                {"handle": "profile.overrides.target", "summary": "Sibling field that names the override target"},
                {"handle": "profile.overrides.with", "summary": "Sibling field that carries the target-specific object payload"},
            ],
            "effects": [
                "reason text is optional but, when present, must stay a non-empty string",
            ],
            "inspect_next": ["profile.overrides.with", "profile.overrides.target", "profile.overrides"],
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
        "playbook.workflows": {
            "definition": "Playbook field for publishing the named workflow catalog that `ordo-playbook` can list, inspect, and activate by workflow name.",
            "use_when": [
                "The project needs one stable launch catalog that maps public workflow names to workflow files plus entry-owned launch metadata.",
                "Plain workflows show adds top-level warnings only for required workflow declarations with coverage missing; these declarations remain hidden from inputs. Each warning contains code discovery.workflow.input_source_missing, input, message, and hint: no workflow default, not supplied by the selected launch profile (or no profile selected), no concrete playbook binding, and no caller slot; expose a caller slot or supply a source. Optional missing declarations do not warn; warnings is omitted when none qualify. --json is unchanged. No readiness or state analysis is added; check, review, plan, run, explain, and next are unchanged.",
                "Each published workflow should carry operator-facing discovery hints such as description, category, when, working_directory, with, or state_bindings at the playbook layer.",
                "workflows show <workflow> presents the main caller interface: plain output keeps the JSON-shaped serialized envelope but filters inputs to caller_slot required or optional, hides caller_slot none, and retains inputs: {} when no caller slots exist. Plain output omits top-level launch_profile entirely and removes caller_slot, sources, and coverage from retained inputs; other record fields are preserved except required, which reports caller-slot obligation: true for a required slot, false for an optional slot, not workflow declaration requiredness. No optional field is added. --json retains the unchanged full declaration contract with all input fields, including original normalized required and caller_slot, and top-level launch_profile: the initial activation name and source, not the final bound workflow profile (default or explicit_cli source, both null when absent). JSON input sources still include launch_profile where present, without exposing profile values. Use command-line.ordo-playbook for the complete output contract; show does not activate the workflow or prove readiness.",
            ],
            "do_not_use_for": [
                "Workflow-internal guards, steps, branching, or dataflow; those belong inside the workflow file selected by the entry.",
                "Bootstrap workflows that must always run before the requested workflow; use playbook.pre_run for that separate launch stage.",
            ],
            "nearest_surfaces": [
                {"handle": "command-line.ordo-playbook", "summary": "Public command surface that lists and launches one named playbook workflow entry"},
                {"handle": "playbook.pre_run", "summary": "Sibling playbook surface for shared launch-time preparation before the requested workflow entry"},
                {"handle": "playbook.workflows.file", "summary": "Required child field that binds each published workflow name to one workflow file"},
            ],
            "required_fields": ["file"],
            "optional_fields": ["with", "description", "category", "when", "working_directory", "state_bindings"],
            "related_examples": [
                {"reference": "examples.playbook-workflows", "inputs": {}},
                {"reference": "playbook.workflows", "inputs": {"remember-profile": {"file": "./playbook-workflow-target.yaml", "description": "Read one remembered profile from shared state", "category": "inspect", "when": "Use when you need one state-backed profile lookup before choosing the next workflow.", "with": {"active_profile_key": "active_profile", "repo_dir": "."}, "working_directory": "${inputs.repo_dir}", "state_bindings": {"shared_state": "shared_state"}}}},
            ],
            "inspect_next": ["command-line.ordo-playbook", "playbook.workflows.file", "playbook.workflows.with", "playbook.workflows.when"],
        },
        "playbook.workflows.file": {
            "definition": "Workflow-entry field that points one published playbook workflow name at the workflow file to load when that entry is selected.",
            "use_when": [
                "A named playbook workflow entry should resolve to one concrete workflow document at activation time.",
            ],
            "do_not_use_for": [
                "Selecting the active workflow at the command line; callers choose the workflow name through ordo-playbook commands, not by editing this field per run.",
                "Profile file selection or pre_run workflow selection; use playbook.profiles.file or playbook.pre_run.file for those sibling catalogs.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.workflows", "summary": "Parent catalog that publishes named workflow entries"},
                {"handle": "playbook.pre_run.file", "summary": "Sibling field for the bootstrap workflow that runs before the requested entry"},
                {"handle": "playbook.profiles.file", "summary": "Sibling field that points at a profile file instead of a workflow file"},
            ],
            "related_examples": [
                {"reference": "playbook.workflows.file", "inputs": {"file": "./playbook-workflow-target.yaml"}},
            ],
            "inspect_next": ["playbook.workflows.with", "playbook.pre_run.file", "playbook.profiles.file"],
        },
        "playbook.workflows.with": {
            "definition": "Workflow-entry field for playbook-owned launch inputs that feed one published workflow entry before any one-run caller overrides are applied, including required and optional caller-slot placeholders.",
            "use_when": [
                "One published workflow should always receive fixed entry-owned input values, should require some caller-provided keys through `key:`, or should allow optional caller-provided keys through `key?:`.",
                "The values belong to the launch catalog entry rather than to the reusable workflow contract or to one operator invocation only.",
                "Plain workflows show adds top-level warnings only for required workflow declarations with coverage missing. Each warning contains code discovery.workflow.input_source_missing, input, message, and hint: no workflow default, not supplied by the selected launch profile (or no profile selected), no concrete playbook binding, and no caller slot; expose a caller slot or supply a source. Either caller-slot form or any present source suppresses this warning. Optional missing declarations do not warn, unlike the broader review advisory; warnings is omitted when none qualify. Plain inputs filtering and --json remain unchanged. No readiness or state analysis is performed; all six runtime modes are unchanged.",
                "Plain output omits top-level launch_profile entirely and removes caller_slot, sources, and coverage from retained inputs; other record fields are preserved except required, which reports caller-slot obligation: true for a required slot, false for an optional slot, not workflow declaration requiredness. No optional field is added. --json keeps all fields unchanged, including original normalized required, caller_slot, the launch_profile source label and initial activation name and source, not the final bound workflow profile.",
                "Expose every declared input with no default, selected launch-profile input, or concrete entry binding through a caller slot. Review reports review.playbook.input_caller_slot_missing (warning, input_authoring; suggested_fix: expose_caller_input), suggesting x: for required inputs and x?: for optional inputs, including unused declarations.",
                "A default or supplied key counts even when null, false, or zero; only the selected launch profile counts. Either caller-slot form suppresses the advisory. CLI --input and --input-file overrides do not suppress it. Available static findings survive review_status unavailable without replacing activation errors.",
                "workflows show <workflow> presents the main caller interface: plain output keeps the JSON-shaped serialized envelope but filters inputs to caller_slot required or optional, hides caller_slot none, and retains inputs: {} when no caller slots exist. --json retains the unchanged full declaration contract using the same source-presence rule as review: each declared input reports caller_slot (required/optional/none), sources (workflow_default/launch_profile/entry_binding), and coverage (provided if any source exists, otherwise caller_slot if exposed, otherwise missing). Caller slots remain visible even with provided coverage; concrete bindings without slots are hidden only in plain inputs. binding shows only a concrete static entry value; profile values remain private. Runtime profile switches do not count as launch sources, and provided coverage never waives a required caller slot.",
            ],
            "do_not_use_for": [
                "Declaring which inputs exist at all; use workflow.inputs for the workflow's activation contract.",
                "Per-run operator overrides; use command-line.ordo-playbook.flag.input or command-line.ordo-playbook.flag.input_file when the caller should supply the value at launch time.",
                "Relaxing activation requirements: x: still requires explicit caller input even with a default, and x?: does not make a required workflow input optional. These warnings do not change check, plan, run, explain, or next.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.inputs", "summary": "Workflow-owned declaration of which activation inputs are valid"},
                {"handle": "playbook.pre_run.with", "summary": "Sibling input surface for playbook-owned pre_run setup rather than for the requested workflow entry"},
                {"handle": "command-line.ordo-playbook.flag.input", "summary": "One-run caller override that can replace entry-owned input values"},
            ],
            "related_examples": [
                {"reference": "playbook.workflows.with", "inputs": {"active_profile_key": "active_profile", "repo_dir": ".", "issue_number": "caller_required", "close_comment": "caller_optional"}},
            ],
            "inspect_next": ["workflow.inputs", "playbook.pre_run.with", "command-line.ordo-playbook.flag.input"],
        },
        "playbook.workflows.description": {
            "definition": "Workflow-entry field for the short human-facing summary that explains what one published workflow does in the catalog listing.",
            "use_when": [
                "Operators need a quick one-line explanation before deciding whether this published workflow entry is the right launch choice.",
            ],
            "do_not_use_for": [
                "Step-by-step operator guidance or applicability advice; use playbook.workflows.when when the user also needs selection guidance.",
                "Replacing the actual workflow contract or launch metadata with prose alone.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.workflows.when", "summary": "Sibling field for operator-facing selection guidance rather than a short summary"},
                {"handle": "playbook.workflows.category", "summary": "Sibling field for grouping entries in catalog output"},
                {"handle": "playbook.workflows", "summary": "Parent catalog surface that publishes the named workflow entry"},
            ],
            "related_examples": [
                {"reference": "playbook.workflows.description", "inputs": {"description": "Read one remembered profile from shared state"}},
            ],
            "inspect_next": ["playbook.workflows.when", "playbook.workflows.category", "command-line.ordo-playbook"],
        },
        "playbook.workflows.category": {
            "definition": "Workflow-entry field for the lightweight catalog group label that helps cluster related published workflows in discovery output.",
            "use_when": [
                "Several published workflows belong to the same operator-facing family such as inspect, lifecycle, or collaboration, and the catalog should show that grouping explicitly.",
                "For graph display ties within a category, preserve authored playbook entry order. Dependency placement takes precedence. Category never creates graph links or execution precedence. Standalone alternatives use compatible authored-order positions around intact source/reader blocks; conflicting category bounds never split those blocks.",
            ],
            "do_not_use_for": [
                "Encoding workflow applicability, permissions, or step behavior; category is discovery metadata only and has no runtime effect.",
                "Replacing the entry summary or selection guidance; pair category with description and when when the grouping label alone would be too vague.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.workflows.description", "summary": "Sibling field that explains what the entry does in one short sentence"},
                {"handle": "playbook.workflows.when", "summary": "Sibling field that explains when an operator should choose this entry"},
                {"handle": "playbook.workflows", "summary": "Parent workflow catalog that publishes grouped entries"},
            ],
            "related_examples": [
                {"reference": "playbook.workflows.category", "inputs": {"category": "inspect"}},
            ],
            "inspect_next": ["playbook.workflows.description", "playbook.workflows.when", "command-line.ordo-playbook"],
        },
        "playbook.workflows.when": {
            "definition": "Workflow-entry field for the operator-facing selection hint that explains when this published workflow is the right one to run.",
            "use_when": [
                "A short summary is not enough and the catalog should also teach the decision context for choosing this workflow entry.",
            ],
            "do_not_use_for": [
                "Workflow guards or machine-enforced applicability; when is guidance for humans, not a runtime rule surface.",
                "Category-style grouping labels or terse one-line summaries; keep those in category and description.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.workflows.description", "summary": "Sibling summary field for what the entry does"},
                {"handle": "playbook.workflows.category", "summary": "Sibling grouping label for the catalog family"},
                {"handle": "command-line.ordo-playbook", "summary": "Command surface that presents the workflow catalog to operators"},
            ],
            "related_examples": [
                {"reference": "playbook.workflows.when", "inputs": {"when": "Use when you need one state-backed profile lookup before choosing the next workflow."}},
            ],
            "inspect_next": ["playbook.workflows.description", "command-line.ordo-playbook", "workflow-rules.early_guards"],
        },
        "playbook.workflows.working_directory": {
            "definition": "Workflow-entry field for overriding the execution working directory of one published workflow entry before the workflow starts running.",
            "use_when": [
                "One published workflow should resolve relative files from a narrower directory than the playbook-wide or profile-wide default.",
                "The chosen directory depends only on activation inputs and should be computed before any workflow steps execute.",
            ],
            "do_not_use_for": [
                "Step-local directory changes after the workflow has already started; keep that behavior in a narrower execution surface instead of the playbook entry.",
                "Reading step outputs or state to decide the directory; this launch-time field only allows activation-input expressions.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.defaults.working_directory", "summary": "Playbook-wide soft default directory when no entry override is needed"},
                {"handle": "profile.working_directory", "summary": "Reusable profile-owned execution directory context"},
                {"handle": "playbook.workflows.with", "summary": "Sibling entry-owned launch inputs that may supply activation values referenced by the directory expression"},
            ],
            "related_examples": [
                {"reference": "playbook.workflows.working_directory", "inputs": {"working_directory": "${inputs.repo_dir}"}},
            ],
            "inspect_next": ["playbook.defaults.working_directory", "profile.working_directory", "playbook.workflows.with"],
        },
        "playbook.workflows.state_bindings": {
            "definition": "Workflow-entry field for binding the requested workflow's declared state roles to named playbook state locations at launch time.",
            "use_when": [
                "One published workflow needs explicit durable state access and that binding should be owned by the catalog entry rather than repeated by the caller.",
            ],
            "do_not_use_for": [
                "Declaring which state roles the workflow itself needs; use workflow.state_needs for that workflow contract.",
                "Binding state only for bootstrap preparation; use playbook.pre_run.state_bindings when the binding belongs to pre_run instead of the requested workflow entry.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.state_bindings", "summary": "Workflow capability surface for what one state-role binding means inside authored workflow source"},
                {"handle": "playbook.pre_run.state_bindings", "summary": "Sibling binding surface scoped only to pre_run setup"},
                {"handle": "playbook.states", "summary": "Catalog of declared state locations that entry bindings may target by name"},
            ],
            "related_examples": [
                {"reference": "playbook.workflows.state_bindings", "inputs": {"shared_state": "shared_state"}},
            ],
            "inspect_next": ["workflow.state_bindings", "playbook.pre_run.state_bindings", "playbook.states"],
        },
        "playbook.pre_run": {
            "definition": "Playbook field for declaring one or more playbook-owned workflows that run before the requested published workflow in the same runtime session.",
            "use_when": [
                "The project needs shared launch-time preparation, validation, or state setup before whichever published workflow the caller selected.",
                "The setup may consult remembered state or other soft launch context, while the caller's explicit --profile choice still remains authoritative for that run.",
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
        "profile.name": {
            "definition": "Required profile field that declares the profile document's own stable internal name for selection, diagnostics, and composition.",
            "use_when": [
                "Every profile document must publish the stable name that playbook profile entries, defaults, and runtime diagnostics refer to.",
            ],
            "do_not_use_for": [
                "Choosing which profile should win for one run; use playbook.defaults.profile, workflow.profile, or the command-line profile selector for activation decisions.",
                "Publishing a human-friendly label unrelated to runtime identity; this field is the profile's declared contract name.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.defaults.profile", "summary": "Playbook field that chooses one declared profile name as the soft default activation choice"},
                {"handle": "command-line.ordo-playbook.flag.profile", "summary": "Launch-time selector that chooses which declared profile name to activate for one invocation"},
                {"handle": "workflow.profile", "summary": "Workflow-owned fixed binding to one declared profile name before guards run"},
            ],
            "effects": [
                "the declared name becomes the stable identity that profile selection and diagnostics use",
                "the profile document must expose exactly one non-empty string name",
            ],
            "examples": [
                {"reference": "profile.name", "inputs": {"name": "read-only-review"}},
            ],
            "inspect_next": ["playbook.defaults.profile", "command-line.ordo-playbook.flag.profile", "workflow.profile"],
        },
        "profile.checks": {
            "definition": "Profile field for publishing one or more named review or verification labels that describe the expected checking posture of this profile.",
            "use_when": [
                "A profile should publish its intended review or verification posture, such as review, unit, or contract, as reusable launch metadata.",
                "Several workflows under one profile share the same checking expectations and readers should see that posture without reverse-engineering workflow bodies.",
            ],
            "do_not_use_for": [
                "Workflow applicability logic or engine-enforced guard behavior; use workflow guards, check, and review surfaces for executable validation semantics.",
                "Pretending the engine will automatically run those named checks merely because the labels are present; this field publishes metadata rather than imperative execution steps.",
            ],
            "nearest_surfaces": [
                {"handle": "profile.overrides", "summary": "Other published profile metadata that later readers may inspect without changing workflow execution semantics directly"},
                {"handle": "workflow-rules.paired_check_review_passes", "summary": "Authoring guidance for the real check/review execution loop rather than profile metadata labels"},
                {"handle": "command-line.ordo-playbook", "summary": "Command surface that actually launches workflows instead of merely publishing profile metadata"},
            ],
            "effects": [
                "named checks are published as profile metadata and remain available to readers, reviewers, or local conventions",
                "the engine does not treat the labels themselves as an automatic execution plan",
            ],
            "examples": [
                {"reference": "profile.checks", "inputs": {"checks": ["unit", "contract"]}},
            ],
            "inspect_next": ["workflow-rules.paired_check_review_passes", "profile.overrides", "command-line.ordo-playbook"],
        },
        "profile.launchers": {
            "definition": "Deprecated profile field for publishing profile-scoped launcher records that older workflows may still reference through workflow.step.launcher.",
            "use_when": [
                "You are maintaining existing launcher-based profile metadata and need to understand or document what one legacy profile publishes today.",
                "A project still has older launcher references and needs a migration-aware surface that points readers toward the preferred routines alternative.",
            ],
            "do_not_use_for": [
                "New workflow authoring when published routines or explicit profile context can express the execution setup more honestly.",
                "Assuming launcher records are the preferred long-term execution-context surface; this field is deprecated and retained mainly for compatibility.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.step.launcher", "summary": "Workflow step field that consumes one named launcher record when older workflows still use launcher-based execution setup"},
                {"handle": "routines", "summary": "Preferred bounded local-automation alternative for new work instead of growing launcher usage"},
                {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance that explains when routines are acceptable as the preferred replacement path"},
            ],
            "fields": [
                {"name": "file", "type": "string", "required": False, "role": "launcher_definition_file"},
                {"name": "connector", "type": "string", "required": False, "role": "legacy_connector_name"},
                {"name": "before", "type": "string", "required": False, "role": "pre_step_shell_hook"},
                {"name": "after", "type": "string", "required": False, "role": "post_step_shell_hook"},
            ],
            "effects": [
                "launcher records are published as profile-scoped compatibility metadata for workflows that still reference them",
                "launcher composition uses first-writer-wins conflict rules and remains deprecated across profile composition",
            ],
            "examples": [
                {"reference": "profile.launchers", "inputs": {"shell_frontend": {"file": "../launchers/shell-frontend.yaml"}}},
            ],
            "inspect_next": ["workflow.step.launcher", "routines", "workflow-rules.routine.*"],
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
        "playbook.version": {
            "definition": "Required top-level playbook format marker that declares which published playbook document shape this file is written against.",
            "use_when": [
                "Every playbook document must start by declaring the required published playbook format version before launch-catalog fields such as states, workflows, or profiles.",
            ],
            "do_not_use_for": [
                "Publishing your repository, release, or product version; this field is only the playbook document-format marker.",
                "Declaring workflow or routine document format versions; use workflow.version or routine_contract.version inside those separate documents.",
            ],
            "nearest_surfaces": [
                {"handle": "workflow.version", "summary": "Required version marker for one workflow document rather than for the playbook catalog"},
                {"handle": "routine_contract.version", "summary": "Required version marker for the routine registry document"},
                {"handle": "playbook.workflows", "summary": "The main playbook catalog field that the version marker makes safe to interpret"},
            ],
            "examples": [
                {"reference": "playbook.version", "inputs": {"version": 1}},
            ],
            "inspect_next": ["playbook.workflows", "workflow.version", "routine_contract.version"],
        },
        "profile.connectors": {
            "definition": "Profile-scoped connector bootstrap field for declaring connector context that applies only when this profile is active.",
            "use_when": [
                "Several runs under one profile need the same connector context, such as Compose directory/file/project settings, without repeating it in every workflow call.",
                "One profile should narrow or override broader playbook connector defaults for a specific execution mode such as review, backend, or deployment work.",
            ],
            "do_not_use_for": [
                "Repository-wide connector defaults that should apply before profile selection; use playbook.connectors for that broader launch scope.",
                "Publishing connector operations themselves; use connector.* handles to learn the public operation surface.",
                "Workflow business inputs that belong in declared workflow inputs rather than connector bootstrap context.",
            ],
            "nearest_surfaces": [
                {"handle": "playbook.connectors", "summary": "Playbook-level connector context that provides broader defaults before profile-specific narrowing or overrides"},
                {"handle": "connector.compose", "summary": "One connector family that reads concrete context fields such as directory, file, and project_name"},
                {"handle": "profile.inputs", "summary": "Profile-owned workflow input defaults, which are different from connector bootstrap context"},
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
            "inspect_next": ["playbook.connectors", "connector.compose", "profile.inputs"],
        },
        "playbook.connectors": {
            "definition": "Playbook top-level field for declaring repository-wide default connector bootstrap context before profile-specific overrides apply.",
            "use_when": [
                "One repository-wide connector context default should apply before any profile-specific connector overrides are considered.",
                "Several published workflows should inherit the same connector bootstrap values without repeating them in each workflow entry.",
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
            "inspect_next": ["profile.connectors", "connector.compose", "playbook.workflows"],
        },
    }

    def add_node(name: str, *, contract: str, node_category: str, summary: str, metadata: JSONObject) -> None:
        snippet_surface = context.snippet_surface(name)
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

    add_node(
        "connector.authoring", contract="connector", node_category="sdk",
        summary="Connector-author SDK dependency calls with already-resolved probe inputs",
        metadata={
            "definition": "Connector-author SDK surface for explicit same-family operation dependencies through ctx.call(name, *, inputs=None).",
            "use_when": [SDK_CALL_GUIDANCE, "A connector probe or action needs a published same-family read-only observation with concrete values, such as gh.pr.create's gh.pr.list precheck."],
            "do_not_use_for": ["Cross-family calls, probe-to-action hidden mutation, or new action composition.", "Workflow expressions, template reevaluation, workflow orchestration, or runtime mode selection inside a handler."],
            "nearest_surfaces": [
                {"handle": "connector.gh.pr.create", "summary": "Action consumer of an explicit resolved-input probe dependency"},
                {"handle": "connector.gh.pr.list", "summary": "Read-only dependency with full traversal semantics"},
                {"handle": "workflow.step.uses", "summary": "Workflow-level invocation rather than Python SDK dependency reuse"},
            ],
            "inspect_next": ["connector.gh.pr.create", "connector.gh.pr.list", "workflow.step.uses"],
        },
    )

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
        if filter_name == "catch":
            filter_metadata.update(
                {
                    "definition": "Pipeline-style local-expression filter `catch(...)` for replacing one explicit set of upstream failure codes with one authored fallback value while preserving unmatched failures.",
                    "use_when": [
                        "One strict probe or adapter lookup should stay strict by default, but one specific failure code or wildcarded set of failure codes should map to one explicit fallback value.",
                    ],
                    "do_not_use_for": [
                        "Catching broad operational breakdown such as generic probe_failed unless the workflow truly intends to normalize that non-success into an authored value.",
                        "Simple boolean absence checks when workflow.local_expression.filter.not_found already states the intent more directly.",
                    ],
                    "nearest_surfaces": [
                        {"handle": "workflow.local_expression.filter.not_found", "summary": "Boolean shorthand for the common not-found conditional case"},
                        {"handle": "workflow.local_expression.filter", "summary": "Overview of the pipeline filter family"},
                        {"handle": "workflow.local_expressions", "summary": "Top-level workflow capability for local expressions"},
                    ],
                    "inspect_next": ["workflow.local_expression.filter.not_found", "workflow.local_expression.filter", "workflow.local_expressions"],
                }
            )
        elif filter_name == "not_found":
            filter_metadata.update(
                {
                    "definition": "Pipeline-style local-expression filter `not_found` for turning one successful strict lookup into `true` and any upstream `*_not_found` failure into `false` while preserving other failures.",
                    "use_when": [
                        "A conditional path should branch on ordinary target absence without widening the underlying strict probe contract.",
                    ],
                    "do_not_use_for": [
                        "Recovering arbitrary non-success beyond not-found cases; use workflow.local_expression.filter.catch for explicit broader recovery.",
                        "Preserving the original success value; `not_found` always returns a boolean verdict rather than the original payload.",
                    ],
                    "nearest_surfaces": [
                        {"handle": "workflow.local_expression.filter.catch", "summary": "General explicit recovery filter with authored fallback values"},
                        {"handle": "workflow.step.if", "summary": "Step-level optional routing surface where a boolean absence verdict is often useful"},
                        {"handle": "workflow.local_expression.filter", "summary": "Overview of the pipeline filter family"},
                    ],
                    "inspect_next": ["workflow.local_expression.filter.catch", "workflow.step.if", "workflow.local_expression.filter"],
                }
            )
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
        lookup["workflow.step.if"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.gate", "summary": "Sibling step-control field for admission decisions rather than optional local branching"},
            {"handle": "workflow.step.condition", "summary": "Shared boolean condition-authoring surface for step-level control fields"},
            {"handle": "workflow.step_forms.gate_checkpoint", "summary": "Sibling checkpoint form whose primary control surface is gate rather than if"},
            {"handle": "workflow-rules.separate_control_surfaces", "summary": "Authoring rule for separating applicability, admission, and local branching roles"},
        ]
        lookup["workflow.step.if"]["metadata"]["inspect_next"] = [
            "workflow.step.gate",
            "workflow.step.condition",
            "workflow.step_forms.gate_checkpoint",
            "workflow-rules.separate_control_surfaces",
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
        lookup["workflow.step.gate"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.if", "summary": "Sibling step-control field for optional local branching rather than admission decisions"},
            {"handle": "workflow.step_forms.gate_checkpoint", "summary": "Dedicated step form whose primary authored surface is gate"},
            {"handle": "workflow.step.condition", "summary": "Shared boolean condition-authoring surface for gate and if"},
            {"handle": "workflow-rules.separate_control_surfaces", "summary": "Authoring rule for separating workflow guards, step gates, and local if branching"},
        ]
        lookup["workflow.step.gate"]["metadata"]["inspect_next"] = [
            "workflow.step_forms.gate_checkpoint",
            "workflow.step.if",
            "workflow.step.condition",
            "workflow-rules.separate_control_surfaces",
        ]
    if "workflow.step.name" in lookup:
        lookup["workflow.step.name"]["summary"] = "Step field that declares one stable local step identity so later surfaces can refer to this step explicitly"
        lookup["workflow.step.name"]["metadata"]["role"] = "step_identity"
        lookup["workflow.step.name"]["metadata"]["use_when"] = [
            "every authored step needs one stable local identity for diagnostics, planning, review, and readable workflow structure",
            "step names should stay unique within the surrounding step list so diagnostics and execution reporting can point at one unambiguous step",
        ]
        lookup["workflow.step.name"]["metadata"]["do_not_use_for"] = [
            "human-facing prose descriptions; the field is the step's local workflow identity, not a narrative label surface",
            "choosing which step form the workflow should use; name identifies the step after the form is already chosen",
        ]
        lookup["workflow.step.name"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.register", "summary": "Sibling naming surface for reusable result bindings rather than for the step itself"},
            {"handle": "workflow.step.outputs", "summary": "Registered-step output read surface, distinct from the step's own authored identity"},
            {"handle": "workflow.step_forms.gate_checkpoint", "summary": "Dedicated step form where name is still required even when no other body field is present"},
        ]
        lookup["workflow.step.name"]["metadata"]["inspect_next"] = [
            "workflow.step.register",
            "workflow.step.outputs",
            "workflow.step_forms.gate_checkpoint",
            "workflow.step_forms.operation_call",
        ]
    if "workflow.step.result" in lookup:
        lookup["workflow.step.result"]["summary"] = "Step field that carries the value appended by a result step to the workflow's ordered result list"
        lookup["workflow.step.result"]["metadata"]["role"] = "workflow_result_emission"
        lookup["workflow.step.result"]["metadata"]["use_when"] = [
            "the step's authored payload should append one final value to the workflow result list",
            "the value is final outward result data rather than one reusable intermediate binding for later steps",
        ]
        lookup["workflow.step.result"]["metadata"]["do_not_use_for"] = [
            "reusable intermediate staging; use workflow.step.value with register when later steps still need to read the payload",
            "caller-facing named publish payloads; use workflow.step.publish when the intent is outward published output rather than the result list",
        ]
        lookup["workflow.step.result"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.publish", "summary": "Sibling emission field for outward-facing publish payloads instead of the workflow result list"},
            {"handle": "workflow.step_forms.result", "summary": "Dedicated step form whose primary authored field is result"},
            {"handle": "workflow.step.value", "summary": "Sibling field for staging reusable workflow-local values before any final emission"},
            {"handle": "workflow-rules.value_register_before_result", "summary": "Authoring rule for staging reusable payloads before emitting them through result"},
        ]
        lookup["workflow.step.result"]["metadata"]["inspect_next"] = [
            "workflow.step_forms.result",
            "workflow.step.publish",
            "workflow.step.value",
            "workflow-rules.value_register_before_result",
        ]
    if "workflow.step.publish" in lookup:
        lookup["workflow.step.publish"]["summary"] = "Step field that carries the outward-facing payload emitted by a publish step for callers"
        lookup["workflow.step.publish"]["metadata"]["role"] = "published_output_emission"
        lookup["workflow.step.publish"]["metadata"]["use_when"] = [
            "the step's authored payload should communicate one outward-facing result such as summary fields, identifiers, or URLs",
            "the output is meant for callers or downstream readers rather than only for the workflow's internal result list",
        ]
        lookup["workflow.step.publish"]["metadata"]["do_not_use_for"] = [
            "reusable intermediate staging; use workflow.step.value when the payload is still workflow-local before final emission",
            "appending one final value to the workflow result list; use workflow.step.result for that narrower emission role",
        ]
        lookup["workflow.step.publish"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.result", "summary": "Sibling emission field for appending to the workflow result list instead of publishing named outward output"},
            {"handle": "workflow.step_forms.publish", "summary": "Dedicated step form whose primary authored field is publish"},
            {"handle": "workflow.step.value", "summary": "Sibling field for staging reusable workflow-local values before publishing them outward"},
            {"handle": "workflow-rules.publish_outputs", "summary": "Authoring rule that prefers explicit minimal publish payloads for outward-facing results"},
        ]
        lookup["workflow.step.publish"]["metadata"]["inspect_next"] = [
            "workflow.step_forms.publish",
            "workflow.step.result",
            "workflow.step.value",
            "workflow-rules.publish_outputs",
        ]
    if "workflow.step.run" in lookup:
        lookup["workflow.step.run"]["summary"] = "Step field that names the reusable runtime target invoked by a run-invocation step"
        lookup["workflow.step.run"]["metadata"]["role"] = "runtime_target_selection"
        lookup["workflow.step.run"]["metadata"]["use_when"] = [
            "the step should invoke one named reusable runtime target instead of expanding a local inline repeated body",
            "the repeated or reusable behavior already has its own target identity and should stay readable as one run invocation",
        ]
        lookup["workflow.step.run"]["metadata"]["do_not_use_for"] = [
            "source-time include expansion; use workflow.include.include for fragment expansion before validation",
            "short local repeated step bodies that belong inline under for_each; use workflow.step.steps for that narrower inline fan-out body",
        ]
        lookup["workflow.step.run"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.steps", "summary": "Sibling field for inline repeated local step bodies instead of a named run target"},
            {"handle": "workflow.step.for_each", "summary": "Sibling repeated-item source field often paired with run for named target fan-out"},
            {"handle": "workflow.step.with", "summary": "Sibling invocation-argument field for binding values into the named run target"},
            {"handle": "workflow.step_forms.run_invocation", "summary": "Dedicated step form whose primary authored field is run"},
        ]
        lookup["workflow.step.run"]["metadata"]["inspect_next"] = [
            "workflow.step.with",
            "workflow.step.for_each",
            "workflow.step_forms.run_invocation",
            "workflow-rules.run_target_vs_inline_fan_out",
        ]
    if "workflow.step.steps" in lookup:
        lookup["workflow.step.steps"]["summary"] = "Step field that carries the inline repeated step body executed for each item in an inline fan-out invocation"
        lookup["workflow.step.steps"]["metadata"]["role"] = "inline_repeated_body"
        lookup["workflow.step.steps"]["metadata"]["use_when"] = [
            "the repeated work is short, workflow-local, and better expressed as one inline repeated body than as a named reusable run target",
            "the step should execute one small list of local steps for each item from for_each",
        ]
        lookup["workflow.step.steps"]["metadata"]["do_not_use_for"] = [
            "large, reusable, or guard-bearing repeated bodies; use workflow.step.run with a named target for those cases",
            "top-level workflow block authoring; this field only defines the inner repeated body of an inline fan-out step",
        ]
        lookup["workflow.step.steps"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.for_each", "summary": "Sibling repeated-item source field that drives this inline repeated body"},
            {"handle": "workflow.step.run", "summary": "Sibling field for named reusable runtime targets instead of inline repeated local steps"},
            {"handle": "workflow.step_forms.inline_fan_out_invocation", "summary": "Dedicated step form whose primary authored fields are for_each and steps"},
            {"handle": "workflow-rules.run_target_vs_inline_fan_out", "summary": "Authoring rule for choosing named run targets versus inline repeated local steps"},
        ]
        lookup["workflow.step.steps"]["metadata"]["inspect_next"] = [
            "workflow.step.for_each",
            "workflow.step.run",
            "workflow.step_forms.inline_fan_out_invocation",
            "workflow-rules.run_target_vs_inline_fan_out",
        ]
    if "workflow.step.for_each" in lookup:
        lookup["workflow.step.for_each"]["summary"] = "Step field that provides the array-valued repeated item source for an inline fan-out step body"
        lookup["workflow.step.for_each"]["metadata"]["role"] = "bounded_repetition_source"
        lookup["workflow.step.for_each"]["metadata"]["use_when"] = [
            "one invocation-shaped step should repeat over an explicit array-valued item source",
            "the workflow needs bounded fan-out through either a named run target or an inline repeated step body",
        ]
        lookup["workflow.step.for_each"]["metadata"]["do_not_use_for"] = [
            "general looping semantics beyond the published bounded fan-out surface",
            "non-array repeated sources or nested repetition that belong outside the current public workflow model",
        ]
        lookup["workflow.step.for_each"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.steps", "summary": "Sibling inline repeated body field for the local steps executed for each item"},
            {"handle": "workflow.step.run", "summary": "Sibling named target field for fan-out over a reusable runtime target"},
            {"handle": "workflow.step_forms.inline_fan_out_invocation", "summary": "Dedicated inline repeated-body form that requires for_each and steps together"},
            {"handle": "workflow-rules.fan_out_scope_and_conditions", "summary": "Authoring rule for outer and inner fan-out scope boundaries"},
        ]
        lookup["workflow.step.for_each"]["metadata"]["inspect_next"] = [
            "workflow.step.steps",
            "workflow.step.run",
            "workflow.step_forms.inline_fan_out_invocation",
            "workflow-rules.fan_out_scope_and_conditions",
        ]
    if "workflow.step.with" in lookup:
        lookup["workflow.step.with"]["summary"] = "Step field that binds invocation arguments into an operation call or named run target at runtime"
        lookup["workflow.step.with"]["metadata"]["role"] = "runtime_argument_binding"
        lookup["workflow.step.with"]["metadata"]["use_when"] = [
            "the invocation needs explicit runtime argument values for an operation call or named run target",
            "workflow-local expressions should be bound into the callee surface instead of being re-read implicitly inside that target",
        ]
        lookup["workflow.step.with"]["metadata"]["do_not_use_for"] = [
            "source-time include argument binding; use workflow.include.with for include expansion",
            "inline repeated step bodies whose local work should read item or workflow context directly rather than through outer with bindings",
        ]
        lookup["workflow.step.with"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.run", "summary": "Sibling field for selecting the named run target that receives these invocation arguments"},
            {"handle": "workflow.step.uses", "summary": "Sibling field for selecting the operation call that may also consume with-bound invocation arguments"},
            {"handle": "workflow.include.with", "summary": "Source-time fragment argument binding surface rather than runtime invocation argument binding"},
            {"handle": "workflow-rules.native_expression_contexts", "summary": "Authoring rule for bare expressions in with bindings"},
        ]
        lookup["workflow.step.with"]["metadata"]["inspect_next"] = [
            "workflow.step.run",
            "workflow.step.uses",
            "workflow.include.with",
            "workflow-rules.native_expression_contexts",
        ]
    if "workflow.step.uses" in lookup:
        lookup["workflow.step.uses"]["summary"] = "Step field that selects the published operation surface invoked by an operation-call step"
        lookup["workflow.step.uses"]["metadata"]["role"] = "published_operation_selection"
        lookup["workflow.step.uses"]["metadata"]["use_when"] = [
            "the step should call one published external operation rather than invoke a named workflow or routine target through run",
            "the operation surface itself should stay explicit and reviewable as a typed connector call",
        ]
        lookup["workflow.step.uses"]["metadata"]["do_not_use_for"] = [
            "named workflow or routine target invocation; use workflow.step.run for that runtime-target surface",
            "runtime argument binding or result reuse; those belong to workflow.step.with and workflow.step.register instead of operation selection itself",
        ]
        lookup["workflow.step.uses"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.step.with", "summary": "Sibling field for binding runtime arguments into the selected operation call"},
            {"handle": "workflow.step.register", "summary": "Sibling field for binding the operation result to a reusable local name"},
            {"handle": "workflow.step.run", "summary": "Sibling field for named workflow or routine targets instead of published connector operations"},
            {"handle": "workflow.step_forms.operation_call", "summary": "Dedicated step form whose primary authored field is uses"},
        ]
        lookup["workflow.step.uses"]["metadata"]["inspect_next"] = [
            "workflow.step.with",
            "workflow.step.register",
            "workflow.step.run",
            "workflow.step_forms.operation_call",
        ]
    if "workflow.run.run" in lookup:
        lookup["workflow.run.run"]["summary"] = "Run-call field that selects the named reusable runtime target invoked by a run step"
        lookup["workflow.run.run"]["metadata"]["role"] = "runtime_target_selection"
        lookup["workflow.run.run"]["metadata"]["use_when"] = [
            "the invocation should call one named reusable workflow fragment or routine target instead of keeping the repeated body inline",
            "the callee deserves its own stable identity and isolated run scope rather than one local inline repeated body",
        ]
        lookup["workflow.run.run"]["metadata"]["do_not_use_for"] = [
            "source-time include expansion; use workflow.include.include when the body should be expanded before validation instead of invoked at runtime",
            "short local repeated work that is clearer as inline steps under workflow.run.steps",
        ]
        lookup["workflow.run.run"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.run.steps", "summary": "Sibling inline repeated-body field for short local repeated work instead of a named run target"},
            {"handle": "workflow.run.with", "summary": "Sibling invocation-argument field for binding caller values into the named run target"},
            {"handle": "workflow.step_forms.run_invocation", "summary": "Dedicated step form whose primary authored field is run"},
        ]
        lookup["workflow.run.run"]["metadata"]["inspect_next"] = [
            "workflow.run.with",
            "workflow.run.for_each",
            "workflow.step_forms.run_invocation",
            "workflow-rules.run_target_vs_inline_fan_out",
        ]
    if "workflow.run.with" in lookup:
        lookup["workflow.run.with"]["summary"] = "Run-call field that binds caller-scoped argument values into the named target selected by workflow.run.run"
        lookup["workflow.run.with"]["metadata"]["role"] = "runtime_argument_binding"
        lookup["workflow.run.with"]["metadata"]["use_when"] = [
            "the named run target needs explicit caller-scoped values rather than implicitly reading caller context inside the callee body",
            "runtime expressions should be bound into args.* for the callee instead of being duplicated there",
        ]
        lookup["workflow.run.with"]["metadata"]["do_not_use_for"] = [
            "source-time fragment argument binding; use workflow.include.with for include expansion",
            "inline repeated bodies that should read item or workflow context directly instead of receiving outer call bindings",
        ]
        lookup["workflow.run.with"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.run.run", "summary": "Sibling field for selecting the named run target that receives these bindings"},
            {"handle": "workflow.include.with", "summary": "Source-time fragment argument binding surface rather than runtime invocation binding"},
            {"handle": "workflow-rules.native_expression_contexts", "summary": "Authoring rule for bare expressions in with bindings"},
        ]
        lookup["workflow.run.with"]["metadata"]["inspect_next"] = [
            "workflow.run.run",
            "workflow.run.for_each",
            "workflow.include.with",
            "workflow-rules.native_expression_contexts",
        ]
    if "workflow.run.for_each" in lookup:
        lookup["workflow.run.for_each"]["summary"] = "Run-call field that provides the array-valued repeated item source for bounded fan-out over one invocation-shaped step"
        lookup["workflow.run.for_each"]["metadata"]["role"] = "bounded_repetition_source"
        lookup["workflow.run.for_each"]["metadata"]["use_when"] = [
            "one run invocation or inline repeated-body step should repeat over an explicit array-valued item source",
            "the workflow needs bounded fan-out while keeping one outer invocation step visible and reviewable",
        ]
        lookup["workflow.run.for_each"]["metadata"]["do_not_use_for"] = [
            "general looping semantics beyond the published bounded fan-out surface",
            "non-array or nested repetition shapes that belong outside the current public workflow model",
        ]
        lookup["workflow.run.for_each"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.run.run", "summary": "Sibling named-target field often paired with for_each for reusable repeated bodies"},
            {"handle": "workflow.run.steps", "summary": "Sibling inline repeated-body field paired with for_each for short local repeated work"},
            {"handle": "workflow-rules.fan_out_scope_and_conditions", "summary": "Authoring rule for outer and inner fan-out scope boundaries"},
        ]
        lookup["workflow.run.for_each"]["metadata"]["inspect_next"] = [
            "workflow.run.run",
            "workflow.run.steps",
            "workflow.step_forms.inline_fan_out_invocation",
            "workflow-rules.fan_out_scope_and_conditions",
        ]
    if "workflow.run.if" in lookup:
        lookup["workflow.run.if"]["summary"] = "Run-call field that gates the whole invocation step with one caller-scoped optionality condition"
        lookup["workflow.run.if"]["metadata"]["role"] = "caller_scoped_invocation_condition"
        lookup["workflow.run.if"]["metadata"]["use_when"] = [
            "the whole invocation step is optional inside an already-valid workflow path",
            "one outer condition should decide whether fan-out or named-target invocation happens at all before any inner step body runs",
        ]
        lookup["workflow.run.if"]["metadata"]["do_not_use_for"] = [
            "workflow-wide applicability that belongs in guards near the top of the workflow",
            "admission decisions whose main meaning is whether the path may run at all; use workflow.run.gate for that stronger control surface",
        ]
        lookup["workflow.run.if"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.run.gate", "summary": "Sibling field for admission decisions rather than optional local branching"},
            {"handle": "workflow.step.if", "summary": "Related step-local branching surface outside the run-call contract"},
            {"handle": "workflow-rules.separate_control_surfaces", "summary": "Authoring rule for separating guards, gates, and if surfaces"},
        ]
        lookup["workflow.run.if"]["metadata"]["inspect_next"] = [
            "workflow.run.gate",
            "workflow.step.if",
            "workflow-rules.separate_control_surfaces",
            "workflow-rules.fan_out_scope_and_conditions",
        ]
    if "workflow.run.gate" in lookup:
        lookup["workflow.run.gate"]["summary"] = "Run-call field that decides whether the whole invocation step may run at all before the protected work begins"
        lookup["workflow.run.gate"]["metadata"]["role"] = "caller_scoped_step_admission_condition"
        lookup["workflow.run.gate"]["metadata"]["use_when"] = [
            "the real question is whether the whole invocation step may execute at all, not just whether it is locally optional",
            "a blocked invocation should publish structured gate-failure context rather than quietly disappearing behind if logic",
        ]
        lookup["workflow.run.gate"]["metadata"]["do_not_use_for"] = [
            "workflow-wide applicability that belongs in guards near the start of the workflow",
            "aggregate result publication on the same outer invocation step; split gate and register across separate steps when both are needed",
        ]
        lookup["workflow.run.gate"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.run.if", "summary": "Sibling outer-branching field for optional invocation instead of admission control"},
            {"handle": "workflow.step.gate", "summary": "Related step-admission surface outside the run-call contract"},
            {"handle": "workflow.step_forms.gate_checkpoint", "summary": "Standalone gate-only checkpoint step when admission should be split from later registered work"},
        ]
        lookup["workflow.run.gate"]["metadata"]["inspect_next"] = [
            "workflow.run.if",
            "workflow.step.gate",
            "workflow.step_forms.gate_checkpoint",
            "workflow-rules.separate_control_surfaces",
        ]
    if "workflow.run.register" in lookup:
        lookup["workflow.run.register"]["summary"] = "Run-call field that binds the outer aggregate result of one invocation step to a reusable local name"
        lookup["workflow.run.register"]["metadata"]["role"] = "aggregate_invocation_result"
        lookup["workflow.run.register"]["metadata"]["use_when"] = [
            "later workflow steps need the aggregate results of one run invocation or bounded fan-out step under one reusable local name",
            "the outer invocation result should stay reviewable as one named aggregate rather than as many unnamed ephemeral outputs",
        ]
        lookup["workflow.run.register"]["metadata"]["do_not_use_for"] = [
            "the same step that also declares gate; split admission and aggregate result capture into separate steps",
            "naming one inner repeated-body register; inner step registers stay iteration-local inside inline fan-out bodies",
        ]
        lookup["workflow.run.register"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.run.gate", "summary": "Sibling admission field that must be split away when aggregate results also need registering"},
            {"handle": "workflow.step.register", "summary": "Related step-level register surface outside the run-call contract"},
            {"handle": "workflow-rules.fan_out_scope_and_conditions", "summary": "Authoring rule that explains outer versus inner register scope in fan-out"},
        ]
        lookup["workflow.run.register"]["metadata"]["inspect_next"] = [
            "workflow.step.register",
            "workflow.run.gate",
            "workflow-rules.fan_out_scope_and_conditions",
            "workflow-rules.value_register_before_result",
        ]
    if "workflow.run.steps" in lookup:
        lookup["workflow.run.steps"]["summary"] = "Run-call field that carries the short inline repeated body executed for each item in an inline fan-out invocation"
        lookup["workflow.run.steps"]["metadata"]["role"] = "inline_repeated_body"
        lookup["workflow.run.steps"]["metadata"]["use_when"] = [
            "the repeated work is short, workflow-local, and clearer as one inline repeated body than as a named reusable run target",
            "one invocation-shaped step should execute a small list of local steps for each item from for_each",
        ]
        lookup["workflow.run.steps"]["metadata"]["do_not_use_for"] = [
            "large, reusable, or guard-bearing repeated bodies that deserve workflow.run.run with a named target",
            "top-level workflow block authoring; this field only defines the inner repeated body of an inline fan-out invocation",
        ]
        lookup["workflow.run.steps"]["metadata"]["nearest_surfaces"] = [
            {"handle": "workflow.run.for_each", "summary": "Sibling repeated-item source field that drives this inline repeated body"},
            {"handle": "workflow.run.run", "summary": "Sibling named-target field for reusable repeated work instead of inline local steps"},
            {"handle": "workflow.step_forms.inline_fan_out_invocation", "summary": "Dedicated step form whose primary authored fields are for_each and steps"},
        ]
        lookup["workflow.run.steps"]["metadata"]["inspect_next"] = [
            "workflow.run.for_each",
            "workflow.run.run",
            "workflow.step_forms.inline_fan_out_invocation",
            "workflow-rules.run_target_vs_inline_fan_out",
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
        if connector["namespace"] == "gh":
            connector_metadata["use_when"] = [*connector_metadata.get("use_when", []), _GH_REPOSITORY_INPUT_GUIDANCE]
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
            if connector["namespace"] == "gh" and "repository" in operation.get("inputs", {}):
                operation_metadata["use_when"] = [*operation_metadata.get("use_when", []), _GH_REPOSITORY_INPUT_GUIDANCE]
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


def _build_workflow_rules_node_lookup() -> dict[str, JSONObject]:
    payload = build_workflow_rules_response()
    lookup: dict[str, JSONObject] = {}

    for rule in payload["rules"]:
        if not isinstance(rule, dict) or not isinstance(rule.get("name"), str):
            continue
        handle = f"workflow-rules.{rule['name']}"
        lookup[handle] = {
            "document_kind": "workflow_rules_node",
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
            handle = f"workflow-rules.example.{example['name']}"
            lookup[handle] = {
                "document_kind": "workflow_rules_node",
                "node_kind": "example",
                "name": handle,
                "summary": str(example.get("summary") or "Published workflow-rules example"),
                "metadata": {"group": example_group, **example},
                "snippet_coverage": "none",
                "canonical_examples": [],
            }

    return lookup


def _build_examples_node_lookup(*, context: _HelpResponseContext | None = None) -> dict[str, JSONObject]:
    if context is None:
        context = _HelpResponseContext()
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
            "summary": str(example.get("definition") or f"Verified example at {example['path']}"),
            "metadata": example,
            **context.snippet_surface(handle),
        }
    return lookup


def _build_command_line_node_lookup(*, context: _HelpResponseContext | None = None) -> dict[str, JSONObject]:
    if context is None:
        context = _HelpResponseContext()
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
                "This explicit launch choice should win over playbook defaults and remembered-profile switching attempted inside playbook-owned pre_run setup.",
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
        (
            "ordo-playbook",
            "--progress-steps",
        ): {
            "definition": "During run, emit each step name to stderr right before execution.",
            "use_when": [
                "You need immediate human-visible progress while run mode is executing real workflow steps.",
                "You want progress lines without corrupting JSON or summary payloads written to stdout.",
            ],
            "do_not_use_for": [
                "Non-run modes; this flag is only supported with run.",
                "Machine-readable progress parsing from stdout; progress is emitted on stderr instead.",
            ],
            "nearest_surfaces": [
                {"handle": "command-line.ordo-playbook", "summary": "Parent command surface for ordo-playbook"},
                {"handle": "command-line.ordo-playbook.flag.json", "summary": "Companion output-format flag that can still keep stdout machine-readable while progress goes to stderr"},
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
            **context.snippet_surface(f"command-line.{command_name}"),
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


def _build_public_handle_reference(handle: str, *, context: _HelpResponseContext | None = None) -> JSONObject:
    if context is None:
        context = _HelpResponseContext()
    topic = next((item for item in PUBLIC_TOPICS if item["name"] == handle), None)
    if topic is not None:
        return {
            "handle": handle,
            "kind": "topic",
            "summary": topic["summary"],
            "command": f"ordo-help {handle} --json",
        }

    # All builders must succeed before resolving even an earlier match. Reuse
    # their tables, but do not turn this tuple into a short-circuiting generator.
    for lookup, topic_name in (
        (context.lookup("workflow-rules"), "workflow-rules"),
        (context.lookup("examples"), "examples"),
        (context.lookup("model"), "model"),
        (context.lookup("command-line"), "command-line"),
        (context.lookup("capabilities"), "capabilities"),
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


def _build_workflow_rule_reference(
    rule_name: str, *, rule_lookup: dict[str, JSONObject], context: _HelpResponseContext | None = None
) -> JSONObject:
    if context is None:
        context = _HelpResponseContext()
    handle = f"workflow-rules.{rule_name}"
    node = context.lookup("workflow-rules").get(handle)
    rule = rule_lookup.get(rule_name)
    summary = str(rule["rule"]) if isinstance(rule, dict) and isinstance(rule.get("rule"), str) else str(node["summary"]) if node is not None else rule_name
    return {
        "name": rule_name,
        "handle": handle,
        "summary": summary,
        "command": f"ordo-help describe {handle} --json",
    }


def _build_example_reference(
    handle: str, *, examples: JSONObject, context: _HelpResponseContext | None = None
) -> JSONObject:
    if context is None:
        context = _HelpResponseContext()
    if handle.startswith("workflow-rules.example."):
        node = context.lookup("workflow-rules").get(handle)
        if node is not None:
            return {
                "name": str(node["metadata"]["name"]),
                "handle": handle,
                "summary": str(node["summary"]),
                "command": f"ordo-help describe {handle} --json",
            }

    node = context.lookup("examples").get(handle)
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

    context = _HelpResponseContext()
    handles: list[JSONObject] = []
    lookup_groups = (
        ("capabilities", context.lookup("capabilities")),
        ("model", context.lookup("model")),
        ("command-line", context.lookup("command-line")),
        ("workflow-rules", context.lookup("workflow-rules")),
        ("examples", context.lookup("examples")),
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
        "coverage_levels": ["none", "excerpt_verified", "harness_verified", "runner_verified"],
        "summary": {
            "total_handles": len(handles),
            "coverage_counts": coverage_counts,
        },
        "handles": handles,
    }


def build_search_response(query: str) -> JSONObject:
    """Return search results across public topics and operation references."""

    context = _HelpResponseContext()
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

    for node_name, node in context.lookup("model").items():
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

    for node_name, node in context.lookup("command-line").items():
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

    workflow_rules = build_workflow_rules_response()
    for rule in workflow_rules["rules"]:
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
                    "kind": "workflow_rule",
                    "name": f"workflow-rules.{rule['name']}",
                    "summary": rule["rule"],
                    "topic": "workflow-rules",
                    "command": f"ordo-help describe workflow-rules.{rule['name']} --json",
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


def _resolve_describe_topic_alias(topic: str, *, context: _HelpResponseContext | None = None) -> str:
    if context is None:
        context = _HelpResponseContext()
    example_alias = _resolve_example_topic_alias(topic)
    if example_alias is not None:
        return example_alias
    if topic.startswith("operation."):
        candidate = f"connector.{topic.removeprefix('operation.')}"
        if candidate in context.lookup("model"):
            return candidate
    return topic


def _build_unknown_topic_suggestions(topic: str, *, context: _HelpResponseContext | None = None) -> list[JSONObject]:
    if context is None:
        context = _HelpResponseContext()
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
        if connector_topic in context.lookup("model"):
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
            "4. ordo-help workflow-rules",
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
            f"- Graph: {payload['graph_guidance']}",
            f"- Reading the symbols: {payload['graph_presentation']}",
            f"- Reading the branches: {payload['graph_source_placement']}",
            f"- Limits and next commands: {payload['graph_context']}",
            f"- Parameters and details: {payload['graph_parameters']}",
            f"- Repeated workflows: {payload['graph_roles']}",
            f"- GitHub merge: {payload['gh_pr_merge_guidance']}",
            f"- GitHub candidate discovery: {payload['gh_pr_list_guidance']}",
            f"- GitHub creation: {payload['gh_pr_create_guidance']}",
            f"- Connector authoring: {payload['connector_authoring_guidance']}",
            f"- modes: {', '.join(payload['execution_concepts']['modes'])}",
            f"- statuses: {', '.join(payload['execution_concepts']['statuses'])}",
            f"- state deferral: {payload['execution_concepts']['state_deferral']}",
            f"- state boundary: {payload['execution_concepts']['state_boundary']}",
            f"- check unknown: {payload['execution_concepts']['check_unknown']}",
            "",
            "Workflow check/review passes:",
            f"- rule: {payload['workflow_check_review_passes']['rule']}",
            *[f"- {item['command']}: {item['purpose']}" for item in payload['workflow_check_review_passes']['passes']],
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
    lines = ["capabilities", "Supported and unsupported runtime surfaces.", "", GRAPH_GUIDANCE, GRAPH_PRESENTATION, GRAPH_SOURCE_PLACEMENT, GRAPH_CONTEXT_GUIDANCE, GRAPH_PARAMETER_GUIDANCE, GRAPH_ROLE_GUIDANCE, GH_PR_MERGE_GUIDANCE, GH_PR_CREATE_GUIDANCE, SDK_CALL_GUIDANCE, "", "Capability states:"]
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
        payload["gh_pr_merge_guidance"],
        payload["gh_pr_create_guidance"],
        payload["graph_guidance"],
        payload["graph_presentation"],
        payload["graph_source_placement"],
        payload["graph_context"],
        payload["graph_parameters"],
        payload["graph_roles"],
        payload["connector_authoring_guidance"],
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


def render_workflow_rules_text(payload: JSONObject) -> str:
    """Return the text workflow-rules surface."""

    lines = ["workflow-rules", payload["purpose"], "", "Workflow heuristic:"]
    lines.extend(f"- {item}" for item in payload["heuristic"])
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
        check_review_passes = command.get("check_review_passes")
        lines.extend(["", "discovery commands:"])
        lines.extend(f"- {item['name']}: {item['summary']}" for item in command["discovery_commands"])
        lines.extend(["", "use when:"])
        lines.extend(f"- {item}" for item in command["use_when"])
        lines.extend(["", "review findings surface:", f"- {command['review_findings_surface']}"])
        if isinstance(check_review_passes, dict):
            lines.extend(["", "workflow check/review passes:", f"- rule: {check_review_passes['rule']}"])
            for item in check_review_passes.get("passes", []):
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

    lines = ["operations", "Public connector namespaces and operations.", "", GH_PR_MERGE_GUIDANCE, GH_PR_CREATE_GUIDANCE, SDK_CALL_GUIDANCE, ""]
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
        if example.get("form") == "graph_bundle" and example.get("display") == "verified_graph_output":
            # Display the very same expected_text checked by the existing graph
            # snippet verifier; keep the complete authored bundle in JSON.
            output = yaml.safe_load(example["yaml"])["expected_text"]
            lines.append("  verified graph output:")
            lines.extend(f"    {line}" for line in output.rstrip("\n").splitlines())
            continue
        if isinstance(example.get("form"), str):
            lines.append(f"  example_for: {example['form']}")
        language = "python" if example.get("form") == "python_fragment" else "yaml"
        source_text = example.get(language)
        if isinstance(source_text, str) and source_text:
            lines.append(f"  {language}:")
            for snippet_line in source_text.splitlines():
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
        reason = payload.get("reason")
        if isinstance(reason, str) and reason:
            lines.extend(["", f"reason: {reason}"])
        related_codes = payload.get("related_codes", [])
        if isinstance(related_codes, list) and related_codes:
            lines.extend(["", "related codes:"])
            lines.extend(f"- {item}" for item in related_codes if isinstance(item, str))
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
    status = metadata.get("status")
    deprecated = metadata.get("deprecated")
    preferred_alternative = metadata.get("preferred_alternative")
    if any(isinstance(item, str) for item in (namespace, kind, maturity, status, preferred_alternative)) or isinstance(deprecated, bool):
        lines.extend(["", "published contract:"])
        if isinstance(namespace, str):
            lines.append(f"- namespace: {namespace}")
        if isinstance(kind, str):
            lines.append(f"- kind: {kind}")
        if isinstance(maturity, str):
            lines.append(f"- maturity: {maturity}")
        if isinstance(status, str):
            lines.append(f"- status: {status}")
        if isinstance(deprecated, bool):
            lines.append(f"- deprecated: {'yes' if deprecated else 'no'}")
        if isinstance(preferred_alternative, str):
            lines.append(f"- preferred_alternative: {preferred_alternative}")

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

    fields = metadata.get("fields", [])
    if isinstance(fields, list) and fields:
        lines.extend(["", "fields:"])
        for item in fields:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            type_name = item.get("type")
            required = item.get("required")
            role = item.get("role") or item.get("authoring_role")
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

    env_reference_roots = metadata.get("env_reference_roots", [])
    env_reference_pattern = metadata.get("env_reference_pattern")
    automatic_input_env_projection = metadata.get("automatic_input_env_projection")
    env_scalar_only = metadata.get("env_scalar_only")
    env_non_scalar_behavior = metadata.get("env_non_scalar_behavior")
    generated_env_name_prefix = metadata.get("generated_env_name_prefix")
    generated_env_name_examples = metadata.get("generated_env_name_examples")
    if any([
        isinstance(env_reference_roots, list) and bool(env_reference_roots),
        isinstance(env_reference_pattern, str),
        isinstance(automatic_input_env_projection, bool),
        isinstance(env_scalar_only, bool),
        isinstance(env_non_scalar_behavior, str),
        isinstance(generated_env_name_prefix, str),
        isinstance(generated_env_name_examples, dict) and bool(generated_env_name_examples),
    ]):
        lines.extend(["", "env forwarding contract:"])
        if isinstance(automatic_input_env_projection, bool):
            lines.append(f"- automatic input env projection: {'yes' if automatic_input_env_projection else 'no'}")
        if isinstance(env_reference_pattern, str):
            lines.append(f"- env reference pattern: {env_reference_pattern}")
        if isinstance(env_reference_roots, list) and env_reference_roots:
            lines.append(f"- env reference roots: {', '.join(str(item) for item in env_reference_roots)}")
        if isinstance(env_scalar_only, bool):
            lines.append(f"- env scalar only: {'yes' if env_scalar_only else 'no'}")
        if isinstance(env_non_scalar_behavior, str):
            lines.append(f"- env non-scalar behavior: {env_non_scalar_behavior}")
        if isinstance(generated_env_name_prefix, str):
            lines.append(f"- generated env prefix: {generated_env_name_prefix}")
        if isinstance(generated_env_name_examples, dict) and generated_env_name_examples:
            lines.append("- generated env examples:")
            for ref, name in generated_env_name_examples.items():
                lines.append(f"  - {ref} -> {name}")

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

    check_review_passes = metadata.get("check_review_passes")
    if isinstance(check_review_passes, dict):
        lines.extend(["", "workflow check/review passes:", f"- rule: {check_review_passes['rule']}"])
        for item in check_review_passes.get("passes", []):
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
    review_findings_surface = metadata.get("review_findings_surface")
    if isinstance(review_findings_surface, str) and review_findings_surface:
        lines.extend(["", "review findings surface:", f"- {review_findings_surface}"])
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


def render_workflow_rules_node_text(payload: JSONObject) -> str:
    """Return the text workflow-rules-node surface."""

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

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    path = metadata.get("path") if isinstance(metadata.get("path"), str) else None
    shows = metadata.get("shows") if isinstance(metadata.get("shows"), list) else []
    related_topics = metadata.get("related_topics") if isinstance(metadata.get("related_topics"), list) else []

    lines = [payload["name"], payload["summary"]]
    if path:
        lines.append(f"Verified example at {path}")
    lines.extend(["", f"node kind: {payload['node_kind']}"])
    if shows:
        lines.append("")
        lines.append("shows:")
        lines.extend(f"- {item}" for item in shows if isinstance(item, str))
    if related_topics:
        lines.append("")
        lines.append("related topics:")
        lines.extend(f"- {item}" for item in related_topics if isinstance(item, str))
    _append_text_canonical_examples(lines, payload.get("canonical_examples", []))
    return "\n".join(lines)


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


def _emit_unknown_topic(topic: str, *, as_json: bool, context: _HelpResponseContext | None = None) -> int:
    """Emit a focused unknown-topic error."""

    payload = {
        "document_kind": "topic_error",
        "topic": topic,
        "status": "unknown_topic",
        "message": f"Unsupported public topic or node '{topic}'",
        "supported_topics": list(DESCRIBABLE_TOPICS),
        "supported_node_kinds": ["capability", "negative_rule", "model_node", "workflow_rules_node", "example_node", "command_line_node"],
        "suggestions": _build_unknown_topic_suggestions(topic, context=context),
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


def _resolve_public_topic(topic: str, *, context: _HelpResponseContext | None = None) -> tuple[JSONObject, object] | None:
    """Resolve one describable public topic to its payload and renderer."""

    if context is None:
        context = _HelpResponseContext()
    if topic == "overview":
        return build_overview_response(), render_overview_text
    if topic == "model":
        return build_model_response(), render_model_text
    if topic == "features":
        return build_features_response(), render_features_text
    if topic == "workflow-rules":
        return build_workflow_rules_response(), render_workflow_rules_text
    if topic == "capabilities":
        return build_capabilities_response(), render_capabilities_text
    if topic == "command-line":
        return build_command_line_response(), render_command_line_text
    if topic == "operations":
        return build_operations_response(), render_operations_text
    if topic == "examples":
        return describe_examples_catalog(), render_examples_text
    if topic == "snippet-coverage":
        return build_snippet_coverage_response(), render_snippet_coverage_text
    capability_node = context.lookup("capabilities").get(topic)
    if capability_node is not None:
        return capability_node, render_capability_node_text
    model_node = context.lookup("model").get(topic)
    if model_node is not None:
        return model_node, render_model_node_text
    command_line_node = context.lookup("command-line").get(topic)
    if command_line_node is not None:
        return command_line_node, render_command_line_node_text
    workflow_rules_node = context.lookup("workflow-rules").get(topic)
    if workflow_rules_node is not None:
        return workflow_rules_node, render_workflow_rules_node_text
    example_node = context.lookup("examples").get(topic)
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

    workflow_rules_parser = subparsers.add_parser("workflow-rules", add_help=False)
    workflow_rules_parser.add_argument("--json", action="store_true", dest="as_json")

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
        return _emit_payload(build_capabilities_response(), as_json=as_json, renderer=render_capabilities_text)
    if parsed.command == "model":
        return _emit_payload(build_model_response(), as_json=as_json, renderer=render_model_text)
    if parsed.command == "features":
        return _emit_payload(build_features_response(), as_json=as_json, renderer=render_features_text)
    if parsed.command == "workflow-rules":
        return _emit_payload(build_workflow_rules_response(), as_json=as_json, renderer=render_workflow_rules_text)
    if parsed.command == "command-line":
        return _emit_payload(build_command_line_response(), as_json=as_json, renderer=render_command_line_text)
    if parsed.command == "operations":
        return _emit_payload(build_operations_response(), as_json=as_json, renderer=render_operations_text)
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
        context = _HelpResponseContext()
        resolved_topic = _resolve_describe_topic_alias(parsed.topic, context=context)
        resolved = _resolve_public_topic(resolved_topic, context=context)
        if resolved is None:
            return _emit_unknown_topic(parsed.topic, as_json=as_json, context=context)
        payload, renderer = resolved
        return _emit_payload(payload, as_json=as_json, renderer=renderer)
    if parsed.command == "search":
        return _emit_payload(build_search_response(parsed.query), as_json=as_json, renderer=render_search_text)

    parser.error(f"Unsupported command: {parsed.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
