"""runtime.profile.use action."""

from __future__ import annotations

from ordo.plugin_sdk import action, ok
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'Use declared runtime profile',
 'goal': 'You are reading or migrating older workflow logic that still invokes runtime.profile.use directly.',
 'summary': 'Legacy runtime action for switching later execution in the current run to another declared profile.',
 'sections': [{'heading': 'Use when',
               'items': ['An existing compatibility workflow must switch profiles for later steps before it can be '
                          'migrated to the workflow-native form.']},
               {'heading': 'What to provide',
                'items': ['`profile`: required; provide the name of a profile already declared for this run. This action does not create or '
                          'discover profiles.']},
              {'heading': 'Result and boundary',
                'items': ['Later execution in the current run uses the selected profile and returns it as `profile`.',
                         'This legacy action changes only later work in the current run. Replace it with the workflow '
                          'profile-switch form during migration; it does not retroactively change earlier work or a fixed '
                          'workflow profile.']},
              {'heading': 'Do not use for',
               'items': ['New profile-switch authoring; use workflow.step.profile_switch instead of a legacy runtime '
                         'action call.',
                         'Declaring a fixed workflow-owned profile binding; use workflow.profile when the subtree '
                         'should always start under one profile.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.runtime', 'summary': 'Parent runtime connector family'},
                              {'handle': 'workflow.step.profile_switch',
                               'summary': 'Preferred workflow-native step surface that replaces this legacy action'},
                              {'handle': 'workflow.profile',
                               'summary': 'Workflow field for fixed project-local profile binding before guards run'}]},
              {'heading': 'Examples', 'items': ['runtime.profile.use with inputs {"profile": "frontend"}']},
               {'heading': 'Inspect next', 'items': ['workflow.step.profile_switch', 'workflow.profile', 'profile.name']}]})

def info():
    return action(
        name="profile.use",
        human=HUMAN,
        summary="Legacy compatibility action for switching runtime execution to another declared profile",
        inputs={"profile": "string"},
        effects=("switch runtime profile for later execution in the current run",),
        outputs={"profile": "string"},
        failure_modes=("input_error", "execution_error"),
        deprecated=True,
        replaced_by=("workflow.step.profile_switch",),
        handler=run,
    )


def run(ctx):
    return ok(summary="Profile switch requested", outputs={"profile": str(ctx.input("profile"))})
