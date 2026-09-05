import unittest
from pathlib import Path

from scripts.github_data import load_profile_config
from scripts.render_profile import render_readme

ROOT = Path(__file__).resolve().parents[1]


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.config = load_profile_config(ROOT / "profile.json")

    def test_readme_is_motion_first_and_reduced_motion_safe(self):
        readme = render_readme(self.config)
        self.assertIn("./assets/motion/hero-dark.gif", readme)
        self.assertIn("./assets/motion/hero-light.gif", readme)
        self.assertIn("./assets/motion/hero-dark.png", readme)
        self.assertIn("prefers-reduced-motion: reduce", readme)
        self.assertIn("./assets/motion/mnestis-light.gif", readme)
        self.assertIn("./assets/motion/rune-light.gif", readme)
        self.assertIn("./assets/motion/contributions-light.gif", readme)

    def test_readme_has_only_the_five_approved_beats(self):
        readme = render_readme(self.config)
        self.assertIn("SELECTED SYSTEMS", readme)
        self.assertIn("BUILD ACTIVITY", readme)
        self.assertIn("CURRENTLY", readme)
        self.assertIn("ELSEWHERE", readme)
        self.assertNotIn("## How I build", readme)
        self.assertNotIn("## Selected work", readme)

    def test_projects_link_to_canonical_repositories(self):
        readme = render_readme(self.config)
        self.assertIn('href="https://github.com/bitreonx/Mnestis"', readme)
        self.assertIn('href="https://github.com/bitreonx/Rune"', readme)

    def test_readme_rejects_profile_cliches(self):
        readme = render_readme(self.config).lower()
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
