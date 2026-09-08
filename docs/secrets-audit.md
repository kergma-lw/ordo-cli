# Repository audit

## Entry points and selection

```text
ordo-playbook check audit-publication
ordo-playbook review audit-publication
ordo-playbook run audit-publication
ordo-playbook check audit-secrets-tree
ordo-playbook review audit-secrets-tree
ordo-playbook run audit-secrets-tree
```

`audit-secrets-tree` scans current tracked worktree bytes with Gitleaks.
`audit-publication` composes the following checks in order. Its `scanner` input
defaults to `all`; selection is fail-fast, not a promise that every check runs.

| Selector | Scope | Routine kind |
| --- | --- | --- |
| `gitleaks-tree` | Current tracked worktree bytes | Action |
| `gitleaks-history` | Local reachable commit patches | Action |
| `gitleaks-metadata` | Raw commit and annotated tag objects | Action |
| `bandit` | Production Python, medium severity/confidence or higher | Probe |
| `semgrep` | Production Python, four local review-cue rules | Probe |
| `pip-audit` | Installed runtime dependency closure, consent-gated lookup | Probe |
| `shellcheck` | Tracked shell files | Probe |
| `inventory` | Privacy and artifact candidates for manual review | Action |

Select one check with `--input scanner=bandit`, for example. Values other than
`all` and the eight selectors above are rejected. `allow_dependency_lookup`
must be an explicit boolean and defaults to `false`. Network lookup requires
consent through this input:

```text
ordo-playbook run audit-publication --input scanner=pip-audit --input allow_dependency_lookup=true
```

Consent authorizes sending installed runtime package names and versions to the
PyPI vulnerability service, not repository files. Tool installation is separate
from lookup consent. For `all` or `pip-audit`, the gate blocks before pip-audit
invocation without consent; the adapter also enforces authorization. Earlier
checks may finish before the gate, but ShellCheck and inventory follow it and
are not reached if it blocks. Selected offline checks bypass the gate.

## Tool baseline

Git and the project-local `.venv/bin/python` are required. Gitleaks **8.20.1**
must be on `PATH`. The shared helper's `PINS` requires **Bandit 1.9.4**,
**Semgrep CE 1.176.1**, and **pip-audit 2.10.1** in the project `.venv`, with
the project's Python **>=3.12** baseline; there is no global-tool fallback.
**ShellCheck 0.11.0** is version-checked on `PATH`. Missing tools or mismatched
versions make the relevant check incomplete.

Adapters do not install tools, download registry rules, upload source, use
`--fix`, or apply remediation. Semgrep's installed console entrypoint is invoked
through the verified venv interpreter, not its deprecated `python -m semgrep`
entrypoint. Local configuration and disabled telemetry are not a network sandbox.

## Worktree scope

Tree-based checks enumerate tracked paths but read **current worktree bytes**,
not index blobs or staged-only contents. Tracked files remain included despite
ignore rules. New files must be tracked to be included; workflows do not stage
them. For commit checks, ensure the intended tree matches the index. Missing
tracked files are excluded and counted in `excluded_deleted`.

Private temporary snapshots copy all present tracked files before language
selection, without binary or size exclusions at the copying stage. Symlinks,
including parent-directory symlinks, nonregular files, gitlinks/submodules,
unresolved index entries, and LFS pointers fail incomplete. Materialized regular
LFS content is ordinary input. Safety checks apply outside language subsets too;
empty Python or shell selections fail incomplete.

Keep the worktree, refs, and object storage stable. Checks take independent
snapshots, not an atomic combined snapshot. Per-file and endpoint checks cannot
guarantee atomicity or detect every change, including changes later reverted.

## Gitleaks coverage

Explicit configuration extends Gitleaks' pinned built-in rules. Repository
configuration and ignore files do not configure these invocations; tracked files
remain scan input. Inline `gitleaks:allow` suppression is disabled, and snapshot
layout prevents implicit source-root ignore-file loading. Built-in allowlists,
rules, binary handling, and other scanner limits still apply. Arbitrary passwords,
personal data, encoded secrets, and archive contents are not reliably detected.

