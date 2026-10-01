# AGENTS

<!-- BEGIN ORDO MANAGED SECTION -->
## Ordo workflows

Ordo workflows are the canonical operational entrypoints for this repository.
When a workflow covers the task, use it instead of reproducing its checks manually.

### Command line

- Discover workflow entries → `ordo-playbook workflows list`
- Inspect one workflow contract → `ordo-playbook workflows show <workflow>`
- Review, check, plan, or explain without making changes → `ordo-playbook <mode> <workflow>`
- Execute a workflow → `ordo-playbook run <workflow>`
- Suggest the next workflow → `ordo-playbook next`
- Show workflow connections → `ordo-playbook graph`
- Read the detailed reference → `ordo-help`
- Pass caller values with repeatable `--input KEY=VALUE`; use `--input-file KEY=PATH` for raw file content.

### Inspect

- Repository status → `ordo-playbook run global-status`
- View an issue → `ordo-playbook run issue-view --input number=<issue-number>`
- View issue comments → `ordo-playbook run issue-view-comments --input number=<issue-number> --input limit=<limit>`
- Inspect a pull request → `ordo-playbook run pr-view --input pull_number=<pull-number>`
- Digest a pull request → `ordo-playbook run pr-digest --input pr_repository=<owner/repo> --input pull_number=<pull-number>`
- List backlog stories → `ordo-playbook run stories-backlog`
- List in-progress stories → `ordo-playbook run stories-in-progress`
- Find uncovered help handles → `ordo-playbook run uncovered-snippet-handles`
- Find unready describe handles → `ordo-playbook run not-ready-describe-handles`

### Task lifecycle

- Create a task → `ordo-playbook run create-task --input title=<title> --input body=<body>`
- Move a task to Ready → `ordo-playbook run task-to-ready --input issue_number=<issue-number>`
- Start or resume a task → `ordo-playbook run set-active-task --input issue_number=<issue-number>`
- Commit the active task worktree → `ordo-playbook run task-commit --input message=<message>`
- Move the local task to review → `ordo-playbook run task-to-review`
- Publish a prepared task → `ordo-playbook run publish-task`
- Merge a published task → `ordo-playbook run merge-task [--input merge_method=<merge-method>] [--input base_branch=<base-branch>]`
- Close a merged task → `ordo-playbook run close-task [--input close_comment=<close-comment>]`
- Cancel a task → `ordo-playbook run cancel-task --input reason=<reason>`

### Context

- Show current task context → `ordo-playbook run current-task-context`

### Collaboration

- Comment on an issue → `ordo-playbook run issue-comment --input number=<issue-number> --input body=<body>`

### Meta

- Rebuild meta packs → `ordo-playbook run meta-packs-build`

### Verify

- Run all tests → `ordo-playbook run verify-all-tests`
- Audit tracked files for secrets → `ordo-playbook run audit-secrets-tree`
- Run the publication audit → `ordo-playbook run audit-publication`

### Create

- Create a story → `ordo-playbook run create-story --input title=<title> --input body=<body>`

### Story

- Show story tasks → `ordo-playbook run story-tasks-show --input issue_number=<issue-number>`
- Add a story task reference → `ordo-playbook run story-task-add --input issue_number=<story-number> --input task_repository=<owner/repo> --input task_issue_number=<task-number>`
- Show ready story tasks → `ordo-playbook run story-tasks-ready --input issue_number=<story-number>`

### Emergency

- Force-close an issue → `ordo-playbook run force-close-issue --input number=<issue-number> --input confirm_break_glass=FORCE_CLOSE --input close_comment=<close-comment>`

### Field update

- Set task size → `ordo-playbook run set-task-size --input issue_number=<issue-number> --input size=<XS|S|M|L|XL>`
- Set task estimate → `ordo-playbook run set-task-estimate --input issue_number=<issue-number> --input estimate=<estimate>`
- Set task iteration → `ordo-playbook run set-task-iteration --input issue_number=<issue-number> --input iteration=<iteration>`
- Set task priority → `ordo-playbook run set-task-priority --input issue_number=<issue-number> --input priority=<P0|P1|P2|P3>`

If no workflow in this section is an obvious match, say that no known matching workflow is available. Do not invoke discovery merely to search for one, invent a workflow, or silently replace a workflow with a manual command sequence.

If a workflow covers the task, use it as the canonical entrypoint instead of reproducing its checks manually.

Prefer the minimal command sequence that answers the request. Do not run
unrelated preflight commands or replace a suitable workflow with a guessed
manual command sequence.
<!-- END ORDO MANAGED SECTION -->

## Meta source layout

- `meta/` source docs are organized first by document type, then by domain.
- Use domain-named subdirectories such as:
  - `meta/requirements/connector/`
  - `meta/model/runtime/`
  - `meta/data/workflow/`
  - `meta/verification/meta/`
- `meta/packs/` is the primary read surface for compact review.
- Optimize source docs for accurate maintenance of domain boundaries, not for single-file reading.

