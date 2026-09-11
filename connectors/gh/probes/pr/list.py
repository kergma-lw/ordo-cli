"""Complete REST pull-request collection traversal, not an atomic snapshot.

Optional observation fields remain null when GitHub omits them (including
deleted head repositories). merged is derived only from a supplied merged_at.
No delivery/merge SHA is inferred from the pulls collection endpoint.
GitHub.com only. REST documents head only as OWNER:branch; a bare head is
matched locally across the full state/base-filtered traversal. Numeric repository
Link aliases are consistency evidence only, never request destinations.
"""

from __future__ import annotations

import json
import re
import subprocess
from urllib.parse import parse_qsl, urlencode, urlsplit

from connectors.gh._repository import normalize_repository_value, resolve_repository_target
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationContext, OperationOutcome, fail, probe


_MAX_PAGES = 100
_PAGE_SIZE = 100
_OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", re.ASCII)
_ITEM_FIELDS = {
    "number": "integer", "pull_ref": "string", "url": "string",
    "state": "string", "draft": "boolean", "merged": "boolean", "merged_at": "string",
    "head_repository": "string", "head_repository_key": "string", "head_owner": "string", "head_ref": "string", "head_sha": "string",
    "base_repository": "string", "base_ref": "string", "base_sha": "string",
}


def info():
    return probe(
        name="pr.list",
        summary="List GitHub.com REST pull requests by explicit state (open|closed|all) and optional branches; bare head is filtered locally across all pages. Complete traversal is not an atomic snapshot.",
        inputs={"repository": "string", "head": "string", "head_owner": "string", "base": "string", "state": "string"},
        outputs={
            "repository": "string", "head": "string", "head_owner": "string", "base": "string", "state": "string",
            "items": [_ITEM_FIELDS], "count": "integer", "complete": "boolean",
        },
        failure_modes=("input_error", "pull_list_unavailable"),
        handler=run,
    )


def _failure(ctx, code, reason, message, *, raw=None, page=None):
    return fail(
        code=code, summary=message,
        diagnostics=(Diagnostic(
            code=f"probe.gh_pr_list.{reason}", level="error", message=message,
            details={"reference": ctx.reference, "page": page},
        ),), raw=raw or {},
    )


def _branch(value):
    # Preserve branch spelling, including URL punctuation and Unicode. A colon
    # is excluded so head_owner is the only way to author OWNER:branch.
    return isinstance(value, str) and bool(value) and not any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 or char == ":" for char in value
    )


