"""Machine-readable taxonomy for runtime-facing error and failure classes."""

from __future__ import annotations

from copy import deepcopy

from .json import JSONObject

ERROR_TAXONOMY: JSONObject = {
    "document_kind": "error_taxonomy",
    "failure_classes": [
        {
            "name": "validation",
            "runtime_statuses": ["validation_error"],
            "code_prefixes": ["validation."],
            "example_codes": [
                "validation.unknown_field",
                "validation.workflow.step.form",
                "validation.workflow.guard_expr.syntax",
            ],
        },
        {
            "name": "composition_conflict",
            "runtime_statuses": ["validation_error"],
            "code_prefixes": ["composition.profile.", "composition.workflow."],
            "example_codes": [
                "composition.profile.input_conflict",
                "composition.profile.override_conflict",
                "composition.workflow.input_conflict",
            ],
        },
        {
            "name": "input_or_reference",
            "runtime_statuses": ["validation_error", "resolution_error"],
            "code_prefixes": ["runtime.value.input_", "runtime.value.reference_", "runtime.state.input_", "runtime.state.reference_", "runtime.state.binding_", "runtime.state.key_"],
            "example_codes": [
                "runtime.value.input_missing",
                "runtime.value.reference_unknown",
                "runtime.state.input_missing",
                "runtime.state.reference_unknown",
                "runtime.state.binding_missing",
                "runtime.state.key_invalid",
            ],
        },
        {
            "name": "unsupported_feature",
            "runtime_statuses": ["validation_error", "resolution_error"],
            "code_prefixes": ["runtime.value.expression_builtin_unsupported"],
            "example_codes": [
                "runtime.value.expression_builtin_unsupported",
            ],
        },
        {
            "name": "blocked_or_precondition",
            "runtime_statuses": ["guard_failed", "resolution_error", "execution_error"],
            "code_prefixes": ["runtime.state.declaration_", "runtime.state.path_", "runtime.value.state_"],
            "example_codes": [
                "runtime.state.declaration_missing",
                "runtime.state.path_invalid",
                "runtime.value.state_missing",
            ],
        },
        {
            "name": "execution_or_io",
            "runtime_statuses": ["execution_error"],
            "code_prefixes": ["runtime.state.read_", "runtime.state.write_", "runtime.state.invalid_", "runtime.value.format_"],
            "example_codes": [
                "runtime.state.read_failed",
                "runtime.state.write_failed",
                "runtime.state.invalid_json",
                "runtime.value.format_template_invalid",
            ],
        },
    ]
}


def describe_error_taxonomy_data() -> JSONObject:
    """Return a defensive copy of the published error taxonomy."""

    return deepcopy(ERROR_TAXONOMY)
