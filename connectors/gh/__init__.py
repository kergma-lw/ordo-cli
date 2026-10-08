"""GitHub connector family."""

from __future__ import annotations

from connectors._family import ActionHandler, ProbeHandler, assemble_family
from ordo.model.human import HumanDeclaration, declare_human

from .bootstrap import BOOTSTRAP

ORDER = 20


_LEGACY_FAMILY_HUMAN = declare_human({'title': 'GitHub connector',
 'goal': 'The workflow needs one published GitHub probe or action whose outputs and failure modes stay stable across '
         'repositories.',
 'summary': 'Published GitHub connector family for typed repository, issue, pull-request, Actions run, and project '
            'operations backed by GitHub CLI authentication rather than ad hoc shell calls.',
 'sections': [{'heading': 'Use when',
               'items': ['The workflow needs one published GitHub probe or action whose outputs and failure modes stay '
                         'stable across repositories.',
                         'Repository-targeted GitHub probes and actions should normally inherit '
                         'connector_contexts.gh.repository instead of repeating the same repository argument on every '
                         'step, and review warns when an explicit repository overrides that default.',
                         'You want separate public surfaces for repository sync, issue snapshots, pull-request review '
                         'surfaces, and GitHub Project membership instead of one coarse GitHub command wrapper.',
                         'The published operations list includes read-only probes and effectful actions. gh.pr and '
                         'gh.pr.checks observe facts; gh.pr.merge submits a mutation, while gh.pr.merge.request '
                         'observes its saved UUID. The project-membership example also includes actions and is not a '
                         'read-only recipe.',
                         'Bootstrap requires an available authenticated gh CLI with repository access. gh.actions.run '
                         'observes one attempt by run_id or check_suite_id (exactly one); omitted/null attempt reads '
                         'latest then pins it. gh.actions.run.jobs requires explicit attempt, normally the returned '
                         'run_attempt. Optional/null repository uses connector_contexts.gh.repository; explicit valid '
                         'OWNER/REPO overrides it, invalid explicit input fails without fallback, and no resolved '
                         'target is input_error.',
                         'A gh.pr.checks check-run item supplies nullable check_suite_id for direct GraphQL '
                         'CheckSuite.workflowRun lookup. A validated null association returns found=false. Jobs expose '
                         'check_run_id only from a validated official API URL, not logs. Complete jobs retrieval and '
                         'pinned attempts remain non-atomic API observations, not tested-SHA attestation or immutable '
                         'PR event snapshots. Run failures are actions_run_unavailable; jobs failures, including '
                         'incomplete pagination, are actions_jobs_unavailable.',
                         'GitHub candidate discovery: gh.pr.list observes a full filtered REST pull-request '
                         'collection, not the search index. repository is optional with the standard '
                         'connector_contexts.gh.repository default and explicit OWNER/REPO override. state is '
                         'required: open|closed|all. Prefer state: all for find/create-oriented inspection, optionally '
                         'narrowed by head/head_owner/base. head_owner is the head repository owner (user or '
                         'organization), not PR author, and requires head; owner plus branch is not exact repository '
                         'identity. Compare returned head_repository for exact fork matching. Internal pagination has '
                         'no public page/cursor/limit; incomplete traversal fails. head with head_owner composes '
                         'server owner:branch; bare head is matched exactly locally across all state/base pages '
                         'because GitHub does not guarantee bare-head filtering. Missing head_ref for local filtering '
                         'fails. The 100-page ceiling applies before local filtering. GitHub.com only, matching '
                         'bootstrap authentication. Full traversal is not an atomic snapshot or a total remote count '
                         'guarantee. Empty success means no matches within the supplied filters; one result is a '
                         'candidate, not automatically the correct PR. Workflow rules classify none, one open, '
                         'multiple open, and closed history; unknown facts block dependent decisions. Closed/merged '
                         'history may require additional workflow rules. Listing does not authorize creation, '
                         'reopening, or merge. gh.pr reads detailed facts by pull_number; gh.pr.create is a separate '
                         'action with its own mandatory open check. Inspect connector.gh.pr.list for canonical '
                         'filtered classification fragments.',
                         'GitHub async merge: gh.pr observes head/base/test-merge identity and stack_state '
                         '(standalone/stacked/unknown) plus stack; gh.pr.checks observes CI evidence. gh.pr.merge '
                         'requires expected_head_sha from the accepted CI head, never a freshly fetched replacement. '
                         'For gh.pr.merge and gh.pr.merge.request, repository is optional: a valid explicit OWNER/REPO '
                         'overrides the bootstrapped connector_contexts.gh.repository; omitted or null uses that '
                         'context. Malformed explicit values fail without fallback, and no resolved repository is an '
                         'error. For checks on candidate M with verified base B and head H, submit '
                         'expected_head_sha=H, not M. The first version rejects stacked PRs and unknown scope before '
                         'submission; there is no atomic base or stack guarantee. Save the action result request_id '
                         'UUID for gh.pr.merge.request: accepted submission is not completion. Observe '
                         'pending/merged/failed/enqueued once; unavailable is not failed and enqueued is not merged. '
                         'Only an exact matching existing request is reusable. No polling, queue administration, or '
                         'admin bypass is provided. GitHub automatic issue closing and branch configuration effects '
                         'are outside this action. Inspect connector.gh.pr.merge and connector.gh.pr.merge.request for '
                         'the verified canonical workflow example.',
                         'GitHub creation: gh.pr.create requires head, base, title, and an explicit boolean draft; '
                         'body defaults to empty. repository is optional: valid explicit OWNER/REPO overrides '
                         'connector_contexts.gh.repository; omitted or null uses context, malformed explicit input '
                         'fails without fallback. head_repository is a full source OWNER/REPO, default target '
                          'repository; explicit cross-repository intent requires it, with no fork guessing. head_owner '
                          'is conditional and acts only as a consistency assertion; otherwise it is derived from the exact source repository. '
                         'Same-organization head_repo API argument is derived repository NAME. Reject '
                         "same-branch/same-repository requests. The action uses ctx.call('gh.pr.list', inputs=...) "
                         'with resolved repository/head/head_owner/base and state: open; require complete traversal '
                         'and exact case-insensitive head_repository_key identity. One exact open match including '
                         'draft returns non-OK already_exists with pull_number, url, created=false and no POST; '
                         'multiple matches return ambiguous; unknown identity and list failure return precheck_failed. '
                         'No existing match permits one POST. Only validated HTTP 201 means created=true; malformed '
                         '201, timeout, or server failure returns creation_unknown with created=null. HTTP 422 is '
                         'generic create_refused, not universal duplicate evidence; preserve API errors. No POST retry '
                         'or automatic readback reconciliation. This is not find-or-reuse or closed-history policy: '
                         "workflow-owned gh.pr.list state: all classification precedes create's separate open check. "
                         'Concurrent duplicates can race the check: no atomic uniqueness or exactly-once guarantee. No '
                         'CI waiting, merge, push, fork, branch cleanup, or extra issue/project operations. Inspect '
                         'connector.gh.pr.create.']},
              {'heading': 'Do not use for',
               'items': ['Repository-local helper scripts or opaque gh invocations when an existing published GitHub '
                         'operation already expresses the intent more directly.',
                         'Non-GitHub repository state such as local branches, commits, or worktrees; use the git '
                         'connector family for repository-local facts.',
                         'Async merge is not polling, queue administration, admin bypass, or an atomic base/stack '
                         'transaction. GitHub automatic issue closing and branch configuration effects remain outside '
                         'the action.',
                         'Actions run probes do not trigger, rerun, cancel, poll, download logs, select required jobs, '
                         'or apply merge policy. gh.actions is a namespace segment, not an executable operation.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.authoring',
                               'summary': 'Connector-author SDK and explicit same-family probe dependency contract'},
                              {'handle': 'operations',
                               'summary': 'Flat public operation catalog across all connector namespaces'},
                              {'handle': 'connector.gh.repo',
                               'summary': 'Repository identity and fork probe for repo-level GitHub workflows'},
                              {'handle': 'connector.gh.repo.actions.permissions',
                               'summary': 'Repository Actions permissions probe for workflows that need to inspect or '
                                          'guard hosted Actions policy'},
                              {'handle': 'connector.gh.actions.run',
                               'summary': 'Observe one numbered Actions attempt by run or check suite'},
                              {'handle': 'connector.gh.actions.run.jobs',
                               'summary': 'Observe all jobs for an explicitly pinned attempt'},
                              {'handle': 'connector.gh.pr',
                               'summary': 'Pull-request metadata probe that anchors the PR inspection subgroup'},
                              {'handle': 'connector.gh.pr.list',
                               'summary': 'Full filtered candidate collection before detailed by-number inspection; '
                                          'workflow owns selection'},
                              {'handle': 'connector.gh.pr.create',
                               'summary': 'Create one PR with a mandatory exact open-duplicate check'},
                              {'handle': 'connector.gh.pr.checks',
                               'summary': 'Observe head or verified test-merge CI evidence before accepting a head'},
                              {'handle': 'connector.gh.pr.merge',
                               'summary': 'Submit a standalone PR merge bound to the accepted CI head'},
                              {'handle': 'connector.gh.pr.merge.request',
                               'summary': 'Observe a saved async merge request UUID once'},
                              {'handle': 'connector.gh.issue',
                               'summary': 'Issue snapshot probe for issue maintenance and routing workflows'},
                              {'handle': 'connector.gh.project',
                               'summary': 'Project identity probe that anchors the GitHub Project field and membership '
                                          'subgroup'},
                              {'handle': 'connector.gh.project.items',
                               'summary': 'Project membership probe when the workflow needs GitHub Project item '
                                          'collections'}]},
              {'heading': 'Examples',
               'items': ['gh.repo with inputs {}',
                         'gh.repo.actions.permissions with inputs {}',
                         'gh.pr with inputs {"pull_number": 42}',
                         'gh.issue with inputs {"issue_number": 17}',
                         'gh.project with inputs {"project_id": "PVT_kwDOExample"}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.repo',
                         'connector.gh.repo.actions.permissions',
                         'connector.gh.actions.run',
                         'connector.gh.actions.run.jobs',
                         'connector.gh.pr',
                         'connector.gh.pr.checks',
                         'connector.gh.pr.merge',
                         'connector.gh.pr.merge.request',
                         'connector.gh.issue',
                         'connector.gh.project',
                         'connector.gh.project.items',
                          'operations']}]})

