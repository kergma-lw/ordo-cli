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

### inspect

- Show local branch, worktree, cached upstream counts, task, and hook status → `ordo-playbook run global-status`
- Show one issue from this repository context without changing state → `ordo-playbook run issue-view --input number=<number>`
- Show comments for one issue from this repository context without changing state → `ordo-playbook run issue-view-comments --input number=<number> --input limit=<limit>`
- Show one pull request inspection snapshot without changing state → `ordo-playbook run pr-view --input pull_number=<pull-number>`
- Show a richer pull request digest with review, checks, and timeline highlights → `ordo-playbook run pr-digest --input pr_repository=<pr-repository> --input pull_number=<pull-number>`
- Show Story issues that are in Backlog in the project → `ordo-playbook run stories-backlog`
- Show Story issues that are In progress in the project → `ordo-playbook run stories-in-progress`
- Show the public help handles that still lack snippet-backed examples → `ordo-playbook run uncovered-snippet-handles`
- Show the public help handles whose describe surfaces are not yet marked ready → `ordo-playbook run not-ready-describe-handles`

### Task lifecycle

- Create a task in Backlog → `ordo-playbook run create-task --input title=<title> --input body=<body>`
- Move a task or bug to Ready → `ordo-playbook run task-to-ready --input issue_number=<issue-number>`
- Start or resume work on an issue → `ordo-playbook run set-active-task --input issue_number=<issue-number>`
- Stage and commit the active task worktree → `ordo-playbook run task-commit --input message=<message>`
- Open the local diff and move a task to In review → `ordo-playbook run task-to-review`
- Invalidate review and return the active task to In progress → `ordo-playbook run task-reopen-review --input reason=<reason>`
- Push the prepared task branch and find or create its PR → `ordo-playbook run publish-task`
- Ask GitHub to merge the published PR or observe a saved merge request → `ordo-playbook run merge-task [--input base_branch=<base-branch>] [--input merge_method=<merge|squash|rebase>]`
- Close a remotely merged task and clean up locally → `ordo-playbook run close-task [--input close_comment=<close-comment>]`
- Cancel the active task with an English reason → `ordo-playbook run cancel-task --input reason=<reason>`

### context

- Show the stored active task or story context for this repository → `ordo-playbook run current-task-context`

### collaboration

- Add a comment to one issue from this repository context → `ordo-playbook run issue-comment --input number=<number> --input body=<body>`

### meta

- Regenerate derived meta packs from source docs → `ordo-playbook run meta-packs-build`

### verify

- Run the full repository pytest suite from a clean worktree → `ordo-playbook run verify-all-tests`
- Scan current tracked worktree files with pinned Gitleaks and sanitized output → `ordo-playbook run audit-secrets-tree`
- Run isolated secret, Python, dependency vulnerability lookup, shell, and publication-inventory checks through one audit workflow → `ordo-playbook run audit-publication`

### create

- Create a new Story issue with a Tasks section → `ordo-playbook run create-story --input title=<title> --input body=<body>`

### story

- Show the raw Tasks section for one story issue → `ordo-playbook run story-tasks-show --input issue_number=<issue-number>`
- Add one task reference to the Tasks section of a story issue → `ordo-playbook run story-task-add --input issue_number=<issue-number> --input task_repository=<task-repository> --input task_issue_number=<task-issue-number>`
- Show Ready tasks referenced from a story Tasks section → `ordo-playbook run story-tasks-ready --input issue_number=<issue-number>`

### emergency

- Close one issue directly, bypassing normal lifecycle checks → `ordo-playbook run force-close-issue --input number=<number> --input confirm_break_glass=<FORCE_CLOSE> --input close_comment=<close-comment>`

### Field update

- Update the project Size field for one open task in this repository → `ordo-playbook run set-task-size --input issue_number=<issue-number> --input size=<XS|S|M|L|XL>`
- Update the project Estimate field for one open task in this repository → `ordo-playbook run set-task-estimate --input issue_number=<issue-number> --input estimate=<estimate>`
- Update the project Iteration field for one open task in this repository → `ordo-playbook run set-task-iteration --input issue_number=<issue-number> --input iteration=<iteration>`
- Update the project Priority field for one open task in this repository → `ordo-playbook run set-task-priority --input issue_number=<issue-number> --input priority=<P0|P1|P2|P3>`

### Operating rules

- Use `ordo-playbook workflows list` as the default discovery surface.
- If no workflow in this section is an obvious match, say that no known matching workflow is available. Do not invoke discovery merely to search for one, invent a workflow, or silently replace a workflow with a manual command sequence.
- Do not run unrelated preflight commands or replace a suitable workflow with a guessed manual command sequence.
- Do not replace a missing or unknown workflow with a self-chosen direct command, helper script, or legacy command just because the intent seems clear.
- If no suitable workflow exists, use `.AGENTS.md.pre-ordo-backup` only as reference material, inspect the current Ordo help and discovery surface, propose the missing workflow, and discuss it before using any legacy procedure directly.
- Do not treat legacy helper scripts or TUI commands as the primary interface.
- Use a direct command or temporary legacy bypass only when the user explicitly asks for or approves it.
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
