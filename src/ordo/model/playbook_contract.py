"""Canonical contract metadata for playbook authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject
from .human import HumanDeclaration, declare_human, human_mapping


PLAYBOOK_FEATURE_HUMAN = declare_human({
    "title": "Playbook", "goal": "Choose a project-local catalog when workflows need shared launch context.",
    "summary": "Project-local catalog for named workflows and launch context.", "sections": [],
})
PLAYBOOK_HUMAN = declare_human({
    "title": "Playbook contract", "goal": "Publish the workflows, profiles, state locations, and defaults available in one project.",
    "summary": "Use a playbook as the project-local catalog and activation boundary for workflows.",
    "sections": [{"heading": "Use it for", "items": ["List workflows that callers can discover.", "Provide project-owned defaults and state bindings.", "Describe when a workflow is appropriate in the project catalog."]}, {"heading": "Related guidance", "references": [{"handle": "workflow.workflow", "summary": "Author the workflow body separately from its project catalog entry."}, {"handle": "command-line", "summary": "Run or inspect a published workflow through the public command line."}]}],
    "feature_clusters": {"playbook": {**human_mapping(PLAYBOOK_FEATURE_HUMAN), "use_when": ["A project needs a stable workflow catalog and shared defaults."], "avoid_when": ["The logic belongs inside one workflow body."]}},
})

# Focused field descriptions belong to the playbook contract, not a help renderer.
PLAYBOOK_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "playbook.defaults": declare_human({
        "definition": "Playbook field for launch-time defaults used when the caller and workflow entry did not choose a value.",
        "use_when": ["Several published workflows should share one default profile or working-directory policy without fixing it in each workflow body."],
        "do_not_use_for": ["Workflow-local behavior that must be fixed inside one workflow contract; use workflow.profile or workflow-owned fields.", "Per-workflow-entry overrides; use playbook.workflows.* when one published workflow needs a different launch setup."],
        "nearest_surfaces": [{"handle": "playbook.defaults.profile", "summary": "Child field for the default active profile"}, {"handle": "playbook.defaults.working_directory", "summary": "Child field for the default execution working directory"}, {"handle": "workflow.profile", "summary": "Workflow-owned fixed profile instead of a playbook launch default"}],
        "examples": [{"reference": "playbook.defaults", "inputs": {"profile": "review", "working_directory": "${inputs.repo_dir}"}}],
        "inspect_next": ["playbook.defaults.profile", "playbook.defaults.working_directory", "playbook.workflows"],
    }),
    "playbook.defaults.profile": declare_human({
        "definition": "Playbook default field for selecting the active profile when a run did not already choose one.",
        "use_when": ["Most published workflows in this playbook should start under one reusable profile unless the caller or entry overrides it."],
        "do_not_use_for": ["A fixed workflow-local profile; use workflow.profile when the workflow must always bind one profile before its guards run.", "One-run overrides; use --profile when the caller wants to override the default at launch time."],
        "nearest_surfaces": [{"handle": "playbook.defaults", "summary": "Parent playbook defaults object"}, {"handle": "command-line.ordo-playbook.flag.profile", "summary": "Launch-time override for one run"}, {"handle": "workflow.profile", "summary": "Workflow-owned fixed profile instead of a playbook launch default"}],
        "examples": [{"reference": "playbook.defaults.profile", "inputs": {"profile": "review"}}],
        "inspect_next": ["command-line.ordo-playbook.flag.profile", "workflow.profile", "profile.name"],
    }),
    "playbook.defaults.working_directory": declare_human({
        "definition": "Playbook default field for setting the execution working directory when no more specific launch setting provided one.",
        "use_when": ["Most published workflows should resolve relative paths from one shared default directory.", "The default directory depends only on launch inputs and should be computed before workflow execution starts."],
        "do_not_use_for": ["Workflow-entry-specific directory overrides; use playbook.workflows.working_directory when one published workflow needs a narrower default.", "Directory changes after the workflow has started; use a more local execution setting for that behavior."],
        "nearest_surfaces": [{"handle": "playbook.defaults", "summary": "Parent playbook defaults object"}, {"handle": "playbook.workflows.working_directory", "summary": "Per-workflow-entry override for the default execution directory"}, {"handle": "profile.working_directory", "summary": "Reusable profile-owned execution directory instead of a playbook-wide default"}],
        "examples": [{"reference": "playbook.defaults.working_directory", "inputs": {"working_directory": "${inputs.repo_dir}"}}],
        "inspect_next": ["playbook.workflows.working_directory", "profile.working_directory", "playbook.defaults"],
    }),
    "playbook.workflows": declare_human({
        "definition": "Playbook field for publishing the named workflow catalog that `ordo-playbook` can list, inspect, and run by workflow name.",
        "use_when": ["The project needs one stable launch catalog that maps public workflow names to workflow files and entry-owned launch details.", "Each published workflow should carry reader-facing discovery details such as description, category, when, working_directory, with, or state_bindings.", "`ordo-playbook workflows show <workflow>` presents the caller interface. Plain output shows inputs a caller may need to provide; `--json` retains the complete declaration. Showing a workflow does not run it or prove readiness."],
        "do_not_use_for": ["Workflow-internal guards, steps, branching, or dataflow; those belong inside the workflow file selected by the entry.", "Bootstrap workflows that must always run before the requested workflow; use playbook.pre_run for that separate launch stage."],
        "nearest_surfaces": [{"handle": "command-line.ordo-playbook", "summary": "Public command surface that lists and launches a named playbook workflow"}, {"handle": "playbook.pre_run", "summary": "Shared launch-time preparation before the requested workflow"}, {"handle": "playbook.workflows.file", "summary": "Required child field that binds each workflow name to a workflow file"}],
        "required_fields": ["file"], "optional_fields": ["with", "description", "category", "when", "working_directory", "state_bindings"],
        "related_examples": [{"reference": "examples.playbook-workflows", "inputs": {}}, {"reference": "playbook.workflows", "inputs": {"remember-profile": {"file": "./playbook-workflow-target.yaml", "description": "Read one remembered profile from shared state", "category": "inspect", "when": "Use when you need one state-backed profile lookup before choosing the next workflow.", "with": {"active_profile_key": "active_profile", "repo_dir": "."}, "working_directory": "${inputs.repo_dir}", "state_bindings": {"shared_state": "shared_state"}}}}],
        "inspect_next": ["command-line.ordo-playbook", "playbook.workflows.file", "playbook.workflows.with", "playbook.workflows.when"],
    }),
    "playbook.workflows.file": declare_human({
        "definition": "Workflow-entry field that points one published workflow name at the workflow file to load when selected.",
        "use_when": ["A named playbook workflow entry should resolve to one workflow document at launch time."],
        "do_not_use_for": ["Selecting the active workflow at the command line; callers choose the workflow name through ordo-playbook commands.", "Profile file selection or pre_run workflow selection; use playbook.profiles.file or playbook.pre_run.file."],
        "nearest_surfaces": [{"handle": "playbook.workflows", "summary": "Parent catalog that publishes named workflow entries"}, {"handle": "playbook.pre_run.file", "summary": "Field for the workflow that runs before the requested entry"}, {"handle": "playbook.profiles.file", "summary": "Field that points at a profile file instead of a workflow file"}],
        "related_examples": [{"reference": "playbook.workflows.file", "inputs": {"file": "./playbook-workflow-target.yaml"}}],
        "inspect_next": ["playbook.workflows.with", "playbook.pre_run.file", "playbook.profiles.file"],
    }),
    "playbook.workflows.with": declare_human({
        "definition": "Workflow-entry field for playbook-owned launch inputs for one published workflow, including required and optional caller placeholders.",
        "use_when": ["One published workflow should receive fixed entry-owned values, require caller-provided keys through `key:`, or allow optional caller-provided keys through `key?:`.", "The values belong to the catalog entry rather than to the reusable workflow contract or one operator invocation.", "Expose each declared input that the caller must provide through `key:`, or use `key?:` when the caller may provide it.", "A supplied value counts even when it is null, false, or zero. Command-line `--input` and `--input-file` values are per-run overrides.", "`workflows show <workflow>` presents caller-facing inputs in plain output; `--json` shows the complete entry declaration."],
        "do_not_use_for": ["Declaring which inputs exist; use workflow.inputs for the workflow's launch-input contract.", "Per-run overrides; use command-line.ordo-playbook.flag.input or command-line.ordo-playbook.flag.input_file when the caller supplies the value at launch time.", "Relaxing launch requirements: `x:` still requires caller input even with a default, and `x?:` does not make a required workflow input optional."],
        "nearest_surfaces": [{"handle": "workflow.inputs", "summary": "Workflow-owned declaration of valid launch inputs"}, {"handle": "playbook.pre_run.with", "summary": "Input setting for playbook-owned pre-run setup"}, {"handle": "command-line.ordo-playbook.flag.input", "summary": "One-run caller override that can replace an entry-owned input"}],
        "related_examples": [{"reference": "playbook.workflows.with", "inputs": {"active_profile_key": "active_profile", "repo_dir": ".", "issue_number": "caller_required", "close_comment": "caller_optional"}}],
        "inspect_next": ["workflow.inputs", "playbook.pre_run.with", "command-line.ordo-playbook.flag.input"],
    }),
    "playbook.workflows.description": declare_human({
        "definition": "Workflow-entry field for the short reader-facing summary of one published workflow in the catalog.",
        "use_when": ["Readers need a quick one-line explanation before deciding whether this workflow is the right choice."],
        "do_not_use_for": ["Step-by-step guidance or selection advice; use playbook.workflows.when when readers also need decision guidance.", "Replacing the workflow contract or launch details with prose alone."],
        "nearest_surfaces": [{"handle": "playbook.workflows.when", "summary": "Selection guidance rather than a short summary"}, {"handle": "playbook.workflows.category", "summary": "Catalog grouping label"}, {"handle": "playbook.workflows", "summary": "Parent catalog that publishes the workflow entry"}],
        "related_examples": [{"reference": "playbook.workflows.description", "inputs": {"description": "Read one remembered profile from shared state"}}],
        "inspect_next": ["playbook.workflows.when", "playbook.workflows.category", "command-line.ordo-playbook"],
    }),
    "playbook.workflows.category": declare_human({
        "definition": "Workflow-entry field for the catalog group label that clusters related published workflows in discovery output.",
        "use_when": ["Several published workflows belong to the same reader-facing family such as inspect, lifecycle, or collaboration, and the catalog should show that grouping.", "For graph display ties within a category, preserve playbook entry order. Dependencies take precedence; category creates neither graph links nor execution order."],
        "do_not_use_for": ["Workflow applicability, permissions, or step behavior; category is discovery information only and has no runtime effect.", "Replacing the entry summary or selection guidance; pair category with description and when when the label alone is too vague."],
        "nearest_surfaces": [{"handle": "playbook.workflows.description", "summary": "Field that explains what the entry does"}, {"handle": "playbook.workflows.when", "summary": "Field that explains when to choose the entry"}, {"handle": "playbook.workflows", "summary": "Parent workflow catalog that publishes grouped entries"}],
        "related_examples": [{"reference": "playbook.workflows.category", "inputs": {"category": "inspect"}}],
        "inspect_next": ["playbook.workflows.description", "playbook.workflows.when", "command-line.ordo-playbook"],
    }),
    "playbook.workflows.when": declare_human({
        "definition": "Workflow-entry field for guidance on when this published workflow is the right one to run.",
        "use_when": ["A short summary is not enough and the catalog should also explain the decision context for choosing this workflow."],
        "do_not_use_for": ["Workflow guards or enforced applicability; when is guidance for people, not a runtime rule.", "Category-style labels or terse summaries; keep those in category and description."],
        "nearest_surfaces": [{"handle": "playbook.workflows.description", "summary": "Summary of what the entry does"}, {"handle": "playbook.workflows.category", "summary": "Grouping label for the catalog family"}, {"handle": "command-line.ordo-playbook", "summary": "Command surface that presents the workflow catalog"}],
        "related_examples": [{"reference": "playbook.workflows.when", "inputs": {"when": "Use when you need one state-backed profile lookup before choosing the next workflow."}}],
        "inspect_next": ["playbook.workflows.description", "command-line.ordo-playbook", "workflow-rules.early_guards"],
    }),
    "playbook.workflows.working_directory": declare_human({
        "definition": "Workflow-entry field for overriding one published workflow's execution working directory before it starts.",
        "use_when": ["One published workflow should resolve relative files from a narrower directory than the playbook-wide or profile-wide default.", "The directory depends only on launch inputs and should be computed before workflow steps execute."],
        "do_not_use_for": ["Directory changes after the workflow has started; use a more local execution setting.", "Reading step outputs or state to choose the directory; this launch-time field only allows launch-input expressions."],
        "nearest_surfaces": [{"handle": "playbook.defaults.working_directory", "summary": "Playbook-wide default directory when no entry override is needed"}, {"handle": "profile.working_directory", "summary": "Reusable profile-owned execution directory"}, {"handle": "playbook.workflows.with", "summary": "Entry-owned launch inputs referenced by the directory expression"}],
        "related_examples": [{"reference": "playbook.workflows.working_directory", "inputs": {"working_directory": "${inputs.repo_dir}"}}],
        "inspect_next": ["playbook.defaults.working_directory", "profile.working_directory", "playbook.workflows.with"],
    }),
    "playbook.workflows.state_bindings": declare_human({
        "definition": "Workflow-entry field for binding the requested workflow's state roles to named playbook state locations at launch time.",
        "use_when": ["One published workflow needs explicit durable state access and the catalog entry should own that binding rather than repeating it for each caller."],
        "do_not_use_for": ["Declaring which state roles the workflow needs; use workflow.state_needs for that workflow contract.", "State bindings only for bootstrap preparation; use playbook.pre_run.state_bindings when the binding belongs to pre_run."],
        "nearest_surfaces": [{"handle": "workflow.state_bindings", "summary": "Workflow surface for a state-role binding inside workflow source"}, {"handle": "playbook.pre_run.state_bindings", "summary": "Binding setting only for pre-run setup"}, {"handle": "playbook.states", "summary": "Catalog of state locations that entry bindings may target by name"}],
        "related_examples": [{"reference": "playbook.workflows.state_bindings", "inputs": {"shared_state": "shared_state"}}],
        "inspect_next": ["workflow.state_bindings", "playbook.pre_run.state_bindings", "playbook.states"],
    }),
    "playbook.pre_run": declare_human({
        "definition": "Playbook field for workflows that run before the requested published workflow in the same run.",
        "use_when": ["The project needs shared launch-time preparation, validation, or state setup before whichever published workflow the caller selected.", "The setup may consult remembered state or other launch context while the caller's explicit --profile choice remains authoritative."],
        "do_not_use_for": ["Workflow-internal sequencing that belongs inside one workflow body.", "Per-workflow-entry preparation that should happen for only one published workflow; keep that logic closer to the entry or workflow body."],
        "nearest_surfaces": [{"handle": "playbook.pre_run_contract", "summary": "What a pre-run entry may declare and its boundaries"}, {"handle": "playbook.pre_run.file", "summary": "Field that selects the workflow to run before the requested workflow"}, {"handle": "playbook.workflows.with", "summary": "Launch inputs for the requested workflow rather than pre-run setup"}],
        "examples": [{"reference": "playbook.pre_run", "inputs": {"file": ".ordo/workflows/bootstrap.yaml", "with": {"repo": "acme/app"}, "state_bindings": {"shared_state": "global"}}}],
        "inspect_next": ["playbook.pre_run_contract", "playbook.pre_run.file", "playbook.pre_run.with"],
    }),
    "playbook.pre_run_contract": declare_human({
        "definition": "Playbook contract for pre-run entries that execute before the requested workflow with playbook-owned launch context.",
        "use_when": ["You need to understand the execution boundary, allowed fields, and state limits for playbook pre-run setup."],
        "do_not_use_for": ["Ordinary workflow-entry invocation rules; use playbook.workflows.* for the requested workflow launch.", "Assuming pre_run may silently add state requirements to the main workflow; that boundary is deliberately restricted."],
        "nearest_surfaces": [{"handle": "playbook.pre_run", "summary": "Parent playbook field that lists pre-run entries"}, {"handle": "playbook.pre_run.state_bindings", "summary": "Field for state locations used only by the pre-run workflow"}, {"handle": "playbook.workflows.with", "summary": "Requested-workflow launch inputs rather than pre-run inputs"}],
        "required_fields": ["file"], "optional_fields": ["with", "state_bindings"],
        "inspect_next": ["playbook.pre_run.file", "playbook.pre_run.with", "playbook.pre_run.state_bindings"],
    }),
    "playbook.pre_run.file": declare_human({
        "definition": "Pre-run entry field that selects the workflow file to execute before the requested workflow.",
        "use_when": ["A specific bootstrap workflow should always run first when this playbook is used."],
        "do_not_use_for": ["Selecting the requested workflow by name; that belongs to playbook.workflows entries and ordo-playbook commands."],
        "nearest_surfaces": [{"handle": "playbook.pre_run", "summary": "Parent pre-run list"}, {"handle": "playbook.pre_run_contract", "summary": "Contract that requires file on every pre-run entry"}, {"handle": "playbook.workflows.file", "summary": "Field for the requested workflow entry rather than pre-run setup"}],
        "examples": [{"reference": "playbook.pre_run.file", "inputs": {"file": ".ordo/workflows/bootstrap.yaml"}}],
        "inspect_next": ["playbook.pre_run.with", "playbook.pre_run_contract", "playbook.workflows.file"],
    }),
    "playbook.pre_run.with": declare_human({
        "definition": "Pre-run entry field for fixed playbook-owned launch inputs passed only to the pre-run workflow.",
        "use_when": ["The bootstrap workflow needs fixed launch-time values owned by the playbook rather than by the caller."],
        "do_not_use_for": ["Caller-supplied launch inputs for the requested workflow; use playbook.workflows.with or command-line overrides.", "Dynamic workflow expressions; this field accepts static YAML values only."],
        "nearest_surfaces": [{"handle": "playbook.pre_run", "summary": "Parent pre-run list"}, {"handle": "playbook.workflows.with", "summary": "Launch input field for the requested workflow entry"}, {"handle": "command-line.ordo-playbook.flag.input", "summary": "One-run caller override instead of fixed pre-run inputs"}],
        "examples": [{"reference": "playbook.pre_run.with", "inputs": {"repo": "acme/app", "strict": True}}],
        "inspect_next": ["playbook.workflows.with", "command-line.ordo-playbook.flag.input", "playbook.pre_run.state_bindings"],
    }),
    "playbook.pre_run.state_bindings": declare_human({
        "definition": "Pre-run entry field for state-location bindings that the pre-run workflow may use without adding to the requested workflow's state contract.",
        "use_when": ["The bootstrap workflow needs declared state access, and that access should stay explicit and limited to pre-run setup."],
        "do_not_use_for": ["Adding extra state requirements to the main requested workflow; that is not allowed here.", "Requested-workflow state bindings; use playbook.workflows.state_bindings for those entry-specific bindings."],
        "nearest_surfaces": [{"handle": "playbook.pre_run_contract", "summary": "Contract that explains the pre-run state boundary"}, {"handle": "playbook.workflows.state_bindings", "summary": "Binding field for the requested workflow entry"}, {"handle": "state.workflow_surface.state_binding_field", "summary": "State contract surface for one state binding"}],
        "examples": [{"reference": "playbook.pre_run.state_bindings", "inputs": {"shared_state": "global"}}],
        "inspect_next": ["playbook.workflows.state_bindings", "state.workflow_surface.state_binding_field", "playbook.pre_run_contract"],
    }),
    "playbook.profiles": declare_human({
        "definition": "Playbook field for declaring reusable named profiles that this playbook may activate by default, entry policy, or caller override.",
        "use_when": ["The project needs a playbook-local catalog of named execution contexts instead of fixing one profile inside each workflow body."],
        "do_not_use_for": ["Choosing which profile wins for one run; use defaults, workflow entry policy, or command-line selection.", "One workflow-owned fixed profile; use workflow.profile when the workflow must bind one profile before its guards run."],
        "nearest_surfaces": [{"handle": "playbook.profiles.file", "summary": "Field for loading one declared profile from a separate file"}, {"handle": "playbook.defaults.profile", "summary": "Default active profile selected from the profiles catalog"}, {"handle": "workflow.profile", "summary": "Workflow-owned fixed profile instead of a reusable playbook profile"}],
        "examples": [{"reference": "playbook.profiles", "inputs": {"backend": {"file": "backend.yml"}, "review": {"file": "review.yml"}}}],
        "inspect_next": ["playbook.profiles.file", "playbook.defaults.profile", "profile.name"],
    }),
    "playbook.profiles.file": declare_human({
        "definition": "Playbook profile-entry field that points one declared profile name at the profile file to load.",
        "use_when": ["A named playbook profile should load its reusable execution context from a separate profile document."],
        "do_not_use_for": ["Selecting the active profile for the current run; use playbook defaults or caller and entry selection.", "Pointing at a workflow file; use playbook.workflows.file or playbook.pre_run.file for workflow launch."],
        "nearest_surfaces": [{"handle": "playbook.profiles", "summary": "Parent playbook profile catalog"}, {"handle": "profile.name", "summary": "Profile name inside the loaded profile document"}, {"handle": "playbook.workflows.file", "summary": "Field that selects a workflow file rather than a profile file"}],
        "examples": [{"reference": "playbook.profiles.file", "inputs": {"file": "backend.yml"}}],
        "inspect_next": ["profile.name", "playbook.defaults.profile", "playbook.workflows.file"],
    }),
    "playbook.states": declare_human({
        "definition": "Playbook field for declaring named state storage locations that workflows and entries may bind explicitly.",
        "use_when": ["The project needs durable named storage that workflows may read, write, or delete through explicit state contracts instead of implicit files."],
        "do_not_use_for": ["Short-lived workflow data; keep it in workflow values, step outputs, or direct inputs instead of declared state storage.", "Binding a workflow to a state location; use workflow.state_bindings or entry state_bindings for that step."],
        "nearest_surfaces": [{"handle": "playbook.states.path", "summary": "Field that maps one declared state name to its storage path"}, {"handle": "workflow.state_bindings", "summary": "Surface for binding declared state names into a workflow or entry"}, {"handle": "state.workflow_surface.state_binding_field", "summary": "State-binding surface that uses declared playbook state names"}],
        "examples": [{"reference": "playbook.states", "inputs": {"shared_state": {"path": "repo.json"}, "cache": {"path": ".ordo/cache.json"}}}],
        "inspect_next": ["playbook.states.path", "workflow.state_bindings", "state.workflow_surface.state_binding_field"],
    }),
    "playbook.states.path": declare_human({
        "definition": "Playbook state-entry field that assigns a declared state name to the filesystem path where its durable state is stored.",
        "use_when": ["A declared state location needs a storage target so workflows can bind and resolve it explicitly."],
        "do_not_use_for": ["Binding a workflow role to a declared state name; use workflow.state_bindings or entry state_bindings.", "Working-directory defaults or workflow file selection; this field declares state storage, not execution context."],
        "nearest_surfaces": [{"handle": "playbook.states", "summary": "Parent playbook state-location catalog"}, {"handle": "workflow.state_bindings", "summary": "Binding surface that references declared state names"}, {"handle": "profile.working_directory", "summary": "Execution-directory setting rather than durable state storage"}],
        "examples": [{"reference": "playbook.states.path", "inputs": {"path": "repo.json"}}],
        "inspect_next": ["workflow.state_bindings", "state.workflow_surface.state_binding_field", "playbook.states"],
    }),
    "playbook.version": declare_human({
        "definition": "Required top-level playbook format marker that declares which playbook document shape this file uses.",
        "use_when": ["Every playbook document must declare the required playbook format version before launch-catalog fields such as states, workflows, or profiles."],
        "do_not_use_for": ["Your repository, release, or product version; this field is only the playbook document-format marker.", "Workflow or routine document format versions; use workflow.version or routine_contract.version in those documents."],
        "nearest_surfaces": [{"handle": "workflow.version", "summary": "Version marker for a workflow document rather than the playbook catalog"}, {"handle": "routine_contract.version", "summary": "Version marker for the routine registry document"}, {"handle": "playbook.workflows", "summary": "Main playbook catalog field interpreted using this version"}],
        "examples": [{"reference": "playbook.version", "inputs": {"version": 1}}],
        "inspect_next": ["playbook.workflows", "workflow.version", "routine_contract.version"],
    }),
    "playbook.connectors": declare_human({
        "definition": "Playbook top-level field for repository-wide default connector settings before profile-specific overrides apply.",
        "use_when": ["One repository-wide connector setting should apply before profile-specific connector overrides.", "Several published workflows should inherit the same connector values without repeating them in each workflow entry."],
        "do_not_use_for": ["Per-profile connector settings; use profile.connectors for that narrower launch context.", "Publishing connector operations; use connector.* handles to inspect the available operations."],
        "nearest_surfaces": [{"handle": "profile.connectors", "summary": "Profile-level connector settings that can narrow or override playbook defaults"}, {"handle": "connector.compose", "summary": "Connector family that reads settings such as directory, file, and project name"}, {"handle": "operations", "summary": "Published connector operation catalog"}],
        "examples": [{"reference": "playbook.connectors", "inputs": {"compose.directory": "./deploy"}}],
        "inspect_next": ["profile.connectors", "connector.compose", "playbook.workflows"],
    }),
}

PLAYBOOK_CONTRACT: JSONObject = {
    "document_kind": "playbook",
    "version": 1,
    "discovery": {"path": ".ordo/ordo.yaml"},
    "top_level_fields": [
        {"name": "version", "required": True, "type": "integer"},
        {"name": "pre_run", "required": False, "type": "array"},
        {"name": "states", "required": True, "type": "object"},
        {"name": "defaults", "required": False, "type": "object"},
        {"name": "connectors", "required": False, "type": "object", "runtime_effect": "supplies_raw_connector_bootstrap_input"},
        {"name": "workflows", "required": True, "type": "object"},
        {"name": "profiles", "required": False, "type": "object"},
    ],
    "workflow_entry_fields": [
        {"name": "file", "required": True, "type": "string"},
        {
            "name": "with",
            "required": False,
            "type": "object",
            "runtime_effect": "supplies_playbook_owned_workflow_entry_inputs_or_declares_required_or_optional_caller_slots",
            "value_surface": "static_yaml_values_or_blank_required_slots_or_blank_optional_question_suffix_slots",
            "caller_slot_forms": [
                {"shape": "key:", "meaning": "caller_must_supply_input_via_cli_or_activation_override"},
                {"shape": "key?:", "meaning": "caller_may_supply_input_via_cli_or_activation_override"},
            ],
        },
        {
            "name": "description",
            "required": False,
            "type": "string",
            "documentation_role": "project_local_workflow_summary",
        },
        {
            "name": "category",
            "required": False,
            "type": "string",
            "documentation_role": "project_local_workflow_catalog_group",
            "runtime_effect": "published_metadata_only",
        },
        {
            "name": "when",
            "required": False,
            "type": "string",
            "documentation_role": "operator_workflow_selection_guidance",
            "runtime_effect": "published_metadata_only",
        },
        {
            "name": "working_directory",
            "required": False,
            "type": "string",
            "runtime_effect": "sets_execution_working_directory",
            "resolution_base": "playbook_dir",
            "expression_syntax": "${...}",
            "expression_surface": "activation_input_value_expression",
            "expression_allowed_roots": ["inputs"],
            "expression_forbidden_roots": ["state", "step"],
        },
        {"name": "state_bindings", "required": False, "type": "object"},
    ],
    "profile_entry_fields": [
        {"name": "file", "required": True, "type": "string"},
    ],
    "pre_run_entry_fields": [
        {"name": "file", "required": True, "type": "string"},
        {
            "name": "with",
            "required": False,
            "type": "object",
            "documentation_role": "playbook_owned_pre_run_invocation_inputs",
            "runtime_effect": "supplies_playbook_owned_pre_run_inputs",
            "value_surface": "static_yaml_values_only",
        },
        {
            "name": "state_bindings",
            "required": False,
            "type": "object",
            "documentation_role": "playbook_owned_pre_run_state_bindings",
        },
    ],
    "state_entry_fields": [
        {"name": "path", "required": True, "type": "string"},
    ],
    "defaults_fields": [
        {"name": "profile", "required": False, "type": "string", "runtime_effect": "selects_active_profile"},
        {
            "name": "working_directory",
            "required": False,
            "type": "string",
            "runtime_effect": "sets_default_execution_working_directory",
            "resolution_base": "playbook_dir",
            "expression_syntax": "${...}",
            "expression_surface": "activation_input_value_expression",
            "expression_allowed_roots": ["inputs"],
            "expression_forbidden_roots": ["state", "step"],
        },
    ],
    "activation_semantics": {
        "discovery": {
            "strategy": "cwd_relative_single_path",
            "path": ".ordo/ordo.yaml",
            "missing": "playbook.discovery.missing",
        },
        "workflow_entries": {
            "requires": ["file"],
            "optional": ["with", "description", "category", "when", "working_directory", "state_bindings"],
        },
        "pre_run": {
            "item_type": "pre_run_entry",
            "requires": ["file"],
            "optional": ["with", "state_bindings"],
            "effect": "executes_before_requested_workflow_in_same_runtime_session",
            "launch_context_boundary": "playbook_owned",
            "state_dependency_boundary": "must_not_widen_main_workflow_state_contract",
        },
        "profile_entries": {
            "requires": ["file"],
        },
        "connector_context": {
            "top_level_field": "connectors",
            "family_entry_type": "object",
            "profile_refinement": True,
            "consumer": "connector_bootstrap",
        },
        "state_entries": {
            "requires": ["path"],
        },
    },
    "human": human_mapping(PLAYBOOK_HUMAN),
}


def describe_playbook_contract_data() -> JSONObject:
    """Return a defensive copy of canonical playbook contract metadata."""

    return deepcopy(PLAYBOOK_CONTRACT)
