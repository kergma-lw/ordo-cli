"""Identity and completeness checks specific to PR creation."""

import re

from connectors.gh._repository import normalize_repository_value


def branch(value):
    return isinstance(value, str) and bool(value) and not any(
        c.isspace() or ord(c) < 32 or ord(c) == 127 or c == ":" for c in value
    )


def repository(value):
    return (isinstance(value, str) and normalize_repository_value(value) == value
            and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", value.split("/")[0]) is not None)


def same_repository(value, expected):
    return repository(value) and value.lower() == expected.lower()


def validate_item(item, target):
    """Unknown identity is never evidence of absence, even for another fork."""
    if not isinstance(item, dict):
        raise ValueError("Malformed pull list item")
    number = item.get("number")
    source = item.get("head_repository")
    if (type(number) is not int or number <= 0 or item.get("state") != "open"
            or not repository(source) or item.get("head_repository_key") != source.lower()
            or not same_repository(item.get("base_repository"), target)
            or not branch(item.get("head_ref")) or not branch(item.get("base_ref"))
            or type(item.get("draft")) is not bool
            or not isinstance(item.get("pull_ref"), str)
            or item["pull_ref"].lower() != f"{target}#{number}".lower()
            or not isinstance(item.get("url"), str)
            or item["url"].lower() != f"https://github.com/{target}/pull/{number}".lower()
            or item.get("merged") is True or item.get("merged_at") is not None):
        raise ValueError("Pull list item has unknown or contradictory required identity")
    owner = item.get("head_owner")
    if owner is not None and (not isinstance(owner, str) or owner.lower() != source.split("/")[0].lower()):
        raise ValueError("Pull list item has contradictory source owner")


def matches(outcome, inputs, source):
    data = outcome.outputs
    if (outcome.status != "ok" or not isinstance(data, dict)
            or data.get("complete") is not True or type(data.get("count")) is not int
            or not isinstance(data.get("items"), list) or data["count"] != len(data["items"])
            or not same_repository(data.get("repository"), inputs["repository"])
            or any(data.get(key) != inputs[key] for key in ("head", "base", "state"))
            or not isinstance(data.get("head_owner"), str)
            or data["head_owner"].lower() != inputs["head_owner"].lower()):
        raise ValueError("Open pull list did not prove a complete, correctly scoped traversal")
    found, seen = [], set()
    for item in data["items"]:
        validate_item(item, inputs["repository"])
        if item["number"] in seen:
            raise ValueError("Duplicate pull number in traversal")
        seen.add(item["number"])
        if item["head_ref"] != inputs["head"] or item["base_ref"] != inputs["base"]:
            raise ValueError("Pull list contradicted branch filters")
        if item["head_repository_key"] == source.lower():
            found.append(item)
    return found


def created_item(payload, target, source, head, base, draft, title):
    if not isinstance(payload, dict):
        raise ValueError("Created PR response is not an object")
    item = {"number": payload.get("number"), "state": payload.get("state"),
            "draft": payload.get("draft"), "url": payload.get("html_url"),
            "pull_ref": f"{target}#{payload.get('number')}", "merged": payload.get("merged"),
            "merged_at": payload.get("merged_at")}
    for side in ("head", "base"):
        node = payload.get(side)
        if not isinstance(node, dict) or not isinstance(node.get("repo"), dict):
            raise ValueError("Created PR is missing repository identity")
        repo = node["repo"]
        full_name = repo.get("full_name")
        if not repository(full_name):
            raise ValueError("Created PR repository identity is malformed")
        owner, name = full_name.split("/")
        if "name" in repo and (not isinstance(repo["name"], str) or repo["name"].lower() != name.lower()):
            raise ValueError("Created PR repository name contradicts identity")
        if "owner" in repo and (not isinstance(repo["owner"], dict)
                or not isinstance(repo["owner"].get("login"), str)
                or repo["owner"]["login"].lower() != owner.lower()):
            raise ValueError("Created PR owner contradicts identity")
        item.update({f"{side}_repository": full_name, f"{side}_ref": node.get("ref"), f"{side}_sha": node.get("sha")})
        sha = node.get("sha")
        if not isinstance(sha, str) or len(sha) != 40 or any(c not in "0123456789abcdefABCDEF" for c in sha):
            raise ValueError("Created PR SHA is missing or malformed")
    item["head_repository_key"] = item["head_repository"].lower()
    validate_item(item, target)
    if (not same_repository(item["head_repository"], source) or item["head_ref"] != head
            or item["base_ref"] != base or item["draft"] is not draft or payload.get("title") != title):
        raise ValueError("Created PR does not match requested identity, draft, or title")
    if "url" in payload and payload["url"] != f"https://api.github.com/repos/{target}/pulls/{item['number']}":
        if not isinstance(payload["url"], str) or payload["url"].lower() != f"https://api.github.com/repos/{target}/pulls/{item['number']}".lower():
            raise ValueError("Created PR API URL contradicts identity")
    return item
