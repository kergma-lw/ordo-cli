# Run legacy shell command

You are reading, debugging, or migrating legacy workflow logic that already depends on shell.command and must understand its coarse runtime contract accurately.

Execute one trusted command through Bash as a login shell and return its exit status, standard output, and standard error.

## Use when

- A compatibility or containment scenario still needs one broad shell escape hatch, and narrower published connector surfaces or project-local helpers have already been ruled out explicitly.

## What to provide

- `command`: required; provide the complete trusted command text. It is executed as `bash -lc <command>` from the runner working directory, so Bash login setup can affect its environment and behavior.
- Treat the complete command as trusted author-controlled code. Do not let untrusted workflow data choose, form, or interpolate command text.

## Result and boundary

- Later steps can inspect `exit_code`, `stdout` (standard output), and `stderr` (standard error) from a successful command.
- This is arbitrary local execution: it can change anything available to the runner and a failed command can leave partial changes. The login shell also runs with the runner's available authority; it has no domain-specific rollback, sandbox, or concurrency safety.

## Do not use for

- New workflow authoring as a default mechanism; prefer narrower published connector operations, composed public workflows, or routines before falling back here.
- Work that needs a published operation with defined inputs, results, and safety boundaries; shell.command only runs raw shell text and leaves parsing, safety, and intent outside the public contract.

## Related references

Use these related references when you need a neighboring operation or more context.


- `ordo-help describe connector.shell`: Parent shell connector family for this coarse legacy execution action
- `ordo-help describe workflow-rules.shell.command`: Authoring rule that marks shell.command as forbidden for new workflow authoring
- `ordo-help describe workflow-rules.routine.*`: Authoring guidance for the limited project-local helper path when structured public options are exhausted
- [`operations`](../../topics/operations.md): Flat connector catalog to check whether a narrower published operation already exists before using shell.command

## Examples

- shell.command with inputs {"command": "printf 'legacy check'"}

## Inspect next

- workflow-rules.shell.command
- workflow-rules.routine.*
- operations
- connector.shell

## Exact machine contract

Use `ordo-help operation shell.command --json` when you need the exact machine-readable input and result contract for this operation.

## Canonical Examples

### shell_command_legacy_step

Run one explicit legacy shell command step when the workflow is documenting or containing compatibility behavior rather than teaching shell.command as a preferred new design.

```yaml
      - name: Run legacy shell command
        uses: shell.command
        with:
          command: "printf 'legacy check'"
        register: shell_result
```
### shell_command_legacy_workflow

Show shell.command only inside an explicitly legacy compatibility workflow so the published example teaches containment and caution rather than endorsement.

```yaml
version: 0
workflow: legacy-shell-command-compatibility
blocks:
   - guards: []
   - steps:
      # Run the legacy command and publish its result.
      - name: Run legacy shell command
        uses: shell.command
        with:
          command: "printf 'legacy check'"
        register: shell_result
      - name: Publish summary
        publish:
          exit_code: step.shell_result.outputs.exit_code
          summary: "Legacy shell command workflow prepared"
```
