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


SCRIPT = Path(__file__).resolve().parents[1] / ".ordo/scripts/audit-gitleaks-metadata.py"
spec = importlib.util.spec_from_file_location("audit_gitleaks_metadata", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
COMMIT, TAG, INNER, BLOB = (letter * 40 for letter in "abcd")


class AuditGitleaksMetadataTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.report = self.base / "report.json"
        self.name = f"commit-{COMMIT}.txt"
        self.known = {self.name: ("commit", COMMIT)}

    def finding(self, **fields):
        return dict({"RuleID": "generic-api-key", "File": self.name, "StartLine": 1}, **fields)

    def sanitize(self, findings, code=10):
        self.report.write_text(json.dumps(findings))
        return audit.sanitize(self.report, code, self.known, self.source)

    def test_sanitization_and_cap(self):
        for name in (self.name, str(self.source / self.name)):
            payload = self.sanitize([self.finding(File=name, Secret="PRIVATE", Email="PRIVATE",
                                                  Match="PRIVATE", Message="PRIVATE")] * 51)
            self.assertEqual(payload["findings_total"], 51)
            self.assertTrue(payload["findings_truncated"])
            self.assertEqual(payload["findings"], [dict(RuleID="generic-api-key",
                ObjectType="commit", ObjectID=COMMIT, StartLine=1)] * 50)
            self.assertNotIn("PRIVATE", json.dumps(payload))

    def test_malformed_reports_and_fields_after_cap(self):
        for findings in ({}, [None], [{}]):
            with self.subTest(findings=findings), self.assertRaisesRegex(audit.Incomplete, "invalid_report"):
                self.sanitize(findings)
        for fields in ({"RuleID": "PRIVATE\n"}, {"StartLine": True}, {"StartLine": 0},
                       {"StartLine": "1"}, {"File": "../" + self.name},
                       {"File": str(self.source / ".." / self.name)},
                       {"File": "source/" + self.name}, {"File": "PRIVATE"},
                       {"File": f"tag-{TAG}.txt"}, {"File": ""}):
            with self.subTest(fields=fields), self.assertRaisesRegex(audit.Incomplete, "invalid_report"):
                self.sanitize([self.finding()] * 50 + [self.finding(**fields)])
        for raw in (b"PRIVATE", b"\xff"):
            self.report.write_bytes(raw)
            with self.assertRaisesRegex(audit.Incomplete, "invalid_report"):
                audit.sanitize(self.report, 0, self.known, self.source)
        self.report.unlink()
        with self.assertRaisesRegex(audit.Incomplete, "invalid_report"):
            audit.sanitize(self.report, 0, self.known, self.source)

    def test_scanner_exit_contract(self):
        self.assertEqual(self.sanitize([], 0)["status"], "clean")
        self.assertEqual(self.sanitize([self.finding()], 10)["status"], "findings")
        for code in (1, 2, 128):
            with self.assertRaisesRegex(audit.Incomplete, "scanner_failed"):
                self.sanitize([self.finding()], code)
        for findings, code in (([], 10), ([self.finding()], 0)):
            with self.assertRaisesRegex(audit.Incomplete, "inconsistent_report"):
                self.sanitize(findings, code)

    def test_strict_batch_parser_and_size_guard(self):
        body = b"author PRIVATE <PRIVATE>\n\nmessage\x00\xff\n"
        header = f"{COMMIT} commit {len(body)}\n".encode()
        def result(raw):
            return subprocess.CompletedProcess([], 0, raw, b"PRIVATE")
        with patch.object(audit.subprocess, "run", side_effect=[result(header), result(header + body + b"\n")]) as run:
            self.assertEqual(audit.read_objects({COMMIT: "commit"}, self.base, {}), {COMMIT: body})
            for call in run.call_args_list:
                self.assertTrue(call.kwargs["capture_output"])
                self.assertEqual(call.kwargs["input"], (COMMIT + "\n").encode())
        for raw in (header + body, header + body + b"\nextra", header.replace(b"commit", b"tag") + body + b"\n"):
            with patch.object(audit.subprocess, "run", side_effect=[result(header), result(raw)]):
                with self.assertRaisesRegex(audit.Incomplete, "invalid_objects"):
                    audit.read_objects({COMMIT: "commit"}, self.base, {})
        for header, reason in ((f"{COMMIT} commit {audit.MAX_OBJECT_BYTES + 1}\n".encode(), "metadata_too_large"),
                               (f"{COMMIT} missing\n".encode(), "invalid_objects"),
                               (b"", "invalid_objects")):
            with patch.object(audit.subprocess, "run", return_value=result(header)) as run:
                with self.assertRaisesRegex(audit.Incomplete, reason):
                    audit.read_objects({COMMIT: "commit"}, self.base, {})
                self.assertEqual(run.call_count, 1)

    def test_nested_tags_and_blob_targets_preserve_bytes(self):
        bodies = {COMMIT: b"author PRIVATE\n\nPRIVATE\xff", TAG: f"object {INNER}\ntype tag\ntag PRIVATE\n\nPRIVATE".encode(),
                  INNER: f"object {BLOB}\ntype blob\ntag PRIVATE\n\nPRIVATE".encode()}
        records = [f"{TAG} refs/other/PRIVATE tag".encode(), f"{INNER} refs/tags/PRIVATE tag".encode()]
        with patch.object(audit, "read_objects", side_effect=lambda expected, *_: {oid: bodies[oid] for oid in expected}), patch.object(
                audit, "git", return_value=subprocess.CompletedProcess([], 0, b"blob\n")):
            known, tags = audit.gather({COMMIT}, records, self.base, {}, self.source)
        self.assertEqual(tags, 2)
        self.assertEqual(len(known), 3)
        for name, (kind, oid) in known.items():
            self.assertEqual(name, f"{kind}-{oid}.txt")
            self.assertEqual((self.source / name).read_bytes(), bodies[oid])
            self.assertEqual((self.source / name).stat().st_mode & 0o777, 0o600)

    def test_tag_cycles_and_invalid_links(self):
        for body, reason in ((f"object {TAG}\ntype tag\n\nPRIVATE".encode(), "tag_cycle"),
                             (b"object PRIVATE\ntype blob\n", "invalid_tag"),
                             (f"object {BLOB}\ntype blob\n".encode(), "invalid_tag")):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory(dir=self.base) as directory:
                with patch.object(audit, "read_objects", return_value={TAG: body}), patch.object(
                        audit, "git", return_value=subprocess.CompletedProcess([], 0, b"tree\n")):
                    with self.assertRaisesRegex(audit.Incomplete, reason):
                        audit.gather(set(), [f"{TAG} refs/tags/PRIVATE tag".encode()], self.base, {}, Path(directory))

    def test_audit_snapshot_and_scanner_invocation(self):
        records = [f"{COMMIT} refs/heads/PRIVATE commit".encode()]
        before = (records, 1, b"", 0, (COMMIT + "\n").encode())
        version, scanner_code, changed = b"8.20.1\n", 0, False
        shallow, partial, missing = b"false\n", False, False
        scanned = []

        def git(args, cwd, env, allowed=(0,)):
            if args[0] == "rev-parse":
                raw, code = shallow, 0
            elif args[0] == "config":
                raw, code = b"", 0 if partial else 1
            elif args[0] in ("clone", "update-ref"):
                self.assertNotEqual(cwd, audit.ROOT)
                raw, code = b"", 0
            elif args[0] == "rev-list":
                raw, code = (COMMIT + "\n").encode(), 0
                if missing and "--objects" in args:
                    raw = ("?" + BLOB + "\n").encode()
            else:
                self.fail("Unexpected Git operation")
            return subprocess.CompletedProcess(args, code, raw, b"PRIVATE")

        def command(args, cwd, env, timeout):
            if args[1] == "version":
                return subprocess.CompletedProcess(args, 0, version, b"PRIVATE")
            for flag in ("--no-git", "--redact", "--ignore-gitleaks-allow", "--no-banner"):
                self.assertIn(flag, args)
            self.assertEqual(args[args.index("--exit-code") + 1], "10")
            source = Path(args[args.index("--source") + 1])
            self.assertFalse((source / ".gitleaksignore").exists())
            for flag in ("--config", "--gitleaks-ignore-path", "--report-path"):
                self.assertEqual(Path(args[args.index(flag) + 1]).parent, cwd)
            report = Path(args[args.index("--report-path") + 1])
            report.write_text("[]")
            scanned.append(True)
            return subprocess.CompletedProcess(args, scanner_code, b"PRIVATE", b"PRIVATE")

        with patch.object(audit.shutil, "which", return_value="/tools/gitleaks"), patch.object(
                audit, "git", side_effect=git), patch.object(audit, "command", side_effect=command), patch.object(
                audit.history, "refs", return_value=records), patch.object(audit.history, "state",
                side_effect=lambda _: before if not (changed and scanned) else ([], *before[1:])), patch.object(
                audit, "gather", return_value=(self.known, 0)):
            payload = audit.audit()
            self.assertTrue(payload["detached_head_included"])
            self.assertEqual(payload["commit_count"], 1)
            self.assertEqual(payload["coverage_snapshot_sha256"], hashlib.sha256(
                b"\n".join(records) + b"\x00" + before[2] + b"\x00" + before[4]).hexdigest())
            version = b"8.20.2"
            with self.assertRaisesRegex(audit.Incomplete, "gitleaks_version_mismatch"):
                audit.audit()
            version, scanner_code = b"8.20.1", 1
            with self.assertRaisesRegex(audit.Incomplete, "scanner_failed"):
                audit.audit()
            scanner_code, changed = 0, True
            scanned.clear()
            with self.assertRaisesRegex(audit.Incomplete, "refs_changed"):
                audit.audit()
            changed, shallow = False, b"true\n"
            with self.assertRaisesRegex(audit.Incomplete, "shallow_repository"):
                audit.audit()
            shallow, partial = b"false\n", True
            with self.assertRaisesRegex(audit.Incomplete, "partial_clone"):
                audit.audit()
            partial, missing = False, True
            with self.assertRaisesRegex(audit.Incomplete, "missing_objects"):
                audit.audit()

    def test_safe_environment_and_single_json_errors(self):
        with patch.dict(os.environ, {"GIT_DIR": "PRIVATE", "GITLEAKS_CONFIG_TOML": "PRIVATE"}):
            env = audit.history.safe_environment()
        self.assertNotIn("GIT_DIR", env)
        self.assertNotIn("GITLEAKS_CONFIG_TOML", env)
        for key in ("GIT_NO_LAZY_FETCH", "GIT_NO_REPLACE_OBJECTS", "GIT_CONFIG_NOSYSTEM"):
            self.assertEqual(env[key], "1")
        for error in (RuntimeError("PRIVATE"), KeyboardInterrupt("PRIVATE"), audit.Incomplete("git_failed")):
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(audit, "audit", side_effect=error), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(audit.main(), 2)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(len(stdout.getvalue().splitlines()), 1)
            self.assertNotIn("PRIVATE", stdout.getvalue())
            self.assertEqual(json.loads(stdout.getvalue())["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
