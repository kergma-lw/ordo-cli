"""Compose connector family."""

from __future__ import annotations

from connectors._family import ActionHandler, ProbeHandler, assemble_family
from ordo.model.human import HumanDeclaration, declare_human

from .bootstrap import BOOTSTRAP

ORDER = 15

FAMILY_HUMAN = declare_human({'title': 'Compose connector',
 'goal': 'You need published Compose-aware project or service operations instead of shelling out to ad hoc docker '
         'compose commands.',
 'summary': 'Published Docker Compose connector family for observing one Compose project or service and for starting, '
            'stopping, or removing service runtime instances.',
 'sections': [{'heading': 'Use when',
               'items': ['You need published Compose-aware project or service operations instead of shelling out to ad '
                         'hoc docker compose commands.',
                         'You want one shared family surface that separates observation from lifecycle-changing '
                         'actions.']},
               {'heading': 'Do not use for',
                'items': ['Pure workflow-local branching or value shaping that does not need an external orchestrator '
                          'call.',
                          'Repository-local helper scripts when the published Compose operations already express the '
                          'intent directly.']},
               {'heading': 'Start here',
                'items': ['Set the Compose directory or file in profile.connectors, then inspect connector.compose.project '
                          'for a project decision or connector.compose.service for one service decision.',
                          'No checked family-level example is published because Compose targets and lifecycle authorization '
                          'are deployment-specific. Start with a focused project or service observation before choosing an '
                          'action.']},
               {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
                'references': [{'handle': 'operations',
                                'summary': 'Flat public operation catalog across all connector namespaces'},
                              {'handle': 'profile.connectors',
                               'summary': 'Profile field where family-specific connector context such as '
                                          'compose.directory or compose.file can be authored'},
                              {'handle': 'connector.compose.project', 'summary': 'Probe one whole Compose project'},
                              {'handle': 'connector.compose.service', 'summary': 'Probe one declared Compose service'},
                              {'handle': 'connector.compose.start',
                               'summary': 'Start one Compose project or one declared service'}]},
              {'heading': 'Inspect next',
               'items': ['connector.compose.project',
                         'connector.compose.service',
                         'connector.compose.start',
                         'connector.compose.stop',
                         'connector.compose.remove']}]})


def get_family_human() -> HumanDeclaration:
    return FAMILY_HUMAN


_ASSEMBLED = assemble_family(package_name=__name__, namespace="compose", bootstrap=BOOTSTRAP)


def get_connector():
    return _ASSEMBLED.connector


def get_probe_handler(name: str) -> ProbeHandler | None:
    return _ASSEMBLED.probe_handlers.get(name)


def get_action_handler(name: str) -> ActionHandler | None:
    return _ASSEMBLED.action_handlers.get(name)
