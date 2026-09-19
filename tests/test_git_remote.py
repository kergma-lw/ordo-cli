"""Native remote probe contracts through a real context and synthetic subprocesses."""

import subprocess
from unittest.mock import patch

import pytest

from connectors.git.probes import remote
from ordo.model.workflow import Workflow
from ordo.plugin_sdk import OperationContext, bootstrap_ok
from ordo.runtime.resolution import ResolvedOperation


def response(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def invoke(responses=(), name="origin"):
    ctx = OperationContext(
        resolved=ResolvedOperation(
            reference="git.remote", connector_namespace="git", source="public",
            operation=remote.info(), resolved_inputs={"remote": name},
        ),
        workflow=Workflow(version=0, workflow="remote-probe-contract"),
        bootstrap=bootstrap_ok(context={"repository_root": "/tmp/repository"}),
        caller=lambda *_: pytest.fail("Unexpected operation dependency"),
    )
    with patch("subprocess.run", side_effect=list(responses)) as command:
        result = remote.run(ctx)
    assert command.call_count == len(responses)
    return result, [item.args[0] for item in command.call_args_list]


def assert_failure(result, diagnostic):
    assert result.status == "probe_failed"
    assert result.outputs == {}
    assert result.diagnostics[0].code == f"probe.git_remote.{diagnostic}"
    assert result.diagnostics[0].level == "error"


def test_schema():
    operation = remote.info()
    assert operation.kind == "probe"
    assert operation.inputs == {"remote": "string"}
    assert operation.outputs == {
        "name": "string", "exists": "boolean", "fetch_urls": ["string"],
        "push_urls": ["string"], "mirror": "boolean | null",
    }
    assert operation.failure_modes == ("probe_failed",)


@pytest.mark.parametrize("name", [None, True, 42, "", " ", " origin", "origin ", "a b", "a\tb", "a\nb", "a\u00a0b", "-origin", "--all", "a\0b"])
def test_invalid_names_do_not_execute(name):
    result, _ = invoke(name=name)
    assert_failure(result, "invalid_input")


@pytest.mark.parametrize("inventory", ["", "upstream\n", "origins\n", "team/origin\n"])
def test_missing_remote_is_normal_and_uses_exact_membership(inventory):
    result, commands = invoke([response(inventory)])
    assert result.status == "ok"
    assert result.outputs == {"name": "origin", "exists": False, "fetch_urls": [], "push_urls": [], "mirror": None}
    assert commands == [["git", "remote"]]


@pytest.mark.parametrize("name", ["origin", "team/origin", "../repo", "/tmp/repo", "https://user:credential@example.test/repo"])
def test_configured_names_are_authoritative_and_commands_are_local(name):
    result, commands = invoke([
        response(name), response("/local/fetch\n"), response("host:push\n"), response("false\n"),
    ], name=name)
    assert result.status == "ok"
    assert result.outputs == {"name": name, "exists": True, "fetch_urls": ["/local/fetch"], "push_urls": ["host:push"], "mirror": False}
    assert commands == [
        ["git", "remote"],
        ["git", "remote", "get-url", "--all", name],
        ["git", "remote", "get-url", "--push", "--all", name],
        ["git", "config", "--bool", "--get", f"remote.{name}.mirror"],
    ]


def test_effective_url_strings_and_standard_evidence_are_preserved():
    fetch = ["https://user:p%40ss@example.test/repo?token=actual-secret", " /local path/repo ", "relative\tpath", "file:///repo\r", "path\u2028part"]
    push = ["ssh://user:password@example.test/repo", "alias:repo", "../push path", "alias:repo"]
    fetch_stdout = "\n".join(fetch) + "\n"
    push_stdout = "\n".join(push)
    result, _ = invoke([response("origin\n"), response(fetch_stdout), response(push_stdout), response("true\n")])
    assert result.status == "ok"
    assert result.outputs["fetch_urls"] == fetch
    assert result.outputs["push_urls"] == push
    assert result.outputs["mirror"] is True
    assert result.raw["fetch_urls"]["stdout"] == fetch_stdout
    assert result.raw["push_urls"]["stdout"] == push_stdout


@pytest.mark.parametrize("mirror, expected", [(response("true"), True), (response("false\n"), False), (response(returncode=1), False)])
def test_mirror_boolean_and_absent_default(mirror, expected):
    result, _ = invoke([response("origin\n"), response("same\n"), response("same\n"), mirror])
    assert result.status == "ok"
    assert result.outputs["mirror"] is expected
    assert result.outputs["fetch_urls"] == result.outputs["push_urls"] == ["same"]


@pytest.mark.parametrize("inventory", ["\n", "origin\n\n", "origin\norigin\n", "origin\n other\n", "origin\n--all\n", "origin\r\n"])
def test_malformed_inventory_is_failure(inventory):
    result, _ = invoke([response(inventory)])
    assert_failure(result, "invalid_inventory")


@pytest.mark.parametrize("stage, diagnostic", [(0, "inventory_failed"), (1, "fetch_urls_failed"), (2, "push_urls_failed"), (3, "mirror_failed")])
@pytest.mark.parametrize("error", [response(returncode=128, stderr="synthetic Git error"), OSError("synthetic OS error")])
def test_command_failures_are_not_remote_absence(stage, diagnostic, error):
    responses = [response("origin\n"), response("fetch\n"), response("push\n")][:stage]
    result, _ = invoke([*responses, error])
    assert_failure(result, diagnostic)


@pytest.mark.parametrize("stage, diagnostic", [(0, "inventory_failed"), (1, "fetch_urls_failed"), (2, "push_urls_failed")])
def test_exit_one_only_means_absent_for_mirror_config(stage, diagnostic):
    responses = [response("origin\n"), response("fetch\n")][:stage]
    result, _ = invoke([*responses, response(returncode=1)])
    assert_failure(result, diagnostic)


@pytest.mark.parametrize("stage", [1, 2])
@pytest.mark.parametrize("stdout", ["", "\n", "url\n\n"])
def test_empty_url_records_fail(stage, stdout):
    result, _ = invoke([*[response("origin\n"), response("fetch\n")][:stage], response(stdout)])
    assert_failure(result, "invalid_fetch_urls" if stage == 1 else "invalid_push_urls")


@pytest.mark.parametrize("mirror, diagnostic", [
    (response(returncode=128, stderr="fatal: bad boolean config value"), "mirror_failed"),
    (response(returncode=2), "mirror_failed"),
    (response("yes\n"), "invalid_mirror"),
    (response(" true\n"), "invalid_mirror"),
    (response("true\nfalse\n"), "invalid_mirror"),
    (response(""), "invalid_mirror"),
])
def test_invalid_mirror_configuration_fails(mirror, diagnostic):
    result, _ = invoke([response("origin\n"), response("fetch\n"), response("push\n"), mirror])
    assert_failure(result, diagnostic)
