"""Strict, read-only Actions API observations shared by run and job probes."""

from __future__ import annotations

import json
import re
import subprocess
from urllib.parse import parse_qs, urlsplit

from connectors.gh._repository import resolve_repository_target
from ordo.plugin_sdk import Diagnostic, MappedOutcomeError, OperationOutcome, fail

REST_HEADERS = ["-H", "Accept: application/vnd.github+json",
                "-H", "X-GitHub-Api-Version: 2026-03-10"]


def positive_int(value, field):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def object_value(value, field):
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def text(value, field, *, required=False, sha=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value):
        raise ValueError(f"{field} must be a string" + (" with a value" if required else " or null"))
    if sha and re.fullmatch(r"[0-9a-fA-F]{40}", value) is None:
        raise ValueError(f"{field} must be a full commit SHA")
    return value


def repository_matches(value, repository):
    if not isinstance(value, str) or value.lower() != repository.lower():
        raise ValueError("API repository does not match the requested repository")


class ActionsObservation:
    def __init__(self, ctx, *, jobs=False):
        self.ctx = ctx
        self.code = "actions_jobs_unavailable" if jobs else "actions_run_unavailable"
        self.prefix = "probe.gh_actions_run.jobs" if jobs else "probe.gh_actions_run"
        self.raw = {}

    def failure(self, reason, message, *, code=None):
        return fail(code=code or self.code, summary=message, raw=self.raw,
                    diagnostics=(Diagnostic(code=f"{self.prefix}.{reason}", level="error",
                                            message=message, details={"reference": self.ctx.reference}),))

    def success(self, summary, outputs, target):
        return OperationOutcome(status="ok", summary=summary, outputs=outputs,
                                diagnostics=target.diagnostics, raw=self.raw)

    def repository(self):
        target = resolve_repository_target(self.ctx, failure_code="input_error", diagnostic_prefix=self.prefix)
        if isinstance(target, OperationOutcome):
            raise MappedOutcomeError(target)
        return target

    def request(self, endpoint, *, fields=(), include=False):
        argv = ["gh", "api", endpoint, "--hostname", "github.com",
                "--method", "POST" if endpoint == "graphql" else "GET", *REST_HEADERS]
        if fields:
            argv.extend(fields)
        if include:
            argv.append("--include")
        try:
            command = self.ctx.command(argv, failures={"os_error": self.code})
        except MappedOutcomeError as exc:
            self.raw[str(len(self.raw) + 1)] = exc.outcome.raw
            raise MappedOutcomeError(self.failure("request_failed", "GitHub Actions API request failed")) from exc
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            self.raw[str(len(self.raw) + 1)] = {"error": str(exc)}
            raise MappedOutcomeError(self.failure("request_failed", "GitHub Actions API request failed")) from exc
        self.raw[str(len(self.raw) + 1)] = command.raw
        if command.returncode != 0:
            raise MappedOutcomeError(self.failure("request_failed", "GitHub Actions API request failed"))
        content = command.stdout
        headers = []
        if include:
            content = content.replace("\r\n", "\n")
            block, separator, content = content.partition("\n\n")
            lines = block.splitlines()
            if not separator or not lines or re.fullmatch(r"HTTP/\S+ 200(?: .*)?", lines[0]) is None:
                raise ValueError("Expected successful API response headers")
            for line in lines[1:]:
                name, colon, value = line.partition(":")
                if not colon or not name:
                    raise ValueError("Malformed API response header")
                if name.lower() == "link":
                    headers.append(value.strip())
        payload = object_value(json.loads(content), "API response")
        return (payload, headers) if include else payload


def validate_run(payload, *, repository, run_id, attempt=None, suite_id=None, suite_node=None):
    if positive_int(payload.get("id"), "run id") != run_id:
        raise ValueError("API run id does not match the requested run")
    repository_matches(object_value(payload.get("repository"), "repository").get("full_name"), repository)
    observed_suite = positive_int(payload.get("check_suite_id"), "check_suite_id")
    observed_attempt = positive_int(payload.get("run_attempt"), "run_attempt")
    if suite_id is not None and observed_suite != suite_id:
        raise ValueError("API run check suite does not match the requested suite")
    if suite_node is not None and payload.get("check_suite_node_id") != suite_node:
        raise ValueError("API run check suite node does not match the requested suite")
    if attempt is not None and observed_attempt != attempt:
        raise ValueError("API run attempt does not match the pinned attempt")
    return observed_attempt, observed_suite


def api_url(value, path):
    """Validate an API link; only OWNER/REPO path segments ignore ASCII case."""
    text(value, "API link", required=True)
    parsed = urlsplit(value)
    actual, expected = parsed.path.split("/"), path.split("/")
    if (not value.startswith("https://api.github.com/") or parsed.netloc != "api.github.com"
            or "#" in value or "%" in value or not value.isascii()
            or any(ord(character) <= 32 or ord(character) == 127 for character in value)
            or len(actual) != len(expected) or len(expected) < 5
            or actual[:2] != ["", "repos"] or expected[:2] != ["", "repos"]
            or [segment.lower() for segment in actual[2:4]] != [segment.lower() for segment in expected[2:4]]
            or actual[4:] != expected[4:]):
        raise ValueError("API link has an unexpected host or path")
    return parsed


def pagination_links(headers, *, path, page, last_page):
    relations = {}
    for header in headers:
        for entry in header.split(","):
            match = re.fullmatch(r'\s*<([^<>]+)>;\s*rel="(next|prev|first|last)"\s*', entry)
            if match is None:
                raise ValueError("Malformed pagination Link header")
            url, relation = match.groups()
            if relation in relations:
                raise ValueError("Duplicate pagination relation")
            parsed = api_url(url, path)
            query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
            if set(query) != {"page", "per_page"} or query["per_page"] != ["100"] or len(query["page"]) != 1:
                raise ValueError("Unexpected pagination query")
            number = query["page"][0]
            if re.fullmatch(r"[1-9][0-9]*", number) is None:
                raise ValueError("Invalid pagination page")
            number = int(number)
            expected = {"next": page + 1, "prev": page - 1, "first": 1, "last": last_page}[relation]
            if number != expected or not 1 <= number <= last_page:
                raise ValueError("Pagination link contradicts the observed total")
            relations[relation] = number
    if ("next" in relations) != (page < last_page):
        raise ValueError("Missing or unexpected next pagination link")
