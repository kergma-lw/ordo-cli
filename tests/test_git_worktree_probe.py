"""Safety boundaries for the Git worktree probe."""

import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

from connectors.git.probes.worktree import run


def test_worktree_probe_disables_git_optional_locks():
    command = Mock(return_value=SimpleNamespace(
        stdout="",
        raw={"returncode": 0},
    ))
    context = SimpleNamespace(
        bootstrap=lambda: SimpleNamespace(context={"repository_root": "/tmp/repository"}),
        command=command,
    )

    result = run(context)

    assert result.status == "ok"
    command.assert_called_once_with(
        ["git", "--no-optional-locks", "status", "--porcelain"],
        failures={"os_error": "probe_failed", "nonzero": "probe_failed"},
    )
