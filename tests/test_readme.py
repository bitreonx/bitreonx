import unittest
from pathlib import Path

from scripts.github_data import load_profile_config
from scripts.render_profile import render_readme

ROOT = Path(__file__).resolve().parents[1]


class ReadmeTests(unittest.TestCase):
    def setUp(self):
        self.config = load_profile_config(ROOT / "profile.json")

    def test_readme_has_editorial_structure_and_theme_aware_assets(self):
        readme = render_readme(self.config)
        self.assertIn("## Selected work", readme)
        self.assertIn("## Contribution record", readme)
        self.assertIn("## How I build", readme)
        self.assertIn("## Elsewhere", readme)
        self.assertIn('media="(prefers-color-scheme: dark)"', readme)
        self.assertIn("./assets/hero-dark.svg", readme)
        self.assertIn("./assets/hero-light.svg", readme)
        self.assertIn("./assets/contributions-dark.svg", readme)
        self.assertIn("./assets/project-mnestis-light.svg", readme)
        self.assertIn("./assets/project-rune-light.svg", readme)

    def test_project_art_is_wrapped_in_canonical_repository_links(self):
        readme = render_readme(self.config)
        self.assertIn('<a href="https://github.com/bitreonx/Mnestis">', readme)
        self.assertIn('<a href="https://github.com/bitreonx/Rune">', readme)

    def test_readme_rejects_legacy_profile_cliches(self):
        readme = render_readme(self.config).lower()
        banned = [
            "ps aux",
            "public build pulse",
            "sudo rm -rf",
            "visitor-counter",
            "visitor counter",
            "streak-card",
            "rainbow-badge",
            "github-readme-stats",
            "ghchart",
            "passionate developer",
        ]
        for phrase in banned:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, readme)

    def test_generated_readme_matches_checked_in_readme(self):
        self.assertEqual(render_readme(self.config), (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
