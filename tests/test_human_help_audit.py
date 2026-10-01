"""Structural migration coverage checks for the developer-facing human-help audit."""

import json
import subprocess
from unittest.mock import patch
from pathlib import Path

from ordo import human_help_audit as audit
from ordo.model.human import declare_human


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "ordo-human-help-audit"


def test_current_public_routes_are_migrated_and_valid():
    report = audit.build_human_help_coverage_report()
    surfaces = {item["handle"]: item for item in report["surfaces"]}

    assert report["status"] == "pass"
    for handle in ("root", "features", "overview", "model", "workflow-rules", "capabilities", "command-line", "operations", "examples", "snippet-coverage", "search"):
        assert surfaces[handle]["migration_status"] == "migrated"
        assert surfaces[handle]["human_content"] == "valid"
        assert surfaces[handle]["source_provenance"] == "verified"
        assert surfaces[handle]["verified_source_paths"]
        assert surfaces[handle]["reference_integrity"] == "valid"
        assert all(item["status"] == "verified" for item in surfaces[handle]["human_consumers"] if item["name"] in surfaces[handle]["declared_consumers"])

    focused = {
        handle.removeprefix("describe."): item
        for handle, item in surfaces.items()
        if handle.startswith("describe.")
    }
    assert focused.keys() == audit.help_cli.focused_describe_declarations().keys()
    for item in focused.values():
        assert item["human_content"] == "valid"
        assert item["source_provenance"] == "verified"
        assert item["reference_integrity"] == "valid"
        assert item["site_boundary"] == "CLI-only: focused describe requires a target and has no generated site page."


def test_every_published_operation_has_its_own_migrated_audit_surface():
    report = audit.build_human_help_coverage_report()
    surfaces = {item["handle"]: item for item in report["surfaces"]}
    expected = {
        f"operation.{connector.namespace}.{operation.name}"
        for connector in audit.help_cli.get_public_connector_registry().list_connectors()
        for operation in connector.operations
    }

    assert expected <= surfaces.keys()
    for handle in expected:
        assert surfaces[handle]["migration_status"] == "migrated"
        assert surfaces[handle]["source_provenance"] == "verified"
        assert surfaces[handle]["verified_source_paths"]
        assert surfaces[handle]["operation_human_completeness"] == "complete"


def test_audit_builds_one_search_catalog_for_all_sentinel_queries():
    with patch.object(audit.help_cli, "_build_search_index", wraps=audit.help_cli._build_search_index) as build:
        report = audit.build_human_help_coverage_report()

    assert report["status"] == "pass"
    assert build.call_count == 1


def test_operation_audit_rejects_a_declaration_from_another_source():
    operation = audit.help_cli.get_public_connector_registry().get_operation("git.branch")
    assert operation is not None
    surface = audit.HumanHelpSurface(
        "operation.git.branch", "migrated", "operation.git.branch", ("text",),
        lambda: audit.help_cli.build_operation_response("git.branch"),
        {"text": audit._text_check(audit.help_cli.render_operation_text)},
        ("/not/the/operation/declaration.py",), lambda: (operation.human_declaration(),),
    )

    report = audit.build_human_help_coverage_report((surface,))

    assert report["status"] == "fail"
    assert report["surfaces"][0]["source_provenance"] == "mismatch"


