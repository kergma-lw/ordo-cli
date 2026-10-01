"""gh.project.field probe."""

from __future__ import annotations

from connectors.gh.probes.project._fields import fetch_project_fields, field_kind, field_nodes, field_options
from ordo.plugin_sdk import OperationContext, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub project field',
 'goal': 'A workflow needs to confirm that a field such as Status or Priority exists before publishing, validating, or '
         'mutating project-backed issue data.',
 'summary': 'Probe one named field in one GitHub Project and return whether it exists, what field kind it is, and '
            'which selectable option names it exposes when applicable.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs to confirm that a field such as Status or Priority exists before '
                         'publishing, validating, or mutating project-backed issue data.',
                         'Later logic needs field metadata such as kind or allowed option names instead of only a '
                         'yes/no answer about one candidate option.']},
              {'heading': 'Do not use for',
               'items': ['Checking only whether one named allowed value exists; use connector.gh.project.field.option '
                         'for that narrower yes/no probe.',
                          'Setting a field value on a project item; use connector.gh.project.issue.field_single_select.set, '
                          'connector.gh.project.issue.field_number.set, or connector.gh.project.issue.field_iteration.set '
                          'for the matching field kind rather than this read-only metadata probe.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.project',
                               'summary': 'Parent project probe for confirming the project identity before '
                                          'field-specific inspection'},
                              {'handle': 'connector.gh.project.field.option',
                               'summary': 'Sibling probe for one candidate selectable value rather than the whole '
                                          'field metadata surface'},
                              {'handle': 'connector.gh.project.issue.field_single_select.set',
                               'summary': 'Action for writing one selectable field value after field inspection '
                                          'confirms the target field'},
                              {'handle': 'connector.gh.project.issue.field_number.set',
                               'summary': 'Action for writing one numeric field value after field inspection confirms '
                                          'the target field'}]},
              {'heading': 'Examples',
               'items': ['gh.project.field with inputs {"field": "Status", "project_id": "PVT_kwDOExample"}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.project.field.option',
                         'connector.gh.project.issue.field_single_select.set',
                         'connector.gh.project.issue.field_number.set']}]})

def info():
    return probe(
        name="project.field",
        human=HUMAN,
        inputs={"project_id": "string", "field": "string"},
        outputs={
            "exists": "boolean",
            "name": "string",
            "kind": "string",
            "options": ["string"],
        },
        failure_modes=("project_not_found", "probe_failed"),
        handler=run,
    )


def run(ctx: OperationContext):
    project_id = str(ctx.input("project_id"))
    field_name = str(ctx.input("field"))
    fetched = fetch_project_fields(ctx, project_id, diagnostic_prefix="probe.gh_project_field")
    if not isinstance(fetched, tuple):
        return fetched
    project, raw = fetched

    for node in field_nodes(project):
        if not isinstance(node, dict):
            continue
        if node.get("name") != field_name:
            continue
        return ok(
            summary="GitHub project field facts retrieved successfully",
            outputs={
                "exists": True,
                "name": node.get("name"),
                "kind": field_kind(node),
                "options": field_options(node),
            },
            raw=raw,
        )

    return ok(
        summary="GitHub project field was not found",
        outputs={
            "exists": False,
            "name": None,
            "kind": None,
            "options": [],
        },
        raw=raw,
    )
