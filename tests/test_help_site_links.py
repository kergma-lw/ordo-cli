"""Every example-related topic must have a generated documentation page."""

from pathlib import Path

from ordo.model.examples_catalog import EXAMPLES_CATALOG
from tools.build_help_site_docs import ROOT, STATIC_TOPICS, copy_repository_examples, render_operation, render_topic


def test_example_related_topics_are_generated():
    referenced = {
        topic
        for example in EXAMPLES_CATALOG["examples"]
        for topic in example.get("related_topics", [])
    }
    assert referenced <= set(STATIC_TOPICS)
    assert "features" in referenced


def test_repository_examples_are_copied_to_the_site(tmp_path: Path):
    copy_repository_examples(tmp_path)

    for example in EXAMPLES_CATALOG["examples"]:
        assert (tmp_path / example["path"]).is_file()


def test_committed_site_examples_match_repository_examples():
    source = ROOT / "examples"
    generated = ROOT / "site-docs" / "examples"

    assert {
        path.relative_to(source) for path in source.rglob("*") if path.is_file()
    } == {
        path.relative_to(generated) for path in generated.rglob("*") if path.is_file()
    }
    for source_path in source.rglob("*"):
        if source_path.is_file():
            assert (generated / source_path.relative_to(source)).read_bytes() == source_path.read_bytes()


def test_operations_site_catalog_links_to_index_and_focused_pages():
    from ordo.help_cli import build_operations_response

    rendered = render_topic(Path("topics/operations.md"), "operations", build_operations_response())

    assert "[Full operation index](../operations/index.md)" in rendered
    assert "`ordo-help operation <namespace.operation>`" in rendered
    assert "`ordo-help operation <namespace.operation> --json`" in rendered
    assert "[gh.pr.create (action)](../operations/gh/pr-create.md)" in rendered
    assert "shell.command (action) [legacy-only; do not use for new workflows]" in rendered


def test_static_topic_references_link_from_the_current_page():
    doc = {
        "human": {
            "title": "Reference links",
            "goal": "Verify static topic navigation.",
            "summary": "References point at generated pages.",
            "sections": [{
                "heading": "Related pages",
                "references": [
                    {"handle": "workflow-rules", "summary": "Topic page."},
                    {"handle": "connector.git.branch", "summary": "Operation page."},
                ],
            }],
        },
    }

    for topic in ("command-line", "examples", "operations"):
        rendered = render_topic(Path(f"topics/{topic}.md"), topic, doc)

        assert "[`workflow-rules`](workflow-rules.md)" in rendered
        assert "[`connector.git.branch`](../operations/git/branch.md)" in rendered


def test_static_shell_operation_page_keeps_all_canonical_examples():
    from ordo.help_cli import build_operation_response

    payload = build_operation_response("shell.command")
    assert payload is not None

    rendered = render_operation(Path("operations/shell/command.md"), payload)

    assert "ordo-help operation shell.command --json" in rendered
    for example in payload["canonical_examples"]:
        assert f"### {example['name']}" in rendered
        assert example["yaml"] in rendered
