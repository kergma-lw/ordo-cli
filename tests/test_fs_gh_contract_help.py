import contextlib
import io
import json
from pathlib import Path

import pytest
import yaml

from ordo.help_cli import build_features_response, build_model_response, main
from ordo.model.help_snippets import describe_help_snippets
from ordo.runtime.help_snippet_runner import verify_help_snippet


def capture_describe(handle, as_json=False):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main(["describe", handle, *(["--json"] if as_json else [])]) == 0
    return json.loads(output.getvalue()) if as_json else output.getvalue()


def test_all_repository_input_describes_publish_literal_contract():
    gh = next(item for item in build_model_response()["connectors"] if item["namespace"] == "gh")
    operations = [op for op in gh["operations"] if "repository" in op["inputs"]]
    assert operations
    for handle in ["connector.gh", *[f"connector.gh.{op['name']}" for op in operations]]:
        text = capture_describe(handle)
        payload = capture_describe(handle, True)
        contract = json.dumps(payload)
        for phrase in ("[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", "strip ASCII spaces only", "not an authorization allowlist", "nameWithOwner", "content_refs", "before authentication", "may follow existing authentication bootstrap"):
            assert phrase in contract, handle
        for field in ("goal", "summary"):
            assert payload["human"][field] in text, handle
    assert all(op["inputs"]["repository"] == "string" for op in operations)
    # Composite content references keep their separate contract.
    assert "full-match" not in capture_describe("connector.gh.project.items.details")


def test_fs_describe_explains_reader_facing_scope_and_has_larger_examples():
    text = capture_describe("connector.fs.file")
    payload = capture_describe("connector.fs.file", True)
    for phrase in ("regular file", "UTF-8", "partial content", "atomic snapshot", "final symlink is rejected", "parent directory may be traversed"):
        assert phrase in text
    for phrase in ("O_NOFOLLOW", "O_NONBLOCK", "fstat", "ELOOP", "probe.fs_file.secure_open_unavailable", "probe.fs_file.stat_failed", "same-UID"):
        assert phrase not in text
    for phrase in ("O_NOFOLLOW", "O_NONBLOCK"):
        assert phrase not in json.dumps(payload)
    examples = describe_help_snippets()["connector.fs.file"]["canonical_examples"]
    assert {example["form"] for example in examples} == {"step_fragment", "workflow_fragment"}
    for example in examples:
        verification = example["verification"]
        result = verify_help_snippet(snippet=example["yaml"], world="default", insertion_mode=verification["insertion_mode"], target="connector.fs.file")
        assert result.status == "ok"
        assert "no real-file default" in result.workflow_text or example["form"] == "step_fragment"


@pytest.mark.parametrize(
    "family,leaf,reader_boundary",
    [
        ("connector.fs", "connector.fs.file", "parent symlinks and hardlinks are allowed"),
        ("connector.gh", "connector.gh.project.issue", "earlier effects are not rolled back"),
    ],
)
def test_family_examples_reuse_whole_source_and_existing_leaf_verification(family, leaf, reader_boundary):
    registry = describe_help_snippets()
    payload = capture_describe(family, True)
    text = capture_describe(family)
    example, = [item for item in payload["canonical_examples"]
                if item["verification"]["target"] == leaf]
    original = next(item for item in registry[leaf]["canonical_examples"] if item["form"] == "workflow_fragment")
    assert example["source_excerpt"] == original["source_excerpt"]
    assert example["verification"] == original["verification"]
    assert example["yaml"] == original["yaml"]
    source = Path(__file__).resolve().parents[1] / example["source_excerpt"]["path"]
    assert example["yaml"] == source.read_text().rstrip("\n")
    assert example["name"] in text and example["summary"] in text
    assert reader_boundary in text
    assert "checks its authored shape" not in text
    verification = example["verification"]
    assert verification["target"] == leaf
    result = verify_help_snippet(snippet=example["yaml"], world=verification["world"], insertion_mode=verification["insertion_mode"], target=verification["target"])
    assert result.status == "ok"
    assert result.workflow_text.rstrip("\n") == example["yaml"]


@pytest.mark.parametrize("mode", ["step_fragment", "workflow_fragment"])
def test_fs_snippet_verifier_rejects_broken_shape_and_unknown_targets(mode):
    example = next(item for item in describe_help_snippets()["connector.fs.file"]["canonical_examples"] if item["form"] == mode)
    broken = example["yaml"].replace("uses: fs.file", "unexpected_step_key: fs.file")
    result = verify_help_snippet(snippet=broken, world="default", insertion_mode=mode, target="connector.fs.file")
    assert result.status != "ok"
    with pytest.raises(ValueError, match="Unsupported"):
        verify_help_snippet(snippet=example["yaml"], world="default", insertion_mode=mode, target="connector.fs.future")


def test_features_match_golden_and_publish_contract_boundaries():
    payload = build_features_response()
    golden = Path(__file__).parent / "golden" / "ordo_help_features.json"
    assert {key: value for key, value in payload.items() if key != "human"} == json.loads(golden.read_text())
    assert payload["human"]
    connector = next(item for item in payload["clusters"] if item["name"] == "connectors")
    text = " ".join(connector["appropriate_when"])
    assert "safely read that file" in text
    assert "literal ASCII OWNER/REPO" in text


def test_gh_repository_excerpt_coordinates_and_site_authoring_contract():
    from tools.build_help_site_docs import render_operation
    from ordo.help_cli import build_operation_response

    registry = describe_help_snippets()
    for handle in ("connector.gh.repo", "connector.gh.repo.sync", "connector.gh.repo.actions.permissions", "connector.gh.repo.actions.permissions.set"):
        for example in registry[handle]["canonical_examples"]:
            shape = yaml.safe_load(example["yaml"])
            if example["form"] == "step_fragment":
                assert isinstance(shape, list)
                assert all(step.get("uses") == handle.removeprefix("connector.") for step in shape)
            elif handle == "connector.gh.repo.actions.permissions":
                assert shape["blocks"][0]["steps"][-1]["with"] == {"enabled": "step.before.outputs.enabled"}
    for reference in ("fs.file", "gh.repo.actions.permissions"):
        describe = capture_describe(f"connector.{reference}", True)
        page = render_operation(Path("operations/example.md"), build_operation_response(reference), describe)
        assert "## Full JSON reference" not in page
        assert describe["human"]["summary"] in page


def test_public_help_keeps_contract_details_without_implementation_mechanics():
    cases = {
        "connector.gh.pr.create": (
            ("explicit draft value", "matching open pull request", "must be inspected by a separate workflow decision"),
            ("ctx.call", "POST", "HTTP 201", "diagnostic code", "analysis modes"),
        ),
        "connector.git.sync.push": (
            ("configured remote name", "upstream remote", "not a URL, path, or command option"),
            ("branch.<current>.remote", "action.git.", "remote inventory", "protocol sandbox"),
        ),
        "workflow.step.state_set": (
            ("future workflow run", "one resolved target entry"),
            ("state_deferral", "validation.workflow", "planned_probe_result", "normalized paths"),
        ),
        "playbook.workflows": (
            ("stable launch catalog", "caller interface", "complete declaration"),
            ("input_source_missing", "caller slot", "source coverage", "launch sources"),
        ),
    }
    for handle, (required, forbidden) in cases.items():
        text = capture_describe(handle)
        for phrase in required:
            assert phrase in text, handle
        for phrase in forbidden:
            assert phrase not in text, (handle, phrase)
