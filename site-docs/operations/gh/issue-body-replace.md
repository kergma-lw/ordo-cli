# GitHub issue body replace

the workflow's GitHub repository context already names the normal repository target and the workflow should rewrite one issue body there by issue number.

Replace the entire GitHub issue body with one new body string and report whether the resulting body changed. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The workflow owns the canonical issue description and should rewrite the full body deterministically.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.
- `body`: required.

## Result and boundary

- Usable result fact: `issue_ref`.
- Usable result fact: `url`.
- Usable result fact: `body`.
- Usable result fact: `changed`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails.

## Do not use for

- Preserving the current body and merely adding one extra section; use connector.gh.issue.body.append for that narrower update.
- Thread-style follow-up notes; use connector.gh.issue.comment.add when the update belongs in conversation history rather than the body.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.issue.body.append`](issue-body-append.md): Append one extra fragment while preserving the rest of the current body
- [`connector.gh.issue.comment.add`](issue-comment-add.md): Add a conversational note instead of rewriting the body
- [`connector.gh.issue`](issue.md): Probe the current issue body before deciding whether a full rewrite is appropriate

## Inspect next

- connector.gh.issue.body.append
- connector.gh.issue.comment.add
- connector.gh.issue

## Exact machine contract

Use `ordo-help operation gh.issue.body.replace --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_issue_body_replace_step

Rewrite the full issue body when the workflow owns the canonical issue description.

```yaml
  - name: replace-body
    uses: gh.issue.body.replace
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      body: |
        Document the onboarding checklist.

        Checklist synced.
```
