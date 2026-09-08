"""Pure GitHub repository operand grammar, not account or existence validation."""

import re


def normalize_github_repository(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    repository = value.strip(" ")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None:
        return None
    owner, repo = repository.split("/")
    if owner in (".", "..") or repo in (".", "..") or owner.startswith("-"):
        return None
    return repository


def split_github_repository(value: object) -> tuple[str, str] | None:
    repository = normalize_github_repository(value)
    if repository is None:
        return None
    owner, repo = repository.split("/")
    return owner, repo
