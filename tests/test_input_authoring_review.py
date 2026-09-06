import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from ordo.cli import main
from ordo.model.runtime import Mode, RuntimeResult, RuntimeStatus
from ordo.model.workflow import Workflow
from ordo.playbook import PlaybookError, activate_playbook
from ordo.runtime.reviewing import review_workflow
from tests.support import STANDARD_CONNECTOR_PROVIDER


DESCRIPTION_CODE = "review.workflow.input_description_missing"
SLOT_CODE = "review.playbook.input_caller_slot_missing"


class InputAuthoringReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.playbook = self.root / "ordo.yaml"

    def write_playbook(self, inputs, *, bindings=None, profile_inputs=None, **workflow_fields):
        workflow = {
            "version": 0,
            "workflow": "sample",
            "inputs": inputs,
            "blocks": [{"guards": []}, {"steps": []}],
            **workflow_fields,
        }
        workflow_path = self.root / "sample.yml"
        workflow_path.write_text(yaml.safe_dump(workflow), encoding="utf-8")
        payload = {
            "version": 1,
            "workflows": {"sample": {"file": str(workflow_path), "with": bindings or {}}},
        }
        if profile_inputs is not None:
            profile_path = self.root / "profile.yml"
            profile_path.write_text(yaml.safe_dump({"name": "selected", "inputs": profile_inputs}), encoding="utf-8")
            payload["profiles"] = {"selected": {"file": str(profile_path)}}
            payload["defaults"] = {"profile": "selected"}
        self.playbook.write_text(yaml.safe_dump(payload), encoding="utf-8")

    def invoke(self, mode="review", *, overrides=(), as_json=True):
        argv = ["ordo-playbook", "--file", str(self.playbook)]
        for override in overrides:
            argv.extend(["--input", override])
        if as_json:
            argv.append("--json")
        argv.extend([mode] if mode == "next" else [mode, "sample"])
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("sys.argv", argv), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main()
        return status, json.loads(stdout.getvalue() or stderr.getvalue())

    def test_description_findings_survive_unavailable_runtime_review(self):
        declarations = {
            "missing": {},
            "null": {"description": None},
            "empty": {"description": ""},
            "blank": {"description": " \t\n"},
            "documented": {"description": "Useful context"},
        }
        workflow = Workflow(version=0, workflow="sample", declared_inputs=declarations, blocks=())
        for status in (RuntimeStatus.OK, RuntimeStatus.VALIDATION_ERROR, RuntimeStatus.RESOLUTION_ERROR):
            with self.subTest(status=status), patch(
                "ordo.runtime.reviewing.check_workflow",
                return_value=RuntimeResult(mode=Mode.CHECK, status=status),
            ):
                result = review_workflow(workflow, connector_provider=STANDARD_CONNECTOR_PROVIDER)
                findings = [item for item in result.outputs["findings"] if item["code"] == DESCRIPTION_CODE]
                self.assertEqual({item["evidence"]["input"] for item in findings}, {"missing", "null", "empty", "blank"})
                self.assertTrue(all(item["level"] == "warning" for item in findings))
                self.assertEqual(result.status, status)
                if status is not RuntimeStatus.OK:
                    self.assertEqual(result.outputs["review_status"], "unavailable")

    def test_non_user_sources_and_both_caller_slots_suppress_exposure_warning(self):
        inputs = {
            "required": {"description": "Required caller value"},
            "optional": {"required": False, "description": "Optional caller value"},
            "default_null": {"default": None},
            "default_false": {"default": False},
            "shorthand": 0,
            "profile": {},
            "static": {},
            "required_slot": {},
            "optional_slot": {"required": False},
        }
        self.write_playbook(
            inputs,
            bindings={"static": False, "required_slot": None, "optional_slot?": None},
            profile_inputs={"profile": None},
        )
        activated = activate_playbook(
            workflow_name="sample", playbook_path=self.playbook,
            input_overrides={"required": "supplied", "required_slot": "supplied"},
        )
        findings = [item for item in activated.review_findings if item["code"] == SLOT_CODE]
        self.assertEqual({item["evidence"]["input"] for item in findings}, {"required", "optional"})
        self.assertEqual({item["evidence"]["suggested_rewrite"] for item in findings}, {"required:", "optional?:"})
        self.assertNotIn("optional", activated.workflow.inputs)

    def test_activation_errors_keep_findings_and_existing_diagnostics(self):
        self.write_playbook({"required": {}, "optional": {"required": False}})
        with self.assertRaises(PlaybookError) as caught:
            activate_playbook(workflow_name="sample", playbook_path=self.playbook)
        self.assertEqual({item.code for item in caught.exception.diagnostics}, {"playbook.workflow.input_missing"})
        for as_json in (True, False):
            with self.subTest(as_json=as_json):
                status, payload = self.invoke(as_json=as_json)
                self.assertEqual(status, 1)
                self.assertEqual(payload["mode"], "activation")
                self.assertEqual(payload["status"], "resolution_error")
                review = payload["outputs"] if as_json else payload
                self.assertEqual(review["review_status"], "unavailable")
                findings = review["findings"] if as_json else review["top_findings"]
                self.assertEqual({item["code"] for item in findings}, {DESCRIPTION_CODE, SLOT_CODE})

    def test_only_selected_profile_supplies_review_input_source(self):
        self.write_playbook({"value": {}}, profile_inputs={"value": "profile value"})
        other_profile = self.root / "other.yml"
        other_profile.write_text("name: other\ninputs: {}\n", encoding="utf-8")
        payload = yaml.safe_load(self.playbook.read_text(encoding="utf-8"))
        payload["profiles"]["other"] = {"file": str(other_profile)}
        self.playbook.write_text(yaml.safe_dump(payload), encoding="utf-8")
        for profile_name, expected_warning in ((None, False), ("other", True)):
            with self.subTest(profile_name=profile_name):
                activated = activate_playbook(
                    workflow_name="sample", playbook_path=self.playbook,
                    profile_name=profile_name, input_overrides={"value": "user value"},
                )
                self.assertEqual(
                    any(item["code"] == SLOT_CODE for item in activated.review_findings),
                    expected_warning,
                )

    def test_input_file_override_does_not_hide_caller_slot_warning(self):
        self.write_playbook({"value": {}})
        input_path = self.root / "value.txt"
        input_path.write_text("user value", encoding="utf-8")
        stdout = io.StringIO()
        with patch("sys.argv", [
            "ordo-playbook", "--file", str(self.playbook),
            "--input-file", f"value={input_path}", "--json", "review", "sample",
        ]), contextlib.redirect_stdout(stdout):
            status = main()
        self.assertEqual(status, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn(SLOT_CODE, {item["code"] for item in payload["outputs"]["findings"]})

    def test_cli_override_does_not_hide_warning_or_duplicate_description(self):
        self.write_playbook({"value": {}})
        status, payload = self.invoke(overrides=("value=provided",))
        self.assertEqual(status, 0)
        self.assertEqual(payload["outputs"]["review_status"], "needs_attention")
        findings = payload["outputs"]["findings"]
        for code in (DESCRIPTION_CODE, SLOT_CODE):
            self.assertEqual(len([item for item in findings if item["code"] == code]), 1)
        self.assertEqual(payload["outputs"]["finding_count"], len(findings))

    def test_optional_missing_caller_slot_is_advisory_in_successful_cli_review(self):
        self.write_playbook({"value": {"required": False, "description": "Optional value"}})
        status, payload = self.invoke(as_json=False)
        self.assertEqual(status, 0)
        finding = next(item for item in payload["top_findings"] if item["code"] == SLOT_CODE)
        self.assertEqual(finding["suggested_rewrite"], "value?:")

    def test_required_caller_slot_still_requires_explicit_input_with_default(self):
        self.write_playbook({"value": {"default": False}}, bindings={"value": None})
        with self.assertRaises(PlaybookError) as caught:
            activate_playbook(workflow_name="sample", playbook_path=self.playbook)
        self.assertEqual(caught.exception.diagnostics[0].details["missing_kind"], "caller_required_slot")
        self.assertNotIn(SLOT_CODE, {item["code"] for item in caught.exception.review_findings})

    def test_optional_caller_slot_does_not_relax_required_workflow_input(self):
        self.write_playbook({"value": {}}, bindings={"value?": None})
        with self.assertRaises(PlaybookError) as caught:
            activate_playbook(workflow_name="sample", playbook_path=self.playbook)
        self.assertEqual(caught.exception.diagnostics[0].details["missing_kind"], "workflow_required_input")
        self.assertNotIn(SLOT_CODE, {item["code"] for item in caught.exception.review_findings})

    def test_root_description_findings_survive_document_validation_failure(self):
        self.write_playbook({"value": {}}, unexpected_field=True)
        status, payload = self.invoke()
        self.assertEqual(status, 1)
        self.assertIn(DESCRIPTION_CODE, {item["code"] for item in payload["outputs"]["findings"]})
        self.assertEqual(payload["outputs"]["review_status"], "unavailable")

    def test_other_modes_do_not_emit_review_findings_on_activation_failure(self):
        self.write_playbook({"value": {}})
        for mode in ("check", "plan", "run", "explain"):
            with self.subTest(mode=mode):
                status, payload = self.invoke(mode)
                self.assertEqual(status, 1)
                self.assertNotIn("outputs", payload)
                self.assertEqual({item["code"] for item in payload["diagnostics"]}, {"playbook.workflow.input_missing"})

    def test_other_modes_do_not_publish_advisories_after_successful_activation(self):
        self.write_playbook({"value": {"required": False}})
        for mode in ("check", "plan", "run", "explain", "next"):
            with self.subTest(mode=mode):
                _, payload = self.invoke(mode)
                serialized = json.dumps(payload)
                self.assertNotIn(DESCRIPTION_CODE, serialized)
                self.assertNotIn(SLOT_CODE, serialized)
