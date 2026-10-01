"""Connector-authoring help stays reader-facing without a copyable implementation fragment."""

import contextlib
import io
import json

from ordo.help_cli import main
from ordo.model.help_snippets import describe_help_snippets


def capture_describe(as_json: bool = False):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main(["describe", "connector.authoring", *(["--json"] if as_json else [])]) == 0
    return json.loads(output.getvalue()) if as_json else output.getvalue()


def test_connector_authoring_has_reader_first_guidance_without_an_implementation_snippet():
    payload = capture_describe(True)
    text = capture_describe()

    assert payload["snippet_coverage"] == "none"
    assert payload["canonical_examples"] == []
    assert "connector.authoring" not in describe_help_snippets()
    assert "clearly bounded operation" in text
    assert "No checked example is published" in text
    assert "no public successor" in text
    assert "workflow-author migration path" in text
    for term in ("SDK", "handler", "ctx.call", "bootstrap", "fixture", "python_fragment"):
        assert term not in text
