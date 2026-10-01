"""gh.pr probe."""

from __future__ import annotations

import builtins
import json

from connectors.gh._merge_api import full_sha
from connectors.gh._pr_commit_evidence import observe_pr_commit, run_gh_command
from connectors.gh._pr_stack import normalize_pr_stack, valid_pr_identity
from connectors.gh._pull_identity import PULL_IDENTITY_INPUTS, resolve_pull_identity
from connectors.gh.probes.pr._shared import fetch_pull_request, normalize_author
from ordo.plugin_sdk import Diagnostic, OperationContext, OperationOutcome, fail, ok, probe
from ordo.model.human import declare_human


OBSERVATION_OUTPUTS = {
    "head_repository": "string",
    "base_repository": "string",
    "base_sha": "string",
    "merged": "boolean",
    "merged_at": "string",
    "merge_commit_sha": "string",
    "test_merge_sha": "string",
    "test_merge_head_sha": "string",
    "test_merge_base_sha": "string",
    "test_merge_state": "string",
    "test_merge_reason": "string",
    "stack_state": "string",
    "stack": "object",
}


HUMAN = declare_human({'title': 'GitHub pr',
 'goal': 'connector_contexts.gh.repository already names the normal repository target and workflow logic now needs one '
         'PR snapshot there by pull number.',
 'summary': 'Probe one GitHub pull request as a typed metadata snapshot with head/base identity, a verified test-merge '
            'candidate, and stack scope. Prefer connector_contexts.gh.repository as the normal repository target; '
            'review warns when an explicit repository overrides it.',
 'sections': [{'heading': 'Use when',
               'items': ['connector_contexts.gh.repository already names the normal repository target and workflow '
                         'logic now needs one PR snapshot there by pull number.',
                         "Workflow logic needs the pull request's current headline facts before deciding which "
                         'narrower PR surfaces to inspect next.',
                         'A later step needs branch refs, draft/state flags, review decision, or change totals from '
                         'one normalized PR snapshot.',
                         'head_sha and base_sha identify head H and base B with their repositories. '
                         'test_merge_state=verified means candidate M has the observed parents B then H; '
                         'test_merge_sha, test_merge_head_sha, and test_merge_base_sha retain that identity. '
                         'merge_commit_sha is the completed merge result only when merged=true.',
                         'stack_state is standalone, stacked, or unknown; stack carries the observed stack data. The '
                         'first-version gh.pr.merge action rejects stacked PRs and unknown scope before submission.']},
              {'heading': 'Do not use for',
               'items': ['Discovering candidates before a pull number is known; use gh.pr.list with explicit state '
                         'filters, then apply workflow-owned identity and history rules.',
                         'Conversation history, submitted reviews, line comments, checks, or lifecycle events; use the '
                         'dedicated PR sibling surfaces for those narrower views.',
                         'Mutating or merging the pull request; this published surface is observation only.',
                          'A test-merge candidate is not a completed merge. Missing identity stays unavailable, not '
                          'invented. A snapshot gives no atomic base or stack '
                         "guarantee; never replace the accepted CI head with this probe's freshly fetched head when "
                         'authoring expected_head_sha.']},
              {'heading': 'Related references',
               'body': 'Use these related references when you need a neighboring operation or more context.',
               'references': [{'handle': 'connector.gh',
                               'summary': 'Parent GitHub connector family for issue, pull-request, and project '
                                          'operations'},
                              {'handle': 'connector.gh.pr.list',
                               'summary': 'Discover filtered PR candidates; one item does not automatically identify '
                                          'the correct PR'},
                              {'handle': 'connector.gh.pr.create',
                               'summary': 'Create a PR before detailed by-number inspection; existing open identity '
                                          'refuses creation'},
                              {'handle': 'connector.gh.pr.diff',
                               'summary': 'Sibling probe for changed files and patch content rather than PR headline '
                                          'metadata'},
                              {'handle': 'connector.gh.pr.reviews',
                               'summary': 'Sibling probe for submitted review decisions rather than the PR snapshot'},
                              {'handle': 'connector.gh.pr.checks',
                               'summary': 'Observe CI attached to head H or verified candidate M'},
                              {'handle': 'connector.gh.pr.merge',
                               'summary': 'Submit a merge with expected_head_sha from accepted CI evidence'},
                              {'handle': 'connector.gh.pr.merge.request',
                               'summary': 'Observe completion using the saved request UUID'}]},
              {'heading': 'Examples', 'items': ['gh.pr with inputs {"pull_number": 42}']},
              {'heading': 'Inspect next',
               'items': ['connector.gh.pr.diff',
                         'connector.gh.pr.comments',
                         'connector.gh.pr.reviews',
                         'connector.gh.pr.checks',
                         'connector.gh.pr.merge',
                         'connector.gh.pr.merge.request']}]})