FAMILY_HUMAN = declare_human({
    'title': 'GitHub connector',
    'goal': 'Use a published GitHub operation when a workflow needs a stable repository, issue, pull-request, Actions, or project interaction.',
    'summary': 'Published GitHub probes and actions for explicit observations and deliberate changes.',
    'sections': [
        {'heading': 'Use when', 'items': [
            'Use the GitHub context repository for shared repository work, or supply an explicit OWNER/REPO when the workflow intentionally targets another repository.',
            'Choose a probe to observe facts and an action only when the workflow intentionally changes GitHub.',
            'Use pull-request list results as decision input; creation, merge, and other changes remain separate actions.',
            'Treat GitHub observations as current facts, not permanent authorization or an atomic view of concurrent changes.',
        ]},
        {'heading': 'Do not use for', 'items': [
            'Repository-local branches, commits, or worktrees; use the Git connector.',
            'Opaque GitHub command wrappers when a published operation already expresses the intended work.',
            'Polling, queue administration, or automatic merge policy.',
        ]},
        {'heading': 'Related references', 'references': [
            {'handle': 'operations', 'summary': 'Browse every published connector operation.'},
            {'handle': 'connector.gh.repo', 'summary': 'Inspect repository identity and fork facts.'},
            {'handle': 'connector.gh.issue', 'summary': 'Inspect one GitHub issue before an issue-specific decision or change.'},
            {'handle': 'connector.gh.project', 'summary': 'Inspect a GitHub Project before field or membership work.'},
        ]},
        {'heading': 'Pull-request decisions', 'items': [
            'Start with the pull-request list when the workflow must classify candidates by repository, branch, or lifecycle state. Its result is decision evidence, not an automatic selection.',
            'Create a pull request only after the workflow has made that decision. Creation checks for an exact open duplicate, but it does not reuse a candidate or settle closed-history policy.',
        ], 'references': [
            {'handle': 'connector.gh.pr.list', 'summary': 'List candidates and keep selection, creation, and closed-history decisions in the workflow.'},
            {'handle': 'connector.gh.pr.create', 'summary': 'Create one authorized pull request after candidate classification.'},
            {'handle': 'connector.gh.pr', 'summary': 'Inspect the current facts for one selected pull request.'},
        ]},
        {'heading': 'Actions attempts', 'items': [
            'Submit a manually dispatched workflow only after the surrounding workflow has decided to start it. Submission confirms acceptance, not completion; an unknown result must be inspected before another submission.',
            'Inspect a run by run ID or check-suite ID. When no attempt is supplied, the run result identifies the current attempt for this observation.',
            'Pass that returned run ID and attempt to the jobs operation when a later decision needs the jobs for the same attempt. A later Actions observation can change independently.',
        ], 'references': [
            {'handle': 'connector.gh.actions.dispatch', 'summary': 'Submit one manual workflow start request with a ref and named inputs.'},
            {'handle': 'connector.gh.actions.run', 'summary': 'Inspect one Actions run and identify the attempt being observed.'},
            {'handle': 'connector.gh.actions.run.jobs', 'summary': 'Inspect jobs for an explicitly identified run attempt.'},
        ]},
        {'heading': 'Async merge lifecycle', 'items': [
            'Inspect the selected pull request and its checks before accepting a tested head for merge.',
            'Submit the merge with that accepted head, save the returned request ID, then inspect that saved request to learn whether it is pending, enqueued, merged, or failed.',
            'An accepted submission or an enqueued request is not proof that the pull request has merged.',
        ], 'references': [
            {'handle': 'connector.gh.pr.checks', 'summary': 'Inspect check evidence before accepting a pull-request head.'},
            {'handle': 'connector.gh.pr.merge', 'summary': 'Submit a merge for the accepted head of a standalone pull request.'},
            {'handle': 'connector.gh.pr.merge.request', 'summary': 'Inspect the saved asynchronous merge request after submission.'},
        ]},
    ],
})


def get_family_human() -> HumanDeclaration:
    return FAMILY_HUMAN


_ASSEMBLED = assemble_family(package_name=__name__, namespace="gh", bootstrap=BOOTSTRAP)


def get_connector():
    return _ASSEMBLED.connector


def get_probe_handler(name: str) -> ProbeHandler | None:
    return _ASSEMBLED.probe_handlers.get(name)


def get_action_handler(name: str) -> ActionHandler | None:
    return _ASSEMBLED.action_handlers.get(name)