History and metadata use private local shared bare mirrors of available local
refs and HEAD, including detached HEAD and remote-tracking refs. They never fetch
or rewrite the source repository. Global/system Git configuration, hooks,
replacement objects, external diff, and text conversion are disabled; source
grafts are not copied. Shallow or configured partial clones and missing reachable
objects fail incomplete. Shared object storage must remain available: do not prune
it during an audit. Ref/HEAD endpoint checks and `coverage_snapshot_sha256`
identify the captured refs, not an attestation of every scanned byte. Reports
include coverage counts without publishing ref names.

History scans commit patches using `--all --full-history --root -m --no-ext-diff
--no-textconv --no-renames`, including root commits and per-parent merge patches.
It rejects empty commit history. It does not scan commit messages, authorship,
tag annotations, or non-commit ref targets; non-commit refs are counted separately.
Patch scanning is not exhaustive Git-object scanning.

Metadata scans full raw reachable commit objects, including author/committer
identities, messages, and additional headers. It follows annotated tag object/type
links from local refs, including nested tags and annotations targeting blobs or
trees; only those annotations, not blob/tree target contents, are scanned.
Lightweight tags have no annotation object. Missing targets, inconsistent types,
malformed links, and cycles fail incomplete. Metadata-only checks can cover tags
without commits, but no metadata objects at all fails incomplete.

Metadata has a **16 MiB per-object limit**, checked before body reads; oversized
objects fail incomplete rather than being truncated. There is **no aggregate
memory cap**. Raw objects become private generated scan files, not configuration.
Findings expose only rule ID, object type/ID, and positive raw-object start line;
all entries are validated, including those beyond the publication cap.

Remote-only refs, reflogs, unreachable objects, LFS payloads, and submodule
repositories are outside historical coverage. Worktree and untracked contents
are outside history/metadata coverage. Metadata secret detection does not assess
the privacy acceptability of identities, email addresses, or messages.

## Python analysis

Bandit and Semgrep select tracked `.py` files only under `src/`, `connectors/`,
`tools/`, and `.ordo/scripts/`. Tests, untracked files, history, and shell strings
embedded in workflow YAML are excluded.

Bandit uses explicit files, JSON, `--quiet`, `--ignore-nosec`, and **MEDIUM-or-higher
severity and confidence**. Quiet mode preserves JSON without progress output; it
does not suppress findings. Source `.bandit` configuration is not used. Every
selected file must appear in metrics. Errors, missing coverage, malformed reports,
and inconsistent exits fail incomplete. Lower-threshold findings are outside
policy, not evidence of safety.

`.ordo/security/bandit-reviewed.json` narrowly accepts `B506` at
`src/ordo/runtime/loading.py:175`. `_AuthoredStyleSafeLoader` subclasses
`yaml.SafeLoader` and customizes the string constructor to preserve authored
quoting. Bandit's loader-name check does not recognize this inheritance;
`yaml.safe_load()` would lose required string-style information.

Acceptance requires the exact rule, path, line, and SHA-256 of the **whole source
file**, covering the loader and its constructors. Changed bytes stop acceptance;
there is no automatic renewal or global B506 suppression. Missing or invalid
policy fails incomplete. Reports retain `raw_finding_count`, `accepted_count`,
unresolved `finding_count`, and accepted locations with exception IDs. Clean means
no unresolved findings under this policy. Raw-exit consistency, scanner errors,
and coverage failures cannot be masked by an exception.

Semgrep uses only `.ordo/security/semgrep.yml` and its four rules:
`ordo-shell-execution`, `ordo-dynamic-execution`, `ordo-pickle-deserialization`,
and `ordo-shell-text`. These are review cues, not a broad security ruleset or
vulnerability proofs. Reports include `rules_sha256`. Both this rule file and the
Bandit policy are trusted local configuration read directly even if untracked;
they do not expand source coverage.

Semgrep uses local OSS rules, metrics/version checks off, `--strict`,
`--disable-nosem`, `--no-git-ignore`, and `--max-target-bytes 0`. Errors, skipped
rules, missing per-path scanned coverage, and incompatible reports/exits fail
incomplete. Restricted YAML-shape validation does not validate the full pattern
grammar by itself.

## Shell and dependency analysis

ShellCheck selects tracked `.sh`/`.bash` files across roots and recognized
`/bin/sh`, `/bin/bash`, or `/usr/bin/env` sh/bash shebangs, including `env -S`.
It never executes scripts and does not inspect YAML shell strings or history.
It uses `--norc`, removes `SHELLCHECK_OPTS`, and rejects inline
`external-sources=` assignments, even `false`. Inline disable comments still
apply; sources outside scope are not followed by default. JSON1 comments and
exit consistency are validated; exits outside `0`/`1` fail incomplete. Syntax
findings do not prove complete semantic analysis was possible.

