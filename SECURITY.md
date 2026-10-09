# Security policy

## Trust model

Workflows, routine implementations, and configured executable helpers are trusted
code. Run only code and configuration you trust. Ordo is not a sandbox for
untrusted workflows and normally operates with the invoking user's permissions.

Treat a pull request's workflow files, routine registry, `.ordo/scripts/`,
connector configuration, and generated agent instructions as code changes. Do
not run `check`, named `review`, `plan`, `explain`, `next`, or `run` for
unreviewed foreign pull-request content with maintainer tokens, SSH keys, cloud
credentials, or other production secrets available.

A probe is an operation classified as observational, not an isolation boundary.
It may start local programs, authenticate to services, read external data,
create tool caches or locks, and expose returned data in results or logs. Only
action steps are withheld by the analysis modes.

Routines and shell commands inherit the invoking process environment. Routine
standard output and standard error are retained in private temporary files, and
portions may appear in command output. Do not pass secrets as workflow inputs or
emit them from helpers; review and delete retained artifacts before sharing
diagnostics.

Workflow inputs and connector results are data in normal operation arguments,
but `shell.command` deliberately passes its command text to Bash. Keep command
text author-controlled; never construct it from issue text, pull-request
content, file names, or other untrusted values.

Intentional command execution is part of the tool's purpose. Unexpected execution
of values meant to remain data, credential disclosure, and violations of an
operation's documented observation or execution boundaries can be security defects.
Technical artifacts such as private reports and logs do not by themselves imply
that an observation changes the project, but they can contain sensitive data.
Review diagnostics and artifacts before sharing them.

## Reporting

- Use repository issues for ordinary bugs and feature requests.
- For suspected security vulnerabilities, use GitHub's private vulnerability
  reporting when the repository offers **Report a vulnerability** under
  **Security → Advisories**.
- If private reporting is unavailable, open an issue asking for a private contact
  channel **without vulnerability details or exploit instructions**.
- Do not include real credentials or personal data in reports. Revoke or rotate
  exposed credentials; removing them from a report or Git history is not sufficient.

## Maintenance

Reports are handled on a best-effort basis, without guaranteed response or
remediation times. Security fixes target the current version; maintenance of
older release branches is not guaranteed.

The [audit guide](docs/secrets-audit.md) describes available checks and their
limitations. A clean scanner result is not a guarantee that code is secure.
