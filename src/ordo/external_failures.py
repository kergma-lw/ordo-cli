"""Shared helpers for classifying and surfacing external command failures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from ordo.model.json import JSONObject, JSONValue

ExternalFailureClassification = Literal[
    "binary_missing",
    "auth_failed",
    "permission_denied",
    "network_failed",
    "tls_failed",
    "timeout",
    "rate_limited",
    "resource_not_found",
    "remote_api_failed",
    "unknown_external",
]

_MAX_EXCERPT_LENGTH = 240
_MAX_ARGV_SUMMARY_LENGTH = 160


@dataclass(frozen=True, slots=True)
class ExternalFailureInfo:
    classification: ExternalFailureClassification
    is_external: bool
    external_tool: str | None = None
    external_system: str | None = None
    argv_summary: str | None = None
    returncode: int | None = None
    stderr_excerpt: str | None = None
    stdout_excerpt: str | None = None
    os_error: str | None = None
    suggested_checks: tuple[str, ...] = ()

    def to_details(self) -> JSONObject:
        details: JSONObject = {
            "is_external": self.is_external,
            "classification": self.classification,
        }
        if self.external_tool is not None:
            details["external_tool"] = self.external_tool
        if self.external_system is not None:
            details["external_system"] = self.external_system
        if self.argv_summary is not None:
            details["argv_summary"] = self.argv_summary
        if self.returncode is not None:
            details["returncode"] = self.returncode
        if self.stderr_excerpt is not None:
            details["stderr_excerpt"] = self.stderr_excerpt
        if self.stdout_excerpt is not None:
            details["stdout_excerpt"] = self.stdout_excerpt
        if self.os_error is not None:
            details["os_error"] = self.os_error
        if self.suggested_checks:
            details["suggested_checks"] = list(self.suggested_checks)
        return details


def build_external_failure_details(
    *,
    raw: Mapping[str, object] | None,
    tool: str | None = None,
    system: str | None = None,
    extra_details: Mapping[str, JSONValue] | None = None,
) -> JSONObject:
    details = classify_external_command_failure(raw=raw, tool=tool, system=system).to_details()
    if extra_details is not None:
        details.update(dict(extra_details))
    return details


def classify_external_command_failure(
    *,
    raw: Mapping[str, object] | None,
    tool: str | None = None,
    system: str | None = None,
) -> ExternalFailureInfo:
    payload = {} if raw is None else dict(raw)
    argv_summary = summarize_command_argv(payload.get("argv"))
    stderr_excerpt = excerpt_text(payload.get("stderr"))
    stdout_excerpt = excerpt_text(payload.get("stdout"))
    os_error = excerpt_text(payload.get("os_error"))
    returncode = payload.get("returncode")
    returncode_value = returncode if isinstance(returncode, int) else None
    haystack = "\n".join(part for part in (str(os_error or ""), str(stderr_excerpt or ""), str(stdout_excerpt or "")) if part).lower()
    classification = _classify_failure_text(haystack=haystack, returncode=returncode_value)
    return ExternalFailureInfo(
        classification=classification,
        is_external=True,
        external_tool=tool or _first_argv_token(payload.get("argv")),
        external_system=system,
        argv_summary=argv_summary,
        returncode=returncode_value,
        stderr_excerpt=stderr_excerpt,
        stdout_excerpt=stdout_excerpt,
        os_error=os_error,
        suggested_checks=_suggested_checks(classification=classification, tool=tool or _first_argv_token(payload.get("argv")), system=system),
    )


def summarize_command_argv(value: object, *, limit: int = _MAX_ARGV_SUMMARY_LENGTH) -> str | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    rendered = " ".join(str(item) for item in value)
    return excerpt_text(rendered, limit=limit)


def excerpt_text(value: object, *, limit: int = _MAX_EXCERPT_LENGTH) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(limit - 3, 1)].rstrip() + "..."


def _classify_failure_text(*, haystack: str, returncode: int | None) -> ExternalFailureClassification:
    if not haystack and returncode is None:
        return "unknown_external"
    if any(token in haystack for token in ("no such file or directory", "not installed", "command not found", "executable file not found", "file not found")):
        return "binary_missing"
    if any(token in haystack for token in ("gh auth login", "authentication", "not logged in", "bad credentials", "requires authentication", "unauthorized", "forbidden", "invalid token")):
        return "auth_failed"
    if any(token in haystack for token in ("permission denied", "access is denied", "operation not permitted")):
        return "permission_denied"
    if any(token in haystack for token in ("timed out", "timeout")):
        return "timeout"
    if any(token in haystack for token in ("tls", "x509", "certificate verify failed", "ssl certificate", "handshake failure")):
        return "tls_failed"
    if any(token in haystack for token in ("rate limit", "too many requests", "secondary rate limit", "api rate limit exceeded")):
        return "rate_limited"
    if any(
        token in haystack
        for token in (
            "could not resolve host",
            "temporary failure in name resolution",
            "name or service not known",
            "network is unreachable",
            "no route to host",
            "connection refused",
            "connection reset",
            "dial tcp",
            "connection timed out",
        )
    ):
        return "network_failed"
    if any(token in haystack for token in ("could not resolve to", "pull request was not found", "issue not found", "repository not found", "not found")):
        return "resource_not_found"
    if any(token in haystack for token in ("server error", "internal server error", "service unavailable", "bad gateway", "gateway timeout", "http 5")):
        return "remote_api_failed"
    return "unknown_external"


def _suggested_checks(
    *,
    classification: ExternalFailureClassification,
    tool: str | None,
    system: str | None,
) -> tuple[str, ...]:
    if classification == "binary_missing":
        if tool:
            return (f"Verify '{tool}' is installed and available on PATH.",)
        return ("Verify the required external command is installed and available on PATH.",)
    if classification == "auth_failed":
        if tool == "gh":
            return ("Run 'gh auth status' to verify GitHub CLI authentication.",)
        return ("Verify authentication and credentials for the external system.",)
    if classification == "permission_denied":
        return ("Check local permissions and remote access rights for the requested operation.",)
    if classification == "timeout":
        return ("Retry the command and check whether the external system is responding slowly.",)
    if classification == "tls_failed":
        return ("Check TLS/certificate settings for the external system.",)
    if classification == "rate_limited":
        if system == "github":
            return ("Check GitHub API rate limits or retry later.",)
        return ("Check whether the remote API is rate limiting requests.",)
    if classification == "network_failed":
        if system == "github":
            return ("Check network, proxy, DNS, and GitHub connectivity.",)
        return ("Check network connectivity, DNS, and any proxy settings.",)
    if classification == "resource_not_found":
        return ("Verify the referenced remote resource exists and is accessible.",)
    if classification == "remote_api_failed":
        return ("Retry later or inspect the remote service status.",)
    return ("Inspect stderr output from the external command for the concrete cause.",)


def _first_argv_token(value: object) -> str | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)) or not value:
        return None
    return str(value[0])
