"""runtime.uuid.generate action."""

from __future__ import annotations

from uuid import uuid4

from ordo.model.human import declare_human
from ordo.plugin_sdk import action, ok


HUMAN = declare_human({
    "title": "Generate execution-local UUID",
    "goal": "You need one opaque identifier for later steps in the current workflow run.",
    "summary": "Generate one lowercase UUID version 4 and return it for explicit use by later steps.",
    "sections": [
        {"heading": "Use when", "items": [
            "A later step needs a fresh opaque request, correlation, or idempotency identifier created during this run.",
        ]},
        {"heading": "What to provide", "items": [
            "No inputs. Register this action when a later step must read its `uuid` output.",
        ]},
        {"heading": "Result and boundary", "items": [
            "Returns `uuid` as one canonical lowercase UUID version 4 string. Each execution generates a new value.",
            "The result is execution-local until the workflow passes it onward or stores it. UUID generation makes collisions practically negligible, but it does not reserve or atomically prove uniqueness in a remote system.",
        ]},
        {"heading": "Do not use for", "items": [
            "A secret, credential, or authentication token; those need a contract that controls disclosure and retention.",
            "A value that must survive a later workflow run unless the workflow explicitly stores it in state.",
        ]},
        {"heading": "Related references", "body": "Use these related references when you need the generated value to outlive this run or to inspect another runtime operation.", "references": [
            {"handle": "connector.runtime", "summary": "Parent connector family for current-run operations"},
            {"handle": "workflow.step.state_set", "summary": "Store a generated value explicitly when a later run must reuse it"},
            {"handle": "workflow.step.outputs", "summary": "Read the registered UUID output in a later step"},
        ]},
        {"heading": "Examples", "items": [
            "Register runtime.uuid.generate, then pass step.request_id.outputs.uuid to the action that owns the remote resource.",
        ]},
        {"heading": "Inspect next", "items": ["workflow.step.outputs", "workflow.step.state_set", "connector.runtime"]},
    ],
})


def info():
    return action(
        name="uuid.generate",
        human=HUMAN,
        summary="Generate one execution-local UUID version 4 for later workflow steps",
        effects=("generate a fresh execution-local UUID",),
        outputs={"uuid": "string"},
        handler=run,
    )


def run(_ctx):
    value = str(uuid4())
    return ok(summary="UUID generated", outputs={"uuid": value})
