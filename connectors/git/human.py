"""Shared structure for source-owned Git operation guidance."""

from __future__ import annotations

from typing import Any

from ordo.model.human import HumanDeclaration, declare_human, human_mapping


def git_human(content: HumanDeclaration | dict[str, Any], *, provide: str, result: str) -> HumanDeclaration:
    """Publish one consistent reader-facing contract for every Git operation."""

    source = human_mapping(content) if isinstance(content, HumanDeclaration) else content
    # The operation declaration supplies the authoritative named inputs and results.
    # Do not repeat raw input shapes or implementation-oriented examples in prose.
    sections = [
        {**section, "items": list(section.get("items", ()))}
        for section in source["sections"]
        if section["heading"] not in {"What to provide", "Examples", "Inspect next"}
    ]
    sections.insert(2, {"heading": "What to provide", "items": [provide]})
    existing_result = next((section for section in sections if section["heading"] == "Result and boundary"), None)
    if existing_result is None:
        sections.insert(3, {"heading": "Result and boundary", "items": [result]})
    else:
        existing_result["items"].append(result)
    declared = declare_human({**source, "sections": sections})
    # The operation module owns its facts even though this helper enforces their structure.
    return HumanDeclaration(content=declared.content, filename=content.filename) if isinstance(content, HumanDeclaration) else declared
