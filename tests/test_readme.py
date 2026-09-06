import unittest
from pathlib import Path

import json

from scripts.github_data import load_profile_config, normalize_graphql_payload
from scripts.render_profile import render_readme

ROOT = Path(__file__).resolve().parents[1]


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.config = load_profile_config(ROOT / "profile.json")
        payload = json.loads((ROOT / "tests/fixtures/github_profile_graphql.json").read_text())
        self.data = normalize_graphql_payload(payload, self.config)

    def test_readme_is_motion_first_and_reduced_motion_safe(self):
        readme = render_readme(self.config, self.data)
        self.assertIn("./assets/motion/hero-dark.gif", readme)
        self.assertIn("./assets/motion/hero-light.gif", readme)
        self.assertIn("./assets/motion/hero-dark.png", readme)
        self.assertIn("prefers-reduced-motion: reduce", readme)
        self.assertIn("./assets/motion/mnestis-light.png", readme)
        self.assertIn("./assets/motion/rune-light.png", readme)
        self.assertNotIn("mnestis-light.gif", readme)
        self.assertNotIn("rune-light.gif", readme)
        self.assertIn("./assets/motion/contributions-light.gif", readme)

    def test_contribution_panel_links_to_official_github_profile_and_has_native_details(self):
        readme = render_readme(self.config, self.data)
        self.assertIn('href="https://github.com/bitreonx?tab=overview"', readme)
        self.assertIn("<details>", readme)
        self.assertIn("Activity details", readme)
        self.assertIn("181 exact contributions", readme)
        self.assertIn("AUG 2026", readme)
        self.assertIn("Calendar through", readme)
        self.assertIn("GitHub GraphQL", readme)
        self.assertIn("from=2026-08-01&amp;to=2026-08-31", readme)

    def test_readme_uses_only_two_animated_surfaces(self):
        readme = render_readme(self.config, self.data)
        self.assertEqual(readme.count(".gif"), 6)  # light/dark/img fallback for hero + contributions

    def test_readme_has_only_the_five_approved_beats(self):
        readme = render_readme(self.config, self.data)
        self.assertIn("SELECTED SYSTEMS", readme)
        self.assertIn("BUILD ACTIVITY", readme)
        self.assertIn("CURRENTLY", readme)
        self.assertIn("ELSEWHERE", readme)
        self.assertNotIn("## How I build", readme)
        self.assertNotIn("## Selected work", readme)

    def test_projects_link_to_canonical_repositories(self):
        readme = render_readme(self.config, self.data)
        self.assertIn('href="https://github.com/bitreonx/Mnestis"', readme)
        self.assertIn('href="https://github.com/bitreonx/Rune"', readme)

    def test_readme_rejects_profile_cliches(self):
        readme = render_readme(self.config, self.data).lower()
        banned = [
            "ps aux", "public build pulse", "sudo rm -rf", "visitor counter",
            "streak", "github-readme-stats", "ghchart", "passionate developer",
            "how i build", "badge", "terminal", "live telemetry",
        ]
        for phrase in banned:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, readme)


if __name__ == "__main__":
    unittest.main()
