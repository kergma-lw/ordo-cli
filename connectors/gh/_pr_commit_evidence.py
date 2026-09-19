"""Read-only PR commit evidence tied to an authoritative REST snapshot."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from connectors.gh._merge_api import full_sha
from connectors.gh._pr_stack import valid_pr_identity
from ordo.plugin_sdk import MappedOutcomeError, OperationContext


PR_COMMIT_QUERY = """query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    nameWithOwner
    pullRequest(number: $number) {
      number state merged headRefOid baseRefOid
      potentialMergeCommit { oid }
      mergeCommit { oid }
    }
  }
}"""


@dataclass(frozen=True)
class PRCommitEvidence:
    sha: str | None
    state: str
    reason: str | None
    raw: dict


def run_gh_command(ctx: OperationContext, argv: list[str]):
    """Retain wrapper-provided raw evidence; never parse a failed command as success."""
    try:
        command = ctx.command(argv, failures={"os_error": "probe_failed", "nonzero": "probe_failed"})
    except MappedOutcomeError as exc:
        return None, exc.outcome.raw
    except (subprocess.TimeoutExpired, OSError, UnicodeError) as exc:
        # Exception text can contain unredacted process output. Keep only its type.
        return None, {"argv": argv, "error": type(exc).__name__}
    if command.returncode != 0:
        return None, command.raw
    return command, command.raw


def observe_pr_commit(ctx: OperationContext, *, identity, payload: dict[str, object]) -> PRCommitEvidence:
    """Select potential/result SHA only after validating the full GraphQL envelope."""
    def unavailable(reason, raw=None, *, mismatch=False):
        return PRCommitEvidence(None, "identity_mismatch" if mismatch else "unavailable", reason, raw or {})

    head = payload.get("head") if isinstance(payload.get("head"), dict) else {}
    base = payload.get("base") if isinstance(payload.get("base"), dict) else {}
    if not all(full_sha(value) for value in (head.get("sha"), base.get("sha"))):
        return unavailable("head_or_base_sha_unavailable")
    if not valid_pr_identity(payload, repository=identity.repository, pull_number=identity.pull_number):
        # Callers reject contradictory REST identities first. Missing metadata
        # cannot bind evidence, but is not evidence of a different PR.
        return unavailable("invalid_commit_response")
    merged, state = payload.get("merged"), payload.get("state")
    if type(merged) is not bool or state not in ("open", "closed") or (merged and state != "closed"):
        return unavailable("pull_not_open_or_merged_unknown")
    command, raw = run_gh_command(ctx, [
        "gh", "api", "graphql", "-f", f"query={PR_COMMIT_QUERY}",
        "-f", f"owner={identity.owner}", "-f", f"repo={identity.repo}",
        "-F", f"number={identity.pull_number}",
    ])
    if command is None:
        return unavailable("api_unavailable", raw)
    try:
        response = json.loads(command.stdout)
        if not isinstance(response, dict):
            raise ValueError("Expected GraphQL response object")
        # Reject partial data and malformed error containers, including null.
        if "errors" in response:
            if not isinstance(response["errors"], list):
                raise ValueError("Invalid GraphQL errors container")
            if response["errors"]:
                return unavailable("api_unavailable", raw)
        data = response.get("data")
        repository = data.get("repository") if isinstance(data, dict) else None
        pull = repository.get("pullRequest") if isinstance(repository, dict) else None
        if (not isinstance(repository, dict) or not isinstance(repository.get("nameWithOwner"), str)
                or not isinstance(pull, dict) or type(pull.get("number")) is not int
                or pull.get("state") not in ("OPEN", "CLOSED", "MERGED")
                or type(pull.get("merged")) is not bool
                or not full_sha(pull.get("headRefOid")) or not full_sha(pull.get("baseRefOid"))):
            raise ValueError("Invalid GraphQL PR envelope")
        expected_state = "MERGED" if merged else state.upper()
        if (repository["nameWithOwner"].lower() != identity.repository.lower()
                or pull["number"] != payload["number"] or pull["state"] != expected_state
                or pull["merged"] is not merged or pull["headRefOid"].lower() != head["sha"].lower()
                or pull["baseRefOid"].lower() != base["sha"].lower()):
            return unavailable("graphql_snapshot_mismatch", raw, mismatch=True)
        field = "mergeCommit" if merged else "potentialMergeCommit"
        for key in ("potentialMergeCommit", "mergeCommit"):
            if key not in pull or (pull[key] is not None and not isinstance(pull[key], dict)):
                raise ValueError("Invalid GraphQL commit object")
            if isinstance(pull[key], dict) and not full_sha(pull[key].get("oid")):
                return unavailable("invalid_candidate_sha" if key == field and not merged else "invalid_commit_response", raw)
        commit = pull[field]
        if commit is None:
            return unavailable("merge_commit_missing" if merged else "candidate_missing", raw)
        return PRCommitEvidence(commit["oid"].lower(), "verified", None, raw)
    except (ValueError, TypeError):
        return unavailable("invalid_commit_response", raw)
