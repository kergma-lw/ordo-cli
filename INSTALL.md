# Install Ordo

The supported user installation channel is a versioned wheel attached to a
[GitHub Release](https://github.com/kergma-lw/ordo-cli/releases). Ordo supports
Python 3.12 or later. Its Python dependencies, including PyYAML, are installed
from the wheel metadata.

Choose a release version and substitute the same value for both `X.Y.Z`
occurrences below:

```sh
pipx install "https://github.com/kergma-lw/ordo-cli/releases/download/vX.Y.Z/ordo-X.Y.Z-py3-none-any.whl"
```

`pipx` creates and manages an isolated environment, then makes
`ordo-playbook` and `ordo-help` available on your command path. Verify the
installation with:

```sh
ordo-playbook --help
ordo-help --help
```

If you do not use `pipx`, install the same wheel into an environment you
manage:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install "https://github.com/kergma-lw/ordo-cli/releases/download/vX.Y.Z/ordo-X.Y.Z-py3-none-any.whl"
.venv/bin/ordo-playbook --help
.venv/bin/ordo-help --help
```

Release tags use `vX.Y.Z`; the wheel version and filename omit the `v` prefix.
For example, release tag `v0.1.0` supplies `ordo-0.1.0-py3-none-any.whl`.

## Contributor setup

A source checkout and editable install are for contributing to Ordo, not for
adopting it in another project:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Local Git safety hooks

To enable the repository's safety hooks, run these commands from the repository
root after cloning:

```sh
chmod +x .githooks/pre-commit .githooks/pre-push
git config --local core.hooksPath .githooks
```

The hooks block:

- Commits while the current branch is `main`.
- Pushes that update or delete `refs/heads/main` on any remote, including pushes
  such as `feature:main`.

Feature-branch commits and pushes remain allowed. Fast-forward updates of local
`main` are unaffected. Detached-HEAD commits are allowed.

Activation is local to each clone. The `core.hooksPath` setting replaces the
previous hook directory; if you already use hooks, integrate them before changing
this setting.

These hooks prevent accidental operations, not deliberate bypasses. Both can be
bypassed with `--no-verify`; they do not replace server-side branch protection.

## Local status

Run `GIT_OPTIONAL_LOCKS=0 ordo-playbook run global-status` from the repository root to publish one
record containing `branch`, `clean`, `upstream`, `ahead`, `behind`, and `task`.
A dirty worktree is valid. The task is the repository-keyed stored
`issue_number` from `.ordo.json`, or `null` when absent.

This is local-only: it does not fetch or use the network or execute hooks.
`GIT_OPTIONAL_LOCKS=0` prevents the existing `git.worktree` probe's Git status
command from optionally refreshing index metadata. The current Git binding does
not let this workflow enforce that environment setting itself; use it for all
status invocations that must avoid Git state mutations.
Ahead and behind counts compare HEAD with the locally cached upstream
ref, so they do not establish the current remote state. An absent, detached, or
unresolved upstream is unavailable and yields `null` for upstream and both
counts. Local-branch upstreams (`remote = .`) are unsupported by the current Git
probe and cause a probe failure rather than an invented status.

Git hook configuration and executability are not inspected by this workflow.
