# Git tag-only fetch requirements

- `git.sync.fetch-tags` fetches only `refs/tags/*` from one configured remote into local tag refs.
- It does not update branches, merge work, prune retained local tags, force-move a conflicting local tag, or publish any ref.
- A successful fetch refreshes local tag observations for later workflow gates. It is not an atomic guarantee that a remote tag cannot appear after the fetch.
- A workflow that creates a release remotely must treat its own final tag-creation check as authoritative; a local preflight fetch is only an early diagnostic.
