import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from ordo.cli import main
from ordo.playbook import PlaybookError, activate_playbook, inspect_playbook_workflow


class WorkflowShowInputsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.playbook = self.root / "ordo.yaml"
        self.declarations = {
            "missing": {"description": "Caller value", "hint": "Provide a value"},
            "optional_missing": {"required": False},
            "null_default": {"default": None},
            "shorthand": False,
            "bound": {},
            "profile_value": {},
            "required_slot": {"required": False, "default": "P1", "description": "Caller slot value", "hint": "Provide a priority", "allowed_values": ["P0", "P1", "P2", "P3"]},
            "optional_slot": {"required": False},
            "required_optional_slot": {"required": True},
            "all_sources": {"default": "fallback"},
        }
        self.bindings = {
            "bound": False, "required_slot": None, "optional_slot?": None,
            "required_optional_slot?": None, "all_sources": "bound value",
        }
        self.workflow = self.root / "sample.yml"
        self.workflow.write_text(yaml.safe_dump({
            "version": 0, "workflow": "sample", "inputs": self.declarations,
            "blocks": [{"guards": []}, {"steps": []}],
        }), encoding="utf-8")
        for name, inputs in (("selected", {"profile_value": None, "all_sources": "secret-profile-value"}), ("other", {})):
            (self.root / f"{name}.yml").write_text(yaml.safe_dump({
                "name": name, "inputs": inputs,
            }), encoding="utf-8")
        self.payload = {
            "version": 1, "defaults": {"profile": "selected"},
            "profiles": {name: {"file": f"./{name}.yml"} for name in ("selected", "other")},
            "workflows": {"sample": {"file": "./sample.yml", "with": self.bindings}},
        }
        self.write_playbook()

    def write_playbook(self):
        self.playbook.write_text(yaml.safe_dump(self.payload), encoding="utf-8")

    def show(self, *options, as_json=False):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["ordo-playbook", "--file", str(self.playbook), *options, "workflows", "show", "sample"]
        if as_json:
            argv.append("--json")
        with patch("sys.argv", argv), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), patch(
            "ordo.cli.activate_playbook", side_effect=AssertionError("Show must not activate a workflow")
        ):
            status = main()
        return status, json.loads(stdout.getvalue() or stderr.getvalue())

    def test_plain_filters_caller_slots_and_json_keeps_complete_contract(self):
        entry = inspect_playbook_workflow("sample", playbook_path=self.playbook)
        contracts = json.loads(json.dumps({item.name: item.contract for item in entry.inputs}))
        with patch("ordo.cli.inspect_playbook_workflow", return_value=entry):
            plain_status, plain = self.show()
            json_status, payload = self.show(as_json=True)
        self.assertEqual((plain_status, json_status), (0, 0))
        self.assertEqual(plain, {
            **{key: value for key, value in payload.items() if key != "launch_profile"},
            "warnings": plain["warnings"],
            "inputs": {name: {
                **{key: value for key, value in payload["inputs"][name].items() if key not in {"coverage", "sources", "caller_slot"}},
                "required": payload["inputs"][name]["caller_slot"] == "required",
            } for name in (
                "required_slot", "optional_slot", "required_optional_slot",
            )},
        })
        self.assertEqual(set(payload["inputs"]), set(self.declarations))
        self.assertEqual(payload["inputs"], contracts)
        self.assertEqual({item.name: item.contract for item in entry.inputs}, contracts)
        for item in plain["inputs"].values():
            self.assertNotIn("coverage", item)
            self.assertNotIn("sources", item)
            self.assertNotIn("caller_slot", item)
        self.assertEqual(plain["inputs"]["required_slot"], {
            "required": True, "default": "P1", "description": "Caller slot value", "hint": "Provide a priority", "allowed_values": ["P0", "P1", "P2", "P3"],
        })
        self.assertEqual(payload["inputs"]["required_slot"]["allowed_values"], ["P0", "P1", "P2", "P3"])
        self.assertEqual(plain["inputs"]["required_optional_slot"], {"required": False})
        self.assertEqual(plain["inputs"]["optional_slot"], {"required": False})
        for removed in ("declared_inputs", "caller_inputs", "optional_caller_inputs"):
            self.assertNotIn(removed, payload)
        self.assertEqual(payload["launch_profile"], {"name": "selected", "source": "default"})
        inputs = payload["inputs"]
        self.assertEqual(inputs["missing"], {
            "description": "Caller value", "hint": "Provide a value", "required": True,
            "caller_slot": "none", "sources": [], "coverage": "missing",
        })
        self.assertNotIn("default", inputs["optional_missing"])
        self.assertFalse(inputs["optional_missing"]["required"])
        self.assertIsNone(inputs["null_default"]["default"])
        self.assertEqual(inputs["null_default"]["sources"], ["workflow_default"])
        self.assertFalse(inputs["null_default"]["required"])
        self.assertIs(inputs["shorthand"]["default"], False)
        self.assertFalse(inputs["shorthand"]["required"])
        self.assertIs(inputs["bound"]["binding"], False)
        self.assertEqual(inputs["bound"]["sources"], ["entry_binding"])
        self.assertEqual(inputs["profile_value"], {
            "required": True, "caller_slot": "none", "sources": ["launch_profile"], "coverage": "provided",
        })
        self.assertEqual(inputs["required_slot"]["caller_slot"], "required")
        self.assertFalse(inputs["required_slot"]["required"])
        self.assertEqual(inputs["required_slot"]["coverage"], "provided")
        self.assertEqual(inputs["optional_slot"]["caller_slot"], "optional")
        self.assertEqual(inputs["optional_slot"]["coverage"], "caller_slot")
        self.assertTrue(inputs["required_optional_slot"]["required"])
        self.assertEqual(inputs["required_optional_slot"]["caller_slot"], "optional")
        self.assertEqual(inputs["all_sources"]["sources"], ["workflow_default", "launch_profile", "entry_binding"])
        self.assertFalse(inputs["all_sources"]["required"])
        self.assertNotIn("secret-profile-value", json.dumps(payload))
        self.assertNotIn("secret-profile-value", json.dumps(plain))
        self.assertNotIn("binding", inputs["profile_value"])
        self.assertNotIn("warnings", payload)
        self.assertEqual([warning["input"] for warning in plain["warnings"]], ["missing"])
        warning = plain["warnings"][0]
        self.assertEqual(warning["code"], "discovery.workflow.input_source_missing")
        for detail in ("no workflow default", "not supplied by launch profile 'selected'",
                       "no concrete playbook binding", "no caller slot declared"):
            self.assertIn(detail, warning["message"])
        self.assertIn("Declare a caller slot", warning["hint"])

    def test_profile_selection_matches_activation_and_review_coverage(self):
        for profile_name, source in ((None, "default"), ("selected", "explicit_cli"), ("other", "explicit_cli")):
            for as_json in (False, True):
                with self.subTest(profile=profile_name, as_json=as_json):
                    options = [] if profile_name is None else ["--profile", profile_name]
                    status, payload = self.show(*options, "--input", "missing=override", as_json=as_json)
                    self.assertEqual(status, 0)
                    activated = activate_playbook(
                        workflow_name="sample", playbook_path=self.playbook, profile_name=profile_name,
                        input_overrides={"missing": "override", "required_slot": "P1", "required_optional_slot": 1, "profile_value": 1},
                    )
                    if as_json:
                        self.assertEqual(payload["launch_profile"], {
                            "name": activated.workflow.launch_profile_name, "source": source,
                        })
                    else:
                        self.assertNotIn("launch_profile", payload)
                    findings = {item["evidence"]["input"] for item in activated.review_findings if item["code"] == "review.playbook.input_caller_slot_missing"}
                    if as_json:
                        missing = {name for name, item in payload["inputs"].items() if item["coverage"] == "missing"}
                        self.assertEqual(missing, findings)
                        self.assertIn("missing", missing)
                        self.assertEqual("profile_value" in missing, profile_name == "other")
                    else:
                        self.assertEqual(
                            {warning["input"] for warning in payload["warnings"]},
                            {"missing", "profile_value"} if profile_name == "other" else {"missing"},
                        )
                        for item in payload["inputs"].values():
                            self.assertNotIn("coverage", item)
                            self.assertNotIn("sources", item)
                            self.assertNotIn("caller_slot", item)
                        self.assertEqual(set(payload["inputs"]), {
                            "required_slot", "optional_slot", "required_optional_slot",
                        })
                    self.assertNotIn("secret-profile-value", json.dumps(payload))

    def test_no_default_does_not_select_an_available_profile(self):
        del self.payload["defaults"]
        for profiles in (self.payload["profiles"], {}):
            self.payload["profiles"] = profiles
            self.write_playbook()
            for as_json in (False, True):
                status, payload = self.show(as_json=as_json)
                self.assertEqual(status, 0)
                if as_json:
                    self.assertEqual(payload["launch_profile"], {"name": None, "source": None})
                    self.assertEqual(payload["inputs"]["profile_value"]["coverage"], "missing")
                else:
                    self.assertNotIn("launch_profile", payload)
                    self.assertNotIn("profile_value", payload["inputs"])
                    self.assertEqual({warning["input"] for warning in payload["warnings"]}, {"missing", "profile_value"})
                    for warning in payload["warnings"]:
                        self.assertIn("no launch profile selected", warning["message"])

    def test_invalid_selected_profiles_use_activation_diagnostics(self):
        for profile_name in ("unknown", "selected"):
            if profile_name == "selected":
                (self.root / "selected.yml").unlink()
            for as_json in (False, True):
                status, payload = self.show("--profile", profile_name, as_json=as_json)
                self.assertEqual(status, 1)
                with self.assertRaises(PlaybookError) as caught:
                    activate_playbook(workflow_name="sample", playbook_path=self.playbook, profile_name=profile_name)
                if as_json:
                    self.assertEqual(payload["diagnostics"][0]["code"], caught.exception.diagnostics[0].code)
                else:
                    self.assertEqual(payload["message"], caught.exception.diagnostics[0].message)

    def test_next_contract_inspection_does_not_load_profiles(self):
        (self.root / "selected.yml").unlink()
        with patch("ordo.playbook.load_profile_file", side_effect=AssertionError("Candidate inspection must defer profile loading")):
            entry = inspect_playbook_workflow("sample", playbook_path=self.playbook, include_launch_sources=False)
        self.assertEqual({item.name for item in entry.inputs}, set(self.declarations))
        self.assertIsNotNone(entry.workflow_contract)

    def test_unselected_missing_profile_does_not_block_show(self):
        (self.root / "other.yml").unlink()
        status, payload = self.show()
        self.assertEqual(status, 0)
        self.assertNotIn("launch_profile", payload)

    def test_empty_workflow_contract_has_empty_inputs_mapping(self):
        self.payload["workflows"]["sample"]["with"] = {}
        self.write_playbook()
        self.workflow.write_text("version: 0\nworkflow: sample\nblocks:\n  - guards: []\n  - steps: []\n", encoding="utf-8")
        for as_json in (False, True):
            status, payload = self.show(as_json=as_json)
            self.assertEqual(status, 0)
            self.assertEqual(payload["inputs"], {})
            self.assertNotIn("warnings", payload)

    def test_no_caller_slots_keeps_empty_plain_inputs_mapping(self):
        self.payload["workflows"]["sample"]["with"] = {}
        self.write_playbook()
        plain_status, plain = self.show()
        json_status, payload = self.show(as_json=True)
        self.assertEqual((plain_status, json_status), (0, 0))
        self.assertEqual(plain, {
            **{key: value for key, value in payload.items() if key != "launch_profile"}, "inputs": {},
            "warnings": plain["warnings"],
        })
        self.assertEqual({warning["input"] for warning in plain["warnings"]}, {"missing", "bound", "required_optional_slot"})
        self.assertEqual(set(payload["inputs"]), set(self.declarations))
        self.assertTrue(all(item["caller_slot"] == "none" for item in payload["inputs"].values()))

    def test_plain_omits_launch_profile_source_and_coverage_on_caller_slot(self):
        self.payload["workflows"]["sample"]["with"]["profile_value"] = None
        self.write_playbook()
        plain_status, plain = self.show()
        json_status, payload = self.show(as_json=True)
        self.assertEqual((plain_status, json_status), (0, 0))
        self.assertNotIn("launch_profile", plain)
        self.assertEqual(payload["launch_profile"], {"name": "selected", "source": "default"})
        self.assertEqual(plain["inputs"]["profile_value"], {"required": True})
        self.assertEqual(payload["inputs"]["profile_value"], {
            "required": True, "caller_slot": "required", "sources": ["launch_profile"], "coverage": "provided",
        })

    def test_no_warning_when_required_inputs_have_sources_or_slots(self):
        self.payload["workflows"]["sample"]["with"]["missing"] = None
        self.write_playbook()
        status, payload = self.show()
        self.assertEqual(status, 0)
        self.assertNotIn("warnings", payload)

    def test_runtime_profile_switch_does_not_supply_launch_coverage(self):
        self.payload["defaults"] = {"profile": "other"}
        self.write_playbook()
        workflow = yaml.safe_load(self.workflow.read_text(encoding="utf-8"))
        workflow["blocks"][1]["steps"] = [{"name": "Switch later", "profile_switch": "selected"}]
        self.workflow.write_text(yaml.safe_dump(workflow), encoding="utf-8")
        status, payload = self.show(as_json=True)
        self.assertEqual(status, 0)
        self.assertEqual(payload["inputs"]["profile_value"]["coverage"], "missing")

        self.assertEqual(payload["launch_profile"], {"name": "other", "source": "default"})

    def test_input_file_override_does_not_supply_authored_coverage(self):
        value_file = self.root / "value.txt"
        value_file.write_text("caller value", encoding="utf-8")
        status, payload = self.show("--input-file", f"missing={value_file}", as_json=True)
        self.assertEqual(status, 0)
        self.assertEqual(payload["inputs"]["missing"]["coverage"], "missing")

    def test_discovery_does_not_change_any_runtime_mode_result(self):
        for mode in ("check", "review", "plan", "run", "explain", "next"):
            with self.subTest(mode=mode):
                outputs = []
                for inspect_first in (False, True):
                    if inspect_first:
                        self.assertEqual(self.show()[0], 0)
                    stdout, stderr = io.StringIO(), io.StringIO()
                    argv = ["ordo-playbook", "--file", str(self.playbook), "--json", mode]
                    if mode != "next":
                        argv.append("sample")
                    # Required inputs are missing; run cannot execute any steps.
                    with patch("sys.argv", argv), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        status = main()
                    outputs.append((status, json.loads(stdout.getvalue() or stderr.getvalue())))
                self.assertEqual(outputs[0], outputs[1])
                if mode == "review":
                    findings = outputs[0][1]["outputs"]["findings"]
                    self.assertTrue(any(item["code"] == "review.playbook.input_caller_slot_missing" for item in findings))
                else:
                    self.assertNotIn("review.playbook.input_caller_slot_missing", json.dumps(outputs[0]))
