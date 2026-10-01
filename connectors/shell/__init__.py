"""Shell connector family."""

from __future__ import annotations

from connectors._family import ActionHandler, ProbeHandler, assemble_family
from ordo.model.human import HumanDeclaration, declare_human

from .bootstrap import BOOTSTRAP

ORDER = 30

FAMILY_HUMAN = declare_human({'title': 'Shell connector',
 'goal': 'You are inspecting, migrating, or containing older workflow logic that still depends on shell.command as a '
         'compatibility surface.',
 'summary': 'Published shell connector family for one coarse legacy command-execution action that runs arbitrary shell '
            'text inside the current working directory context.',
 'sections': [{'heading': 'Use when',
               'items': ['You are inspecting, migrating, or containing older workflow logic that still depends on '
                         'shell.command as a compatibility surface.',
                         'You need to understand the broad fallback namespace that exists when no narrower published '
                         'connector operation yet expresses the required external behavior.']},
               {'heading': 'Do not use for',
                'items': ['New workflow authoring when a narrower published connector surface, a composed public '
                           'workflow, or a published project-local helper can express the intent more honestly.',
                          'Treating arbitrary shell execution as a normal first-choice operation family; this namespace '
                          'is intentionally coarse and high-risk.']},
               {'heading': 'Start here',
                'items': ['Start with operations to find a narrower published operation. If none fits, read '
                          'workflow-rules.shell.command before inspecting the legacy shell.command action.',
                          'No checked family-level example is published because a generic shell workflow would endorse an '
                          'unsafe fallback. The checked shell.command example is limited to an explicit legacy '
                          'compatibility workflow.']},
               {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
                'references': [{'handle': 'operations',
                                'summary': 'Flat public operation catalog across all connector namespaces'},
                              {'handle': 'connector.shell.command',
                               'summary': 'The one coarse shell action published in this family'},
                              {'handle': 'workflow-rules.shell.command',
                               'summary': 'Authoring rule that explains why shell.command is forbidden for new '
                                          'workflow work'},
                               {'handle': 'workflow-rules.routine.*',
                                 'summary': 'Authoring guidance for the limited project-local helper path preferred over '
                                           'new shell.command work when structured public surfaces are exhausted'}]},
               {'heading': 'Inspect next',
                'items': ['connector.shell.command', 'workflow-rules.shell.command', 'workflow-rules.routine.*', 'operations']}]})


def get_family_human() -> HumanDeclaration:
    return FAMILY_HUMAN


_ASSEMBLED = assemble_family(package_name=__name__, namespace="shell", bootstrap=BOOTSTRAP)


def get_connector():
    return _ASSEMBLED.connector


def get_probe_handler(name: str) -> ProbeHandler | None:
    return _ASSEMBLED.probe_handlers.get(name)


def get_action_handler(name: str) -> ActionHandler | None:
    return _ASSEMBLED.action_handlers.get(name)