def info():
    return probe(
        name="pr",
        human=HUMAN,
        summary="Read normalized metadata from a GitHub pull request.",
        inputs=PULL_IDENTITY_INPUTS,
        outputs={
            **OBSERVATION_OUTPUTS,
            "number": "integer",
            "repository": "string",
            "title": "string",
            "body": "string",
            "author": "object",
            "state": "string",
            "draft": "boolean",
            "url": "string",
            "created_at": "string",
            "updated_at": "string",
            "base_ref": "string",
            "head_ref": "string",
            "head_sha": "string",
            "mergeable": "boolean",
            "mergeable_state": "string",
            "review_decision": "string",
            "additions": "integer",
            "deletions": "integer",
            "changed_files": "integer",
            "commits_count": "integer",
        },
        failure_modes=("pull_not_found", "probe_failed"),
        handler=run,
        examples=(
            {
                "reference": "gh.pr",
                "inputs": {"pull_number": 42},
            },
        ),
    )


def run(ctx: OperationContext) -> OperationOutcome:
    identity = resolve_pull_identity(ctx, failure_code="probe_failed", diagnostic_prefix="probe.gh_pr")
    if isinstance(identity, OperationOutcome):
        return identity

    fetched = fetch_pull_request(ctx, identity=identity, diagnostic_prefix="probe.gh_pr")
    if isinstance(fetched, OperationOutcome):
        return fetched
    payload, raw = fetched
    invalid_identity = validate_observation_identity(ctx, identity=identity, payload=payload, raw=raw)
    if invalid_identity is not None:
        return invalid_identity
    candidate = observe_test_merge(ctx, identity=identity, payload=payload)
    candidate_outputs, candidate_raw = candidate
    merge_commit_sha = None
    if payload.get("merged") is True:
        evidence = observe_pr_commit(ctx, identity=identity, payload=payload)
        merge_commit_sha = evidence.sha
        raw = {**raw, "merge_commit": {"state": evidence.state, "reason": evidence.reason, "graphql": evidence.raw}}
    stack_state = "unknown"
    if valid_pr_identity(payload, repository=identity.repository, pull_number=identity.pull_number):
        stack_state = normalize_pr_stack(payload)
    return ok(
        summary="GitHub pull request retrieved successfully",
        outputs={**_to_public_outputs(identity.repository, payload), **candidate_outputs,
                 "merge_commit_sha": merge_commit_sha,
                 "stack_state": stack_state, "stack": payload.get("stack") if stack_state == "stacked" else None},
        raw={**raw, "test_merge": candidate_raw},
    )


