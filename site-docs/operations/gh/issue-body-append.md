# GitHub issue body append

the workflow's GitHub repository context already names the normal repository target and the workflow should append one note to one issue body there.

Append one text fragment to the end of an existing GitHub issue body, optionally separated from the prior body by one explicit separator. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The workflow should preserve the current issue body and add one extra section, note, or footer to it.

## What to provide

- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `issue_number`: required.
- `text`: required.
- `separator`: optional.

## Result and boundary

- Usable result fact: `issue_ref`.
- Usable result fact: `url`.
- Usable result fact: `body`.
- Usable result fact: `changed`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails.

## Do not use for

- Regenerating the whole canonical body from scratch; use connector.gh.issue.body.replace for a full rewrite.
- Adding conversational discussion that belongs in the comment thread instead of the issue body; use connector.gh.issue.comment.add.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.issue.body.replace`](issue-body-replace.md): Rewrite the full body instead of appending one trailing fragment
- [`connector.gh.issue.comment.add`](issue-comment-add.md): Write a discussion comment instead of mutating the issue body
- [`connector.gh.issue`](issue.md): Probe the current body first when the append decision depends on existing issue metadata

## Inspect next

- connector.gh.issue.body.replace
- connector.gh.issue.comment.add
- connector.gh.issue

## Exact machine contract

Use `ordo-help operation gh.issue.body.append --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_issue_body_append_step

Append one extra note to the existing issue body while preserving earlier body content.

```yaml
  - name: Append body note
    uses: gh.issue.body.append
    with:
      repository: inputs.repository
      issue_number: step.created_issue.outputs.number
      text: "Follow-up note: checklist synced."
      separator: "\n\n"
```
