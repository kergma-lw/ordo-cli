"""shell.command action."""

from ordo.plugin_sdk import MappedOutcomeError, OperationContext, OperationOutcome, action, fail_external_command, ok
from ordo.model.human import declare_human


HUMAN = declare_human({'title': 'Run legacy shell command',
 'goal': 'You are reading, debugging, or migrating legacy workflow logic that already depends on shell.command and '
         'must understand its coarse runtime contract accurately.',
  'summary': 'Execute one trusted command through Bash as a login shell and return its exit status, standard output, and standard error.',
 'sections': [{'heading': 'Use when',
               'items': ['You are reading, debugging, or migrating legacy workflow logic that already depends on '
                         'shell.command and must understand its coarse runtime contract accurately.',
                         'A compatibility or containment scenario still needs one broad shell escape hatch, and '
                          'narrower published connector surfaces or project-local helpers have already been ruled out '
                          'explicitly.']},
               {'heading': 'What to provide',
                 'items': ['`command`: required; provide the complete trusted command text. It is executed as `bash -lc <command>` from the runner working directory, so Bash login setup can affect its environment and behavior.',
                           'Treat the complete command as trusted author-controlled code. Do not let untrusted workflow data choose, form, or interpolate command text.']},
              {'heading': 'Result and boundary',
                 'items': ['Later steps can inspect `exit_code`, `stdout` (standard output), and `stderr` (standard error) from a successful '
                           'command.',
                           'This is arbitrary local execution: it can change anything available to the runner and a failed '
                           'command can leave partial changes. The login shell also runs with the runner\'s available authority; it has no domain-specific rollback, sandbox, or concurrency safety.']},
              {'heading': 'Do not use for',
               'items': ['New workflow authoring as a default mechanism; prefer narrower published connector '
                         'operations, composed public workflows, or routines before falling back here.',
                          'Work that needs a published operation with defined inputs, results, and safety boundaries; '
                          'shell.command only runs raw shell text and leaves parsing, safety, and intent outside the '
                          'public contract.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.shell',
                               'summary': 'Parent shell connector family for this coarse legacy execution action'},
                              {'handle': 'workflow-rules.shell.command',
                               'summary': 'Authoring rule that marks shell.command as forbidden for new workflow '
                                          'authoring'},
                               {'handle': 'workflow-rules.routine.*',
                                 'summary': 'Authoring guidance for the limited project-local helper path when '
                                           'structured public options are exhausted'},
                              {'handle': 'operations',
                               'summary': 'Flat connector catalog to check whether a narrower published operation '
                                          'already exists before using shell.command'}]},
              {'heading': 'Examples', 'items': ['shell.command with inputs {"command": "printf \'legacy check\'"}']},
              {'heading': 'Inspect next',
                'items': ['workflow-rules.shell.command', 'workflow-rules.routine.*', 'operations', 'connector.shell']}]})

def info():
    return action(
        name="command",
        human=HUMAN,
        inputs={"command": "string"},
        effects=("execute shell command",),
        outputs={"exit_code": "integer", "stdout": "string", "stderr": "string"},
        failure_modes=("command_failed", "action_failed"),
        handler=run,
    )


def run(ctx: OperationContext) -> OperationOutcome:
    command = str(ctx.input("command"))
    try:
        result = ctx.command(
            ["bash", "-lc", command],
            failures={
                "os_error": "action_failed",
                "nonzero": "command_failed",
            },
        )
    except MappedOutcomeError as exc:
        return fail_external_command(
            code=exc.outcome.status,
            summary="Shell command execution failed",
            diagnostic_code="action.shell_command.command_failed",
            reference=ctx.reference,
            details={"command": command},
            raw=exc.outcome.raw,
            tool="bash",
        )
    return ok(
        summary="Command completed successfully",
        outputs={"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
        raw=result.raw,
    )
