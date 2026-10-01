"""Canonical contract metadata for workflow authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject
from .human import HumanDeclaration, declare_human, human_mapping
from ordo.runtime.local_expression_engine.core import VALUE_EXPRESSION_BUILTINS, VALUE_EXPRESSION_FILTERS


_PUBLISHED_FILTERS = list(VALUE_EXPRESSION_FILTERS)
_PUBLISHED_BUILTINS = list(VALUE_EXPRESSION_BUILTINS)

WORKFLOW_FEATURE_HUMANS = {
    name: declare_human({"title": name.replace("-", " ").title(), "goal": "Choose this workflow authoring surface when it fits the intended work.", "summary": summary, "sections": []})
    for name, summary in {
        "workflow": "An executable workflow with explicit inputs, guards, steps, and outputs.", "include": "Reusable source fragments with explicit arguments.", "run": "Runtime invocation for reusable fragments and bounded repeated work.", "guards": "Early workflow applicability and input validation.", "gates": "Admission control for a path inside an already-applicable workflow.", "conditions": "Readable boolean decisions for local branching and admission.", "local-expressions": "Short workflow-local reads, checks, comparisons, and transformations.", "adapters": "Structured representations for clearer workflow decisions and results.",
    }.items()
}

WORKFLOW_HUMAN = declare_human({
    "title": "Workflow contract", "goal": "Define one workflow's inputs, applicability checks, and ordered work.", "summary": "Use this contract to author a workflow file and keep its decisions explicit.",
    "sections": [{"heading": "Start with", "items": ["Declare the workflow name and only the inputs it needs.", "Put applicability checks near the start.", "Use named steps and publish only the result a caller needs."]}, {"heading": "Related guidance", "references": [{"handle": "workflow-rules", "summary": "Choose the right conditional surface and validate changes with both check and review."}, {"handle": "capabilities", "summary": "Confirm that the workflow surface you need is supported."}]}],
    "feature_clusters": {
        "workflow": {**human_mapping(WORKFLOW_FEATURE_HUMANS["workflow"]), "use_when": ["One task needs a reviewable execution contract."], "avoid_when": ["You only need catalog metadata or reusable fragment material."]},
        "include": {**human_mapping(WORKFLOW_FEATURE_HUMANS["include"]), "use_when": ["A repeated authored fragment has one clear source-level purpose."], "avoid_when": ["The reuse needs runtime invocation or repeated execution."]},
        "run": {**human_mapping(WORKFLOW_FEATURE_HUMANS["run"]), "use_when": ["A named fragment or short repeated body expresses the work clearly."], "avoid_when": ["The repeated work needs unsupported nested control flow."]},
        "guards": {**human_mapping(WORKFLOW_FEATURE_HUMANS["guards"]), "use_when": ["The workflow must reject an inapplicable situation before work starts."], "avoid_when": ["The decision only controls one local step."]},
        "gates": {**human_mapping(WORKFLOW_FEATURE_HUMANS["gates"]), "use_when": ["A protected path may run only when earlier facts allow it."], "avoid_when": ["The decision determines whole-workflow applicability."]},
        "conditions": {**human_mapping(WORKFLOW_FEATURE_HUMANS["conditions"]), "use_when": ["A local decision benefits from an explicit boolean condition."], "avoid_when": ["The value is payload construction rather than a decision."]},
        "local-expressions": {**human_mapping(WORKFLOW_FEATURE_HUMANS["local-expressions"]), "use_when": ["A small inline expression makes a workflow field clearer."], "avoid_when": ["The expression is long or repeated enough to need a named value or another surface."]},
        "adapters": {**human_mapping(WORKFLOW_FEATURE_HUMANS["adapters"]), "use_when": ["A published representation makes a transformation clearer than inline rewriting."], "avoid_when": ["A plain expression already states the intent clearly."]},
    },
})


# Focused-describe records live with the workflow contract so their guidance
# shares the same source of truth as the workflow surfaces it explains.
WORKFLOW_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "workflow.step.profile_switch": declare_human({
        "definition": "Step field for changing the declared profile used by later work on the current workflow path.",
        "use_when": ["Later work must use another declared profile based on workflow logic.", "The profile changes part way through the workflow rather than applying from the start."],
        "do_not_use_for": ["A fixed workflow profile; use workflow.profile.", "New launcher-based profile setup; use this field instead."],
        "nearest_surfaces": [{"handle": "workflow.step_forms.profile_switch", "summary": "Step form for a named profile change"}, {"handle": "workflow.profile", "summary": "Fixed profile binding for the whole workflow"}, {"handle": "connector.runtime.profile.use", "summary": "Older profile action replaced by this field"}],
        "inspect_next": ["workflow.step_forms.profile_switch", "workflow.profile", "profile.name"],
    }),
    "workflow.step_forms.profile_switch": declare_human({
        "definition": "Named step form whose primary purpose is changing the profile for later work.",
        "use_when": ["One named step only needs to change to another declared profile."],
        "do_not_use_for": ["Operation calls or value-producing steps.", "A fixed profile that should apply from the workflow start; use workflow.profile."],
        "nearest_surfaces": [{"handle": "workflow.step.profile_switch", "summary": "Field that supplies the target profile"}, {"handle": "workflow.profile", "summary": "Fixed profile binding from the start"}, {"handle": "workflow.step.gate", "summary": "Optional condition before the profile change"}],
        "inspect_next": ["workflow.step.profile_switch", "workflow.profile", "workflow.step.gate"],
    }),
    "workflow.step_forms.result": declare_human({
        "definition": "Named step form that adds one resolved value to the workflow result list.",
        "use_when": ["The step emits one final result value rather than storing an intermediate value or publishing named output."],
        "do_not_use_for": ["An intermediate value needed by later steps; use workflow.step.value with register.", "Named output for callers; use workflow.step_forms.publish."],
        "nearest_surfaces": [{"handle": "workflow.step.result", "summary": "Field that supplies the result value"}, {"handle": "workflow.step_forms.publish", "summary": "Form for named output"}, {"handle": "workflow.step_forms.value", "summary": "Form for an intermediate local value"}, {"handle": "workflow-rules.value_register_before_result", "summary": "Guidance for storing reusable values before emitting them"}],
        "inspect_next": ["workflow.step.result", "workflow.step_forms.publish", "workflow.step_forms.value", "workflow-rules.value_register_before_result"],
    }),
    "workflow.step_forms.publish": declare_human({
        "definition": "Named step form that publishes one named output payload for workflow callers.",
        "use_when": ["The step communicates caller-facing data such as summary fields, identifiers, or URLs."],
        "do_not_use_for": ["An intermediate value needed by later steps; use workflow.step_forms.value.", "One unnamed result-list value; use workflow.step_forms.result."],
        "nearest_surfaces": [{"handle": "workflow.step.publish", "summary": "Field that supplies the published payload"}, {"handle": "workflow.step_forms.result", "summary": "Form for result-list values"}, {"handle": "workflow.step_forms.value", "summary": "Form for intermediate local values"}, {"handle": "workflow-rules.publish_outputs", "summary": "Guidance for explicit published output"}],
        "inspect_next": ["workflow.step.publish", "workflow.step_forms.result", "workflow.step_forms.value", "workflow-rules.publish_outputs"],
    }),
    "workflow.step_forms.operation_call": declare_human({
        "definition": "Named step form that calls one published operation through uses.",
        "use_when": ["The step calls a published operation rather than a named workflow fragment or a short repeated body."],
        "do_not_use_for": ["A named workflow fragment; use workflow.step_forms.run_invocation.", "New launcher-based authoring; launcher is retained only for compatibility."],
        "effects": [
            "Author every operation call with `name` for the step identity and `uses` for the published operation.",
            "Use `if` to make the call optional, `gate` to admit the call, `with` to supply operation inputs, and `register` to retain its result for later steps.",
            "`launcher` remains available only to maintain an older launcher-based workflow; use routines or profile context for new setup.",
        ],
        "nearest_surfaces": [{"handle": "workflow.step.uses", "summary": "Field that selects the operation"}, {"handle": "workflow.step_forms.run_invocation", "summary": "Form for named workflow fragments"}, {"handle": "workflow.step.with", "summary": "Optional operation arguments"}],
        "inspect_next": ["workflow.step.uses", "workflow.step.with", "workflow.step_forms.run_invocation", "workflow.step.launcher"],
    }),
    "workflow.step_forms.run_invocation": declare_human({
        "definition": "Named step form that invokes a named workflow fragment through run.",
        "use_when": ["A step invokes a named workflow fragment rather than calling an operation.", "A reusable repeated body belongs behind a named target, optionally with for_each."],
        "do_not_use_for": ["Short local repeated work that is clearer as inline steps.", "Including source fragments before validation; use include for that."],
        "nearest_surfaces": [{"handle": "workflow.run.run", "summary": "Field that names the target"}, {"handle": "workflow.step_forms.inline_fan_out_invocation", "summary": "Form for short inline repeated work"}, {"handle": "workflow.step_forms.operation_call", "summary": "Form for published operations"}],
        "inspect_next": ["workflow.run.run", "workflow.run.with", "workflow.run.for_each", "workflow.step_forms.inline_fan_out_invocation"],
    }),
    "workflow.step_forms.inline_fan_out_invocation": declare_human({
        "definition": "Named step form that repeats one short inline step list for each item.",
        "use_when": ["A small local repeated body runs once per item without a separate named target.", "The body is short, has no fragment-specific guards, and does not need reuse."],
        "do_not_use_for": ["Large, reusable, or guarded repeated bodies; use a named run target.", "General loops or nested repetition outside this bounded form."],
        "nearest_surfaces": [{"handle": "workflow.run.for_each", "summary": "Field that supplies the items"}, {"handle": "workflow.run.steps", "summary": "Field that supplies the inline body"}, {"handle": "workflow.step_forms.run_invocation", "summary": "Form for named repeated targets"}],
        "inspect_next": ["workflow.run.for_each", "workflow.run.steps", "workflow.step_forms.run_invocation", "workflow-rules.run_target_vs_inline_fan_out"],
    }),
    "workflow.local_expression.filter": declare_human({
        "definition": "Pipeline helpers that transform, select, or check a value after choosing an expression root.",
        "use_when": ["You need short inline shaping such as projection, normalization, comparison, type checks, or collection helpers."],
        "do_not_use_for": ["Call-style helpers such as is_present(...) or format(...); use builtins.", "Reading structured text such as JSON, YAML, Markdown, or plain text; use the matching adapter."],
        "effects": [
            "Available filters: `lower`, `trim`, and `slug` turn one string into a string; `eq(value)`, `ne(value)`, `not`, `is_string`, `is_number`, `is_integer`, `is_boolean`, `in(values)`, and `not_found` produce a boolean.",
            "Use `field(name)` or `lookup(key)` to select from structured data; `only(field=value)` or `only(field!=value)`, `flatten`, `first`, `last`, and `unique` reshape JSON values; `length` produces a number. `catch(codes, fallback)` says which expected failure names to replace and which value to use instead, for example `value | catch([\"issue_not_found\"], null)`.",
        ],
        "nearest_surfaces": [{"handle": "workflow.local_expressions", "summary": "Workflow expression capability"}, {"handle": "workflow.local_expression.builtin", "summary": "Call-style expression helpers"}, {"handle": "workflow.local_expression.filter.lookup", "summary": "Filter for selecting a mapping value by key"}],
        "inspect_next": ["workflow.local_expression.filter.lookup", "workflow.local_expression.filter.only", "workflow.local_expression.builtin"],
    }),
    "workflow.local_expression.builtin": declare_human({
        "definition": "Call-style expression helpers for checks and formatting that do not read naturally as pipeline stages.",
        "use_when": ["A helper such as a presence check or formatter is clearer as a direct call."],
        "do_not_use_for": ["Ordinary shaping of one root value; use filters.", "Reading structured text; use the matching adapter."],
        "effects": ["Available builtins: `format(template, values...)` returns formatted text; `is_present(value)` and `is_missing(value)` return booleans."],
        "nearest_surfaces": [{"handle": "workflow.local_expressions", "summary": "Workflow expression capability"}, {"handle": "workflow.local_expression.filter", "summary": "Pipeline expression helpers"}, {"handle": "workflow.local_expression.builtin.is_present", "summary": "Helper for checking whether a value is present"}],
        "inspect_next": ["workflow.local_expression.builtin.is_present", "workflow.local_expression.builtin.is_missing", "workflow.local_expression.filter"],
    }),
    "workflow.local_expression.adapter_binding": declare_human({
        "definition": "Form for explicitly passing workflow values into an adapter expression with with{...}.",
        "use_when": ["An adapter expression needs workflow values before its own selector or action runs."],
        "do_not_use_for": ["Filters or builtins that can read the value directly.", "Writing bare workflow references inside adapter syntax."],
        "nearest_surfaces": [{"handle": "workflow.local_expression.adapter", "summary": "Choose an adapter family"}, {"handle": "workflow.local_expression.adapter_seam", "summary": "Rules for supplying workflow values and choosing read or update"}, {"handle": "workflow.local_expression.adapter.json", "summary": "JSON adapter family"}],
        "inspect_next": ["workflow.local_expression.adapter_seam", "workflow.local_expression.adapter.json", "workflow.local_expression.adapter"],
    }),
    "workflow.local_expression.adapter_seam": declare_human({
        "definition": "Shared authoring rules for supplying workflow values to an adapter and choosing whether it reads or changes the represented value.",
        "use_when": ["You need the common `with{...}` binding form or need to know whether the current expression may only read."],
        "do_not_use_for": ["Assuming each adapter family takes workflow values differently.", "Using a change expression where only a read is allowed, such as a guard."],
        "nearest_surfaces": [{"handle": "workflow.local_expression.adapter", "summary": "Choose an adapter family"}, {"handle": "workflow.local_expression.adapter_binding", "summary": "Form for supplying workflow values"}, {"handle": "workflow-rules.representation_adapters", "summary": "Guidance for choosing adapters"}],
        "inspect_next": ["workflow.local_expression.adapter_binding", "workflow.local_expression.adapter.json", "workflow-rules.representation_adapters"],
    }),
    "workflow.local_expression.adapter.json": declare_human({
        "definition": "Adapter family for selecting or updating JSON text by structure. `json.user.name with{root: inputs.body}` reads one nested value from the bound JSON text.",
        "use_when": ["The value is JSON text and structural selection or updates are clearer than inline parsing."],
        "do_not_use_for": ["Markdown, plain text, YAML, or key-value text; choose the matching adapter.", "Simple comparisons that do not need structured parsing."],
        "effects": ["Read selectors include `.field`, `..field`, `[n]`, `.one(field=value)`, and `.many(field=value)`; use `-> set(...)` only where an updated root value is allowed.", "Bind workflow values outside the adapter body: `json.user.name with{root: inputs.body}`."],
        "nearest_surfaces": [{"handle": "workflow.local_expression.adapter", "summary": "Adapter families"}, {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared adapter boundary"}, {"handle": "workflow.local_expression.adapter.yaml", "summary": "YAML adapter family"}],
        "inspect_next": ["workflow.local_expression.adapter.yaml", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
    }),
    "workflow.local_expression.adapter.key_value": declare_human({
        "definition": "Adapter family for interpreting key-value text supplied through an outer binding such as `key_value with{root: inputs.body}`.",
        "use_when": ["The value is key-value text and needs that format's interpretation instead of generic line parsing."],
        "do_not_use_for": ["JSON, YAML, Markdown, or ordinary plain text; choose the matching adapter."],
        "effects": ["This family currently has no extra selector or update action syntax; its usable form is the family invocation with `with{root: ...}`.", "It returns the interpreted key-value representation for downstream expression use."],
        "nearest_surfaces": [{"handle": "workflow.local_expression.adapter", "summary": "Adapter families"}, {"handle": "workflow.local_expression.adapter.text", "summary": "Plain-text adapter family"}, {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared adapter boundary"}],
        "inspect_next": ["workflow.local_expression.adapter.text", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
    }),
    "workflow.local_expression.adapter.markdown": declare_human({
        "definition": "Adapter family for selecting or changing Markdown sections, blocks, lists, and task lists.",
        "use_when": ["The value is Markdown and needs heading, block, list, or task-list meaning rather than string slicing."],
        "do_not_use_for": ["JSON, YAML, or plain text; choose the matching adapter."],
        "effects": ["Use markdown selectors such as `prelude`, `heading(...)`, `block(...)`, `list(...)`, or `tasks(...)`; actions include `add`, `replace`, and `remove` where updates are allowed.", "For example, bind source text with `markdown.heading(\"Release notes\") with{root: inputs.body}`."],
        "nearest_surfaces": [{"handle": "workflow.local_expression.adapter", "summary": "Adapter families"}, {"handle": "workflow.local_expression.adapter.text", "summary": "Plain-text adapter family"}, {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared adapter boundary"}],
        "inspect_next": ["workflow.local_expression.adapter.text", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
    }),
    "workflow.local_expression.adapter.text": declare_human({
        "definition": "Adapter family for selecting or changing plain text by line or substring.",
        "use_when": ["The value is plain text and line or substring selection is clearer than structured parsing."],
        "do_not_use_for": ["Markdown sections or lists, or JSON/YAML structure; choose the matching adapter."],
        "effects": ["Use selectors such as `lines`, `line(n)`, `before(text)`, `after(text)`, and `contains(text)`; supported updates include `add`, `replace`, and `remove` where writes are allowed.", "For example, `text.lines with{root: inputs.body}` reads the bound text as lines."],
        "nearest_surfaces": [{"handle": "workflow.local_expression.adapter", "summary": "Adapter families"}, {"handle": "workflow.local_expression.adapter.markdown", "summary": "Markdown adapter family"}, {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared adapter boundary"}],
        "inspect_next": ["workflow.local_expression.adapter.markdown", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
    }),
    "workflow.local_expression.adapter.yaml": declare_human({
        "definition": "Adapter family for selecting YAML values by structure while preserving YAML interpretation.",
        "use_when": ["The value is YAML text and structural selection should respect YAML meaning."],
        "do_not_use_for": ["JSON, Markdown, or plain text; choose the matching adapter."],
        "effects": ["Read selectors include `.field`, `[\"literal-key\"]`, `[n]`, `.one(field=value)`, and `.many(field=value)`.", "For example, `yaml.services.api.image with{root: inputs.compose_file}` reads a structured YAML value; this family has no update action."],
        "nearest_surfaces": [{"handle": "workflow.local_expression.adapter", "summary": "Adapter families"}, {"handle": "workflow.local_expression.adapter.json", "summary": "JSON adapter family"}, {"handle": "workflow.local_expression.adapter_seam", "summary": "Shared adapter boundary"}],
        "inspect_next": ["workflow.local_expression.adapter.json", "workflow.local_expression.adapter_binding", "workflow.local_expression.adapter"],
    }),
    "workflow.include_contract": declare_human({
        "definition": "Source-time reuse contract: `include` inserts a fragment before the assembled workflow is validated or run.",
        "use_when": ["The same authored block belongs in more than one workflow and should become ordinary workflow content before validation."],
        "do_not_use_for": ["Running an isolated workflow call later; use run for that run-time decision.", "Guessing fragment arguments from workflow inputs; fragments declare their own arguments."],
        "effects": ["Choose the fragment with `include`; use `with` only to supply that fragment's declared arguments.", "After insertion, the assembled workflow crosses the normal validation boundary and then executes as one workflow; include does not create a separate run, `if`, `gate`, repetition, or result capture boundary."],
        "nearest_surfaces": [{"handle": "workflow.include_fragments", "summary": "Include fragment reuse"}, {"handle": "workflow.include.include", "summary": "Field that names the fragment file"}, {"handle": "workflow.include.with", "summary": "Field that supplies fragment arguments"}, {"handle": "examples.include-args", "summary": "Complete include example with declared fragment arguments"}],
        "required_fields": ["include"], "optional_fields": ["with"], "inspect_next": ["workflow.include.include", "workflow.include.with", "workflow.fragment.args", "examples.include-args"],
    }),
    "workflow.include.include": declare_human({
        "definition": "Field that names a fragment file to insert before checking the workflow.",
        "use_when": ["A block should be replaced with reusable fragment content."],
        "do_not_use_for": ["Selecting a workflow to invoke later; use run or a playbook workflow entry."],
        "nearest_surfaces": [{"handle": "workflow.include_contract", "summary": "Include rules"}, {"handle": "workflow.include.with", "summary": "Field for fragment arguments"}, {"handle": "workflow.fragment.description", "summary": "Fragment purpose text"}],
        "examples": [{"reference": "workflow.include.include", "inputs": {"include": "fragments/check_issue.yaml"}}], "inspect_next": ["workflow.include.with", "workflow.fragment.args", "examples.include-plain"],
    }),
    "workflow.include.with": declare_human({
        "definition": "Field for supplying declared fragment arguments while the fragment is included.",
        "use_when": ["A fragment declares arguments and the caller supplies their values."],
        "do_not_use_for": ["Step arguments or workflow activation inputs.", "Values that should wait until a named workflow invocation."],
        "nearest_surfaces": [{"handle": "workflow.include_contract", "summary": "Include argument rules"}, {"handle": "workflow.fragment.args", "summary": "Fragment argument declarations"}, {"handle": "workflow.run.with", "summary": "Arguments for a named workflow invocation"}],
        "examples": [{"reference": "workflow.include.with", "inputs": {"issue_number": "${inputs.issue_number}"}}], "inspect_next": ["workflow.fragment.args", "examples.include-args", "workflow.run.with"],
    }),
    "workflow.fragment.args": declare_human({
        "definition": "Fragment metadata that declares local arguments available as args.name in the included body.",
        "use_when": ["A reusable fragment needs a small explicit input contract."],
        "do_not_use_for": ["Top-level workflow activation inputs.", "Assuming every caller value is available without declaring it."],
        "nearest_surfaces": [{"handle": "workflow.include.with", "summary": "Field that supplies fragment arguments"}, {"handle": "workflow.include_contract", "summary": "Include argument rules and defaults"}, {"handle": "workflow.inputs", "summary": "Workflow activation inputs"}],
        "inspect_next": ["workflow.include.with", "workflow.include_contract", "examples.include-args"],
    }),
    "workflow.fragment.description": declare_human({
        "definition": "Fragment metadata for a short explanation of the fragment's purpose.",
        "use_when": ["A reusable fragment needs a reader-facing purpose statement."],
        "do_not_use_for": ["Workflow behavior or activation inputs; this is documentation."],
        "nearest_surfaces": [{"handle": "workflow.include.include", "summary": "Field that selects the fragment"}, {"handle": "workflow.fragment.args", "summary": "Fragment argument declarations"}, {"handle": "examples.include-plain", "summary": "Example of a simple include"}],
        "inspect_next": ["workflow.fragment.args", "examples.include-plain", "workflow.include.include"],
    }),
    "workflow.step_forms.state_delete": declare_human({
        "definition": "Named step form that removes one bound state target.",
        "use_when": ["The step's primary job is removing durable state."],
        "do_not_use_for": ["Combining deletion with unrelated behavior.", "Cleaning up a local value that should not change durable state."],
        "nearest_surfaces": [{"handle": "workflow.step.state_delete", "summary": "Field that names the state target"}, {"handle": "state.workflow_surface.step_state_delete_field", "summary": "State guidance for the field"}, {"handle": "workflow.step_forms.state_set", "summary": "Form for writing state"}],
        "inspect_next": ["workflow.step.state_delete", "state.workflow_surface.step_state_delete_field", "workflow.step_forms.state_set"],
    }),
    "workflow.step_forms.value": declare_human({
        "definition": "Named step form that computes one local value and can register it for later use.",
        "use_when": ["The step produces a derived local value rather than calling an operation, changing durable state, or emitting final output."],
        "do_not_use_for": ["State changes; use state_set or state_delete.", "Final result or published output; use result or publish."],
        "nearest_surfaces": [{"handle": "workflow.step.value", "summary": "Field that supplies the local value"}, {"handle": "workflow.step.result", "summary": "Field for a final result"}, {"handle": "workflow.step.publish", "summary": "Field for named output"}],
        "inspect_next": ["workflow.step.value", "workflow.step.result", "workflow.step.publish"],
    }),
    "workflow.step_forms.state_set": declare_human({
        "definition": "Named step form that stores one value in one bound state target.",
        "use_when": ["The step's primary job is saving one durable state value."],
        "do_not_use_for": ["Several state writes in one step.", "Local value staging that should not become durable state."],
        "nearest_surfaces": [{"handle": "workflow.step.state_set", "summary": "Field that supplies the one target entry"}, {"handle": "workflow.state_needs", "summary": "Declare the state role before using it"}, {"handle": "workflow.state_bindings", "summary": "Bind the declared role to a playbook state location"}, {"handle": "state.workflow_surface.step_state_set_field", "summary": "State guidance for the field"}],
        "inspect_next": ["workflow.state_needs", "workflow.state_bindings", "workflow.step.state_set", "state_set.single_target_entry"],
    }),
    "workflow.inputs": declare_human({
        "definition": "Top-level field that declares the activation inputs a workflow accepts, requires, or gives defaults.",
        "use_when": ["The workflow needs an explicit caller request shape.", "Guards, steps, or results need named activation values."],
        "do_not_use_for": ["Fragment arguments; use workflow.fragment.args.", "Values owned by one playbook entry; use playbook.workflows.with."],
        "nearest_surfaces": [{"handle": "workflow.inputs_contract", "summary": "Input declaration and activation rules"}, {"handle": "playbook.workflows.with", "summary": "Values supplied by a playbook entry"}, {"handle": "command-line.ordo-playbook.flag.input", "summary": "One-run input override"}],
        "inspect_next": ["workflow.inputs_contract", "playbook.workflows.with", "command-line.ordo-playbook.flag.input"],
    }),
    "workflow.inputs_contract": declare_human({
        "definition": "Rules for declaring, accessing, validating, and rejecting workflow activation inputs.",
        "use_when": ["You need the required/default rules or unknown-input behavior at activation."],
        "do_not_use_for": ["Assuming undeclared caller keys are accepted.", "Treating input declaration as semantic validation; use guards when validation is needed."],
        "nearest_surfaces": [{"handle": "workflow.inputs", "summary": "Input declaration field"}, {"handle": "workflow-rules.input_validation_default", "summary": "Guidance for validating inputs"}, {"handle": "command-line.ordo-playbook.flag.input", "summary": "One-run input value"}],
        "inspect_next": ["workflow.inputs", "workflow-rules.input_validation_default", "command-line.ordo-playbook.flag.input"],
    }),
    "workflow.profile": declare_human({
        "definition": "Top-level field that fixes one declared profile for the workflow before guards run.",
        "use_when": ["A project-local workflow always starts with one profile.", "Guards and later steps need the same profile context from the start."],
        "do_not_use_for": ["Portable workflows where the caller or playbook selects the profile.", "A profile change later in the workflow; use workflow.step.profile_switch."],
        "nearest_surfaces": [{"handle": "workflow.step.profile_switch", "summary": "Later profile change"}, {"handle": "workflow-rules.workflow_profile_binding_is_project_local", "summary": "Guidance for the fixed-profile boundary"}, {"handle": "profile.name", "summary": "Declared profile name"}],
        "inspect_next": ["workflow.step.profile_switch", "workflow-rules.workflow_profile_binding_is_project_local", "profile.name"],
    }),
    "workflow.version": declare_human({
        "definition": "Required top-level marker for the workflow document format.",
        "use_when": ["Every workflow document declares its format version before its other fields."],
        "do_not_use_for": ["A business or release version for the workflow.", "The format version for a playbook or routine registry."],
        "nearest_surfaces": [{"handle": "playbook.version", "summary": "Playbook format marker"}, {"handle": "routine_contract.version", "summary": "Routine registry format marker"}, {"handle": "workflow.workflow", "summary": "Workflow name field"}],
        "examples": [{"reference": "workflow.version", "inputs": {"version": 0}}], "inspect_next": ["workflow.workflow", "playbook.version", "routine_contract.version"],
    }),
    "workflow.workflow": declare_human({
        "definition": "Required top-level field that gives the workflow its stable name.",
        "use_when": ["Every workflow document declares the name used to identify this workflow."],
        "do_not_use_for": ["Naming a playbook entry, profile, or description.", "Selecting another workflow to run; use a playbook entry or run."],
        "nearest_surfaces": [{"handle": "playbook.workflows.file", "summary": "Playbook field that points to a workflow file"}, {"handle": "profile.name", "summary": "Profile name field"}, {"handle": "workflow.version", "summary": "Workflow format marker"}],
        "examples": [{"reference": "workflow.workflow", "inputs": {"workflow": "set-active-task"}}], "inspect_next": ["workflow.version", "playbook.workflows.file", "profile.name"],
    }),
}


def _focused_surface(
    *, definition: str, use_when: str, details: list[str], boundary: str,
    related: list[dict[str, str]], inspect_next: list[str],
) -> HumanDeclaration:
    """Keep the repeated focused-guide structure separate from its authored facts."""

    return declare_human({
        "definition": definition,
        "use_when": [use_when],
        "effects": details,
        "do_not_use_for": [boundary],
        "nearest_surfaces": related,
        "inspect_next": inspect_next,
    })


WORKFLOW_ADDITIONAL_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    **{
        f"workflow.local_expression.filter.{name}": _focused_surface(
            definition=f"Pipeline filter `{syntax}` for {purpose}.",
            use_when=use_when,
            details=[f"Input: {input_type}. Result: {result}.", f"Write it as `{syntax}` after a value, for example `{example}`."],
            boundary=boundary,
            related=[
                {"handle": "workflow.local_expression.filter", "summary": "All pipeline filters and their place in an expression"},
                {"handle": "workflow.local_expression.builtin", "summary": "Call-style helpers for formatting and presence checks"},
            ],
            inspect_next=["workflow.local_expression.filter", "workflow.local_expression.builtin"],
        )
        for name, syntax, purpose, use_when, input_type, result, example, boundary in (
            ("eq", "eq(value)", "testing equality", "the selected value must be compared with one value", "any JSON value", "a boolean", "inputs.status | eq(\"ready\")", "Use `ne(value)` for an inequality test, not a general boolean expression."),
            ("ne", "ne(value)", "testing inequality", "the selected value must differ from one value", "any JSON value", "a boolean", "inputs.status | ne(\"closed\")", "Use `eq(value)` when equality is the intended condition."),
            ("field", "field(name)", "selecting one named object field", "an object has a known field to read", "an object", "that field's value", "inputs.issue | field(\"title\")", "Use `lookup(key)` when the key is itself a value or is not a fixed field name."),
            ("lookup", "lookup(key)", "selecting one mapping value by key", "a mapping key comes from the expression or needs an exact lookup", "an object or mapping", "the selected value", "inputs.labels | lookup(\"ready\")", "Use `field(name)` for a fixed object field; missing keys are errors unless handled deliberately."),
            ("first", "first", "taking the first item", "only the first item of a non-empty collection matters", "a list", "the first item", "inputs.labels | first", "Do not use it when every item must be considered."),
            ("last", "last", "taking the last item", "only the final item of a non-empty collection matters", "a list", "the last item", "inputs.labels | last", "Do not use it when order is not meaningful."),
            ("flatten", "flatten", "joining one level of nested lists", "a list contains lists that should become one list", "a list of lists", "one flattened list", "inputs.groups | flatten", "It flattens one collection shape; do not use it as a general recursive transform."),
            ("unique", "unique", "removing duplicate list values", "a list should retain each distinct value once", "a list", "a list without duplicates", "inputs.labels | unique", "Do not rely on it to sort values or choose a preferred item."),
            ("length", "length", "counting a string or collection", "a decision needs the number of characters or items", "a string, list, or object", "a number", "inputs.labels | length", "Use a comparison after it when the workflow needs a boolean decision."),
            ("lower", "lower", "normalizing text to lowercase", "case-insensitive text comparison needs one normalized value", "a string", "a lowercase string", "inputs.status | lower", "It changes case only; trim surrounding whitespace separately when needed."),
            ("trim", "trim", "removing surrounding whitespace", "text needs leading and trailing whitespace removed", "a string", "a trimmed string", "inputs.title | trim", "It does not change whitespace inside the text."),
            ("slug", "slug", "making a slug from text", "a compact identifier is needed from a text value", "a string", "a slug string", "inputs.title | slug", "Do not use it when the original human-readable text must be preserved."),
            ("not", "not", "negating a boolean", "a boolean decision must be reversed", "a boolean", "a boolean", "inputs.enabled | not", "Use it only with boolean input, not to test whether a value is absent."),
            ("is_string", "is_string", "checking a value's string type", "a condition needs to distinguish string input", "any JSON value", "a boolean", "inputs.value | is_string", "Use it as a type check, not as text validation."),
            ("is_number", "is_number", "checking a value's numeric type", "a condition needs to distinguish numeric input", "any JSON value", "a boolean", "inputs.value | is_number", "It accepts numeric values; use `is_integer` when whole-number meaning matters."),
            ("is_integer", "is_integer", "checking a value's whole-number type", "a condition needs an integer rather than any number", "any JSON value", "a boolean", "inputs.value | is_integer", "Use `is_number` when decimal numbers are also valid."),
            ("is_boolean", "is_boolean", "checking a value's boolean type", "a condition needs to distinguish true or false values", "any JSON value", "a boolean", "inputs.value | is_boolean", "Do not use it to coerce text such as \"true\" into a boolean."),
            ("in", "in(values)", "checking membership", "one value must be tested against an explicit collection", "any JSON value", "a boolean", "inputs.status | in([\"ready\", \"queued\"])", "Use `only(...)` to select matching collection entries rather than test one value."),
            ("only", "only(field=value)", "selecting matching collection entries", "a list of objects needs a simple equality or inequality filter", "a list of objects", "the matching list entries", "inputs.items | only(state=\"ready\")", "Only `field=value` and `field!=value` predicates are supported; use a named value for more complex selection."),
            ("not_found", "not_found", "turning a missing lookup into an absence decision", "a strict probe lookup should become a boolean absence check", "a lookup result or expected lookup failure", "a boolean", "probe.issue(...) | not_found", "Use `catch(...)` when an expected failure needs a fallback value other than a boolean."),
        )
    },
    "workflow.local_expression.filter.catch": declare_human({
        "definition": "Fallback filter for an expected expression failure. `catch(codes, fallback)` lists the failure names to handle, then returns `fallback` instead of that failure.",
        "use_when": ["A missing or expected lookup should produce a clear ordinary value for a later decision rather than stop the workflow."],
        "do_not_use_for": ["Hiding every failure with a broad fallback. List only the expected failure names so unexpected failures remain visible.", "Replacing an ordinary boolean check that can be written directly."],
        "effects": ["For example, `value | catch([\"issue_not_found\"], false)` turns an expected missing issue into `false`; other failures still stop the expression."],
        "nearest_surfaces": [{"handle": "workflow.local_expression.filter.not_found", "summary": "Turn a strict lookup into an absence boolean when that is the only decision needed"}, {"handle": "workflow.local_expression.filter", "summary": "Other pipeline transformations"}],
        "inspect_next": ["workflow.local_expression.filter.not_found", "workflow.local_expression.filter"],
    }),
    **{
        f"workflow.local_expression.builtin.{name}": _focused_surface(
            definition=f"Call-style builtin `{syntax}` for {purpose}.", use_when=use_when,
            details=[result, f"Example: `{example}`."], boundary=boundary,
            related=[{"handle": "workflow.local_expression.filter", "summary": "Pipeline transformations for a selected value"}],
            inspect_next=["workflow.local_expression.filter", "workflow.local_expressions"],
        )
        for name, syntax, purpose, use_when, result, example, boundary in (
            ("format", "format(template, values...)", "building formatted text", "a readable string combines a template with one or more values", "It returns formatted text.", "format(\"task/{0}\", inputs.issue_number)", "Use a filter when transforming one already-selected value."),
            ("is_present", "is_present(value)", "checking whether a value is present", "optional input or data must be tested before use", "It returns true for a present value and false for a missing one.", "is_present(inputs.close_comment)", "Use `is_missing(value)` when the positive condition is absence."),
            ("is_missing", "is_missing(value)", "checking whether a value is absent", "a workflow should take a path only when a value is absent", "It returns true for a missing value and false for a present one.", "is_missing(inputs.assignee)", "Use `is_present(value)` when the positive condition is presence."),
        )
    },
    **{
        f"workflow.run.{name}": _focused_surface(
            definition=definition, use_when=use_when, details=details, boundary=boundary,
            related=related, inspect_next=inspect_next,
        )
        for name, definition, use_when, details, boundary, related, inspect_next in (
            ("run", "Required `run` field that names the workflow target called by this step", "a named reusable target should run at runtime", ["Form: `name` + `run`, with optional `with`, `if`, `gate`, `for_each`, and `register`.", "The target receives only explicit `with` bindings as `args.name`."], "Use `steps` with `for_each` for a short local repeated body instead of inventing a target.", [{"handle": "workflow.run.with", "summary": "Explicit target arguments"}, {"handle": "workflow.run.steps", "summary": "Inline repeated-body alternative"}], ["workflow.run.with", "workflow.run.steps", "workflow.step_forms.run_invocation"]),
            ("with", "Optional `with` field that passes named values to a `run` target", "the target needs caller values", ["Form: an object of named values; the target reads them as `args.name`.", "Bindings are evaluated in the caller before the target begins."], "It is for named `run` targets, not source-time include arguments or an inline `steps` body.", [{"handle": "workflow.run.run", "summary": "The target that receives these values"}, {"handle": "workflow.include.with", "summary": "Source-time fragment arguments"}], ["workflow.run.run", "workflow.include.with"]),
            ("for_each", "Optional `for_each` field that repeats a named target or inline body once per item", "one invocation-shaped step needs bounded fan-out", ["Its value must resolve to an array; each iteration exposes `item` to its inner work.", "It requires either `run` or `steps`."], "Nested fan-out and guards inside the repeated body are not supported.", [{"handle": "workflow.run.run", "summary": "Named repeated target"}, {"handle": "workflow.run.steps", "summary": "Short inline repeated body"}], ["workflow.run.run", "workflow.run.steps", "workflow-rules.fan_out_scope_and_conditions"]),
            ("steps", "Inline `steps` field for a short repeated body", "small local work should repeat without a named target", ["Form: a list of steps paired with `for_each`.", "Each inner step runs once for the current `item`."], "It cannot stand alone and should not hold large, reusable, or guarded work.", [{"handle": "workflow.run.for_each", "summary": "Required item source"}, {"handle": "workflow.run.run", "summary": "Named-target alternative"}], ["workflow.run.for_each", "workflow.run.run", "workflow.step_forms.inline_fan_out_invocation"]),
            ("if", "Optional `if` field for skipping an otherwise valid invocation", "one invocation is locally optional", ["Accepts a local boolean expression, a list meaning all conditions, or `all`, `any`, and `not` objects.", "It is evaluated once before fan-out begins."], "Use a guard for workflow applicability and `gate` when the question is admission to protected work.", [{"handle": "workflow.run.gate", "summary": "Admission rather than optionality"}, {"handle": "workflow.step.if", "summary": "The same local branching role on a step"}], ["workflow.run.gate", "workflow.step.if", "workflow-rules.separate_control_surfaces"]),
            ("gate", "Optional `gate` field for deciding whether protected invocation work may proceed", "earlier facts admit or block the whole invocation", ["Accepts the same expression, list, and `all`/`any`/`not` condition forms as `if`.", "A structured gate may include `on_fail` context, evaluated only when it blocks."], "A gated invocation cannot also use `register`; split admission and result capture into separate steps.", [{"handle": "workflow.run.if", "summary": "Optional local branching"}, {"handle": "workflow.step_forms.gate_checkpoint", "summary": "Standalone gate checkpoint"}], ["workflow.run.if", "workflow.step_forms.gate_checkpoint", "workflow-rules.separate_control_surfaces"]),
            ("register", "Optional `register` field that names the invocation's result for later steps", "later work needs the result or fan-out aggregate", ["Form: one literal name.", "For fan-out, it contains the outer aggregate; inner registers remain local to each iteration."], "Do not combine it with `gate` on the same step.", [{"handle": "workflow.run.gate", "summary": "Admission must be a separate step"}, {"handle": "workflow.step.register", "summary": "Step result binding"}], ["workflow.run.gate", "workflow.step.register", "workflow-rules.fan_out_scope_and_conditions"]),
        )
    },
    **{
        f"workflow.step.{name}": _focused_surface(
            definition=definition, use_when=use_when, details=details, boundary=boundary,
            related=related, inspect_next=inspect_next,
        )
        for name, definition, use_when, details, boundary, related, inspect_next in (
            ("name", "Required `name` field that gives a step its stable local identity", "every step needs an unambiguous name", ["Form: one literal string, unique in its surrounding step list.", "Later diagnostics and step references use this identity."], "It identifies a step; it does not select the step form or publish a result.", [{"handle": "workflow.step.register", "summary": "Name for a reusable result"}, {"handle": "workflow.step_forms.operation_call", "summary": "One form that requires a step name"}], ["workflow.step.register", "workflow.step_forms.operation_call"]),
            ("uses", "Required `uses` field for an operation-call step", "the step calls one published operation", ["Form: a literal operation reference such as `gh.issue`.", "Optional `with` supplies inputs and `register` retains the result for later steps."], "Use `run` for a named workflow or routine target, not for operation selection.", [{"handle": "workflow.step.with", "summary": "Operation inputs"}, {"handle": "workflow.step.run", "summary": "Named workflow target"}], ["workflow.step.with", "workflow.step.register", "workflow.step_forms.operation_call"]),
            ("with", "Optional `with` field for operation or named-run inputs", "a selected operation or run target needs explicit values", ["Form: an object whose string values may be local expressions.", "It is allowed only with `uses` or `run`."], "Use `include.with` for source-time fragment arguments, not this runtime field.", [{"handle": "workflow.step.uses", "summary": "Operation that receives these values"}, {"handle": "workflow.step.run", "summary": "Run target that receives these values"}], ["workflow.step.uses", "workflow.step.run", "workflow.include.with"]),
            ("run", "Required `run` field for a named workflow invocation", "a reusable target should execute as one explicit call", ["Form: `name` + `run`; optional `with`, `if`, `gate`, `for_each`, and `register` refine it.", "The callee sees only explicit bindings through `args.name`."], "Use `steps` with `for_each` for a short inline repeated body.", [{"handle": "workflow.step.steps", "summary": "Inline repeated-body alternative"}, {"handle": "workflow.step_forms.run_invocation", "summary": "Required and optional run form fields"}], ["workflow.step.steps", "workflow.step.with", "workflow.step_forms.run_invocation"]),
            ("for_each", "Required fan-out field for an inline repeated body and optional field for a named run", "one invocation-shaped step repeats over selected items", ["Its value must resolve to an array and each inner body sees `item`.", "Inline `steps` requires it; it must be paired with `run` or `steps`."], "Nested fan-out is not an available workflow form.", [{"handle": "workflow.step.steps", "summary": "Inline body paired with this source"}, {"handle": "workflow.step.run", "summary": "Named repeated target"}], ["workflow.step.steps", "workflow.step.run", "workflow-rules.fan_out_scope_and_conditions"]),
            ("steps", "Required inline body field for an inline fan-out step", "short local work should run once for each `for_each` item", ["Form: `name`, `for_each`, and a list of inner `steps`.", "Inner steps may use `item`; their registers are local to each iteration."], "Use a named `run` target for reusable, large, or guarded repeated work.", [{"handle": "workflow.step.for_each", "summary": "Required item source"}, {"handle": "workflow.step.run", "summary": "Named-target alternative"}], ["workflow.step.for_each", "workflow.step.run", "workflow.step_forms.inline_fan_out_invocation"]),
            ("if", "Optional `if` field for local branching inside an already-valid path", "one step should be skipped when its boolean condition is false", ["It accepts a local boolean expression, a list meaning all conditions, or an `all`, `any`, or `not` object.", "It changes local behavior without changing workflow applicability."], "Use guards for applicability and `gate` when the question is whether protected work may proceed.", [{"handle": "workflow.step.gate", "summary": "Admission control"}, {"handle": "workflow.branching", "summary": "How guards, gates, and if differ"}], ["workflow.step.gate", "workflow.branching", "workflow-rules.separate_control_surfaces"]),
            ("gate", "Optional `gate` field for admitting or blocking protected step work", "earlier facts determine whether a path may run at all", ["It accepts the same expression, list, and `all`/`any`/`not` forms as `if`.", "A structured gate may provide `on_fail` details only when the gate blocks."], "A gate and `register` cannot share a step; use a gate checkpoint followed by a result-producing step.", [{"handle": "workflow.step.if", "summary": "Optional local behavior"}, {"handle": "workflow.step_forms.gate_checkpoint", "summary": "Standalone admission checkpoint"}], ["workflow.step.if", "workflow.step_forms.gate_checkpoint", "workflow-rules.separate_control_surfaces"]),
            ("result", "Required `result` field for a result-emission step", "one final value belongs in the workflow's ordered result list", ["Form: `name` + `result`.", "The resolved value is emitted; it does not create a reusable step binding."], "Use `value` with `register` when later steps also need the value, or `publish` for named caller output.", [{"handle": "workflow.step.value", "summary": "Reusable intermediate value"}, {"handle": "workflow.step.publish", "summary": "Named caller output"}], ["workflow.step.value", "workflow.step.publish", "workflow.step_forms.result"]),
            ("publish", "Required `publish` field for a named caller-facing output", "the workflow must communicate a deliberate payload to its caller", ["Form: `name` + `publish` with an expression or object payload.", "Only the supplied fields become the published output."], "Use `result` for one ordered result value and `value` for an intermediate local value.", [{"handle": "workflow.step.result", "summary": "Ordered result-list output"}, {"handle": "workflow.step.value", "summary": "Intermediate local value"}], ["workflow.step.result", "workflow.step.value", "workflow.step_forms.publish"]),
        )
    },
    "workflow.blocks": _focused_surface(
        definition="Organize a workflow into readable named areas of work with the optional top-level `blocks` field",
        use_when="a workflow needs readable ordered areas of work",
        details=["A block is exactly one of `guards`, `steps`, or `include` (with optional include `with`).", "Blocks organize authored flow; guards decide applicability and step fields decide local behavior."],
        boundary="Blocks do not create a new scope or implicit control-flow boundary.",
        related=[{"handle": "workflow.include_contract", "summary": "Include block form"}, {"handle": "workflow.branching", "summary": "Explicit decision surfaces"}],
        inspect_next=["workflow.include_contract", "workflow.branching", "workflow.step_forms.operation_call"],
    ),
    "workflow.branching": _focused_surface(
        definition="Authoring guide for the three explicit decision roles: guards, `gate`, and `if`",
        use_when="a workflow decision needs the smallest clear control surface",
        details=["Guards reject an inapplicable workflow before work starts; `gate` admits or blocks protected work; `if` makes one local step optional.", "`if` and `gate` accept a boolean expression, a list meaning all conditions, or `all`, `any`, and `not` objects."],
        boundary="Do not use `if` as a hidden applicability check or `gate` merely to make ordinary local work optional.",
        related=[{"handle": "workflow.step.if", "summary": "Local optional behavior"}, {"handle": "workflow.step.gate", "summary": "Protected-work admission"}],
        inspect_next=["workflow.step.if", "workflow.step.gate", "workflow-rules.separate_control_surfaces"],
    ),
    "workflow.let": _focused_surface(
        definition="Optional top-level `let` mapping for named workflow-local expressions",
        use_when="an important expression is repeated or needs a meaningful name",
        details=["Each mapping value is a local expression available to later guards and steps as `let.name`.", "Keep the binding descriptive and use it to avoid repeated inline transformation."],
        boundary="Do not name a one-off trivial expression when the extra indirection makes the workflow harder to read.",
        related=[{"handle": "workflow.local_expressions", "summary": "Available expression roots and helpers"}, {"handle": "workflow.branching", "summary": "Conditions that can use named values"}],
        inspect_next=["workflow.local_expressions", "workflow.branching"],
    ),
    "workflow.run_contract": declare_human({
        "definition": "Run-time invocation contract: a step uses `run` to call a named target after the workflow has passed validation and started. Use it to repeat the same workflow work for each selected item without losing explicit inputs and results.",
        "use_when": ["A named target needs explicit `with` inputs, optional `if` behavior, admission through `gate`, result capture through `register`, or `for_each` repetition across selected items.", "A small repeated body is clearer inline: use `for_each` with `steps` instead of a named target."],
        "do_not_use_for": ["Source-time insertion of reusable authored content; use include before validation.", "An ordinary non-repeated local step that does not need an invocation boundary."],
        "effects": ["Use `run` for a named target and `with` for its inputs. `if` skips optional work; `gate` admits or blocks the protected work; `register` preserves the invocation result for later steps.", "Use `for_each` to repeat a named target or a small inline `steps` body. Keep a larger, guarded, or reusable repeated body behind a named target."],
        "nearest_surfaces": [{"handle": "workflow.include_contract", "summary": "Source-time fragment insertion before validation"}, {"handle": "workflow.run.run", "summary": "Named run target"}, {"handle": "workflow.run.with", "summary": "Invocation inputs"}, {"handle": "workflow.run.for_each", "summary": "Bounded repetition"}, {"handle": "examples.run-fan-out", "summary": "Complete named-target and inline repetition example"}],
        "inspect_next": ["workflow.run.run", "workflow.run.with", "workflow.run.for_each", "workflow.run.steps", "examples.run-fan-out"],
    }),
    "workflow.step_forms.gate_checkpoint": _focused_surface(
        definition="Step form with required `name` and `gate` and optional `if`",
        use_when="admission must be checked separately before later result-producing work",
        details=["It has no operation or value body: a passing gate permits the following path.", "Use its structured `on_fail` context to explain a blocked path."],
        boundary="It does not register a result; follow it with a separate step when a result is needed.",
        related=[{"handle": "workflow.step.gate", "summary": "Admission condition field"}, {"handle": "workflow.step.if", "summary": "Optional local branching"}],
        inspect_next=["workflow.step.gate", "workflow.step.if", "workflow-rules.separate_control_surfaces"],
    ),
    "workflow.value_expression_root.args": _focused_surface(
        definition="Local-expression root `args` for values explicitly passed to a named run target",
        use_when="a reusable target needs one of its caller-supplied arguments",
        details=["Read a value as `args.name` inside the target.", "The caller supplies it through the run step's `with` mapping."],
        boundary="Use `inputs.name` for workflow activation input, not `args.name`.",
        related=[{"handle": "workflow.run.with", "summary": "Caller bindings that create args values"}, {"handle": "workflow.inputs", "summary": "Workflow activation inputs"}],
        inspect_next=["workflow.run.with", "workflow.inputs"],
    ),
}

for _name, _definition, _boundary, _related in (
    ("workflow_fragment.no_state_surface", "Included fragments share their caller workflow's state declarations and bindings.", "Declare state needs on the assembled workflow, not inside a reusable fragment.", "workflow.state_needs"),
    ("workflow_state_role.write_after_last_read", "A state role must be read for the last time before a step writes or deletes it.", "Reorder the steps instead of relying on an earlier value after the mutation.", "workflow.step.state_set"),
    ("workflow_state_storage.relevant_identity_required", "State ordering can be checked only after the target storage identity is known.", "Provide the role, profile, key, and field facts needed to identify the storage target.", "workflow.state_bindings"),
    ("workflow_state_storage.write_after_last_read", "All reads of one storage target must precede its write or deletion.", "Split or reorder steps when one value is needed both before and after a mutation.", "workflow.step.state_delete"),
    ("workflow_step.exactly_one_form", "Every step chooses one primary body: uses, run, inline steps, profile switch, value, result, publish, state set, or state delete.", "Use a standalone gate checkpoint when admission needs no body; otherwise split unrelated work into named steps.", "workflow.step_forms.operation_call"),
    ("workflow_step.gate_conflicts_with_register", "A gated step cannot also register a result because blocked work has no result to bind.", "Place the gate in a checkpoint step and register the later admitted work.", "workflow.step_forms.gate_checkpoint"),
    ("workflow_step.if_conflicts_with_register", "A conditionally skipped step cannot promise a registered result on every path.", "Split optional work from the later step that requires a guaranteed result.", "workflow.step.if"),
    ("workflow_step.launcher_requires_uses", "The compatibility-only launcher field is valid only on an operation step with `uses`.", "Use a routine or profile context for new setup rather than adding launcher to another form.", "workflow.step_forms.operation_call"),
    ("workflow_step.register_requires_uses", "A registered operation result requires an operation step selected by `uses`.", "Use the run form when registering a named invocation result, or value for a local computed value.", "workflow.step.uses"),
    ("workflow_step.with_requires_uses", "Step `with` supplies an operation or named-run invocation and cannot stand alone.", "Pair it with `uses` or `run`; use `include.with` for source-time fragment arguments.", "workflow.step.with"),
):
    WORKFLOW_ADDITIONAL_FOCUSED_DESCRIBE_HUMAN[_name] = _focused_surface(
        definition=_definition,
        use_when="checking a workflow shape against this authoring boundary",
        details=["Correct the authored form before the workflow runs."],
        boundary=_boundary,
        related=[{"handle": _related, "summary": "Related authoring surface"}],
        inspect_next=[_related],
    )

WORKFLOW_CONTRACT: JSONObject = {
    "document_kind": "workflow",
    "version": 0,
    "top_level_fields": [
        {"name": "version", "required": True, "type": "integer"},
        {"name": "workflow", "required": True, "type": "string"},
        {
            "name": "profile",
            "required": False,
            "type": "string",
            "authoring_role": "workflow_owned_execution_profile_binding",
            "activation_timing": "before_guard_evaluation",
            "applicability": "internal_project_bound_workflows_only",
        },
        {
            "name": "inputs",
            "required": False,
            "type": "object",
            "authoring_role": "declares_global_activation_inputs",
            "activation_requirement": "per_input_required_or_default_semantics",
            "unknown_input_policy": "reject_unknown_inputs",
        },
        {
            "name": "let",
            "required": False,
            "type": "object",
            "authoring_role": "declares_workflow_local_named_expressions",
        },
        {"name": "state_needs", "required": False, "type": "object"},
        {"name": "blocks", "required": False, "type": "array"},
    ],
    "inputs_contract": {
        "scope": "global",
        "access_surface": "inputs.name",
        "declaration_shape": "mapping",
        "declaration_fields": [
            {"name": "required", "required": False, "type": "boolean", "authoring_role": "input_requiredness", "default_when_omitted": True},
            {"name": "default", "required": False, "type": "json", "authoring_role": "input_default_value", "runtime_effect": "applies_when_input_is_missing"},
            {"name": "description", "required": False, "type": "string", "authoring_role": "input_meaning"},
            {"name": "hint", "required": False, "type": "string", "authoring_role": "input_guidance", "validation_effect": "none"},
        ],
        "declared_keys_required_at_activation": False,
        "requiredness_surface": "per_input_required_field",
        "default_semantics": {
            "default_makes_input_optional": True,
            "legacy_scalar_shorthand_supported": True,
            "legacy_empty_object_shorthand_required": True,
        },
        "rejects_unknown_activation_inputs": True,
        "empty_string_is_distinct_value": True,
        "null_is_distinct_from_missing": True,
        "validated_by": "runtime",
    },
    "include_contract": {
        "directive_field": "include",
        "authoring_role": "workflow_fragment_reuse",
        "expansion_semantics": "resolve_bind_expand_whole_node_replacement",
        "targets": "files_only",
        "call_fields": [
            {"name": "include", "required": True, "type": "string"},
            {"name": "with", "required": False, "type": "object", "authoring_role": "fragment_argument_bindings"},
        ],
        "fragment_metadata_fields": [
            {"name": "description", "required": False, "type": "string"},
            {"name": "args", "required": False, "type": "object", "authoring_role": "declares_fragment_local_inputs"},
        ],
        "fragment_argument_declaration_forms": [
            {"name": "required_short_form", "shape": "arg_name: string_type_name"},
            {"name": "object_form", "shape": {"type": "string", "required": "boolean_optional", "default": "json_value_optional"}},
        ],
        "fragment_argument_access_surface": "args.name",
        "fragment_argument_default_semantics": {
            "default_makes_argument_optional": True,
            "default_null_is_valid": True,
            "omitted_argument_is_distinct_from_explicit_null_binding": True,
        },
        "state_scope": "global_across_assembled_workflow",
        "step_scope": "shared_across_assembled_workflow_after_include_expansion",
        "search_order": [
            "including_file_dir",
            "launch_dir",
            "launch_dir_dot_ordo",
            "home_dot_ordo",
            "built_in_includes_dir",
        ],
        "extension_probe_order": [".yaml", ".yml"],
        "stops_on_first_match": True,
        "cycle_detection": "current_expansion_stack",
        "max_depth": 32,
        "validation_boundary": "assembled_workflow_after_include_expansion_and_argument_binding",
        "error_codes": [
            "load.workflow.include.not_found",
            "load.workflow.include.cycle",
            "load.workflow.include.depth",
            "load.workflow.include.forbidden_path",
            "load.workflow.include.not_file",
            "load.workflow.include.with.type",
            "load.workflow.include.args.invalid_declaration",
            "load.workflow.include.args.missing",
            "load.workflow.include.args.unknown",
            "load.workflow.include.args.type",
        ],
    },
    "run_contract": {
        "directive_field": "run",
        "authoring_role": "workflow_fragment_invocation",
        "execution_semantics": "runtime_scoped_fragment_invocation",
        "surface_kind": "step_form",
        "body_forms": ["named_run_target", "inline_repeated_steps"],
        "call_fields": [
            {"name": "run", "required": True, "type": "string"},
            {"name": "steps", "required": False, "type": "array", "authoring_role": "inline_repeated_body"},
            {
                "name": "if",
                "required": False,
                "type": "condition",
                "authoring_role": "caller_scoped_invocation_condition",
                "surface": "expression_or_structured_condition",
                "structured_operators": ["all", "any", "not"],
                "list_semantics": "implicit_all",
            },
            {
                "name": "gate",
                "required": False,
                "type": "condition",
                "authoring_role": "caller_scoped_step_admission_condition",
                "surface": "expression_or_structured_condition",
                "structured_operators": ["all", "any", "not"],
                "list_semantics": "implicit_all",
                "structured_optional_fields": [
                    {
                        "name": "on_fail",
                        "type": "object",
                        "authoring_role": "gate_failure_diagnostic_context",
                        "value_surface": "step_local_read_only_expression_or_literal",
                        "evaluation_timing": "only_when_gate_verdict_is_failed",
                    }
                ],
            },
            {"name": "with", "required": False, "type": "object", "authoring_role": "fragment_argument_bindings"},
            {"name": "for_each", "required": False, "type": "runtime_value", "authoring_role": "bounded_fan_out_source"},
            {"name": "register", "required": False, "type": "string", "authoring_role": "aggregate_invocation_result"},
        ],
        "fragment_argument_access_surface": "args.name",
        "caller_scoped_condition_surface": ["inputs", "state", "step", "probe"],
        "caller_scoped_binding_surface": ["inputs", "state", "step", "probe"],
        "named_target_scope_boundary": "isolated_callee_scope",
        "named_target_callee_scope": {
            "direct_roots": ["inputs", "state", "args", "step", "probe"],
            "caller_step_scope": "not_directly_visible_inside_callee_body",
            "caller_data_transfer": "explicit_run_with_bindings_only",
            "step_scope": "callee_local_only",
            "let_scope": "callee_local_only",
        },
        "fan_out_surface": {
            "item_binding": "item",
            "outer_if_scope": "whole_invocation_step",
            "inner_if_scope": "per_iteration_inner_step",
            "inner_step_scope": ["inputs", "state", "step", "item", "probe"],
            "inner_register_scope": "iteration_local",
            "outer_register_scope": "aggregate_results",
            "forbidden_nested_surfaces": ["for_each", "guards"],
            "caller_step_scope": "not_directly_visible_inside_named_run_target_body",
        },
    },
    "block_forms": [
        {"name": "guard_block", "required_fields": ["guards"], "optional_fields": []},
        {"name": "step_block", "required_fields": ["steps"], "optional_fields": []},
        {"name": "include_block", "required_fields": ["include"], "optional_fields": ["with"]},
    ],
    "guard_forms": [
        {"name": "operation_call", "shape": {"uses": "string", "with": "object"}, "status": "compatibility_only"},
        {"name": "expression", "shape": "string", "status": "stable_preferred"},
    ],
    "step_form_rules": [
        {
            "name": "exactly_one_step_form",
            "kind": "exclusive_choice",
            "fields": ["uses", "run", "steps", "profile_switch", "value", "result", "publish", "state_set", "state_delete"],
            "message": "A workflow step must define exactly one of uses, run, steps, profile_switch, value, result, publish, state_set, or state_delete",
            "exception": "a standalone gate-only checkpoint step may omit a body form",
        },
        {
            "name": "with_requires_uses",
            "kind": "dependency",
            "field": "with",
            "requires": ["uses", "run"],
            "message": "The with field is allowed only together with uses or run",
        },
        {
            "name": "for_each_requires_invocation_body",
            "kind": "dependency",
            "field": "for_each",
            "requires": ["run", "steps"],
            "message": "The for_each field is allowed only together with run or inline steps",
        },
        {
            "name": "inline_steps_require_for_each",
            "kind": "dependency",
            "field": "steps",
            "requires": ["for_each"],
            "message": "Inline repeated step bodies require for_each",
        },
        {
            "name": "gate_forbids_register",
            "kind": "conflict",
            "fields": ["gate", "register"],
            "message": "A workflow step must not define both gate and register. Split this into a standalone gate checkpoint step followed by a separate step that declares register.",
        },
    ],
    "step_forms": [
        {
            "name": "operation_call",
            "required_fields": ["name", "uses"],
            "optional_fields": ["if", "gate", "with", "register", "launcher"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "with_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
            "deprecated_optional_fields": ["launcher"],
            "preferred_alternatives": {"launcher": "routine_or_profile_context"},
        },
        {
            "name": "run_invocation",
            "required_fields": ["name", "run"],
            "optional_fields": ["if", "gate", "with", "for_each", "register"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "with_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
            "for_each_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "inline_fan_out_invocation",
            "required_fields": ["name", "for_each", "steps"],
            "optional_fields": ["if", "gate", "register"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "for_each_value_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "profile_switch",
            "required_fields": ["name", "profile_switch"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
        },
        {
            "name": "value",
            "required_fields": ["name", "value"],
            "optional_fields": ["if", "gate", "register"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "value_expression_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "result",
            "required_fields": ["name", "result"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "value_expression_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "publish",
            "required_fields": ["name", "publish"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
            "value_expression_surface": "bare_first_quoted_string_literals_embedded_escape_hatch",
        },
        {
            "name": "state_set",
            "required_fields": ["name", "state_set"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
        },
        {
            "name": "state_delete",
            "required_fields": ["name", "state_delete"],
            "optional_fields": ["if", "gate"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
        },
        {
            "name": "gate_checkpoint",
            "required_fields": ["name", "gate"],
            "optional_fields": ["if"],
            "if_expression_surface": "native_local_expression_or_structured_condition_preferred_embedded_deprecated",
            "if_structured_operators": ["all", "any", "not"],
            "if_list_semantics": "implicit_all",
        },
    ],
    "surface_constraints": {
        "authored_surfaces": {
            "literal_only_fields": ["version", "workflow", "name", "uses", "run", "register", "launcher", "state_delete"],
            "literal_only_keyed_fields": ["state_set"],
            "native_condition_fields": ["let", "guards", "if", "gate"],
            "condition_field_forms": {
                "expression_string": "native_local_expression",
                "expression_embedded_string": "deprecated_compatibility",
                "structured_list": "implicit_all",
                "structured_object_operators": ["all", "any", "not"],
                "gate_structured_optional_fields": ["on_fail"],
            },
            "expression_first_value_fields": ["with", "value", "publish", "result", "for_each"],
            "expression_first_value_rules": {
                "plain_scalar_string": "local_expression",
                "quoted_string": "literal_string",
                "yaml_number_boolean_null": "native_literal",
                "nested_objects_and_lists": "recursive_leaf_rule",
                "embedded_escape_form": "${...}",
            },
        },
        "guard_expression": {
            "allowed_roots": ["inputs", "probe", "state"],
            "allowed_filters": list(_PUBLISHED_FILTERS),
            "allowed_builtins": list(_PUBLISHED_BUILTINS),
            "boolean_operators": ["and", "or", "not", "parentheses"],
            "representation_adapter_policy": {
                "read_only_allowed": True,
                "write_paths_forbidden": True,
                "forbidden_write_surface": "->...",
            },
            "result_contract": {
                "required_output_type": "boolean",
                "non_boolean_result": "error",
            },
        },
        "runtime_value_surface": {
            "allowed_roots": ["inputs", "args", "state", "step"],
            "allowed_builtins": list(_PUBLISHED_BUILTINS),
            "allowed_filters": list(_PUBLISHED_FILTERS),
            "boolean_operators": ["and", "or", "not", "parentheses"],
        },
    },
    "human": human_mapping(WORKFLOW_HUMAN),
}


def describe_workflow_contract_data() -> JSONObject:
    """Return a defensive copy of canonical workflow contract metadata."""

    return deepcopy(WORKFLOW_CONTRACT)


def workflow_focused_describe_human(handle: str) -> HumanDeclaration | None:
    """Return workflow-owned reader guidance for one focused describe handle."""

    return (WORKFLOW_FOCUSED_DESCRIBE_HUMAN | WORKFLOW_ADDITIONAL_FOCUSED_DESCRIBE_HUMAN).get(handle)