def test_focused_describe_cli_uses_source_owned_human_content_and_rejects_technical_nodes():
    public = subprocess.run(
        [str(ROOT / "ordo-help"), "describe", "profile.inputs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    technical = subprocess.run(
        [str(ROOT / "ordo-help"), "describe", "workflow.blocks"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert public.returncode == 0
    assert "Profile field for declaring default values" in public.stdout
    assert "runtime_effect" not in public.stdout
    assert technical.returncode == 0
    assert "Organize a workflow into readable named areas of work" in technical.stdout
    assert "runtime_effect" not in technical.stdout


def test_audit_fails_for_invalid_human_schema():
    invalid = audit.HumanHelpSurface(
        "invalid-human", "migrated", "test.owner", ("text",), lambda: {"human": {}}
    )

    report = audit.build_human_help_coverage_report((invalid,))

    assert report["status"] == "fail"
    assert report["surfaces"][0]["human_content"] == "invalid"


def test_audit_fails_for_broken_human_references():
    broken = audit.HumanHelpSurface(
        "broken-reference",
        "migrated",
        "test.owner",
        ("text",),
        lambda: {
            "document_kind": "test",
            "human": {
                "title": "Title", "goal": "Goal", "summary": "Summary",
                "sections": [{"heading": "Links", "references": [{"handle": "missing", "summary": "Missing"}]}],
            },
        },
    )

    report = audit.build_human_help_coverage_report((broken,))

    assert report["status"] == "fail"
    assert report["surfaces"][0]["reference_integrity"] == "broken"


def test_audit_fails_for_inconsistent_inventory():
    inconsistent = (
        audit.HumanHelpSurface("duplicate", "migrated", "test.owner", (), None),
        audit.HumanHelpSurface("duplicate", "unknown", "", ("unknown",), None),
    )

    report = audit.build_human_help_coverage_report(inconsistent)

    assert report["status"] == "fail"
    findings = " ".join(
        finding for surface in report["surfaces"] for finding in surface["findings"]
    )
    assert "unique" in findings
    assert "migration status" in findings
    assert "owner" in findings
    assert "consumer" in findings


def test_audit_fails_for_a_declared_consumer_that_does_not_use_human_content():
    surface = audit.HumanHelpSurface(
        "consumer-failure",
        "migrated",
        "test.owner",
        ("text",),
        lambda: {"document_kind": "test", "human": {"title": "Title", "goal": "Goal", "summary": "Summary", "sections": []}},
        {"text": lambda payload: (_ for _ in ()).throw(ValueError("sentinel was not rendered"))},
    )

    report = audit.build_human_help_coverage_report((surface,))

    assert report["status"] == "fail"
    assert report["surfaces"][0]["human_consumers"][2]["status"] == "failed"


def test_audit_fails_for_misplaced_human_declaration():
    declaration = declare_human({"title": "Title", "goal": "Goal", "summary": "Summary", "sections": []})
    surface = audit.HumanHelpSurface(
        "misplaced", "migrated", "test.owner", ("text",),
        lambda: {"document_kind": "test", "human": declaration.content},
        {"text": lambda payload: None},
        ("/expected/domain.py",), lambda: (declaration,),
    )

    report = audit.build_human_help_coverage_report((surface,))

    assert report["status"] == "fail"
    assert report["surfaces"][0]["source_provenance"] == "mismatch"
    assert "source provenance mismatch" in " ".join(report["surfaces"][0]["findings"])


def test_audit_fails_when_renderer_defines_human_content(monkeypatch, tmp_path):
    renderer = tmp_path / "renderer.py"
    renderer.write_text('INLINE_HUMAN = {"title": "Forbidden"}\n', encoding="utf-8")
    monkeypatch.setattr(audit, "_ROOT", tmp_path)
    monkeypatch.setattr(audit, "_RENDERER_SOURCES", ("renderer.py",))

    report = audit.build_human_help_coverage_report(())

    assert report["status"] == "fail"
    assert report["renderer_human_declarations"] == "fail"
    assert "renderer defines inline human mapping" in report["renderer_findings"][0]


def test_audit_cli_text_and_json_are_deterministic():
    command = [str(LAUNCHER)]
    text = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    payload = subprocess.run([*command, "--json"], cwd=ROOT, capture_output=True, text=True, check=False)

    assert text.returncode == 0
    assert "not prose quality" in text.stdout
    assert "command-line [migrated]" in text.stdout
    assert payload.returncode == 0
    report = json.loads(payload.stdout)
    assert report["status"] == "pass"
    assert report["prose_quality_assessed"] is False
    assert report["renderer_human_declarations"] == "verified"
