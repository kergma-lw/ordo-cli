"""Git connector family."""

from __future__ import annotations

from connectors._family import ActionHandler, ProbeHandler, assemble_family
from ordo.model.human import HumanDeclaration, declare_human

from .bootstrap import BOOTSTRAP

ORDER = 10

FAMILY_HUMAN = declare_human({
    "title": "Git connector",
    "goal": "Choose one Git operation for a local repository question or one deliberate repository change.",
    "summary": "Guidance for selecting Git observations and changes without treating independent history strategies as a sequence.",
    "sections": [
        {"heading": "Use when", "items": [
            "Inspect the current repository, branch, worktree, history, tags, remotes, or tracking relationship before making a decision.",
            "Make one intentional change, such as staging, committing, switching or cleaning up a branch, synchronizing, or applying one chosen integration strategy.",
        ]},
        {"heading": "Choose safely", "items": [
            "For integration, choose exactly one operation for the intended outcome: merge to record an integration commit, fast-forward only to preserve a linear history, cherry-pick to copy one commit, or rebase onto to rewrite a topic branch.",
            "Inspect first when the decision depends on current repository state. Observations describe a moment in time and do not guarantee a later change will remain safe.",
        ]},
        {"heading": "Do not use for", "items": [
            "Running several integration strategies one after another as fallbacks or comparisons. Put each intentional alternative in its own reviewed workflow path.",
            "Choosing a remote destination or publication policy from a name alone. Confirm the destination and authorization outside the observation.",
        ]},
        {"heading": "Related references", "references": [
            {"handle": "operations", "summary": "Browse every published connector operation."},
        ]},
        {"heading": "Inspect local state", "references": [
            {"handle": "connector.git.repo", "summary": "Inspect the current repository context."},
            {"handle": "connector.git.state", "summary": "Inspect repository state before a state-dependent decision."},
            {"handle": "connector.git.worktree", "summary": "Inspect the current worktree."},
            {"handle": "connector.git.worktrees", "summary": "List linked worktrees."},
            {"handle": "connector.git.branch", "summary": "Inspect one branch."},
            {"handle": "connector.git.branches", "summary": "List local branches."},
            {"handle": "connector.git.upstream", "summary": "Inspect the current branch's tracking relationship."},
            {"handle": "connector.git.remote", "summary": "Inspect one named remote."},
            {"handle": "connector.git.ref", "summary": "Resolve one revision reference."},
        ]},
        {"heading": "Inspect history and labels", "references": [
            {"handle": "connector.git.commits", "summary": "Inspect commits selected by the workflow."},
            {"handle": "connector.git.range", "summary": "Inspect the changes or commits between two revisions."},
            {"handle": "connector.git.stash", "summary": "Inspect saved work in the stash."},
            {"handle": "connector.git.tag", "summary": "Inspect one tag."},
            {"handle": "connector.git.tags", "summary": "List tags."},
        ]},
        {"heading": "Change branches and history", "references": [
            {"handle": "connector.git.branch.create", "summary": "Create one named branch."},
            {"handle": "connector.git.branch.delete", "summary": "Delete one deliberate branch target."},
            {"handle": "connector.git.branch.switch", "summary": "Switch the current worktree to one branch."},
            {"handle": "connector.git.index.add_all", "summary": "Stage the intended worktree changes."},
            {"handle": "connector.git.commit.create", "summary": "Create one commit from staged changes."},
            {"handle": "connector.git.commit.amend", "summary": "Amend the current commit deliberately."},
            {"handle": "connector.git.commit.revert", "summary": "Create a new commit that reverts one earlier commit."},
        ]},
        {"heading": "Synchronize and integrate", "references": [
            {"handle": "connector.git.sync.fetch", "summary": "Fetch updated remote references."},
            {"handle": "connector.git.sync.push", "summary": "Push the selected local publication."},
            {"handle": "connector.git.integrate.merge", "summary": "Integrate with a merge commit."},
            {"handle": "connector.git.integrate.merge_ff_only", "summary": "Integrate only when a fast-forward is possible."},
            {"handle": "connector.git.integrate.cherry_pick", "summary": "Copy one selected commit onto the current branch."},
            {"handle": "connector.git.integrate.rebase_onto", "summary": "Rewrite a topic branch onto its chosen base."},
        ]},
    ],
})


def get_family_human() -> HumanDeclaration:
    return FAMILY_HUMAN


_ASSEMBLED = assemble_family(package_name=__name__, namespace="git", bootstrap=BOOTSTRAP)


def get_connector():
    return _ASSEMBLED.connector


def get_probe_handler(name: str) -> ProbeHandler | None:
    return _ASSEMBLED.probe_handlers.get(name)


def get_action_handler(name: str) -> ActionHandler | None:
    return _ASSEMBLED.action_handlers.get(name)