def run(ctx: OperationContext) -> OperationOutcome:
    target = resolve_repository_target(ctx, failure_code="input_error", diagnostic_prefix="probe.gh_pr_list")
    if isinstance(target, OperationOutcome):
        return target
    filters = {key: ctx.optional_input(key) for key in ("head", "head_owner", "base", "state")}
    if filters["state"] not in ("open", "closed", "all"):
        return _failure(ctx, "input_error", "invalid_state", "state is required and must be open, closed, or all")
    for key in ("head", "base"):
        if filters[key] is not None and not _branch(filters[key]):
            return _failure(ctx, "input_error", "invalid_branch", f"{key} must be a nonempty branch name without whitespace, controls, or colon")
    owner = filters["head_owner"]
    if owner is not None and (not isinstance(owner, str) or not _OWNER.fullmatch(owner) or filters["head"] is None):
        return _failure(ctx, "input_error", "invalid_head_owner", "head_owner must be an OWNER username or organization and requires head")
    query = {"state": filters["state"], "per_page": str(_PAGE_SIZE)}
    local_head = filters["head"] is not None and owner is None
    if owner is not None:
        query["head"] = f"{owner}:{filters['head']}"
    if filters["base"] is not None:
        query["base"] = filters["base"]
    path = f"/repos/{target.repository}/pulls"
    items, pages, seen = [], [], set()
    repository_id = None
    for page in range(1, _MAX_PAGES + 1):
        endpoint = f"{path}?{urlencode({**query, 'page': str(page)})}"
        try:
            command = ctx.command(
                ["gh", "api", "--hostname", "github.com", "--method", "GET", "--include", endpoint],
                failures={"os_error": "pull_list_unavailable", "nonzero": "pull_list_unavailable"},
            )
        except MappedOutcomeError as exc:
            pages.append(exc.outcome.raw)
            return _failure(ctx, "pull_list_unavailable", "command_failed", "GitHub pull list request failed", raw={"pages": pages}, page=page)
        except subprocess.TimeoutExpired as exc:
            pages.append({
                "argv": exc.cmd, "timeout": exc.timeout,
                "stdout": _timeout_text(exc.stdout), "stderr": _timeout_text(exc.stderr),
            })
            return _failure(ctx, "pull_list_unavailable", "command_timeout", "GitHub pull list request timed out", raw={"pages": pages}, page=page)
        except UnicodeError as exc:
            pages.append({"argv": ["gh", "api", endpoint], "read_error": str(exc)})
            return _failure(ctx, "pull_list_unavailable", "read_failed", "GitHub pull list response could not be decoded", raw={"pages": pages}, page=page)
        pages.append(command.raw)
        try:
            headers, nodes = _response(command.stdout)
            next_page, repository_id = _next_page(headers, path, query, page, repository_id)
            for node in nodes:
                item = _item(node, target.repository, filters)
                repository_id = _bind_repository_id(
                    repository_id, _object(_object(node, "base"), "repo").get("id"),
                )
                if item["number"] in seen:
                    raise ValueError("Duplicate PR number indicates pagination drift")
                seen.add(item["number"])
                if local_head:
                    if item["head_ref"] is None:
                        raise ValueError("PR head ref is required for local bare-head filtering")
                    if item["head_ref"] != filters["head"]:
                        continue
                items.append(item)
        except (ValueError, TypeError) as exc:
            return _failure(ctx, "pull_list_unavailable", "invalid_response", str(exc), raw={"pages": pages}, page=page)
        if next_page is None:
            return OperationOutcome(
                status="ok",
                summary="Complete GitHub pull request list retrieved successfully",
                outputs={"repository": target.repository, **filters, "items": items, "count": len(items), "complete": True},
                diagnostics=target.diagnostics, raw={"pages": pages},
            )
    return _failure(ctx, "pull_list_unavailable", "page_limit_exceeded", "GitHub pull list exceeds the protective ceiling of 100 pages of 100 items", raw={"pages": pages}, page=_MAX_PAGES)


def _timeout_text(value):
    # TimeoutExpired can carry bytes even when subprocess uses text=True.
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def _response(stdout):
    if not isinstance(stdout, str):
        raise ValueError("GitHub pull list response is not text")
    header, separator, body = stdout.replace("\r\n", "\n").partition("\n\n")
    lines = header.split("\n")
    if not separator or not re.fullmatch(r"HTTP/\d(?:\.\d)? 200(?: .*)?", lines[0]):
        raise ValueError("GitHub pull list response requires HTTP 200 status and complete headers")
    headers = {}
    for line in lines[1:]:
        name, colon, value = line.partition(":")
        if not colon or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
            raise ValueError("Malformed GitHub HTTP response header")
        key = name.lower()
        headers[key] = f"{headers[key]}, {value.strip()}" if key in headers else value.strip()
    try:
        nodes = json.loads(body)
    except (ValueError, RecursionError) as exc:
        raise ValueError("GitHub pull list response was not valid complete JSON") from exc
    if not isinstance(nodes, list) or len(nodes) > _PAGE_SIZE:
        raise ValueError("GitHub pull list response must be an array of at most 100 items")
    return headers, nodes


def _bind_repository_id(known, observed):
    if observed is None:
        return known
    if type(observed) is not int or observed <= 0:
        raise ValueError("Malformed base repository ID")
    if known is not None and known != observed:
        raise ValueError("Contradictory canonical repository ID across links or PR responses")
    return observed


