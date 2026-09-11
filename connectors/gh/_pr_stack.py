"""Conservative scope normalization for GitHub REST pull request responses.

The published Get a pull request schema at
https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request declares `stack`
as optional, with an object value (required base.ref and base.sha). Unlike
explicitly nullable PR properties, it does not document null. An absent stack
therefore represents an ordinary PR only on a validated PR envelope; null or
malformed data is unknown, never permission to merge.
"""

from connectors.gh._merge_api import full_sha
from connectors.gh._repository import normalize_repository_value


def valid_pr_identity(payload: object, *, repository: str, pull_number: int) -> bool:
    """Validate response PR number and its base/target repository identity."""
    if not isinstance(payload, dict) or type(payload.get("number")) is not int or payload["number"] != pull_number:
        return False
    base = payload.get("base")
    repo = base.get("repo") if isinstance(base, dict) else None
    if not isinstance(repo, dict):
        return False
    full_name = normalize_repository_value(repo.get("full_name"))
    owner = repo.get("owner")
    if not isinstance(owner, dict) or not isinstance(owner.get("login"), str) or not isinstance(repo.get("name"), str):
        return False
    return (full_name is not None and full_name.lower() == repository.lower()
            and f"{owner['login']}/{repo['name']}".lower() == repository.lower())


def normalize_pr_stack(payload: object) -> str:
    """Return stacked, standalone, or unknown; does not validate caller identity.

Consumers must separately bind number/base repository to their requested PR.
Head repository is intentionally not compared to base: fork PRs are supported.
"""
    if not isinstance(payload, dict):
        return "unknown"
    if "stack" in payload:
        stack = payload["stack"]
        base = stack.get("base") if isinstance(stack, dict) else None
        if not isinstance(base, dict) or not isinstance(base.get("ref"), str) or not base["ref"] or not full_sha(base.get("sha")):
            return "unknown"
        for key in ("size", "position", "id", "number"):
            if key in stack and (type(stack[key]) is not int or stack[key] < 0):
                return "unknown"
        return "stacked"
    if (type(payload.get("number")) is not int or payload["number"] <= 0
            or payload.get("state") not in ("open", "closed")
            or type(payload.get("merged")) is not bool or type(payload.get("draft")) is not bool):
        return "unknown"
    for key in ("head", "base"):
        branch = payload.get(key)
        if (not isinstance(branch, dict) or not full_sha(branch.get("sha"))
                or not isinstance(branch.get("ref"), str) or not branch["ref"]):
            return "unknown"
    return "standalone"
