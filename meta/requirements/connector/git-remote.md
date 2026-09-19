# Git remote observation requirements

`git.remote` is a read-only probe answering which effective fetch URLs, push URLs,
and mirror setting one named remote has in local Git configuration.

- Accept a required `remote: string` configured identifier, including nested names
  such as `team/origin`. Reject empty names, whitespace, NUL, and leading `-`.
- Report `name`, `exists`, `fetch_urls`, `push_urls`, and nullable `mirror`.
  Exact inventory absence is successful `exists=false`, empty URL arrays, and
  `mirror=null`, preserving the requested name.
- For an existing remote, observe all effective URLs through Git's URL resolution,
  including rewrites and push-URL fallback. Preserve literal observed values and
  their order and duplicates. Do not normalize, trim, redact, or impose URL safety,
  host/protocol restrictions, or remote policy. The caller chooses acceptable
  destinations.
- An absent mirror setting on an existing remote means `mirror=false`.
- Perform no network access or mutation. Observations do not establish remote
  identity, reachability, authentication, or the destination of a later push.
  Configuration reads are non-atomic and may become stale.
- Fail local command or malformed-response observations honestly with
  `probe_failed`; do not substitute absence or partial success for failure.
- Keep repository context in `git.repo`, current-branch tracking in `git.upstream`,
  configured destination observation in `git.remote`, and publication in
  `git.sync.push`. Shared Git prerequisites belong to family bootstrap.

The probe uses ordinary evaluation in `check`, `review`, `plan`, `run`, `explain`,
and `next`, without engine-mode logic. Features, search, operation metadata, and
verified describe examples must publish this same observation contract.

See the [model](../../model/connector/git-remote.md) for command and failure details.
