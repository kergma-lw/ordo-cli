"""Concrete markdown representation-adapter family."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re

from ordo.model.json import JSONArray, JSONObject, JSONValue

from .representation_adapters import (
    RepresentationAdapterError,
    RepresentationAdapterInvocation,
    RepresentationAdapterMetadata,
    RepresentationAdapterResult,
    adapter_read_result,
    adapter_write_result,
    register_representation_adapter,
)


@dataclass(slots=True)
class _MarkdownBlock:
    kind: str
    start_line: int
    end_line: int
    lines: list[str]
    items: list[str] = field(default_factory=list)
    checked: list[bool] = field(default_factory=list)


@dataclass(slots=True)
class _MarkdownSection:
    title: str | None
    level: int | None
    start_line: int
    heading_line: str | None = None
    blocks: list[_MarkdownBlock] = field(default_factory=list)
    sections: list["_MarkdownSection"] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _MarkdownPrelude:
    blocks: tuple[_MarkdownBlock, ...]


@dataclass(frozen=True, slots=True)
class _TitleStep:
    title: str


@dataclass(frozen=True, slots=True)
class _IndexStep:
    index: int


@dataclass(frozen=True, slots=True)
class _BlockKindStep:
    kind: str
    expect_one: bool


@dataclass(frozen=True, slots=True)
class _PreludeStep:
    pass


@dataclass(frozen=True, slots=True)
class _ActionArgument:
    kind: str
    value: str


@dataclass(frozen=True, slots=True)
class _MarkdownAction:
    name: str
    argument: _ActionArgument


@dataclass(frozen=True, slots=True)
class _MarkdownSelectorPlan:
    steps: tuple[object, ...]
    action: _MarkdownAction | None = None


def _register() -> None:
    register_representation_adapter(
        "markdown",
        _evaluate_markdown_invocation,
        metadata=RepresentationAdapterMetadata(
            name="markdown",
            summary="Select and transform markdown sections, blocks, and lists through a family-owned path surface.",
            selectors=("[\"title\"]", "[n]", '.blocks("kind")'),
            actions=("append_item",),
            shortcuts=("list", "lists", "task_list", "task_lists", "paragraph", "paragraphs"),
        ),
    )


def _evaluate_markdown_invocation(invocation: RepresentationAdapterInvocation) -> RepresentationAdapterResult:
    if not isinstance(invocation.root_value, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_root_value",
            message="Markdown adapter requires a string root value",
            details={"family": invocation.family, "actual_type": type(invocation.root_value).__name__},
        )
    plan = _parse_markdown_body(invocation.body)
    document = _parse_markdown_document(invocation.root_value)
    if plan.action is None:
        selection = _evaluate_markdown_plan(plan, document, action_mode=False)
        return adapter_read_result(_selection_to_json(selection))
    updated_root = _apply_markdown_action(plan, document, invocation.parameters)
    return adapter_write_result(updated_root)


def _parse_markdown_body(body: str) -> _MarkdownSelectorPlan:
    position = 0
    steps: list[object] = []
    action: _MarkdownAction | None = None
    while position < len(body):
        char = body[position]
        if char.isspace():
            position += 1
            continue
        if char == "[":
            step, position = _parse_bracket_step(body, position)
            steps.append(step)
            continue
        if char == ".":
            step, position = _parse_dot_step(body, position)
            steps.append(step)
            continue
        if body.startswith("->", position):
            action, position = _parse_action(body, position)
            break
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Markdown adapter body contains unsupported syntax",
            details={"body": body, "position": position},
        )
    if position < len(body) and body[position:].strip():
        trailing_start = position + len(body[position:]) - len(body[position:].lstrip())
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Markdown adapter body has unexpected trailing syntax",
            details={"body": body, "position": trailing_start},
        )
    return _MarkdownSelectorPlan(steps=tuple(steps), action=action)


def _parse_action(body: str, start: int) -> tuple[_MarkdownAction, int]:
    if not body.startswith("->append_item(", start):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="Unknown markdown action",
            details={"body": body, "position": start},
        )
    close = body.find(")", start + len("->append_item("))
    if close == -1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="Markdown append_item action expected closing ')'",
            details={"body": body, "position": start},
        )
    argument_text = body[start + len("->append_item(") : close].strip()
    if not argument_text:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="Markdown append_item action requires one argument",
            details={"body": body, "position": start},
        )
    try:
        literal = json.loads(argument_text)
    except json.JSONDecodeError:
        literal = None
    if isinstance(literal, str):
        argument = _ActionArgument(kind="literal", value=literal)
    elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", argument_text):
        argument = _ActionArgument(kind="parameter", value=argument_text)
    else:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="Markdown append_item action expects a string literal or parameter name",
            details={"body": body, "position": start},
        )
    return _MarkdownAction(name="append_item", argument=argument), close + 1


def _parse_bracket_step(body: str, start: int) -> tuple[object, int]:
    end = body.find("]", start + 1)
    if end == -1:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Markdown adapter expected ']' in bracket selector",
            details={"body": body, "position": start},
        )
    inner = body[start + 1 : end].strip()
    if inner.isdigit():
        return _IndexStep(index=int(inner)), end + 1
    try:
        title = json.loads(inner)
    except json.JSONDecodeError as exc:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Markdown title selectors must use a JSON string literal",
            details={"body": body, "position": start},
        ) from exc
    if not isinstance(title, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Markdown title selectors must resolve to a string",
            details={"body": body, "position": start},
        )
    return _TitleStep(title=title), end + 1


def _parse_dot_step(body: str, start: int) -> tuple[object, int]:
    if body.startswith('.blocks("', start):
        close = body.find('")', start + 9)
        if close == -1:
            raise RepresentationAdapterError(
                code="runtime.value.adapter_invalid_path",
                message="Markdown blocks selector expected closing '\")'",
                details={"body": body, "position": start},
            )
        kind = body[start + 9 : close]
        return _BlockKindStep(kind=kind, expect_one=False), close + 2
    match = re.match(r"\.([A-Za-z_][A-Za-z0-9_]*)", body[start:])
    if match is None:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Markdown adapter expected a selector name after '.'",
            details={"body": body, "position": start},
        )
    name = match.group(1)
    end = start + len(match.group(0))
    if name == "prelude":
        return _PreludeStep(), end
    if name == "list":
        return _BlockKindStep(kind="list", expect_one=True), end
    if name == "lists":
        return _BlockKindStep(kind="list", expect_one=False), end
    if name == "task_list":
        return _BlockKindStep(kind="task_list", expect_one=True), end
    if name == "task_lists":
        return _BlockKindStep(kind="task_list", expect_one=False), end
    if name == "paragraph":
        return _BlockKindStep(kind="paragraph", expect_one=True), end
    if name == "paragraphs":
        return _BlockKindStep(kind="paragraph", expect_one=False), end
    raise RepresentationAdapterError(
        code="runtime.value.adapter_invalid_path",
        message=f"Unknown markdown selector '.{name}'",
        details={"body": body, "position": start},
    )


def _parse_markdown_document(text: str) -> _MarkdownSection:
    root = _MarkdownSection(title=None, level=None, start_line=0)
    stack: list[_MarkdownSection] = [root]
    block_lines: list[str] = []
    line_index = 0
    block_start = 0

    def flush_block() -> None:
        nonlocal block_lines, block_start
        if not block_lines:
            return
        block = _make_block(block_lines, block_start)
        if block is not None:
            stack[-1].blocks.append(block)
        block_lines = []

    for raw_line in text.splitlines():
        heading_match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", raw_line)
        if heading_match is not None:
            flush_block()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            while len(stack) > 1 and stack[-1].level is not None and stack[-1].level >= level:
                stack.pop()
            section = _MarkdownSection(title=title, level=level, start_line=line_index, heading_line=raw_line)
            stack[-1].sections.append(section)
            stack.append(section)
            line_index += 1
            continue
        if not raw_line.strip():
            flush_block()
            line_index += 1
            continue
        if not block_lines:
            block_start = line_index
        block_lines.append(raw_line)
        line_index += 1

    flush_block()
    return root


def _make_block(lines: list[str], start_line: int) -> _MarkdownBlock | None:
    stripped = [line for line in lines if line.strip()]
    if not stripped:
        return None
    task_matches = [re.match(r"^\s*[-*]\s+\[([ xX])]\s+(.*)$", line) for line in stripped]
    if all(match is not None for match in task_matches):
        return _MarkdownBlock(
            kind="task_list",
            start_line=start_line,
            end_line=start_line + len(lines),
            lines=list(lines),
            items=[match.group(2) for match in task_matches if match is not None],
            checked=[match.group(1).lower() == "x" for match in task_matches if match is not None],
        )
    list_matches = [re.match(r"^\s*[-*]\s+(.*)$", line) for line in stripped]
    if all(match is not None for match in list_matches):
        return _MarkdownBlock(
            kind="list",
            start_line=start_line,
            end_line=start_line + len(lines),
            lines=list(lines),
            items=[match.group(1) for match in list_matches if match is not None],
        )
    return _MarkdownBlock(kind="paragraph", start_line=start_line, end_line=start_line + len(lines), lines=list(lines))


def _evaluate_markdown_plan(plan: _MarkdownSelectorPlan, document: _MarkdownSection, *, action_mode: bool) -> object:
    current: list[object] = [document]
    for index, step in enumerate(plan.steps):
        remaining_steps = plan.steps[index + 1 :]
        if isinstance(step, _TitleStep):
            matches = [section for node in current for section in _child_sections(node) if section.title == step.title]
            if not matches and action_mode:
                matches = _auto_create_sections(current, step.title)
            if not matches:
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_not_found",
                    message=f"Markdown section '{step.title}' was not found",
                    details={"title": step.title},
                )
            current = matches
            continue
        if isinstance(step, _IndexStep):
            if step.index >= len(current):
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_not_found",
                    message=f"Markdown selection index {step.index} is not available",
                    details={"index": step.index, "matches": len(current)},
                )
            current = [current[step.index]]
            continue
        if isinstance(step, _PreludeStep):
            if len(current) != 1 or not isinstance(current[0], _MarkdownSection) or current[0].title is not None:
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_invalid_path",
                    message="Markdown prelude is only available from the document root",
                    details={},
                )
            current = [_MarkdownPrelude(blocks=tuple(current[0].blocks))]
            continue
        if isinstance(step, _BlockKindStep):
            matches = [block for node in current for block in _child_blocks(node) if block.kind == step.kind]
            if not matches and action_mode and not remaining_steps and step.expect_one:
                matches = [_auto_create_block(current, step.kind)]
            if not matches:
                raise RepresentationAdapterError(
                    code="runtime.value.adapter_not_found",
                    message=f"Markdown {step.kind} selection found no matches",
                    details={"kind": step.kind},
                )
            if step.expect_one:
                if len(matches) > 1:
                    raise RepresentationAdapterError(
                        code="runtime.value.adapter_ambiguous",
                        message=f"Markdown {step.kind} selection is ambiguous",
                        details={"kind": step.kind, "matches": len(matches)},
                    )
                current = [matches[0]]
            else:
                current = matches
            continue
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_path",
            message="Markdown selector step is not supported",
            details={"step_type": type(step).__name__},
        )
    if len(current) == 1:
        return current[0]
    return current


def _apply_markdown_action(plan: _MarkdownSelectorPlan, document: _MarkdownSection, parameters: JSONObject) -> str:
    assert plan.action is not None
    selection = _evaluate_markdown_plan(plan, document, action_mode=True)
    if isinstance(selection, list):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_ambiguous",
            message="Markdown write path requires one explicit target",
            details={"matches": len(selection)},
        )
    if not isinstance(selection, _MarkdownBlock) or selection.kind not in {"list", "task_list"}:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message="Markdown append_item requires a list or task_list target",
            details={"target_kind": getattr(selection, "kind", type(selection).__name__)},
        )
    item_text = _resolve_action_argument(plan.action.argument, parameters)
    selection.items.append(item_text)
    if selection.kind == "task_list":
        selection.checked.append(False)
    selection.lines = _render_block_lines(selection)
    selection.end_line = selection.start_line + len(selection.lines)
    return _render_markdown(document)


def _resolve_action_argument(argument: _ActionArgument, parameters: JSONObject) -> str:
    if argument.kind == "literal":
        return argument.value
    value = parameters.get(argument.value)
    if not isinstance(value, str):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_invalid_action",
            message=f"Markdown action parameter '{argument.value}' must resolve to a string",
            details={"parameter": argument.value, "actual_type": type(value).__name__ if value is not None else "null"},
        )
    return value


def _auto_create_sections(current: list[object], title: str) -> list[_MarkdownSection]:
    if len(current) != 1 or not isinstance(current[0], _MarkdownSection):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_ambiguous",
            message="Markdown write path cannot create through an ambiguous section selection",
            details={"matches": len(current)},
        )
    parent = current[0]
    level = 2 if parent.level is None else parent.level + 1
    section = _MarkdownSection(title=title, level=level, start_line=0)
    parent.sections.append(section)
    return [section]


def _auto_create_block(current: list[object], kind: str) -> _MarkdownBlock:
    if len(current) != 1 or not isinstance(current[0], _MarkdownSection):
        raise RepresentationAdapterError(
            code="runtime.value.adapter_ambiguous",
            message="Markdown write path cannot create through an ambiguous block selection",
            details={"matches": len(current)},
        )
    if kind not in {"list", "task_list", "paragraph"}:
        raise RepresentationAdapterError(
            code="runtime.value.adapter_unsupported",
            message=f"Markdown auto-creation for block kind '{kind}' is not supported",
            details={"kind": kind},
        )
    block = _MarkdownBlock(kind=kind, start_line=0, end_line=0, lines=[])
    current[0].blocks.append(block)
    return block


def _child_sections(node: object) -> list[_MarkdownSection]:
    if isinstance(node, _MarkdownSection):
        found: list[_MarkdownSection] = []
        stack = list(node.sections)
        while stack:
            section = stack.pop(0)
            found.append(section)
            stack[0:0] = section.sections
        return found
    return []


def _child_blocks(node: object) -> list[_MarkdownBlock]:
    if isinstance(node, _MarkdownSection):
        return list(node.blocks)
    if isinstance(node, _MarkdownPrelude):
        return list(node.blocks)
    return []


def _selection_to_json(selection: object) -> JSONValue:
    if isinstance(selection, list):
        return [_selection_to_json(item) for item in selection]
    if isinstance(selection, _MarkdownSection):
        return {
            "kind": "section",
            "title": selection.title,
            "level": selection.level,
            "blocks": [_selection_to_json(block) for block in selection.blocks],
        }
    if isinstance(selection, _MarkdownPrelude):
        return {
            "kind": "prelude",
            "blocks": [_selection_to_json(block) for block in selection.blocks],
            "text": _render_markdown_blocks(selection.blocks),
        }
    if isinstance(selection, _MarkdownBlock):
        payload: JSONObject = {
            "kind": selection.kind,
            "text": "\n".join(selection.lines),
        }
        if selection.items:
            payload["items"] = list(selection.items)
        if selection.checked:
            payload["checked"] = list(selection.checked)
        return payload
    return selection  # type: ignore[return-value]


def _render_block_lines(block: _MarkdownBlock) -> list[str]:
    if block.kind == "list":
        return [f"- {item}" for item in block.items]
    if block.kind == "task_list":
        return [f"- [{'x' if checked else ' '}] {item}" for item, checked in zip(block.items, block.checked, strict=False)]
    return list(block.lines)


def _render_markdown(section: _MarkdownSection) -> str:
    parts: list[str] = []
    if section.heading_line is not None:
        parts.append(section.heading_line)
    elif section.title is not None and section.level is not None:
        parts.append(f"{'#' * section.level} {section.title}")
    for block in section.blocks:
        block_lines = _render_block_lines(block)
        if block_lines:
            parts.append("\n".join(block_lines))
    for child in section.sections:
        rendered = _render_markdown(child)
        if rendered:
            parts.append(rendered)
    return "\n\n".join(parts)


def _render_markdown_blocks(blocks: tuple[_MarkdownBlock, ...] | list[_MarkdownBlock]) -> str:
    rendered: list[str] = []
    for block in blocks:
        block_lines = _render_block_lines(block)
        if block_lines:
            rendered.append("\n".join(block_lines))
    return "\n\n".join(rendered)


_register()
