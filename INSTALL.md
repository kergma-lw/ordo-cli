# Local Git safety hooks

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
