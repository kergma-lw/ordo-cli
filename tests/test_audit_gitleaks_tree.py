import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / ".ordo/scripts/audit-gitleaks-tree.py"
spec = importlib.util.spec_from_file_location("audit_gitleaks_tree", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditGitleaksTreeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        self.root.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(audit, "ROOT", self.root).start()
        self.which = patch.object(audit.shutil, "which", return_value="/tools/gitleaks").start()
        self.run = patch.object(audit.subprocess, "run", side_effect=self.child).start()
        patch.dict(os.environ, {
            "GITLEAKS_CONFIG": "hostile", "GITLEAKS_CONFIG_TOML": "hostile",
            "GIT_INDEX_FILE": "hostile",
        }).start()
        self.index = b""
        self.version = b"8.20.1\n"
        self.report = []
        self.raw_report = None
        self.scan_code = 0
        self.git_code = 0
        self.copied = None
        self.absolute_paths = False

    def tracked(self, name="tracked.txt", content=b"current worktree", mode="100644", stage="0"):
        self.index += f"{mode} {'a' * 40} {stage}\t".encode() + os.fsencode(name) + b"\x00"
        if content is not None:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def child(self, args, **kwargs):
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["check"])
        self.assertGreater(kwargs["timeout"], 0)
        for key in ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML", "GIT_INDEX_FILE"):
            self.assertNotIn(key, kwargs["env"])
        if args[0] == "git":
            self.assertEqual(args, ["git", "ls-files", "--stage", "-z"])
            self.assertEqual(kwargs["cwd"], self.root)
            return subprocess.CompletedProcess(args, self.git_code, self.index, b"private git error")
        self.assertEqual(args[0], "/tools/gitleaks")
        base = kwargs["cwd"]
        self.assertFalse(base.is_relative_to(self.root))
        self.assertEqual(stat.S_IMODE(base.stat().st_mode), 0o700)
        if args[1] == "version":
            return subprocess.CompletedProcess(args, 0, self.version, b"private version error")
        self.assertEqual(args[1], "detect")
        for flag in ("--no-git", "--redact", "--no-banner", "--ignore-gitleaks-allow"):
            self.assertIn(flag, args)
        for flag, value in (("--exit-code", "10"), ("--report-format", "json")):
            self.assertEqual(args[args.index(flag) + 1], value)
        config = Path(args[args.index("--config") + 1])
        self.assertEqual(config.read_text(), "[extend]\nuseDefault = true\n")
        ignore = Path(args[args.index("--gitleaks-ignore-path") + 1])
        self.assertEqual(ignore.read_bytes(), b"")
        source = Path(args[args.index("--source") + 1])
        self.assertEqual(source, base / "source")
        self.assertFalse((source / ".gitleaksignore").exists())
        self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o700)
        self.assertEqual(config.parent, base)
        self.assertEqual(ignore.parent, base)
        tree = source / "tree"
        self.copied = {}
        for path in tree.rglob("*"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600)
            if path.is_file():
                self.copied[path.relative_to(tree).as_posix()] = path.read_bytes()
        report_path = Path(args[args.index("--report-path") + 1])
        self.assertEqual(report_path.parent, base)
        if self.raw_report is not None:
            report_path.write_bytes(self.raw_report)
        elif self.report is not None:
            report = self.report
            if self.absolute_paths:
                report = [dict(item, File=str(source / item["File"])) for item in report]
            report_path.write_text(json.dumps(report))
        return subprocess.CompletedProcess(args, self.scan_code, b"SECRET child stdout", b"SECRET child stderr")

    def invoke(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = audit.main()
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(stdout.getvalue().splitlines()), 1)
        self.assertNotIn("SECRET", stdout.getvalue())
        self.assertNotIn("private", stdout.getvalue())
        return code, json.loads(stdout.getvalue())

    def incomplete(self, reason):
        code, report = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(report, {"status": "incomplete", "code": reason})

    def test_clean_copies_only_tracked_worktree_bytes_including_binary(self):
        self.tracked("nested/file", b"\x00current unstaged bytes\xff")
        (self.root / "untracked").write_bytes(b"not scanned")
        (self.root / ".git").mkdir()
        (self.root / ".git/history").write_bytes(b"not scanned")
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report["coverage"], "tracked-worktree-scanner-limited")
        self.assertEqual(report["scanned_files"], 1)
        self.assertEqual(self.copied, {"nested/file": b"\x00current unstaged bytes\xff"})
        self.assertEqual(self.run.call_count, 3)

    def test_findings_are_allowlisted_capped_and_relative(self):
        self.tracked()
        self.scan_code = 10
        self.absolute_paths = True
        self.report = [{
            "RuleID": "generic-api-key", "File": "tree/tracked.txt", "StartLine": 2,
            "Secret": "SECRET", "Match": "SECRET", "Description": "SECRET",
            "Fingerprint": "SECRET",
        }] * 51
        code, report = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(report["findings_total"], 51)
        self.assertTrue(report["findings_truncated"])
        self.assertEqual(report["findings"], [{
            "RuleID": "generic-api-key", "File": "tracked.txt", "StartLine": 2,
        }] * 50)

    def test_missing_or_wrong_version(self):
        self.which.return_value = None
        self.incomplete("gitleaks_unavailable")
        self.run.assert_not_called()
        self.which.return_value = "/tools/gitleaks"
        for version in (b"8.20.2", b"v8.20.1", b"8.20.1 extra"):
            with self.subTest(version=version):
                self.version = version
                self.incomplete("gitleaks_version_mismatch")

    def test_child_failures_are_sanitized(self):
        self.git_code = 128
        self.incomplete("git_failed")
        self.git_code = 0
        self.scan_code = 2
        self.incomplete("scanner_failed")
        for error, reason in (
            (subprocess.TimeoutExpired("SECRET", 15, output=b"SECRET"), "command_timeout"),
            (FileNotFoundError("SECRET"), "command_unavailable"),
            (RuntimeError("SECRET"), "unexpected_error"),
        ):
            with self.subTest(reason=reason):
                self.run.side_effect = error
                self.incomplete(reason)

    def test_partial_scan_exit_one_is_incomplete_even_with_findings(self):
        self.tracked()
        self.scan_code = 1
        for findings in ([], [{"RuleID": "rule", "File": "tree/tracked.txt", "StartLine": 1}]):
            with self.subTest(findings=findings):
                self.report = findings
                self.incomplete("scanner_failed")

    def test_missing_malformed_and_invalid_reports(self):
        self.tracked()
        for report in (None, {}, [None], [{}]):
            with self.subTest(report=report):
                self.report = report
                self.incomplete("invalid_report")
        for raw in (b"SECRET invalid JSON", b"\xff"):
            self.raw_report = raw
            self.incomplete("invalid_report")

    def test_invalid_finding_fields_and_paths(self):
        self.tracked()
        self.scan_code = 10
        valid = {"RuleID": "rule", "File": "tree/tracked.txt", "StartLine": 1}
        for key, value, reason in (
            ("File", "untracked", "invalid_report"),
            ("File", "tracked.txt", "invalid_report"),
            ("File", "tree/untracked", "invalid_report"),
            ("File", "tree/../tracked.txt", "invalid_path"),
            ("File", "../tracked.txt", "invalid_path"),
            ("File", "/outside/tracked.txt", "invalid_path"),
            ("File", "a/../tracked.txt", "invalid_path"),
            ("StartLine", True, "invalid_report"),
            ("StartLine", 0, "invalid_report"),
            ("StartLine", "1", "invalid_report"),
            ("RuleID", "rule\nSECRET", "invalid_report"),
        ):
            with self.subTest(key=key, value=value):
                self.report = [dict(valid, **{key: value})]
                self.incomplete(reason)
        self.report = [valid] * 50 + [{}]
        self.incomplete("invalid_report")

    def test_exit_report_consistency(self):
        self.tracked()
        self.scan_code = 10
        self.incomplete("inconsistent_report")
        self.scan_code = 0
        self.report = [{"RuleID": "rule", "File": "tree/tracked.txt", "StartLine": 1}]
        self.incomplete("inconsistent_report")

    def test_deleted_tracked_files_are_counted(self):
        self.tracked("deleted", None)
        self.tracked("gone/also-deleted", None)
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report["excluded_deleted"], 2)
        self.assertEqual(report["scanned_files"], 0)

    def test_unsupported_index_entries_and_traversal(self):
        for mode, stage, name, reason in (
            ("100644", "1", "file", "unresolved_index"),
            ("160000", "0", "module", "submodule"),
            ("120000", "0", "link", "symlink"),
            ("100644", "0", "../outside", "invalid_path"),
            ("100644", "0", ".git/config", "invalid_path"),
        ):
            with self.subTest(reason=reason):
                self.index = b""
                self.tracked(name, None, mode, stage)
                self.incomplete(reason)
        self.index = b"not a nul terminated index"
        self.incomplete("invalid_index")

    def test_worktree_symlinks_are_rejected_including_intermediate(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        (outside / "file").write_bytes(b"SECRET")
        for name, target in (("link", outside / "file"), ("directory", outside)):
            (self.root / name).symlink_to(target)
        for name in ("link", "directory/file", "directory/missing"):
            with self.subTest(name=name):
                self.index = b""
                self.tracked(name, None)
                self.incomplete("symlink")
        self.assertIsNone(self.copied)

    def test_nonregular_worktree_file(self):
        self.tracked("directory", None)
        (self.root / "directory").mkdir()
        self.incomplete("nonregular_file")

    def test_lfs_pointer_is_incomplete(self):
        self.tracked(content=b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 10\n")
        self.incomplete("lfs_pointer")
        self.assertIsNone(self.copied)

    def test_unusual_filename_is_json_escaped(self):
        name = "line\nbreak-\u2603.txt"
        self.tracked(name)
        self.scan_code = 10
        self.report = [{"RuleID": "rule", "File": "tree/" + name, "StartLine": 1}]
        code, report = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(report["findings"][0]["File"], name)

    def test_source_relative_and_absolute_paths_preserve_tracked_tree_prefix(self):
        self.tracked("foo")
        self.tracked("tree/foo")
        self.scan_code = 10
        self.report = [
            {"RuleID": "rule", "File": "tree/foo", "StartLine": 1},
            {"RuleID": "rule", "File": "tree/tree/foo", "StartLine": 1},
        ]
        for absolute in (False, True):
            with self.subTest(absolute=absolute):
                self.absolute_paths = absolute
                code, report = self.invoke()
                self.assertEqual(code, 1)
                self.assertEqual([item["File"] for item in report["findings"]], ["foo", "tree/foo"])

    def test_tracked_ignore_file_is_scanned_as_data(self):
        self.tracked(".gitleaksignore", b"ignored-fingerprint\n")
        self.tracked("inline.txt", b"secret # gitleaks:allow\n")
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report["scanned_files"], 2)
        self.assertEqual(self.copied, {
            ".gitleaksignore": b"ignored-fingerprint\n",
            "inline.txt": b"secret # gitleaks:allow\n",
        })


if __name__ == "__main__":
    unittest.main()
