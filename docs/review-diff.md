# Local review diff report

The project-local `review.render-open-diff` routine is consumed by `task-to-review`.
That workflow also performs task lifecycle operations; it is not report-only.
The routine emits one JSON object whose `path` field is the absolute HTML report
path. Its issue input must be a canonical positive ASCII decimal (`[1-9][0-9]*`),
validated before Git or report allocation and never used as a filesystem path.

## Report and storage

The routine obtains `git diff --no-ext-diff --no-textconv main...HEAD` and
HTML-escapes the diff body. External diff and text-conversion helpers are disabled;
files requiring textconv may appear as binary differences instead of text.

Each invocation exclusively creates a file in a unique private temporary
directory, with `0700` directory and `0600` file permissions. The report is fully
written and closed before `xdg-open` starts. It remains available for asynchronous
viewing until manual or system temporary-file cleanup, not as a durable archive.
The script does not remove unrelated files or reports from other invocations.
HTML escaping is not secret redaction: review sensitive source changes before
sharing the report. Private storage is not a sandbox or secure-erasure guarantee.

## Failure behavior

- Invalid arguments invoke neither Git nor report allocation.
- Git launch or command failure creates no report; command errors forward Git's
  stderr and nonzero exit status.
- Handled allocation/write failures clean only this invocation's partial
  directory. Abrupt termination can leave artifacts.
- A launched viewer returning nonzero is best-effort success and still emits
  path JSON. A viewer launch `OSError` fails without success JSON, retains the
  completed report, and includes its path in stderr.

## Observation boundary

The routine is a `probe`: its intent is observation, not domain mutation. Private
report storage and viewer presentation are explicit technical effects of running
it; inspection modes do not automatically execute it or open a viewer as preflight.
Installed Git and the explicitly invoked viewer remain trusted executables;
disabling diff/textconv helpers does not sandbox either program.

Static test reference: `tests/test_render_review_diff.py` covers command arguments,
permissions, escaping, retention, input validation, and failure handling with
mocked subprocesses, rather than exercising a real Git command or viewer.