def _to_public_outputs(repository: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        **observation_metadata(payload),
        "number": payload.get("number"),
        "repository": repository,
        "title": payload.get("title"),
        "body": payload.get("body"),
        "author": normalize_author(payload.get("user")),
        "state": payload.get("state"),
        "draft": payload.get("draft"),
        "url": payload.get("html_url"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "base_ref": ((payload.get("base") or {}).get("ref")) if isinstance(payload.get("base"), dict) else None,
        "head_ref": ((payload.get("head") or {}).get("ref")) if isinstance(payload.get("head"), dict) else None,
        "head_sha": ((payload.get("head") or {}).get("sha")) if isinstance(payload.get("head"), dict) else None,
        "mergeable": payload.get("mergeable"),
        "mergeable_state": payload.get("mergeable_state"),
        "review_decision": payload.get("review_decision"),
        "additions": payload.get("additions"),
        "deletions": payload.get("deletions"),
        "changed_files": payload.get("changed_files"),
        "commits_count": payload.get("commits"),
    }


def observation_metadata(payload: dict[str, object]) -> dict[str, object]:
    """REST metadata alone never supplies a completed merge commit SHA."""
    head = payload.get("head") if isinstance(payload.get("head"), dict) else {}
    base = payload.get("base") if isinstance(payload.get("base"), dict) else {}
    head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
    base_repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
    return {
        "head_repository": head_repo.get("full_name"),
        "base_repository": base_repo.get("full_name"),
        "base_sha": base.get("sha"),
        "merged": payload.get("merged") if type(payload.get("merged")) is bool else None,
        "merged_at": payload.get("merged_at"),
        "merge_commit_sha": None,
    }


def validate_observation_identity(ctx: OperationContext, *, identity, payload: dict[str, object], raw):
    """Reject contradictory identities, but tolerate missing legacy repo metadata.

    Missing fields never authorize stack classification: that separately requires
    the complete envelope accepted by valid_pr_identity.
    """
    base = payload.get("base") if isinstance(payload.get("base"), dict) else {}
    repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
    full_name = repo.get("full_name")
    owner = repo.get("owner") if isinstance(repo.get("owner"), dict) else {}
    login, name = owner.get("login"), repo.get("name")
    mismatch = type(payload.get("number")) is not int or payload["number"] != identity.pull_number
    if full_name is not None:
        mismatch = mismatch or not isinstance(full_name, str) or full_name.lower() != identity.repository.lower()
    if login is not None and name is not None:
        mismatch = mismatch or not isinstance(login, str) or not isinstance(name, str)
        if isinstance(login, str) and isinstance(name, str):
            mismatch = mismatch or f"{login}/{name}".lower() != identity.repository.lower()
    if not mismatch:
        return None
    return fail(
        code="probe_failed", summary="GitHub pull request response identity did not match the requested PR",
        diagnostics=(Diagnostic(code="probe.gh_pr.identity_mismatch", level="error",
                                message="GitHub pull request response identity did not match the requested PR",
                                details={"pull_ref": identity.pull_ref, "number": payload.get("number"),
                                         "base_repository": full_name}),),
        raw=raw,
    )


def observe_test_merge(ctx: OperationContext, *, identity, payload: dict[str, object]):
    """Verify the synthetic commit against this PR snapshot, never against a fallback SHA.

    Only an explicitly unmerged, open PR can supply a GraphQL test candidate.
    Parent order is base then head. This is API commit
    identity evidence, not evidence of what a CI worker actually checked out.
    Optional lookup failures retain their command raw and an unavailable reason;
    callers decide whether candidate availability is required for their probe.
    """
    outputs = {
        "test_merge_sha": None,
        "test_merge_head_sha": None,
        "test_merge_base_sha": None,
        "test_merge_state": "unavailable",
        "test_merge_reason": "pull_not_open_or_merged_unknown",
    }
    if payload.get("merged") is True:
        outputs["test_merge_state"] = "merged"
        outputs["test_merge_reason"] = "already_merged"
        return outputs, {}
    if payload.get("merged") is not False or payload.get("state") != "open":
        return outputs, {}
    head = payload.get("head") if isinstance(payload.get("head"), dict) else {}
    base = payload.get("base") if isinstance(payload.get("base"), dict) else {}
    evidence = observe_pr_commit(ctx, identity=identity, payload=payload)
    if evidence.sha is None:
        outputs.update(test_merge_state=evidence.state, test_merge_reason=evidence.reason)
        return outputs, {"graphql": evidence.raw}
    sha = evidence.sha
    command, commit_raw = run_gh_command(
        ctx, ["gh", "api", f"repos/{identity.owner}/{identity.repo}/commits/{sha}"],
    )
    raw = {"graphql": evidence.raw, "commit": commit_raw}
    if command is None:
        outputs["test_merge_reason"] = "api_unavailable"
        return outputs, raw
    try:
        commit = json.loads(command.stdout)
        # The child module ``pr.list`` occupies this package's ``list`` name.
        if not isinstance(commit, dict) or not full_sha(commit.get("sha")) or not isinstance(commit.get("parents"), builtins.list):
            raise ValueError("Expected a commit object with parents")
        parents = commit["parents"]
        if not all(isinstance(parent, dict) and full_sha(parent.get("sha")) for parent in parents):
            raise ValueError("Expected parent SHA objects")
    except (ValueError, TypeError):
        outputs["test_merge_reason"] = "invalid_commit_response"
        return outputs, raw
    if commit["sha"].lower() != sha or [parent["sha"].lower() for parent in parents] != [base["sha"].lower(), head["sha"].lower()]:
        outputs["test_merge_state"] = "identity_mismatch"
        outputs["test_merge_reason"] = "candidate_or_parents_mismatch"
        return outputs, raw
    outputs.update(test_merge_sha=sha, test_merge_head_sha=head["sha"].lower(),
                   test_merge_base_sha=base["sha"].lower(), test_merge_state="verified", test_merge_reason=None)
    return outputs, raw
