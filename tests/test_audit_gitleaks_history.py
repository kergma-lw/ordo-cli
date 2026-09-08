import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / ".ordo/scripts/audit-gitleaks-history.py"
spec = importlib.util.spec_from_file_location("audit_gitleaks_history", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
COMMIT = "a" * 40
OTHER = "b" * 40


class AuditGitleaksHistoryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        self.root.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(audit, "ROOT", self.root).start()
        self.which = patch.object(audit.shutil, "which", return_value="/tools/gitleaks").start()
        self.run = patch.object(audit.subprocess, "run", side_effect=self.child).start()
        patch.dict(os.environ, {"GIT_DIR": "SECRET", "GIT_CONFIG_COUNT": "99",
                              "GITLEAKS_CONFIG_TOML": "SECRET"}).start()
        self.version = b"8.20.1\n"
        self.version_code = 0
        self.shallow = b"false\n"
        self.partial = False
        self.git_failure = False
        self.ref_data = f"{COMMIT} refs/heads/private commit\n".encode()
        self.head = COMMIT
        self.detached = False
        self.commits = (COMMIT + "\n").encode()
        self.objects = (COMMIT + "\n").encode()
        self.report = []
        self.raw_report = None
        self.scan_code = 0
        self.scanned = False
        self.change = None
        self.mirror_changed = False
        self.updated = []

    def child(self, args, **kwargs):
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["check"])
        env = kwargs["env"]
        self.assertNotIn("GIT_DIR", env)
        self.assertNotIn("GITLEAKS_CONFIG_TOML", env)
        for key in ("GIT_NO_LAZY_FETCH", "GIT_NO_REPLACE_OBJECTS", "GIT_CONFIG_NOSYSTEM"):
            self.assertEqual(env[key], "1")
        self.assertEqual(env["GIT_CONFIG_COUNT"], "4")
        self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GIT_OPTIONAL_LOCKS"], "0")
        self.assertEqual(env["GIT_CONFIG_VALUE_0"], os.devnull)
        code, stdout = 0, b""
        cwd = kwargs["cwd"]
        if args[0] == "git":
            self.assertEqual(kwargs["timeout"], 120)
            if self.git_failure:
                return subprocess.CompletedProcess(args, 128, b"SECRET", b"SECRET")
            operation = args[1]
            if operation == "for-each-ref":
                stdout = self.ref_data
                if self.mirror_changed and cwd != self.root:
                    stdout = b""
                if self.scanned and self.change == "refs" and cwd == self.root:
                    stdout += f"{OTHER} refs/tags/private commit\n".encode()
            elif operation == "symbolic-ref":
                code = 1 if self.detached else 0
                stdout = b"" if self.detached else b"refs/heads/private\n"
                if self.scanned and self.change == "symbolic":
                    stdout = b"refs/heads/changed\n"
            elif operation == "rev-parse":
                if args[2] == "--is-shallow-repository":
                    stdout = self.shallow
                elif args[-1].endswith("^{commit}"):
                    code = 1
                else:
                    head = OTHER if self.scanned and self.change == "head" else self.head
                    code, stdout = (0, (head + "\n").encode()) if head else (1, b"")
            elif operation == "config":
                self.assertIn("--no-includes", args)
                code, stdout = (0, b"remote.private.promisor true\n") if self.partial else (1, b"")
            elif operation == "clone":
                self.assertEqual(args, ["git", "clone", "--mirror", "--shared", "--local",
                                       "--quiet", "--", str(self.root), str(cwd / "mirror")])
                self.assertFalse(cwd.is_relative_to(self.root))
                (cwd / "mirror").mkdir()
            elif operation == "update-ref":
                self.assertNotEqual(cwd, self.root)
                self.updated.append(args[2:])
            elif operation == "rev-list":
                stdout = self.objects if "--objects" in args else self.commits
            else:
                self.fail(f"Unexpected Git operation: {operation}")
        elif args[1] == "version":
            self.assertEqual(kwargs["timeout"], 15)
            code, stdout = self.version_code, self.version
        else:
            self.assertEqual(args[0:2], ["/tools/gitleaks", "detect"])
            self.assertEqual(kwargs["timeout"], 600)
            self.assertNotIn("--no-git", args)
            for flag in ("--redact", "--ignore-gitleaks-allow", "--no-banner"):
                self.assertIn(flag, args)
            for flag, value in (("--log-opts", "--all --full-history --root -m --no-ext-diff --no-textconv --no-renames"),
                                ("--exit-code", "10"), ("--report-format", "json")):
                self.assertEqual(args[args.index(flag) + 1], value)
            source = Path(args[args.index("--source") + 1])
            self.assertEqual(source, cwd / "mirror")
            self.assertFalse((source / ".gitleaksignore").exists())
            self.assertFalse(cwd.is_relative_to(self.root))
            config = Path(args[args.index("--config") + 1])
            ignore = Path(args[args.index("--gitleaks-ignore-path") + 1])
            report = Path(args[args.index("--report-path") + 1])
            for path in (config, ignore, report):
                self.assertEqual(path.parent, cwd)
            self.assertEqual(config.read_text(), "[extend]\nuseDefault = true\n")
            self.assertEqual(ignore.read_bytes(), b"")
            if self.raw_report is not None:
                report.write_bytes(self.raw_report)
            elif self.report is not None:
                report.write_text(json.dumps(self.report))
            self.scanned = True
            code, stdout = self.scan_code, b"SECRET scanner output"
        return subprocess.CompletedProcess(args, code, stdout, b"SECRET stderr")

    def invoke(self):
        self.scanned = False
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = audit.main()
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(len(stdout.getvalue().splitlines()), 1)
        self.assertTrue(stdout.getvalue().isascii())
        self.assertNotIn("SECRET", stdout.getvalue())
        self.assertNotIn("private", stdout.getvalue())
        return code, json.loads(stdout.getvalue())

    def incomplete(self, reason):
        self.assertEqual(self.invoke(), (2, {"status": "incomplete", "code": reason}))

    def finding(self, **fields):
        return dict({"RuleID": "generic-api-key", "File": "nested/file", "StartLine": 1,
                     "Commit": COMMIT}, **fields)

    def test_clean_and_detached_head(self):
        self.detached = True
        self.head = OTHER
        self.commits += (OTHER + "\n").encode()
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "clean")
        self.assertEqual(report["commit_count"], 2)
        self.assertTrue(report["detached_head_included"])
        self.assertEqual(self.updated, [["refs/ordo-audit/head", OTHER]])
        self.assertEqual(report["local_ref_counts"], dict(heads=1, tags=0, remote_tracking=0, other=0))
        self.assertEqual(len(report["coverage_snapshot_sha256"]), 64)
        self.assertFalse(report["replacement_graft_semantics"])

    def test_ref_categories_noncommit_and_private_ref_collision(self):
        self.ref_data += (f"{OTHER} refs/tags/private blob\n"
                          f"{COMMIT} refs/remotes/private commit\n"
                          f"{COMMIT} refs/ordo-audit/head commit\n").encode()
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report["excluded_noncommit_refs"], 1)
        self.assertEqual(report["local_ref_counts"], dict(heads=1, tags=1, remote_tracking=1, other=1))
        self.assertEqual(self.updated[0][0], "refs/ordo-audit/head-head")

    def test_findings_allowlist_cap_and_escaping(self):
        self.scan_code = 10
        self.report = [self.finding(File="line\nbreak-\u2603", Secret="SECRET", Match="SECRET",
                                    Author="SECRET", Email="SECRET", Message="SECRET",
                                    Fingerprint="SECRET")] * 51
        code, report = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(report["findings_total"], 51)
        self.assertTrue(report["findings_truncated"])
        self.assertEqual(report["findings"], [self.finding(File="line\nbreak-\u2603")] * 50)

    def test_missing_and_wrong_version(self):
        self.which.return_value = None
        self.incomplete("gitleaks_unavailable")
        self.run.assert_not_called()
        self.which.return_value = "/tools/gitleaks"
        for version in (b"8.20.2", b"v8.20.1", b"8.20.1 extra"):
            self.version = version
            self.incomplete("gitleaks_version_mismatch")
        self.version, self.version_code = b"8.20.1", 1
        self.incomplete("gitleaks_version_mismatch")

    def test_shallow_partial_missing_and_empty(self):
        self.shallow = b"true\n"
        self.incomplete("shallow_repository")
        self.shallow, self.partial = b"false\n", True
        self.incomplete("partial_clone")
        self.partial, self.objects = False, ("?" + OTHER + "\n").encode()
        self.incomplete("missing_objects")
        self.objects, self.commits, self.head, self.ref_data = b"", b"", "", b""
        self.incomplete("empty_history")
        self.assertFalse(self.scanned)

    def test_failures_and_partial_scan_are_sanitized(self):
        self.git_failure = True
        self.incomplete("git_failed")
        self.git_failure = False
        for scan_code in (1, 2, 128):
            self.scan_code = scan_code
            self.report = [self.finding()]
            self.incomplete("scanner_failed")
        for error, reason in (
            (subprocess.TimeoutExpired("SECRET", 15, output=b"SECRET"), "command_timeout"),
            (FileNotFoundError("SECRET"), "command_unavailable"),
            (RuntimeError("SECRET"), "unexpected_error"),
        ):
            self.run.side_effect = error
            self.incomplete(reason)

    def test_malformed_and_missing_reports(self):
        for report in (None, {}, [None], [{}]):
            self.report = report
            self.incomplete("invalid_report")
        for raw in (b"SECRET", b"\xff"):
            self.raw_report = raw
            self.incomplete("invalid_report")

    def test_fields_validated_even_after_cap(self):
        self.scan_code = 10
        for key, value in (("RuleID", "rule\nSECRET"), ("StartLine", 0),
                           ("StartLine", True), ("StartLine", "1"),
                           ("Commit", OTHER), ("Commit", "A" * 40), ("Commit", None)):
            with self.subTest(key=key, value=value):
                self.report = [self.finding()] * 50 + [self.finding(**{key: value})]
                self.incomplete("invalid_report")
        for path in ("/absolute", "../outside", "a/../b", "a//b", ".git/config",
                     "C:/outside", "a\\b", "a\x00b", ""):
            self.report = [self.finding(File=path)]
            self.incomplete("invalid_path")

    def test_exit_consistency(self):
        self.scan_code = 10
        self.incomplete("inconsistent_report")
        self.scan_code, self.report = 0, [self.finding()]
        self.incomplete("inconsistent_report")

    def test_original_refs_and_head_changes(self):
        for change in ("refs", "head", "symbolic"):
            with self.subTest(change=change):
                self.change = change
                self.incomplete("refs_changed")

    def test_invalid_commit_listing_and_missing_head_coverage(self):
        self.commits = b"SECRET\n"
        self.incomplete("invalid_commits")
        self.commits = (OTHER + "\n").encode()
        self.incomplete("invalid_head")

    def test_mirror_ref_mismatch(self):
        self.mirror_changed = True
        self.incomplete("refs_changed")
        self.assertFalse(self.scanned)

    def test_sha256_commit_ids(self):
        commit = "c" * 64
        self.ref_data = f"{commit} refs/heads/private commit\n".encode()
        self.head = commit
        self.commits = (commit + "\n").encode()
        self.report, self.scan_code = [self.finding(Commit=commit)], 10
        code, report = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(report["findings"][0]["Commit"], commit)

    def test_unsafe_temp_directory(self):
        with patch.object(audit.tempfile, "gettempdir", return_value=str(self.root)):
            self.incomplete("unsafe_temp_directory")
        self.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