def _next_page(headers, path, query, page, repository_id):
    if "link" not in headers:
        return None, repository_id
    next_page = None
    relations = set()
    # GitHub's Link format: <URL>; rel="next", <URL>; rel="last".
    # Validate every advertised link, but never execute its URL.
    for entry in headers["link"].split(","):
        match = re.fullmatch(r'\s*<([^<>]+)>;\s*rel="(next|prev|first|last)"\s*', entry)
        if match is None or match[2] in relations:
            raise ValueError("Malformed or duplicate GitHub pagination relation")
        relations.add(match[2])
        url = urlsplit(match[1])
        if url.scheme != "https" or url.netloc != "api.github.com" or url.fragment:
            raise ValueError("GitHub pagination link changed host or endpoint")
        if url.path != path:
            alias = re.fullmatch(r"/repositories/([1-9][0-9]*)/pulls", url.path)
            if alias is None:
                raise ValueError("GitHub pagination link changed endpoint")
            repository_id = _bind_repository_id(repository_id, int(alias[1]))
        pairs = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
        params = dict(pairs)
        number = params.pop("page", "")
        if len(pairs) != len(set(key for key, _ in pairs)) or params != query or not re.fullmatch(r"[1-9][0-9]*", number):
            raise ValueError("GitHub pagination link changed filters or has an invalid page")
        if match[2] == "next":
            next_page = int(number)
            if next_page != page + 1:
                raise ValueError("GitHub pagination next link loops or skips a page")
        elif match[2] == "last" and int(number) > page:
            # A last page ahead without a next link is not completeness proof.
            relations.add("more")
    if "more" in relations and next_page is None:
        raise ValueError("GitHub pagination advertises more pages without a next link")
    return next_page, repository_id


def _text(node, key):
    value = node.get(key)
    if value is not None and (not isinstance(value, str) or not value):
        raise ValueError(f"Malformed PR field: {key}")
    return value


def _object(node, key):
    value = node.get(key)
    if value is not None and not isinstance(value, dict):
        raise ValueError(f"Malformed PR object: {key}")
    return value or {}


def _repo(side):
    repo = _object(side, "repo")
    full_name = _text(repo, "full_name")
    owner = _text(_object(repo, "owner"), "login")
    name = _text(repo, "name")
    if full_name is not None:
        if normalize_repository_value(full_name) != full_name:
            raise ValueError("Malformed PR repository identity")
        repo_owner, repo_name = full_name.split("/")
        if (owner is not None and owner.lower() != repo_owner.lower()) or (name is not None and name.lower() != repo_name.lower()):
            raise ValueError("Contradictory PR repository identity")
        owner = owner or repo_owner
    return full_name, owner, name


def _item(node, repository, filters):
    if not isinstance(node, dict) or type(node.get("number")) is not int or node["number"] <= 0 or node.get("state") not in ("open", "closed"):
        raise ValueError("Malformed essential PR number or state")
    number = node["number"]
    head, base = _object(node, "head"), _object(node, "base")
    head_repo, head_owner, _ = _repo(head)
    base_repo, base_owner, base_name = _repo(base)
    owner, name = repository.split("/")
    if ((base_repo is not None and base_repo.lower() != repository.lower())
            or (base_owner is not None and base_owner.lower() != owner.lower())
            or (base_name is not None and base_name.lower() != name.lower())):
        raise ValueError("PR response contradicts target repository")
    for key, prefix, suffix in (("url", "https://api.github.com/repos/", f"/pulls/{number}"),
                                ("html_url", "https://github.com/", f"/pull/{number}")):
        value = _text(node, key)
        if value is not None and value.lower() != f"{prefix}{repository}{suffix}".lower():
            raise ValueError("PR URL contradicts target repository or number")
    head_ref, base_ref = _text(head, "ref"), _text(base, "ref")
    for key, actual in (("head", head_ref), ("base", base_ref), ("head_owner", head_owner)):
        if key == "head" and filters["head_owner"] is None:
            continue  # Bare head is a client-side selection, not a server assertion.
        expected = filters[key]
        if expected is not None and actual is not None and (actual.lower() != expected.lower() if key == "head_owner" else actual != expected):
            raise ValueError(f"PR response contradicts {key} filter")
    if filters["state"] != "all" and node["state"] != filters["state"]:
        raise ValueError("PR response contradicts state filter")
    draft = node.get("draft")
    if draft is not None and type(draft) is not bool:
        raise ValueError("Malformed PR draft field")
    merged_at = _text(node, "merged_at")
    if merged_at is not None and node["state"] == "open":
        raise ValueError("Open PR contradicts nonempty merged_at")
    return {
        "number": number, "pull_ref": f"{repository}#{number}", "url": node.get("html_url"),
        "state": node["state"], "draft": draft,
        "merged": (merged_at is not None) if "merged_at" in node else None, "merged_at": merged_at,
        "head_repository": head_repo, "head_repository_key": head_repo.lower() if head_repo is not None else None,
        "head_owner": head_owner, "head_ref": head_ref, "head_sha": _text(head, "sha"),
        "base_repository": base_repo, "base_ref": base_ref, "base_sha": _text(base, "sha"),
    }
