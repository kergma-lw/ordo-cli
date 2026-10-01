"""Filesystem connector family."""

from __future__ import annotations

from connectors._family import ActionHandler, ProbeHandler, assemble_family
from ordo.model.human import HumanDeclaration, declare_human

from .bootstrap import BOOTSTRAP

ORDER = 40

FAMILY_HUMAN = declare_human({'title': 'Filesystem connector',
 'goal': 'You need one typed filesystem probe instead of a broader shell command just to inspect a file.',
  'summary': 'Published filesystem connector family for observing UTF-8 content and metadata from one '
            'regular file, not an atomic snapshot.',
 'sections': [{'heading': 'Use when',
               'items': ['You need one typed filesystem probe instead of a broader shell command just to inspect a '
                         'file.']},
              {'heading': 'Do not use for',
               'items': ['Writing, mutating, or deleting files; this family currently publishes observation only.',
                          'Atomic snapshots or workspace confinement; parent symlinks and hardlinks remain allowed.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
                'references': [{'handle': 'operations',
                                'summary': 'Flat public operation catalog across all connector namespaces'},
                               {'handle': 'connector.fs.file',
                                'summary': 'Observe content and metadata from one opened regular file'},
                               {'handle': 'workflow-rules.routine.*',
                                'summary': 'Guidance for the limited project-local helper path after published operations and composition are exhausted'}]},
               {'heading': 'Inspect next', 'items': ['connector.fs.file', 'operations', 'workflow-rules.routine.*']}]})


def get_family_human() -> HumanDeclaration:
    return FAMILY_HUMAN


_ASSEMBLED = assemble_family(package_name=__name__, namespace="fs", bootstrap=BOOTSTRAP)


def get_connector():
    return _ASSEMBLED.connector


def get_probe_handler(name: str) -> ProbeHandler | None:
    return _ASSEMBLED.probe_handlers.get(name)


def get_action_handler(name: str) -> ActionHandler | None:
    return _ASSEMBLED.action_handlers.get(name)
