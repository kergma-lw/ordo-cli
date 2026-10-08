"""Validated reader-facing content stored beside public contracts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping, NotRequired, TypedDict

from .json import JSONObject


class HumanReference(TypedDict):
    handle: str
    summary: str


class HumanKeywordTarget(HumanReference, total=False):
    """A focused guide with an optional public keyword used to reach it."""

    keyword: str


class HumanKeyword(TypedDict):
    """One reader-facing keyword and its declared focused-help destinations."""

    name: str
    targets: list[HumanKeywordTarget]


class HumanSection(TypedDict, total=False):
    heading: str
    body: str
    items: list[str]
    references: list[HumanReference]
    examples: list[str]
    subsections: list["HumanSection"]


class HumanContent(TypedDict):
    title: str
    goal: str
    summary: str
    sections: list[HumanSection]
    keywords: NotRequired[list[HumanKeyword]]


@dataclass(frozen=True, slots=True)
class HumanDeclaration:
    """Canonical human content with internal source provenance."""

    content: HumanContent
    filename: str


def declare_human(content: HumanContent) -> HumanDeclaration:
    """Capture the source file that physically declares reader-facing content."""

    from inspect import currentframe

    frame = currentframe()
    assert frame is not None and frame.f_back is not None
    return HumanDeclaration(
        content=_canonical_human_content(content),
        filename=str(Path(frame.f_back.f_code.co_filename).resolve()),
    )


def _canonical_human_content(content: object) -> HumanContent:
    """Normalize the source-owned focused-guide shorthand into human content."""

    if not isinstance(content, dict):
        return content  # type: ignore[return-value]
    if {"title", "goal", "summary", "sections"} <= content.keys():
        return content  # type: ignore[return-value]
    definition = content.get("definition")
    if not isinstance(definition, str) or not definition.strip():
        return content  # type: ignore[return-value]
    sections: list[HumanSection] = []
    for key, heading in (
        ("use_when", "Use when"),
        ("do_not_use_for", "Do not use for"),
        ("effects", "What happens"),
        ("inspect_next", "Inspect next"),
    ):
        items = content.get(key)
        if isinstance(items, list) and all(isinstance(item, str) for item in items):
            if key == "inspect_next":
                items = [f"Run `ordo-help describe {item}`." for item in items]
            sections.append({"heading": heading, "items": items})
    for key, heading in (("nearest_surfaces", "Related surfaces"), ("related_surfaces", "Related surfaces")):
        references = content.get(key)
        if isinstance(references, list) and all(
            isinstance(item, dict)
            and isinstance(item.get("handle"), str)
            and isinstance(item.get("summary"), str)
            for item in references
        ):
            sections.append({"heading": heading, "references": references})  # type: ignore[typeddict-item]
    return {
        "title": "Focused reference",
        "goal": "Choose this public surface when it matches the work you need to do.",
        "summary": definition,
        "sections": sections,
    }


def human_mapping(value: HumanDeclaration) -> HumanContent:
    """Return the public JSON-shaped projection without internal provenance."""

    # Declarations stay beside their operations, while this projection keeps
    # incidental implementation spelling out of every reader-facing surface.
    return _reader_facing_human_content(value.content)


def complete_gh_operation_human(
    value: HumanDeclaration | None,
    *,
    name: str,
    inputs: Mapping[str, object],
    outputs: Mapping[str, object],
    is_action: bool,
    has_preflight: bool = False,
) -> HumanDeclaration | None:
    """Complete author-facing contract sections for a GitHub declaration.

    Individual connector modules own their purpose, selection, and operation
    boundaries. This publishes explicit input statuses and usable result facts
    without rendering schema types.
    """

    if value is None or "/connectors/gh/" not in value.filename:
        return value
    content = deepcopy(value.content)
    # Operation snippets are rendered separately for both CLI and site. Do not
    # publish prose-only input sketches as if they were runnable examples.
    content["sections"] = [section for section in content["sections"] if section.get("heading") != "Examples"]
    input_statuses = _gh_input_statuses(name, inputs)
    reader_outputs = {name: shape for name, shape in outputs.items() if name != "http_status"}
    headings = {section.get("heading") for section in content["sections"]}
    additions: list[HumanSection] = []
    _complete_gh_section(
        content["sections"],
        additions,
        heading="What to provide",
        missing_items=_missing_input_status_items(content["sections"], input_statuses),
    )
    _complete_gh_section(
        content["sections"],
        additions,
        heading="Result and boundary",
        missing_items=_missing_result_items(
            content["sections"], reader_outputs, is_action=is_action, has_preflight=has_preflight,
        ),
    )
    if additions:
        index = next((i for i, section in enumerate(content["sections"])
                      if section.get("heading") == "Do not use for"), len(content["sections"]))
        content["sections"][index:index] = additions
    return HumanDeclaration(content=content, filename=value.filename)


_GH_INPUT_STATUSES: dict[str, dict[str, str]] = {
    "actions.dispatch": {"repository": "context-defaulted", "workflow": "required", "ref": "required", "inputs": "required", "request_id": "required"},
    "actions.run": {"repository": "context-defaulted", "run_id": "conditional", "check_suite_id": "conditional", "attempt": "optional"},
    "actions.run.search": {"repository": "context-defaulted", "workflow": "required", "event": "required", "ref": "required", "request_id": "required"},
    "actions.run.jobs": {"repository": "context-defaulted", "run_id": "required", "attempt": "required"},
    "issue": {"repository": "context-defaulted", "issue_number": "required"},
    "issue.body.append": {"repository": "context-defaulted", "issue_number": "required", "text": "required", "separator": "optional"},
    "issue.body.replace": {"repository": "context-defaulted", "issue_number": "required", "body": "required"},
    "issue.close": {"repository": "context-defaulted", "issue_number": "required"},
    "issue.comment.add": {"repository": "context-defaulted", "issue_number": "required", "body": "required"},
    "issue.comments": {"repository": "context-defaulted", "issue_number": "required", "limit": "optional"},
    "issue.create": {"repository": "context-defaulted", "title": "required", "body": "optional"},
    "pr": {"repository": "context-defaulted", "pull_number": "required"},
    "pr.checks": {"repository": "context-defaulted", "pull_number": "required", "target": "optional", "expected_head_sha": "conditional"},
    "pr.comments": {"repository": "context-defaulted", "pull_number": "required", "limit": "optional"},
    "pr.create": {"repository": "context-defaulted", "head": "required", "base": "required", "title": "required", "body": "optional", "draft": "required", "head_repository": "conditional", "head_owner": "conditional"},
    "pr.diff": {"repository": "context-defaulted", "pull_number": "required", "limit": "optional"},
    "pr.list": {"repository": "context-defaulted", "head": "optional", "head_owner": "conditional", "base": "optional", "state": "required"},
    "pr.merge": {"repository": "context-defaulted", "pull_number": "required", "merge_method": "required", "expected_head_sha": "required"},
    "pr.merge.request": {"repository": "context-defaulted", "pull_number": "required", "request_id": "required"},
    "pr.review_comments": {"repository": "context-defaulted", "pull_number": "required", "limit": "optional"},
    "pr.reviews": {"repository": "context-defaulted", "pull_number": "required", "limit": "optional"},
    "pr.timeline": {"repository": "context-defaulted", "pull_number": "required", "limit": "optional"},
    "project": {"project_id": "required"},
    "project.field": {"project_id": "required", "field": "required"},
    "project.field.option": {"project_id": "required", "field": "required", "option": "required"},
    "project.issue": {"repository": "context-defaulted", "issue_number": "required", "project_id": "required"},
    "project.issue.add": {"repository": "context-defaulted", "issue_number": "required", "project_id": "required"},
    "project.issue.field_iteration.set": {"repository": "context-defaulted", "issue_number": "required", "project_id": "required", "field": "required", "iteration": "required"},
    "project.issue.field_number.set": {"repository": "context-defaulted", "issue_number": "required", "project_id": "required", "field": "required", "value": "required"},
    "project.issue.field_single_select.set": {"repository": "context-defaulted", "issue_number": "required", "project_id": "required", "field": "required", "option": "required"},
    "project.items": {"project_id": "required", "content_kind": "optional", "filters": "optional", "content_refs": "optional"},
    "project.items.details": {"project_id": "required", "content_kind": "optional", "filters": "optional", "content_refs": "optional"},
    "repo": {"repository": "context-defaulted"},
    "repo.actions.permissions": {"repository": "context-defaulted"},
    "repo.actions.permissions.set": {"repository": "context-defaulted", "enabled": "required"},
    "repo.sync": {"repository": "context-defaulted"},
}


def _gh_input_statuses(name: str, inputs: Mapping[str, object]) -> dict[str, str]:
    statuses = _GH_INPUT_STATUSES.get(name)
    if statuses is None or set(statuses) != set(inputs):
        raise ValueError(f"GitHub operation input statuses are missing for {name}")
    return statuses


def _complete_gh_section(
    sections: list[HumanSection],
    additions: list[HumanSection],
    *,
    heading: str,
    missing_items: list[str],
) -> None:
    """Append only contract facts absent from an authored section."""

    if not missing_items:
        return
    section = next((section for section in sections if section.get("heading") == heading), None)
    if section is None:
        additions.append({"heading": heading, "items": missing_items})
        return
    section.setdefault("items", []).extend(missing_items)


def _missing_input_status_items(
    sections: list[HumanSection], statuses: Mapping[str, str],
) -> list[str]:
    section = next((section for section in sections if section.get("heading") == "What to provide"), None)
    text = " ".join(section.get("items", ())) if section is not None else ""
    items = []
    for name, status in statuses.items():
        marker = f"`{name}`: {status}"
        if marker in text:
            continue
        if status == "context-defaulted" and name == "repository":
            items.append(
                "`repository`: context-defaulted; when omitted, it uses the GitHub repository selected by the "
                "workflow's playbook or profile settings. Provide an explicit `OWNER/REPO` value to override "
                "that default for this call."
            )
        else:
            items.append(f"{marker}.")
    return items


def _missing_result_items(
    sections: list[HumanSection], outputs: Mapping[str, object], *, is_action: bool, has_preflight: bool,
) -> list[str]:
    section = next((section for section in sections if section.get("heading") == "Result and boundary"), None)
    text = " ".join(section.get("items", ())) if section is not None else ""
    items = [f"Usable result fact: `{name}`." for name in outputs if name not in text]
    if "Material constraint:" not in text:
        items.append(_material_constraint_sentence(is_action=is_action, has_preflight=has_preflight))
    return items


def _material_constraint_sentence(*, is_action: bool, has_preflight: bool) -> str:
    change_boundary = " A successful change is not rolled back if a later workflow step fails." if is_action else ""
    preflight_boundary = " Required preflight facts must be established before the change is submitted." if has_preflight else ""
    return (
        "Material constraint: unavailable, invalid, contradictory, or incomplete facts stop the operation without a usable result; concurrent changes can make a result stale, so observe again before a current-state decision."
        f"{change_boundary}{preflight_boundary}"
    )


def _reader_facing_human_content(content: HumanContent) -> HumanContent:
    """Normalize repeated migration-era wording without consulting contracts."""

    public = deepcopy(content)
    def reader_text(text: str) -> str:
        return text.replace(
            "connector_contexts.gh.repository",
            "the workflow's GitHub repository context",
        )

    public["title"] = reader_text(public["title"]).replace("_", "-")
    public["goal"] = reader_text(public["goal"])
    public["summary"] = reader_text(public["summary"])
    for section in public["sections"]:
        if isinstance(section.get("body"), str):
            section["body"] = reader_text(section["body"])
        if isinstance(section.get("items"), list):
            section["items"] = [reader_text(item) for item in section["items"]]
        if isinstance(section.get("examples"), list):
            section["examples"] = [reader_text(item) for item in section["examples"]]
        if isinstance(section.get("references"), list):
            for reference in section["references"]:
                reference["summary"] = reader_text(reference["summary"])
        items = section.get("items")
        if section.get("heading") != "Use when" or not isinstance(items, list) or not items:
            continue
        # The goal is the page introduction; repeating it as the first reason
        # to use the operation hides the operation-specific guidance below it.
        if items[0] == public["goal"]:
            section["items"] = (
                items[1:]
                if len(items) > 1
                else [f"Choose this focused operation for its specific result: {public['summary']}"]
            )
    return public


def validate_human_mapping(value: object, *, owner: str) -> None:
    """Reject incomplete reader-facing projections before they reach consumers."""

    if not isinstance(value, dict):
        raise ValueError(f"{owner}.human must be a mapping")
    for key in ("title", "goal", "summary", "sections"):
        if key not in value:
            raise ValueError(f"{owner}.human must include {key}")
    if not all(isinstance(value[key], str) and value[key].strip() for key in ("title", "goal", "summary")):
        raise ValueError(f"{owner}.human title, goal, and summary must be non-empty text")
    sections = value["sections"]
    if not isinstance(sections, list):
        raise ValueError(f"{owner}.human.sections must be a list")
    for section in sections:
        _validate_human_section(section, owner=owner)
    _validate_human_keywords(value.get("keywords"), owner=owner)


_HUMAN_KEYWORD_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


def _validate_human_keywords(keywords: object, *, owner: str) -> None:
    """Require published keyword entries to be normalized and resolvable in intent."""

    if keywords is None:
        return
    if not isinstance(keywords, list):
        raise ValueError(f"{owner}.human.keywords must be a list")
    names: set[str] = set()
    for keyword in keywords:
        if not isinstance(keyword, dict):
            raise ValueError(f"{owner}.human.keywords entries must be mappings")
        name = keyword.get("name")
        if not isinstance(name, str) or not _HUMAN_KEYWORD_PATTERN.fullmatch(name):
            raise ValueError(f"{owner}.human keyword names must be normalized public names")
        if name in names:
            raise ValueError(f"{owner}.human keyword {name!r} is declared more than once; use one dispatcher entry")
        names.add(name)
        targets = keyword.get("targets")
        if not isinstance(targets, list) or not targets:
            raise ValueError(f"{owner}.human keyword {name!r} must declare one or more targets")
        for target in targets:
            if not isinstance(target, dict) or not all(
                isinstance(target.get(key), str) and target[key]
                for key in ("handle", "summary")
            ):
                raise ValueError(f"{owner}.human keyword {name!r} targets must include handle and summary")
            target_keyword = target.get("keyword")
            if target_keyword is not None and (
                not isinstance(target_keyword, str) or not _HUMAN_KEYWORD_PATTERN.fullmatch(target_keyword)
            ):
                raise ValueError(f"{owner}.human keyword {name!r} target keywords must be normalized public names")


def human_keywords(value: HumanContent, *, owner: str) -> list[HumanKeyword]:
    """Return the checked reader-facing keyword catalogue for one public surface."""

    keywords = value.get("keywords", [])
    _validate_human_keywords(keywords, owner=owner)
    return deepcopy(keywords)  # type: ignore[return-value]


def _validate_human_section(section: object, *, owner: str) -> None:
    if not isinstance(section, dict) or not isinstance(section.get("heading"), str):
        raise ValueError(f"{owner}.human sections must include a heading")
    for key in ("body",):
        if key in section and not isinstance(section[key], str):
            raise ValueError(f"{owner}.human section {key} must be text")
    for key in ("items", "examples"):
        if key in section and (not isinstance(section[key], list) or not all(isinstance(item, str) for item in section[key])):
            raise ValueError(f"{owner}.human section {key} must be text entries")
    for reference in section.get("references", []):
        if not isinstance(reference, dict) or not all(isinstance(reference.get(key), str) and reference[key] for key in ("handle", "summary")):
            raise ValueError(f"{owner}.human references must include handle and summary")
    for subsection in section.get("subsections", []):
        _validate_human_section(subsection, owner=owner)


def human_text(value: JSONObject, *, owner: str) -> HumanContent:
    """Return a checked human projection without consulting contract metadata."""

    human = value.get("human")
    if isinstance(human, HumanDeclaration):
        human = human_mapping(human)
    validate_human_mapping(human, owner=owner)
    return human  # type: ignore[return-value]


def human_content(value: HumanDeclaration | JSONObject, *, owner: str) -> HumanContent:
    """Validate and return the canonical reader-facing projection unchanged."""

    if isinstance(value, HumanDeclaration):
        human = human_mapping(value)
        validate_human_mapping(human, owner=owner)
        return deepcopy(human)
    return human_text(value, owner=owner)
