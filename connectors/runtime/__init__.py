"""Runtime connector family."""

from __future__ import annotations

from connectors._family import ActionHandler, ProbeHandler, assemble_family
from ordo.model.human import HumanDeclaration, declare_human

from .bootstrap import BOOTSTRAP

ORDER = 5

FAMILY_HUMAN = declare_human({'title': 'Runtime connector',
  'goal': 'You need a published operation that acts only within the current Ordo workflow run.',
  'summary': 'Published runtime connector family for current-run operations, including fresh UUID generation and a '
             'legacy profile-switch action.',
  'sections': [{'heading': 'Use when',
                'items': ['A workflow needs a structured current-run value or context operation rather than an '
                          'external-system call.',
                          'You are maintaining a legacy workflow that still switches profiles through an action.']},
                {'heading': 'Do not use for',
                 'items': ['New profile-switch authoring when workflow.step.profile_switch can express the intent directly and '
                           'more honestly.',
                           'External system operations; this family changes local Ordo runtime context rather than '
                           'calling a remote tool or service.']},
                {'heading': 'Start here',
                 'items': ['For a fresh opaque value needed during this run, inspect connector.runtime.uuid.generate.',
                           'For new profile-switch authoring, start with workflow.step.profile_switch; inspect '
                           'connector.runtime.profile.use only when maintaining an existing legacy workflow.']},
                {'heading': 'Related references',
                'body': 'Use these related references when you need a neighboring operation or more context.',
                 'references': [{'handle': 'operations',
                                 'summary': 'Flat public operation catalog across all connector namespaces'},
                               {'handle': 'connector.runtime.uuid.generate',
                                'summary': 'Generate a fresh UUID for later work in the current run'},
                               {'handle': 'connector.runtime.profile.use',
                                'summary': 'Legacy runtime action for switching the active execution profile in the '
                                'current run'},
                              {'handle': 'workflow.step.profile_switch',
                               'summary': 'Preferred workflow-native step surface for profile switching'}]},
               {'heading': 'Inspect next',
                 'items': ['connector.runtime.uuid.generate', 'connector.runtime.profile.use', 'workflow.step.profile_switch']}]})


def get_family_human() -> HumanDeclaration:
    return FAMILY_HUMAN


_ASSEMBLED = assemble_family(package_name=__name__, namespace="runtime", bootstrap=BOOTSTRAP)


def get_connector():
    return _ASSEMBLED.connector


def get_probe_handler(name: str) -> ProbeHandler | None:
    return _ASSEMBLED.probe_handlers.get(name)


def get_action_handler(name: str) -> ActionHandler | None:
    return _ASSEMBLED.action_handlers.get(name)
