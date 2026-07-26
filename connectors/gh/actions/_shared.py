"""Shared invalidation scopes for GitHub actions."""

from __future__ import annotations

ISSUE_INVENTORY_INVALIDATION: tuple[str, ...] = ("gh.issue",)
PROJECT_ISSUE_INVALIDATION: tuple[str, ...] = ("gh.project.issue",)
