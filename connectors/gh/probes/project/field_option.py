"""gh.project.field.option probe."""

from __future__ import annotations

from connectors.gh.probes.project._fields import fetch_project_fields, field_nodes, field_options
from ordo.plugin_sdk import OperationContext, ok, probe
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'GitHub project field option',
 'goal': 'A workflow needs one explicit yes/no check that a candidate value such as Done is valid before publishing or '
         'applying it elsewhere.',
 'summary': 'Probe whether one named selectable value exists inside one GitHub Project field when that field publishes '
            'an allowed-value set.',
 'sections': [{'heading': 'Use when',
               'items': ['A workflow needs one explicit yes/no check that a candidate value such as Done is valid '
                         'before publishing or applying it elsewhere.',
                         'A guard or preparatory step should fail early when one expected project field option is '
                         'missing but the full field metadata is not otherwise needed later.']},
              {'heading': 'Do not use for',
               'items': ["Inspecting the field's broader metadata such as kind or the full option list; use "
                         'connector.gh.project.field for the parent field surface.',
                         "Mutating an issue's project field value; use "
                         'connector.gh.project.issue.field_single_select.set when the workflow should actually set the '
                         'value after validation.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh.project.field',
                               'summary': 'Parent field probe that returns the field kind and full option list instead '
                                          'of only one boolean option check'},
                              {'handle': 'connector.gh.project.issue.field_single_select.set',
                               'summary': 'Action for setting one single-select project field value after the option '
                                          'check succeeds'},
                              {'handle': 'connector.gh.project.issue.field_iteration.set',
                               'summary': 'Action for setting one iteration field value when the project field is '
                                          'iteration-backed rather than free-form'}]},
              {'heading': 'Examples',
               'items': ['gh.project.field.option with inputs {"field": "Status", "option": "Done", "project_id": '
                         '"PVT_kwDOExample"}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.project.field',
                         'connector.gh.project.issue.field_single_select.set',
                         'connector.gh.project.issue.field_iteration.set']}]})

def info():
    return probe(
        name="project.field.option",
        human=HUMAN,
        inputs={"project_id": "string", "field": "string", "option": "string"},
        outputs={"exists": "boolean"},
        failure_modes=("project_not_found", "probe_failed"),
        handler=run,
        summary="Return whether one named allowed value exists in one GitHub Project field when that field exposes a selectable value set",
    )


def run(ctx: OperationContext):
    project_id = str(ctx.input("project_id"))
    field_name = str(ctx.input("field"))
    option_name = str(ctx.input("option"))
    fetched = fetch_project_fields(ctx, project_id, diagnostic_prefix="probe.gh_project_field_option")
    if not isinstance(fetched, tuple):
        return fetched
    project, raw = fetched

    for node in field_nodes(project):
        if not isinstance(node, dict):
            continue
        if node.get("name") != field_name:
            continue
        return ok(
            summary="GitHub project field allowed-value fact retrieved successfully",
            outputs={"exists": option_name in field_options(node)},
            raw=raw,
        )

    return ok(
        summary="GitHub project field allowed value was not found",
        outputs={"exists": False},
        raw=raw,
    )