pip-audit follows installed runtime dependencies from `pyproject.toml`, including
environment markers and requested extras. It checks exact installed versions,
not all allowed versions. Build, test, and audit-tool dependencies are not roots
unless included in that runtime closure. Missing distributions, constraint or
metadata mismatches, direct URL/local/editable installs, and missing `WHEEL`
metadata fail incomplete.

Exact requirements are written privately for `--no-deps --disable-pip --strict`
with the PyPI service. Reports must have `dependencies` and empty `fixes`, no
skip reasons, and exactly the requested names/versions without duplicates or
omissions. Clean means no reported advisories for that closure at lookup time,
not that dependencies have no vulnerabilities.

## Results and confidentiality

Wrapper exits are `0` for `clean` (inventory: `manual-review-needed`), `1` for
`findings`, and `2` for `incomplete`. Gitleaks uses scanner exit `10` for findings;
scanner exit `1` means incomplete even with partial findings. Ordo normalizes
nonzero routine exits as execution failures, not distinct audit engine statuses.

Successful checks publish sanitized JSON objects. Data probes expose
`outputs.data` only on success; nonzero exits leave sanitized failure stdout
tails in routine diagnostics, not structured probe outputs. Fail-fast stops
before the failed check's publish step and later checks. Earlier reports remain
in execution evidence but may be absent from the CLI failure summary; there is
no guaranteed final bundle. The final summary reports `audit_scope` and
`publication_status: manual-review-needed`, even for one selected check.

Unresolved findings block the gate but are review targets, not automatically
confirmed vulnerabilities. Inspection modes (`check`, `review`, `plan`, `explain`,
`next`) do not certify results; `run` executes the audit. Probe intent is
observation, with temporary artifacts as technical effects. Engine `ok`, a clean
scan, or a selected check is not publication clearance. These workflows do not
install hooks, change GitHub settings, stage files, or run the test suite.

Reports exclude raw child stdout/stderr, source excerpts, secrets, scanner message
text, and advisory prose. Validated rule/advisory IDs, relative locations, levels,
package names/versions, and fix versions may be included. Finding lists are capped
at **50**, with full counts and truncation indicators or count/list differences.
Paths, package inventories, and object IDs can still disclose private context.

Snapshots and raw reports use private temporary storage outside the repository,
normally removed on success/failure. Abrupt termination may leave artifacts;
deletion is not secure erasure. Sanitized routine logs may persist in private
per-invocation directories. This is not isolation from the same UID or root, nor
a guarantee that published pathnames cannot later change. Review before sharing.

## Privacy and artifact inventory

Inventory examines current tracked names and bounded UTF-8 text for absolute
local paths, email identifiers, and private network references; historical names
from all locally reachable commit trees; and nonignored untracked names only.
It does not read untracked or historical file contents, traverse ignored files,
assess historical metadata privacy, follow untracked symlinks, or unpack archives.
History uses the same mirror safety limits and its own independent coverage hash;
per-commit path enumeration can be expensive.

Tracked text inspection is limited to **2 MiB per file** and **128 MiB total**,
after snapshot copying. Binary/non-UTF-8, oversized, and over-budget skips are
counted; these limits do not bound snapshot disk use. Categories include archives,
databases/dumps, logs, backups, credentials/environment files, fixtures/sample
data, and local configuration. Legitimate documentation and source may match.

Reports retain full per-scope/category counts and at most **40** deterministic
round-robin candidate examples, with omitted counts. Candidates are
path/category/scope tuples, not unique files. Locations are capped at **240
characters**; long paths receive a hash, and credential-like long tokens cause
locations to be withheld. Matched values, excerpts, author/email lists, remote
URLs, and child output are not published. Samples are not complete review lists.

Inventory always requires manual review, even with zero candidates; skips and
omissions remain review obligations. It neither auto-approves nor removes files
and applies no allowlist. Review project automation under `.ordo/` individually;
directory membership alone does not establish sensitivity or safety.
Repository/project IDs are not secrets by default; assess absolute paths for
portability separately from private data. For recognized secrets, rotate or
revoke first, then address exposed content and history.