## Authoring rules

- All project documentation must be written in English.
- Issue text and issue comments must also be written in English.
- Avoid generic catch-all glossary files.
- Put terminology next to the domain it belongs to, for example in `meta/domain/connector.md`.
- Keep connector concerns, workflow concerns, runtime concerns, and policy concerns separated.
- Do not change `meta/` source truth merely to fit the current code shape without explicit user discussion and agreement.
- If code and `meta/` disagree, treat it as a drift signal to investigate first rather than silently rewriting the meta docs.
- Do not edit `meta/packs/**` by hand; regenerate them from source docs.
- After changing `meta/` source docs, regenerate `meta/packs/**` in the same work so derived artifacts stay in sync.
- Regenerate `meta/packs/**` via `ordo-playbook run meta-packs-build`.

## Python environment

- The project-local virtual environment is `/home/ww/projects/ordo/.venv`.
- Create or recreate this environment with `/usr/bin/python3.12 -m venv /home/ww/projects/ordo/.venv`.
- Use this environment for testing, local runs, dependency installation, and other Python-based project commands.
- Prefer invoking tools through the virtual environment explicitly, for example `/home/ww/projects/ordo/.venv/bin/python`, or activate it before running project commands.

## Operational workflows (Ordo-first)

- `ordo-playbook` is the canonical operational entrypoint.
- If a suitable workflow exists, do not use a direct command instead of it.
- `ordo-playbook` command modes from `--help`:
  - Discovery: `workflows`
  - Execution: `review`, `check`, `plan`, `explain`, `run`, `next`
- Example:
  - inspect available workflows: `ordo-playbook workflows list`
  - execute a workflow: `ordo-playbook run <workflow>`
- Use `ordo-playbook workflows list` as the default discovery surface.
- If a suitable `ordo-*`/`ordo-playbook` workflow exists, run it directly.
- Do not run unrelated preflight shell commands (`ls`, `pwd`, ad-hoc env checks, etc.) before an Ordo workflow unless they are strictly required for the workflow to succeed or the user explicitly asked for them.
- Prefer the minimal command sequence that answers the user request.
- Do not improvise operational entrypoints from memory or by guessing the most likely shell command.
- Hard rule: do not replace a missing or unknown workflow with a self-chosen “obvious” direct command (`gh`, `git`, `npm`, `python`, helper script, ad-hoc one-liner, etc.) just because the intent seems clear.
- If no suitable workflow exists yet:
  - use `.AGENTS.md.pre-ordo-backup` only as reference material;
  - inspect the current Ordo help/discovery surface;
  - propose how the missing workflow should look;
  - discuss it with the user before executing any legacy ritual directly.
- Do not treat legacy helper scripts or TUI commands as the primary interface.
- A direct command or temporary legacy bypass is allowed only when the user explicitly asks for it or explicitly approves the bypass.

## End-user workflow verification

- Do not write automated tests for concrete end-user project workflows. Do not duplicate their YAML composition in Python tests with mocked probe or action results.
- Verify these workflows through `ordo-playbook check`, `review`, and, when safe and authorized, a trial `run`. Do not execute side-effecting workflows merely to validate them.
- Automated tests for engine semantics, connectors, and reusable primitives remain in scope; this rule does not weaken their testing requirements.

## Engine change discipline

- Treat engine changes as contract changes, not isolated code edits.
- Any change to engine, runtime, workflow-model, execution, validation, planning, review, explanation, next-step selection, introspection, or other behavior-bearing core code must review its impact on all public runtime modes:
  - `check`
  - `review`
  - `plan`
  - `run`
  - `explain`
  - `next`
- If the change affects any of those modes, update the affected behavior, diagnostics, or published semantics in the same work.
- Do not assume that updating one mode is sufficient just because the touched code path looks local; review the full mode surface explicitly.

### Discovery and help parity

- Engine changes must also review their impact on the public discovery surface.
- If a change affects authoring meaning, recommended usage, applicability, validation rules, diagnostics, public handles, runtime semantics, fallback semantics, or other user-visible behavior, review and update the affected discovery surfaces in the same work.
- This includes, when relevant:
  - `ordo-help features`
  - `ordo-help overview`
  - `ordo-help model`
  - `ordo-help workflow-rules`
  - `ordo-help capabilities`
  - `ordo-help command-line`
  - `ordo-help operations`
  - `ordo-help describe ...`
  - `ordo-help search ...`
- Do not treat discovery or help updates as optional polish. They are part of the published behavior contract.

### Reader-facing help vocabulary

