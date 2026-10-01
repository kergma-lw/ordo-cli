# Git remote

A workflow needs the recorded destinations for one named remote before deciding whether to synchronize or publish.

Observe one named remote, including whether it exists, its fetch and push destinations, and whether it mirrors.

## Use when

- Use this before fetch or push when a workflow needs to select a local remote by name.
- Later logic needs the recorded destination facts, not proof that a network operation will succeed.

## Do not use for

- Destination safety or policy; decide whether an observed destination is acceptable.
- Reachability, access, remote identity, or proof of a later push destination.
- Repository-root facts, current-branch tracking, or publication itself; use connector.git.repo, connector.git.upstream, or connector.git.sync.push respectively.

## What to provide

- `remote`: required; provide a recorded remote name, such as origin or team/origin. It identifies a saved destination rather than a destination to invent.

## Result and boundary

- Returns name, exists, fetch_urls, push_urls, and mirror. A missing name is reported with exists=false; recorded destinations are descriptive only and may change, while invalid or unreadable information fails without partial facts.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.git.repo`](repo.md): Local repository-root, git-dir, and default-branch facts
- [`connector.git.upstream`](upstream.md): Current branch's configured tracking remote and tracking ref
- [`connector.git.sync.push`](sync-push.md): Publish a branch to a configured remote after the caller's decision

## Exact machine contract

Use `ordo-help operation git.remote --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### git_remote_exists

Inspect a named remote and publish its name, existence, fetch destinations, push destinations, and mirror state. The workflow stops dependent work when the named remote is absent. Destination acceptance remains the author's decision; recorded destinations are observations, not proof that a later publication is appropriate.

```yaml
version: 0
workflow: inspect-configured-origin
inputs:
  remote:
    default: 'origin'
blocks:
  - steps:
      - name: observe-remote
        uses: git.remote
        with:
          remote: inputs.remote
        register: observed
      - name: require-existing-remote
        gate: step.observed.outputs.exists | eq(true)
      - name: publish-remote-facts
        publish:
          name: step.observed.outputs.name
          exists: step.observed.outputs.exists
          fetch_urls: step.observed.outputs.fetch_urls
          push_urls: step.observed.outputs.push_urls
          mirror: step.observed.outputs.mirror
      - name: count-fetch-urls
        value: step.observed.outputs.fetch_urls | length
        register: fetch_count
      - name: count-push-urls
        value: step.observed.outputs.push_urls | length
        register: push_count
      - name: publish-url-counts
        publish:
          fetch_count: step.fetch_count.outputs.value
          push_count: step.push_count.outputs.value

```
### git_remote_missing

Inspect a named remote and publish its name, existence, fetch destinations, push destinations, and mirror state. The workflow stops dependent work when the named remote is absent. Destination acceptance remains the author's decision; recorded destinations are observations, not proof that a later publication is appropriate.

```yaml
version: 0
workflow: inspect-configured-origin
inputs:
  remote:
    default: 'origin'
blocks:
  - steps:
      - name: observe-remote
        uses: git.remote
        with:
          remote: inputs.remote
        register: observed
      - name: require-existing-remote
        gate: step.observed.outputs.exists | eq(true)
      - name: publish-remote-facts
        publish:
          name: step.observed.outputs.name
          exists: step.observed.outputs.exists
          fetch_urls: step.observed.outputs.fetch_urls
          push_urls: step.observed.outputs.push_urls
          mirror: step.observed.outputs.mirror
      - name: count-fetch-urls
        value: step.observed.outputs.fetch_urls | length
        register: fetch_count
      - name: count-push-urls
        value: step.observed.outputs.push_urls | length
        register: push_count
      - name: publish-url-counts
        publish:
          fetch_count: step.fetch_count.outputs.value
          push_count: step.push_count.outputs.value

```
