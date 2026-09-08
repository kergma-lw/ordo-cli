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


SCRIPT = Path(__file__).resolve().parents[1] / ".ordo/scripts/render-review-diff.py"
spec = importlib.util.spec_from_file_location("render_review_diff", SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class RenderReviewDiffTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.addCleanup(patch.stopall)
        patch.object(review.tempfile, "tempdir", str(self.root)).start()
        self.run = patch.object(review.subprocess, "run", side_effect=self.child).start()
        self.diff = "diff body\n"
        self.git_code = 0
        self.git_error = None
        self.opener_code = 0
        self.opener_error = None
        self.opened = []
        self.streams = []
        fdopen = os.fdopen

        def record_stream(*args, **kwargs):
            stream = fdopen(*args, **kwargs)
            self.streams.append(stream)
            return stream

        patch.object(review.os, "fdopen", side_effect=record_stream).start()

    def assert_private(self, path):
        self.assertTrue(path.is_absolute())
        self.assertEqual(path.parent.parent, self.root)
        self.assertTrue(path.parent.name.startswith("ordo-review-"))
        self.assertEqual(path.suffix, ".html")
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def child(self, args, **kwargs):
        if args == ["git", "diff", "--no-ext-diff", "--no-textconv", "main...HEAD"]:
            self.assertEqual(kwargs, dict(check=False, capture_output=True, text=True))
            if self.git_error:
                raise self.git_error
            return subprocess.CompletedProcess(args, self.git_code, self.diff, "git stderr\n")
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0], "xdg-open")
        self.assertEqual(kwargs, dict(check=False, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL))
        path = Path(args[1])
        self.assert_private(path)
        self.assertTrue(self.streams)
        self.assertTrue(all(stream.closed for stream in self.streams))
        self.assertTrue(path.read_text().endswith("</pre></body></html>"))
        self.opened.append(path)
        if self.opener_error:
            raise self.opener_error
        return subprocess.CompletedProcess(args, self.opener_code)

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(review.sys, "argv", [str(SCRIPT), *args]):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = review.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_invalid_arguments_have_no_side_effects(self):
        cases = [(), ("1", "2"), ("",), ("0",), ("01",), ("-1",), ("+1",),
                 (" 1",), ("1 ",), ("1\n",), ("\u0661",), ("\uff11",),
                 ("../1",), ("1;touch x",)]
        with patch.object(review.tempfile, "mkdtemp") as allocate:
            with patch.object(review.tempfile, "mkstemp") as create:
                for args in cases:
                    with self.subTest(args=args):
                        code, stdout, stderr = self.invoke(*args)
                        self.assertEqual(code, 2)
                        self.assertEqual(stdout, "")
                        self.assertTrue(stderr)
                allocate.assert_not_called()
                create.assert_not_called()
        self.run.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_success_escapes_html_and_is_private_with_permissive_umask(self):
        self.diff = '</pre><script>alert("x" & \'y\')</script>'
        old_umask = os.umask(0)
        try:
            code, stdout, stderr = self.invoke("123")
        finally:
            os.umask(old_umask)
        self.assertEqual((code, stderr), (0, ""))
        path = self.opened[0]
        self.assertEqual(json.loads(stdout), {"path": str(path)})
        self.assert_private(path)
        self.assertEqual(path.read_text(),
                         '<!doctype html><html><body><h1>Branch diff vs main</h1><pre>'
                         '&lt;/pre&gt;&lt;script&gt;alert(&quot;x&quot; &amp; '
                         '&#x27;y&#x27;)&lt;/script&gt;</pre></body></html>')

    def test_repeated_issue_uses_distinct_paths_and_preserves_old_symlink(self):
        target = self.root / "untouched"
        target.write_text("original")
        legacy = self.root / "ordo-review-123.html"
        legacy.symlink_to(target)
        with patch.object(Path, "write_text", side_effect=AssertionError("unsafe write_text")):
            for _ in range(2):
                self.assertEqual(self.invoke("123")[0], 0)
        self.assertNotEqual(self.opened[0], self.opened[1])
        self.assertNotEqual(self.opened[0].parent, self.opened[1].parent)
        for path in self.opened:
            self.assert_private(path)
        self.assertTrue(legacy.is_symlink())
        self.assertEqual(legacy.readlink(), target)
        self.assertEqual(target.read_text(), "original")

    def test_git_failures_allocate_nothing(self):
        with patch.object(review.tempfile, "mkdtemp") as allocate:
            for error, status, expected in [(None, 17, (17, "", "git stderr\n")),
                                             (OSError("private"), 0,
                                              (1, "", "failed to launch git diff\n"))]:
                with self.subTest(error=error):
                    self.git_error, self.git_code = error, status
                    self.assertEqual(self.invoke("1"), expected)
            allocate.assert_not_called()
        self.assertEqual(self.opened, [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_allocation_failures_cleanup(self):
        for name in ["mkdtemp", "mkstemp"]:
            with self.subTest(name=name):
                with patch.object(review.tempfile, name, side_effect=OSError("private")):
                    self.assertEqual(self.invoke("1"),
                                     (1, "", "failed to create review report\n"))
                self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.opened, [])

    def test_fdopen_failure_closes_descriptor_and_cleans_up(self):
        descriptors = []

        def fail(fd, *args, **kwargs):
            descriptors.append(fd)
            raise OSError("private")

        with patch.object(review.os, "fdopen", side_effect=fail):
            self.assertEqual(self.invoke("1"), (1, "", "failed to create review report\n"))
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(self.opened, [])

    def test_write_failure_closes_stream_and_cleans_only_own_directory(self):
        unrelated = self.root / "keep"
        unrelated.mkdir()
        target = unrelated / "report.html"
        target.write_text("keep")
        fdopen = os.fdopen
        streams = []

        def failing_writer(fd, *args, **kwargs):
            stream = fdopen(fd, *args, **kwargs)
            streams.append(stream)
            stream.write("partial")
            patch.object(stream, "write", side_effect=OSError("private")).start()
            return stream

        self.opener_error = OSError("must not open partial report")
        with patch.object(review.os, "fdopen", side_effect=failing_writer):
            self.assertEqual(self.invoke("1"), (1, "", "failed to create review report\n"))
        self.assertTrue(streams[0].closed)
        self.assertEqual(list(self.root.iterdir()), [unrelated])
        self.assertEqual(target.read_text(), "keep")
        self.assertEqual(self.opened, [])

    def test_nonzero_opener_exit_remains_success(self):
        self.opener_code = 9
        code, stdout, stderr = self.invoke("1")
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout), {"path": str(self.opened[0])})
        self.assert_private(self.opened[0])

    def test_opener_launch_failure_retains_report_without_success_json(self):
        self.opener_error = FileNotFoundError("private")
        code, stdout, stderr = self.invoke("1")
        path = self.opened[0]
        self.assertEqual((code, stdout), (1, ""))
        self.assertEqual(stderr, f"failed to launch xdg-open; review report retained at {path}\n")
        self.assert_private(path)
        self.assertIn(self.diff, path.read_text())
