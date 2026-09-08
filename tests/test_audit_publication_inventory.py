import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / ".ordo/scripts/audit-publication-inventory.py"
spec = importlib.util.spec_from_file_location("audit_publication_inventory", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
COMMIT = b"a" * 40


class PublicationInventoryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        self.root.mkdir()
        self.addCleanup(patch.stopall)
        # Imported helpers hold their own ROOT; patch all three explicitly.
        for module in (audit, audit.tree, audit.history):
            patch.object(module, "ROOT", self.root).start()
        self.run = patch.object(audit.history.subprocess, "run", side_effect=self.child).start()
        self.index = b""
        self.historical = b""
        self.untracked = b""
        self.shallow = b"false\n"
        self.partial = False
        self.objects = COMMIT + b"\n"
        self.commits = COMMIT + b"\n"
        self.changed = False
        self.enumerated = False
        self.mirror_changed = False
        self.updated = []
        self.refs = COMMIT + b" refs/heads/main commit\n"

    def child(self, args, **kwargs):
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["check"])
        self.assertEqual(kwargs["env"]["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(kwargs["env"]["GIT_CONFIG_VALUE_0"], os.devnull)
        self.assertEqual(kwargs["env"]["GIT_CONFIG_VALUE_2"], "never")
        self.assertEqual(kwargs["timeout"], 120)
        operation, cwd = args[1], kwargs["cwd"]
        code, output = 0, b""
        if operation == "for-each-ref":
            output = self.refs
            if (self.changed and self.enumerated and cwd == self.root) or (
                self.mirror_changed and cwd != self.root
            ):
                output = b""
        elif operation == "symbolic-ref":
            code = 1  # Exercise detached HEAD inclusion by default.
        elif operation == "rev-parse":
            output = self.shallow if args[2] == "--is-shallow-repository" else COMMIT + b"\n"
        elif operation == "config":
            self.assertIn("--no-includes", args)
            code = 0 if self.partial else 1
        elif operation == "clone":
            self.assertEqual(args[2:7], ["--mirror", "--shared", "--local", "--quiet", "--"])
            self.assertFalse(cwd.is_relative_to(self.root))
            self.assertEqual(cwd.stat().st_mode & 0o777, 0o700)
            (cwd / "mirror").mkdir()
        elif operation == "update-ref":
            self.assertNotEqual(cwd, self.root)
            self.updated.append(args[2:])
        elif operation == "rev-list":
            output = self.objects if "--objects" in args else self.commits
        elif operation == "ls-tree":
            self.assertNotEqual(cwd, self.root)
            self.assertEqual(args[2:5], ["-r", "--name-only", "-z"])
            output = self.historical
            self.enumerated = True
        elif operation == "ls-files":
            self.assertEqual(cwd, self.root)
            if "--stage" in args:
                output = self.index
            else:
                self.assertEqual(args[2:], ["--others", "--exclude-standard", "-z"])
                output = self.untracked
        else:
            self.fail("Unexpected operation")
        return subprocess.CompletedProcess(args, code, output, b"SECRET stderr")

    def invoke(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = audit.main()
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(stdout.getvalue().splitlines()), 1)
        self.assertTrue(stdout.getvalue().isascii())
        self.assertNotIn("SECRET", stdout.getvalue())
        return code, json.loads(stdout.getvalue())

    def test_zero_is_not_readiness_and_snapshot_hash_matches_history(self):
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "manual-review-needed")
        self.assertFalse(report["privacy_acceptability_assessed"])
        self.assertFalse(report["historical_contents_reviewed"])
        self.assertFalse(report["atomic_snapshot"])
        self.assertTrue(report["report_private_context_possible"])
        self.assertEqual(report["candidate_total"], 0)
        self.assertTrue(report["detached_head_included"])
        self.assertEqual(self.updated, [["refs/ordo-audit/head", COMMIT.decode()]])
        expected = hashlib.sha256(self.refs.rstrip(b"\n") + b"\0\0" + COMMIT + b"\n").hexdigest()
        self.assertEqual(report["coverage_snapshot_sha256"], expected)

    def test_name_categories(self):
        for name, category in (
            ("export.tar.gz", "archives"), ("db.sqlite3", "database_or_dump"),
            ("logs/run.txt", "logs"), ("copy.bak", "backup"),
            (".env.production", "credentials_or_environment"),
            ("fixtures/person.json", "fixture_or_sample_data"),
            (".ordo/config.yaml", "repository_local_configuration"),
        ):
            with self.subTest(name=name):
                self.assertIn(category, audit.classify(name, audit.NAME_RULES))
        self.assertEqual(audit.classify("src/main.py", audit.NAME_RULES), set())

    def test_tracked_content_only_and_no_values(self):
        name = "notes.txt"
        (self.root / name).write_text(
            "person@example.org /home/SECRET/work C:\\Users\\SECRET\\work "
            "localhost 10.2.3.4 host.internal person@example.org"
        )
        self.index = b"100644 " + COMMIT + b" 0\tnotes.txt\0"
        self.historical = b"old.sql\0line\nbreak.zip\0old.sql\0"
        self.untracked = b"private.db\0"
        # These paths are never opened, nor is an ignored directory traversed.
        (self.root / "private.db").symlink_to(self.root / "absent")
        (self.root / ".venv").symlink_to(self.root / "absent")
        code, report = self.invoke()
        self.assertEqual(code, 0)
        rendered = json.dumps(report)
        for value in ("person@example.org", "10.2.3.4", "host.internal", "localhost"):
            self.assertNotIn(value, rendered)
        self.assertEqual(report["text_files_inspected"], 1)
        for category in audit.CONTENT_RULES:
            self.assertEqual(report["category_counts"]["tracked"][category], 1)
            self.assertEqual(report["category_counts"]["history"][category], 0)
        self.assertEqual(report["path_counts"], dict(tracked=1, history=2, untracked=1))

    def test_caps_counts_determinism_and_long_locations(self):
        long_name = "aaaa/" * 50 + "file.zip"
        self.historical = b"\0".join(os.fsencode(name) for name in (
            [long_name] + [f"z{i:03}.zip" for i in range(50)]
        )) + b"\0"
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report["candidate_total"], 51)
        self.assertEqual(len(report["candidates"]), 40)
        self.assertEqual(report["omitted_count"], 11)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["category_counts"]["history"]["archives"], 51)
        entry = report["candidates"][0]
        self.assertEqual(len(entry["File"]), 240)
        self.assertEqual(entry["location_id"], hashlib.sha256(os.fsencode(long_name)).hexdigest())
        self.assertEqual(report, self.invoke()[1])

    def test_content_skip_counts(self):
        source = self.root
        files = {"a": b"\0", "b": b"12345", "c": b"1234", "d": b"12", "e": b"\xff"}
        for name, data in files.items():
            (source / name).write_bytes(data)
        with patch.object(audit, "MAX_FILE_BYTES", 4), patch.object(audit, "MAX_TOTAL_BYTES", 6):
            report = audit.inventory(dict(tracked=set(files), history=set(), untracked=set()),
                                     set(files), source)
        self.assertEqual(report["content_skip_counts"], dict(binary=2, large=1, budget=1))
        self.assertEqual(report["content_bytes_inspected"], 6)
        self.assertEqual(report["text_files_inspected"], 1)

    def test_round_robin_keeps_rare_groups_among_many_configurations(self):
        configurations = {f".ordo/config-{i:03}.yaml" for i in range(100)}
        text = "/home/SECRET/work"
        (self.root / "notes.txt").write_text(text)
        names = dict(tracked=configurations | {"notes.txt", "copy.bak"},
                     history=configurations, untracked={"export.zip"})
        report = audit.inventory(names, {"notes.txt"}, self.root)
        self.assertEqual(report["sampling"], "round-robin-scope-category")
        self.assertEqual(report["status"], "manual-review-needed")
        self.assertFalse(report["privacy_acceptability_assessed"])
        self.assertEqual(report["candidate_total"], 203)
        self.assertEqual(len(report["candidates"]), 40)
        self.assertEqual(report["omitted_count"], 163)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["candidates"][:5], [
            dict(File="notes.txt", Category="local_absolute_path", Scope="tracked"),
            dict(File="export.zip", Category="archives", Scope="untracked"),
            dict(File="copy.bak", Category="backup", Scope="tracked"),
            dict(File=".ordo/config-000.yaml", Category="repository_local_configuration", Scope="tracked"),
            dict(File=".ordo/config-000.yaml", Category="repository_local_configuration", Scope="history"),
        ])
        expected_counts = {scope: dict.fromkeys(audit.CATEGORIES, 0) for scope in audit.SCOPES}
        expected_counts["tracked"].update(local_absolute_path=1, backup=1,
                                          repository_local_configuration=100)
        expected_counts["history"]["repository_local_configuration"] = 100
        expected_counts["untracked"]["archives"] = 1
        self.assertEqual(report["category_counts"], expected_counts)
        self.assertEqual(report["path_counts"], dict(tracked=102, history=100, untracked=1))
        self.assertEqual(report["content_bytes_inspected"], len(text))
        self.assertEqual(report["text_files_inspected"], 1)
        self.assertEqual(report["content_skip_counts"], dict(binary=0, large=0, budget=0))
        self.assertNotIn("SECRET", json.dumps(report))
        groups = [(entry["Scope"], entry["Category"]) for entry in report["candidates"]]
        self.assertEqual(groups[5:], [("tracked", "repository_local_configuration"),
                                     ("history", "repository_local_configuration")] * 17
                         + [("tracked", "repository_local_configuration")])
        self.assertEqual(report, audit.inventory(names, {"notes.txt"}, self.root))

    def test_public_endpoints_are_not_a_category(self):
        self.assertEqual(audit.classify("https://example.com/path", audit.CONTENT_RULES), set())

    def test_credential_like_filename_is_withheld(self):
        name = "credentials/" + "SECRETtoken123" * 4 + ".txt"
        self.untracked = os.fsencode(name) + b"\0"
        code, report = self.invoke()
        self.assertEqual(code, 0)
        entry = report["candidates"][0]
        self.assertEqual(entry["File"], "[withheld]")
        self.assertTrue(entry["path_withheld"])
        self.assertEqual(entry["location_id"], hashlib.sha256(os.fsencode(name)).hexdigest())

    def test_shared_snapshot_refuses_symlink_and_lfs(self):
        self.index = b"100644 " + COMMIT + b" 0\tdata.txt\0"
        (self.root / "data.txt").symlink_to(self.root / "absent")
        self.assertEqual(self.invoke(), (2, dict(status="incomplete", code="symlink")))
        (self.root / "data.txt").unlink()
        (self.root / "data.txt").write_bytes(b"version https://git-lfs.github.com/spec/v1\n")
        self.assertEqual(self.invoke(), (2, dict(status="incomplete", code="lfs_pointer")))

    def test_broken_enumeration_and_state_are_incomplete(self):
        for value in (b"SECRET", b"../SECRET\0", b"\0", b"/SECRET\0"):
            self.historical = value
            code, report = self.invoke()
            self.assertEqual(code, 2)
            self.assertIn(report["code"], ("invalid_paths", "invalid_path"))
        self.historical = b""
        self.changed = True
        self.assertEqual(self.invoke(), (2, dict(status="incomplete", code="refs_changed")))
        self.changed, self.mirror_changed = False, True
        self.assertEqual(self.invoke(), (2, dict(status="incomplete", code="refs_changed")))

    def test_coverage_refusals(self):
        for field, value, reason in (
            ("shallow", b"true\n", "shallow_repository"),
            ("partial", True, "partial_clone"),
            ("objects", b"?" + COMMIT + b"\n", "missing_objects"),
            ("commits", b"SECRET\n", "invalid_commits"),
            ("commits", b"", "empty_history"),
            ("commits", b"b" * 40 + b"\n", "invalid_head"),
        ):
            old = getattr(self, field)
            setattr(self, field, value)
            self.assertEqual(self.invoke(), (2, dict(status="incomplete", code=reason)))
            setattr(self, field, old)

    def test_errors_are_fixed_codes_only(self):
        for error in (RuntimeError("SECRET"), audit.Incomplete("SECRET"),
                      audit.tree.Incomplete("SECRET"), KeyboardInterrupt("SECRET")):
            with patch.object(audit, "audit", side_effect=error):
                self.assertEqual(self.invoke(), (2, dict(status="incomplete", code="unexpected_error")))
        self.run.side_effect = subprocess.TimeoutExpired("SECRET", 120, output=b"SECRET")
        self.assertEqual(self.invoke(), (2, dict(status="incomplete", code="command_timeout")))

    def test_path_parser_preserves_newlines_tabs_and_non_utf8(self):
        raw = b"line\nname.zip\0tab\tname.sql\0bad-\xff.log\0"
        self.assertEqual({os.fsencode(name) for name in audit.paths(raw)}, set(raw.split(b"\0")[:-1]))


if __name__ == "__main__":
    unittest.main()
