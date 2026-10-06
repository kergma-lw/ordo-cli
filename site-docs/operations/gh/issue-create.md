# Create GitHub issue

Open a new issue in the workflow's normal GitHub repository or in one deliberate repository override.

Create one new GitHub issue in one repository and return its canonical reference, number, title, and URL for later workflow steps. Prefer the workflow's GitHub repository context as the normal repository target and use an explicit repository argument only as a one-off override.

## Use when

- The workflow must open a new issue and then reuse the returned issue number or URL in later steps.

## What to provide

- Provide a non-empty issue title. Optionally provide body text; omit it when the issue should start without a body.
- Use the workflow's GitHub repository context normally. Name a repository only for a deliberate one-off target change.
- `repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override that default for this call.
- `title`: required.
- `body`: optional.

## Result and boundary

- Later steps can use the created issue's repository-qualified reference, number, title, or URL.
- Creation can succeed before a later step fails and is not rolled back. It fails when the target repository cannot be used, the title is blank, or GitHub blocks creation.
- Usable result fact: `issue_ref`.
- Usable result fact: `url`.
- Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision. A successful change is not rolled back if a later workflow step fails.

## Do not use for

- Editing or commenting on an already existing issue; use the narrower body or comment actions for that follow-up work.
- Reading current issue metadata before deciding whether creation is necessary; use connector.gh.issue or other probe surfaces first when the issue already exists.

## Related references

Use these related references when you need a neighboring operation or more context.


- [`connector.gh.issue`](issue.md): Probe the created issue later when you need its full current snapshot
- [`connector.gh.issue.comment.add`](issue-comment-add.md): Add a follow-up comment to an existing issue instead of creating a new one
- [`connector.gh.issue.body.replace`](issue-body-replace.md): Rewrite the body of an existing issue instead of creating a fresh issue

## Inspect next

- connector.gh.issue
- connector.gh.issue.comment.add
- connector.gh.issue.body.append

## Exact machine contract

Use `ordo-help operation gh.issue.create --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### gh_issue_create_step

Create one new GitHub issue and register its returned reference for later steps.

```yaml
  - name: Create issue
    uses: gh.issue.create
    with:
      repository: inputs.repository
      title: inputs.title
      body: inputs.initial_body
    register: created_issue
```
