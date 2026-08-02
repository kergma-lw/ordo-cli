import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "ordo-help"


class GhPrDiffHelpTest(unittest.TestCase):
    def test_operation_help_publishes_gh_pr_diff_contract(self) -> None:
        result = subprocess.run(
            [str(LAUNCHER), "operation", "gh.pr.diff", "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["reference"], "gh.pr.diff")
        self.assertEqual(payload["operation_name"], "pr.diff")
        self.assertEqual(payload["operation"]["summary"], "Read normalized change content from a GitHub pull request.")
        self.assertEqual(payload["operation"]["inputs"]["repository"], "string")
        self.assertIn("limit_invalid", payload["operation"]["failure_modes"])
        self.assertEqual(payload["operation"]["outputs"]["total_files"], "integer")


if __name__ == "__main__":
    unittest.main()
