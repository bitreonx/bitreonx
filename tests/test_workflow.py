import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/refresh-profile.yml"


class WorkflowContractTests(unittest.TestCase):
    def test_refresh_workflow_installs_motion_dependency_and_commits_assets(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("contents: write", text)
        self.assertIn('python-version: "3.12"', text)
        self.assertIn("pip install -r requirements.txt", text)
        test_cmd = "python -m unittest discover -s tests -v"
        render_cmd = "python scripts/render_profile.py --username bitreonx --config profile.json"
        self.assertIn(test_cmd, text)
        self.assertIn(render_cmd, text)
        self.assertLess(text.index(test_cmd), text.index(render_cmd))
        self.assertIn("assets/motion", text)
        self.assertIn("github-actions[bot]", text)

    def test_workflow_requires_profile_token_and_has_no_github_token_fallback(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("PROFILE_TOKEN: ${{ secrets.PROFILE_TOKEN }}", text)
        self.assertNotIn("GITHUB_TOKEN: ${{ github.token }}", text)
        self.assertIn("PROFILE_TOKEN is required", text)


if __name__ == "__main__":
    unittest.main()
