"""Canonical contract metadata for profile authoring surface."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject
from .human import HumanDeclaration, declare_human, human_mapping


PROFILE_FEATURE_HUMAN = declare_human({
    "title": "Profile", "goal": "Choose a named project context for stable execution defaults.",
    "summary": "Reusable project execution context for stable defaults.", "sections": [],
})
PROFILE_HUMAN = declare_human({
    "title": "Profile contract", "goal": "Supply a named project execution context without hiding workflow intent.",
    "summary": "Use profiles for deliberate project-local defaults such as inputs and working directory.",
    "sections": [{"heading": "Use it for", "items": ["Select stable project context before a workflow runs.", "Keep workflow-specific decisions in the workflow rather than in a profile.", "Prefer published routines over deprecated launchers for small project-local helpers."]}],
    "feature_clusters": {"profile": {**human_mapping(PROFILE_FEATURE_HUMAN), "use_when": ["Several runs share the same project context."], "avoid_when": ["The choice changes workflow behavior and should be explicit in the workflow."]}},
})

# Focused-describe records live with the profile contract so their guidance has
# the same source of truth as the fields it explains.
PROFILE_FOCUSED_DESCRIBE_HUMAN: dict[str, HumanDeclaration] = {
    "profile.inputs": declare_human({
        "definition": "Profile field for declaring default values for workflow-declared inputs when the caller did not supply those inputs explicitly.",
        "use_when": ["Several runs under one profile should reuse the same declared workflow input defaults without copying them into every playbook entry or command invocation.", "One execution mode such as review or backend should supply stable fallback input values while still allowing explicit caller overrides."],
        "do_not_use_for": ["Undeclared workflow inputs or arbitrary profile-local scratch data; this field only supplies values for workflow-declared activation inputs.", "Forcing one value even when the caller or playbook workflow entry already supplied it; profile.inputs is a missing-input default surface, not an unconditional override."],
        "nearest_surfaces": [{"handle": "workflow.inputs_contract", "summary": "Workflow contract that declares which activation inputs may be supplied or required"}, {"handle": "playbook.workflows.with", "summary": "Playbook workflow-entry field for entry-owned launch inputs rather than reusable profile defaults"}, {"handle": "profile.overrides", "summary": "Profile metadata records that do not feed workflow activation inputs directly"}],
        "effects": ["profile-owned values fill only missing declared workflow inputs during activation", "explicit caller inputs and playbook entry-owned inputs remain higher-precedence than profile defaults"],
        "examples": [{"reference": "profile.inputs", "inputs": {"command": ".venv/bin/python -m unittest discover -s tests", "issue": "kergma-lw/ordo-cli#1"}}],
        "inspect_next": ["workflow.inputs_contract", "playbook.workflows.with", "playbook.defaults.profile"],
    }),
    "profile.working_directory": declare_human({
        "definition": "Profile field for declaring one reusable execution working-directory context that becomes active when this profile is selected.",
        "use_when": ["Several runs under one profile should execute from the same repository-relative directory without repeating that directory in every playbook workflow entry.", "One profile should derive its execution directory from activation inputs such as inputs.repo_dir while still remaining reusable across workflows."],
        "do_not_use_for": ["Per-workflow-entry directory overrides; use playbook.workflows.working_directory when one published workflow entry needs a narrower directory choice.", "Arbitrary runtime expressions over step or state data; this activation-time field only allows ${...} expressions rooted in inputs."],
        "nearest_surfaces": [{"handle": "playbook.defaults.working_directory", "summary": "Playbook-wide soft default execution directory when no profile-specific directory is needed"}, {"handle": "playbook.workflows.working_directory", "summary": "Per-workflow-entry execution directory override that is narrower than one reusable profile context"}, {"handle": "profile.inputs", "summary": "Profile-owned input defaults that may feed the working_directory expression through inputs.* values"}],
        "effects": ["the resolved directory becomes the active execution directory for runs under this profile when no narrower workflow-entry override wins", "working_directory expressions resolve relative to the playbook directory and may read only inputs.* roots"],
        "examples": [{"reference": "profile.working_directory", "inputs": {"working_directory": "${inputs.repo_dir}"}}],
        "inspect_next": ["playbook.defaults.working_directory", "playbook.workflows.working_directory", "profile.inputs"],
    }),
    "profile.overrides": declare_human({
        "definition": "Profile field for publishing explicit override records, each naming a reader and optionally providing structured data and a reason.",
        "use_when": ["Several runs under one profile should expose the same project-local adaptation metadata without pretending that the profile silently rewrites workflow behavior.", "A known integration, compatibility path, or local convention reads one named record from the active profile."],
        "do_not_use_for": ["Workflow inputs, guards, or step branching that should be authored on the workflow or playbook surfaces that actually drive runtime behavior.", "Assuming Ordo will infer behavior from the supplied data automatically; overrides are published metadata, not implicit workflow changes."],
        "nearest_surfaces": [{"handle": "profile.inputs", "summary": "Profile field for missing-input defaults that do affect workflow activation data"}, {"handle": "profile.overrides.target", "summary": "Required child field that names which reader should use this record"}, {"handle": "workflow.profile", "summary": "Workflow-owned fixed profile binding rather than profile-scoped adaptation metadata"}],
        "fields": [{"name": "target", "type": "string", "required": True, "role": "consumer_owned_override_key"}, {"name": "with", "type": "object", "required": False, "role": "opaque_override_data"}, {"name": "reason", "type": "string", "required": False, "role": "human_readable_override_explanation"}],
        "effects": ["each active profile may publish at most one override record per target", "Ordo keeps the record as published; its data does not change workflow behavior unless the named reader explicitly uses it"],
        "examples": [{"reference": "profile.overrides", "inputs": {"overrides": [{"target": "local.issue-triage", "with": {"default_label": "bug", "board": "intake"}, "reason": "Share one profile-scoped triage adaptation record."}]}}],
        "inspect_next": ["profile.overrides.target", "profile.overrides.with", "profile.overrides.reason"],
    }),
    "profile.overrides.target": declare_human({
        "definition": "Required override field that names which integration or local convention should read one override record.",
        "use_when": ["One integration or local convention expects a stable target name so it can select the right override record from the active profile."],
        "do_not_use_for": ["Workflow input names or connector context fields; this key selects one override record, not ordinary workflow data."],
        "nearest_surfaces": [{"handle": "profile.overrides", "summary": "Parent profile field that collects the override records"}, {"handle": "profile.overrides.with", "summary": "Sibling field that carries the data for the named target"}, {"handle": "profile.overrides.reason", "summary": "Sibling field that explains why this target-specific record exists"}],
        "effects": ["duplicate target names conflict when profiles are composed or when one profile repeats the same target"],
        "inspect_next": ["profile.overrides.with", "profile.overrides.reason", "profile.overrides"],
    }),
    "profile.overrides.with": declare_human({
        "definition": "Optional override field for structured data that the named target may use.",
        "use_when": ["The named override target needs structured profile-scoped data in addition to the target key itself."],
        "do_not_use_for": ["Fields that need first-class workflow or playbook validation; use the published workflow or playbook field instead.", "Free-form text explanation; use profile.overrides.reason for the human-facing why."],
        "nearest_surfaces": [{"handle": "profile.overrides", "summary": "Parent profile field that publishes override records"}, {"handle": "profile.overrides.target", "summary": "Sibling field that names which integration should read this data"}, {"handle": "profile.inputs", "summary": "Profile-owned input defaults that do change workflow activation data"}],
        "effects": ["Ordo keeps this object as published and does not treat its keys as built-in workflow behavior"],
        "inspect_next": ["profile.overrides.reason", "profile.overrides.target", "profile.overrides"],
    }),
    "profile.overrides.reason": declare_human({
        "definition": "Optional override field for one short human-readable explanation of why the target-specific override record exists.",
        "use_when": ["Later readers would benefit from a short intent note instead of reverse-engineering the supplied data alone."],
        "do_not_use_for": ["Machine-readable override data that belongs in profile.overrides.with.", "The required target identifier itself; use profile.overrides.target for that."],
        "nearest_surfaces": [{"handle": "profile.overrides", "summary": "Parent profile field that groups the override record"}, {"handle": "profile.overrides.target", "summary": "Sibling field that names the override target"}, {"handle": "profile.overrides.with", "summary": "Sibling field that carries the target-specific object data"}],
        "effects": ["reason text is optional but, when present, must stay a non-empty string"],
        "inspect_next": ["profile.overrides.with", "profile.overrides.target", "profile.overrides"],
    }),
    "profile.name": declare_human({
        "definition": "Required profile field that gives the profile its stable name for selection and messages.",
        "use_when": ["Every profile document must publish the stable name that playbook profile choices and defaults refer to."],
        "do_not_use_for": ["Choosing which profile should win for one run; use playbook.defaults.profile, workflow.profile, or the command-line profile selector for activation decisions.", "Publishing a human-friendly label unrelated to runtime identity; this field is the profile's declared contract name."],
        "nearest_surfaces": [{"handle": "playbook.defaults.profile", "summary": "Playbook field that chooses one declared profile name as the soft default activation choice"}, {"handle": "command-line.ordo-playbook.flag.profile", "summary": "Launch-time selector that chooses which declared profile name to activate for one invocation"}, {"handle": "workflow.profile", "summary": "Workflow-owned fixed binding to one declared profile name before guards run"}],
        "effects": ["the declared name is used when selecting and reporting the profile", "the profile document must expose exactly one non-empty string name"],
        "examples": [{"reference": "profile.name", "inputs": {"name": "read-only-review"}}],
        "inspect_next": ["playbook.defaults.profile", "command-line.ordo-playbook.flag.profile", "workflow.profile"],
    }),
    "profile.checks": declare_human({
        "definition": "Profile field for publishing one or more named review or verification labels that describe the expected checking posture of this profile.",
        "use_when": ["A profile should publish its intended review or verification posture, such as review, unit, or contract, as reusable launch metadata.", "Several workflows under one profile share the same checking expectations and readers should see that posture without reverse-engineering workflow bodies."],
        "do_not_use_for": ["Workflow applicability logic or enforced guard behavior; use workflow guards, check, and review surfaces for executable validation semantics.", "Assuming the named checks run automatically merely because the labels are present; this field publishes metadata rather than execution steps."],
        "nearest_surfaces": [{"handle": "profile.overrides", "summary": "Other published profile metadata that later readers may inspect without changing workflow execution semantics directly"}, {"handle": "workflow-rules.paired_check_review_passes", "summary": "Authoring guidance for the real check/review execution loop rather than profile metadata labels"}, {"handle": "command-line.ordo-playbook", "summary": "Command surface that actually launches workflows instead of merely publishing profile metadata"}],
        "effects": ["named checks are published as profile metadata and remain available to readers, reviewers, or local conventions", "the labels themselves do not form an automatic execution plan"],
        "examples": [{"reference": "profile.checks", "inputs": {"checks": ["unit", "contract"]}}],
        "inspect_next": ["workflow-rules.paired_check_review_passes", "profile.overrides", "command-line.ordo-playbook"],
    }),
    "profile.launchers": declare_human({
        "definition": "Deprecated profile field for publishing profile-scoped launcher records that older workflows may still reference through workflow.step.launcher.",
        "use_when": ["You are maintaining existing launcher-based profile metadata and need to understand or document what one legacy profile publishes today.", "A project still has older launcher references and needs a migration-aware surface that points readers toward the preferred routines alternative."],
        "do_not_use_for": ["New workflow authoring when published routines or explicit profile context can express the execution setup more honestly.", "Assuming launcher records are the preferred long-term execution-context surface; this field is deprecated and retained mainly for compatibility."],
        "nearest_surfaces": [{"handle": "workflow.step.launcher", "summary": "Legacy workflow step field that selects one named launcher record"}, {"handle": "workflow-rules.routine.*", "summary": "Authoring guidance for the supported routines alternative"}, {"handle": "examples.launcher-step", "summary": "Legacy launcher example for understanding an existing workflow"}],
        "fields": [{"name": "file", "type": "string", "required": False, "role": "launcher_definition_file"}, {"name": "connector", "type": "string", "required": False, "role": "legacy_connector_name"}, {"name": "before", "type": "string", "required": False, "role": "pre_step_shell_hook"}, {"name": "after", "type": "string", "required": False, "role": "post_step_shell_hook"}],
        "effects": [
            "A legacy launcher record may provide `file` for its launcher definition, `connector` for the operation family, `before` for setup before the step, and `after` for cleanup after it.",
            "Keep these records only while maintaining an existing launcher-based workflow; the field remains deprecated and routines are the preferred path for new local automation.",
        ],
        "examples": [{"reference": "profile.launchers", "inputs": {"shell_frontend": {"file": "../launchers/shell-frontend.yaml"}}}],
        "inspect_next": ["workflow.step.launcher", "examples.launcher-step", "workflow-rules.routine.*"],
    }),
    "profile.connectors": declare_human({
        "definition": "Profile-scoped connector setup field for declaring connector context that applies only when this profile is active.",
        "use_when": ["Several runs under one profile need the same connector context, such as Compose directory/file/project settings, without repeating it in every workflow call.", "One profile should narrow or override broader playbook connector defaults for a specific execution mode such as review, backend, or deployment work."],
        "do_not_use_for": ["Repository-wide connector defaults that should apply before profile selection; use playbook.connectors for that broader launch scope.", "Publishing connector operations themselves; use connector.* handles to learn the public operation surface.", "Workflow business inputs that belong in declared workflow inputs rather than connector setup context."],
        "nearest_surfaces": [{"handle": "playbook.connectors", "summary": "Playbook-level connector context that provides broader defaults before profile-specific narrowing or overrides"}, {"handle": "connector.compose", "summary": "One connector family that reads concrete context fields such as directory, file, and project_name"}, {"handle": "profile.inputs", "summary": "Profile-owned workflow input defaults, which are different from connector setup context"}],
        "examples": [{"reference": "profile.connectors", "inputs": {"compose.directory": "./deploy", "compose.file": "compose.prod.yaml", "compose.project_name": "orders-prod"}}],
        "inspect_next": ["playbook.connectors", "connector.compose", "profile.inputs"],
    }),
}

PROFILE_CONTRACT: JSONObject = {
    "document_kind": "profile",
    "top_level_fields": [
        {"name": "name", "required": True, "type": "string"},
        {"name": "inputs", "required": False, "type": "object", "runtime_effect": "applies_missing_workflow_inputs"},
        {
            "name": "working_directory",
            "required": False,
            "type": "string",
            "runtime_effect": "sets_profile_execution_working_directory",
            "resolution_base": "playbook_dir",
            "expression_syntax": "${...}",
            "expression_surface": "activation_input_value_expression",
            "expression_allowed_roots": ["inputs"],
            "expression_forbidden_roots": ["state", "step"],
        },
        {"name": "connectors", "required": False, "type": "object", "runtime_effect": "supplies_raw_connector_bootstrap_input"},
        {"name": "checks", "required": False, "type": "array", "runtime_effect": "published_metadata_only"},
        {"name": "overrides", "required": False, "type": "array", "runtime_effect": "published_metadata_only"},
        {"name": "launchers", "required": False, "type": "object", "runtime_effect": "publishes_profile_scoped_launchers", "status": "deprecated", "preferred_alternative": "published_routines"},
    ],
    "override_fields": [
        {"name": "target", "required": True, "type": "string"},
        {"name": "with", "required": False, "type": "object"},
        {"name": "reason", "required": False, "type": "string"},
    ],
    "launcher_fields": [
        {"name": "file", "required": False, "type": "string"},
        {"name": "connector", "required": False, "type": "string"},
        {"name": "before", "required": False, "type": "string"},
        {"name": "after", "required": False, "type": "string"},
    ],
    "compose_semantics": {
        "inputs": {
            "strategy": "first_writer_wins",
            "conflict": "validation_error",
        },
        "working_directory": {
            "strategy": "first_writer_wins",
            "conflict": "validation_error",
        },
        "connectors": {
            "strategy": "shallow_merge_by_family",
            "conflict": "validation_error",
            "conflict_key": "family_field",
        },
        "checks": {
            "strategy": "deduplicated_union",
            "order": "left_to_right",
        },
        "overrides": {
            "conflict_key": "target",
            "conflict": "validation_error",
        },
        "launchers": {
            "strategy": "first_writer_wins",
            "conflict": "validation_error",
            "conflict_key": "launcher_name",
            "status": "deprecated",
        },
    },
    "workflow_apply_semantics": {
        "inputs": {
            "may_add_missing": True,
            "may_override_explicit_workflow_values": False,
            "conflict": "validation_error",
        },
        "working_directory": {
            "mutates_workflow_steps": False,
            "published_as_explicit_metadata": True,
        },
        "connectors": {
            "mutates_workflow_steps": False,
            "published_as_explicit_metadata": False,
            "consumer": "connector_bootstrap",
        },
        "checks": {
            "mutates_workflow_contract": False,
        },
        "overrides": {
            "mutates_workflow_steps": False,
            "published_as_explicit_metadata": True,
        },
        "launchers": {
            "mutates_workflow_steps": False,
            "published_as_explicit_metadata": True,
            "status": "deprecated",
        },
    },
    "human": human_mapping(PROFILE_HUMAN),
}


def describe_profile_contract_data() -> JSONObject:
    """Return a defensive copy of canonical profile contract metadata."""

    return deepcopy(PROFILE_CONTRACT)


def describe_profile_focused_describe_human() -> dict[str, JSONObject]:
    """Return defensive copies of profile-focused describe records."""

    return {name: deepcopy(declaration.content) for name, declaration in PROFILE_FOCUSED_DESCRIBE_HUMAN.items()}  # type: ignore[return-value]
