import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "ordo-help"
GOLDEN_DIR = ROOT / "tests" / "golden"
REAL_VENV_PYTHON = ROOT / ".venv" / "bin" / "python"


class OrdoHelpCliTest(unittest.TestCase):
    def run_help(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(LAUNCHER), *args],
            cwd=str(ROOT if cwd is None else cwd),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )

    def test_root_text_bootstrap_screen(self) -> None:
        result = self.run_help()

        self.assertEqual(result.returncode, 0)
        self.assertIn("ordo-help", result.stdout)
        self.assertIn("Recommended first calls:", result.stdout)
        self.assertIn("overview", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_root_json_matches_golden(self) -> None:
        result = self.run_help("--json")

        self.assertEqual(result.returncode, 0)
        actual = json.loads(result.stdout)
        expected = json.loads((GOLDEN_DIR / "ordo_help_root.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_overview_json_matches_golden(self) -> None:
        result = self.run_help("overview", "--json")

        self.assertEqual(result.returncode, 0)
        actual = json.loads(result.stdout)
        expected = json.loads((GOLDEN_DIR / "ordo_help_overview.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_bootstrap_flow_commands_succeed(self) -> None:
        root = json.loads(self.run_help("--json").stdout)
        overview = json.loads(self.run_help("overview", "--json").stdout)
        capabilities = json.loads(self.run_help("capabilities", "--json").stdout)
        model = json.loads(self.run_help("model", "--json").stdout)
        operations = json.loads(self.run_help("operations", "--json").stdout)

        self.assertEqual(root["tool_name"], "ordo-help")
        self.assertEqual(overview["document_kind"], "overview")
        self.assertIn("capabilities", capabilities)
        self.assertEqual(model["document_kind"], "model")
        self.assertIn("connectors", operations)

    def test_launcher_reports_missing_virtualenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            launcher_copy = temp_root / "ordo-help"
            shutil.copy2(LAUNCHER, launcher_copy)
            launcher_copy.chmod(launcher_copy.stat().st_mode | stat.S_IXUSR)

            result = subprocess.run(
                [str(launcher_copy)],
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                env=os.environ.copy(),
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing project virtualenv interpreter", result.stderr)

    def test_launcher_reports_missing_help_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            launcher_copy = temp_root / "ordo-help"
            shutil.copy2(LAUNCHER, launcher_copy)
            launcher_copy.chmod(launcher_copy.stat().st_mode | stat.S_IXUSR)

            venv_bin = temp_root / ".venv" / "bin"
            venv_bin.mkdir(parents=True)
            os.symlink(REAL_VENV_PYTHON, venv_bin / "python")

            result = subprocess.run(
                [str(launcher_copy)],
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                env=os.environ.copy(),
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing ordo-help CLI module", result.stderr)


if __name__ == "__main__":
    unittest.main()