- Public `ordo-help` text is for people who may know neither Ordo nor its implementation.
- Write every public help surface in terms of the user's goal, the action to take, and the observable result. Introduce any necessary Ordo-specific term through its purpose before relying on it.
- Do not expose implementation vocabulary in ordinary help prose: module, class, function, SDK, handler, serializer, fixture, test-harness, internal-state, graph-layout, backend-protocol, or internal diagnostic terminology.
- Do not use internal identifiers, field names, diagnostic codes, API status codes, or backend query details as the primary explanation. If one is part of a focused public contract or troubleshooting path, first give the reader-facing explanation and place the technical identifier in an explicitly labelled contract or troubleshooting detail.
- Machine-readable `--json` output may retain stable technical identifiers when they are part of its public contract; this does not justify repeating them in ordinary text help.
- Before completing a change to any public help surface, generate every affected text surface and review it from the perspective of a person unfamiliar with Ordo and its codebase. Confirm that the surface contains no unnecessary implementation jargon, and report the reviewed surfaces and any deliberate, focused technical exceptions in the completion summary.

### Canonical reader-facing content

- Keep reader-facing content in a `human` mapping beside the canonical contract data that it explains. Do not create a separately maintained site-documentation source.
- The `human` mapping holds the reader's goal, the action to take, the observable result, boundaries, examples, and structured links to related public surfaces. Keep implementation details in their own contract fields rather than mixing them into `human` prose.
- Text `ordo-help`, the reader-facing site, and text search must consume `human` content and explicitly permitted public references. They must not fall back to arbitrary contract fields, raw metadata, or serialized JSON when a `human` value is absent.
- When a public surface changes, update its relevant `human` content in the same change. A new public surface must not enter reader-facing help without the `human` content required for its published role.
- Treat migration of an existing surface to `human` as a content-preservation task: retain its useful reader-facing meaning, move technical facts to structured contract fields, and do not replace a substantive surface with a generic summary.

### Features parity

- `ordo-help features` is the compact workflow-authoring feature map for authors and agents.
- Any engine change that affects workflow authoring surfaces, discoverability, named primitives, fallback paths, recommended patterns, discouraged patterns, or cluster boundaries must review and update `ordo-help features` in the same work.
- If a new or changed behavior exists but is not surfaced correctly in `ordo-help features`, the change is incomplete.

### Snippet-backed example parity

- After completing a task that changes a public authoring or discovery surface, review whether any relevant snippet-backed examples must be updated in the same work.
- This applies to help surfaces such as `ordo-help describe ...`, `ordo-help workflow-rules`, `ordo-help features`, and other published discovery output that teaches or confirms authored shapes.
- Any task that changes one or more public `ordo-help describe ...` surfaces must explicitly run those affected describe surfaces against the describe readiness checklist and treat that review as part of the work, not as optional follow-up polish.
- If one or more affected describe surfaces do not satisfy the checklist cleanly, discuss the gap before closing the work instead of silently accepting a half-ready describe surface.
- If a relevant verified snippet already exists for the affected surface, update it in the same work so the published example stays aligned with the implemented behavior.
- If no relevant snippet exists but the supported snippet-world path can represent the changed surface honestly, add the missing snippet in the same work rather than treating snippet coverage as optional follow-up polish.
- If the supported snippet-world path does not yet support the required example shape, do not silently ignore the gap.
- In that case, explicitly call out the unsupported snippet shape as a problem before closing the work, because the lack of snippet support is now blocking accurate help parity.
- Do not paper over the gap with decorative rendering tricks, silently transformed examples, or unverifiable prose that pretends to be a real snippet.
- Snippet updates belong to the same parity discipline as help text updates: if the public surface changed, the relevant verified examples must change with it, or the work is incomplete.

### Ambiguity requires discussion

- For engine changes, ambiguity is a stop signal, not a license to guess.
- If it is unclear whether or how a change should affect `check` / `review` / `plan` / `run` / `explain` / `next`, discuss it before implementation or, at the latest, before considering the change complete.
- If it is unclear whether or how discovery surfaces should change, discuss it before implementation or before closure.
- If the semantic radius of the change is broad, cross-cutting, or difficult to propagate confidently, prefer discussion over silent completion.
- Do not close an engine change on guessed parity.
- When in doubt, raise the discussion earlier rather than silently shipping a partial interpretation.

### Completion rule

- An engine change is not complete until all affected runtime modes and all affected discovery/help surfaces have been reviewed and updated together, or their non-impact has been explicitly established.

## GitHub and project operations

- Prefer the corresponding `ordo-playbook` workflow for GitHub and project operations.
- GitHub writing rule: issue titles, bodies, comments, labels, and project field values must be in English only.
- Keep API responses lean: request only the fields needed for the decision.

## Commit inspection restraint

- Use `ordo-playbook run task-commit` as the canonical commit entrypoint.
- Do not perform discretionary Git inspection immediately before invoking `task-commit`.
- Where a controlling instruction requires pre-commit inspection, perform only that minimum required read-only inspection. Do not add unrelated preflight commands, repeated test runs, or exploratory checks.
- Inspection is not authorization to change files, broaden scope, repair incidental findings, or alter tests. If it reveals a concern outside the accepted task, report it and wait for an explicit instruction.
- Do not rerun verification solely because a read-only inspection occurred. Run only the verification required by the accepted task or an explicitly requested final verification.
