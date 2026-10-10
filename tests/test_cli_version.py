import contextlib
import io
import unittest
from unittest.mock import patch

from ordo import cli, help_cli
from ordo.version import distribution_version


class CliVersionTest(unittest.TestCase):
    def test_playbook_reports_installed_distribution_version(self) -> None:
        stdout = io.StringIO()

        with (
            patch("sys.argv", ["ordo-playbook", "--version"]),
            contextlib.redirect_stdout(stdout),
            self.assertRaises(SystemExit) as raised,
        ):
            cli.main()

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stdout.getvalue(), f"ordo-playbook {distribution_version()}\n")

    def test_help_reports_installed_distribution_version(self) -> None:
        stdout = io.StringIO()

        with (
            contextlib.redirect_stdout(stdout),
            self.assertRaises(SystemExit) as raised,
        ):
            help_cli.main(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(stdout.getvalue(), f"ordo-help {distribution_version()}\n")
