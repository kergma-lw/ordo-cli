# Git remote observation model

`git.remote` accepts required `remote: string`. A valid name is nonempty, does not
start with `-`, and contains neither whitespace nor NUL. Names are matched exactly
against `git remote`; nested names such as `team/origin` are ordinary identifiers.

## Structured outputs

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | Requested configured identifier, preserved |
| `exists` | boolean | Exact membership in local remote inventory |
| `fetch_urls` | array of strings | All effective fetch URLs, in observed order |
| `push_urls` | array of strings | All effective push URLs, in observed order |
| `mirror` | boolean or null | Git mirror boolean; null only for a missing remote |

Missing inventory membership succeeds with `exists=false`, both arrays `[]`, and
`mirror=null`. No URL or mirror lookup follows absence.

## Existing remote resolution

1. Read `git remote get-url --all <name>` for fetch URLs.
2. Read `git remote get-url --push --all <name>` for push URLs.
3. Read `git config --bool --get remote.<name>.mirror` for mirror configuration.
   Exit 1 means the setting is absent and yields `false`; successful output must
   be exactly `true` or `false` after removing one trailing LF.

Git owns effective URL resolution, including `insteadOf`, `pushInsteadOf`, and
push-URL fallback. The probe preserves literal observed URLs without normalization,
trimming, or redaction. Only LF separates records; one terminal LF is removed.
Duplicates, whitespace within URLs, CR, and Unicode line separators are preserved.
Each existing-remote URL list must be nonempty and contain no empty record.

URL safety and remote policy are caller responsibilities. No protocol or host
allowlist, URL interpretation, network access, authentication check, or remote
identity assertion is performed. Reads are non-atomic, and do not bind a later
push to this configuration snapshot.

## Failures

All local failures return `probe_failed`, with diagnostic prefix
`probe.git_remote.`:

- `invalid_input`: invalid configured-name operand;
- `inventory_failed`: inventory command failure;
- `invalid_inventory`: malformed or duplicate inventory names;
- `fetch_urls_failed`, `push_urls_failed`: corresponding URL command failure;
- `invalid_fetch_urls`, `invalid_push_urls`: empty list or empty URL record;
- `mirror_failed`: mirror command failure other than exit 1;
- `invalid_mirror`: successful command with a non-boolean spelling.

Raw command evidence is supplementary; consumers use structured outputs, not
stdout parsing. Git executable and repository prerequisites remain family bootstrap
concerns. No partial structured success replaces a failed observation.

## Domain and mode boundaries

`git.repo` observes repository context; `git.upstream` observes current-branch
tracking; `git.remote` observes one configured destination; `git.sync.push`
publishes a branch. Destination acceptance belongs to the caller.

`check`, `review`, `plan`, `run`, `explain`, and `next` retain ordinary probe
evaluation semantics. This probe adds no runtime-mode policy or transport action.
The [requirements](../../requirements/connector/git-remote.md) and public help
describe the same five-field contract.
