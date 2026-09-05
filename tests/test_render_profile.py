import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.github_data import load_profile_config, normalize_graphql_payload
from scripts.render_profile import THEMES, esc, render_all, render_contributions, render_hero, render_project_card

ROOT = Path(__file__).resolve().parents[1]


class RenderProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = load_profile_config(ROOT / "profile.json")
        payload = json.loads((ROOT / "tests/fixtures/github_profile_graphql.json").read_text())
        self.data = normalize_graphql_payload(payload, self.config)

    def test_escapes_svg_text(self):
        self.assertEqual(esc('A&B <x> "q"'), "A&amp;B &lt;x&gt; &quot;q&quot;")

    def test_hero_uses_real_profile_metrics_without_terminal_gimmicks(self):
        svg = render_hero(self.data, self.config, THEMES["light"])
        self.assertIn("55", svg)
        self.assertIn("5", svg)
        self.assertIn("54", svg)
        self.assertIn("developer tools", svg)
        self.assertNotIn("terminal", svg.lower())
        self.assertNotIn("ps aux", svg.lower())
        self.assertNotIn("gradient", svg.lower())

    def test_contribution_panel_has_53_weeks_and_exact_tooltip_counts(self):
        svg = render_contributions(self.data, THEMES["dark"])
        self.assertEqual(svg.count('data-week="'), 53)
        self.assertIn("2026-08-29 · 50 contributions", svg)
        self.assertIn("2026-08-27 · 21 contributions", svg)
        self.assertIn(">179<", svg)
        self.assertNotIn("PUBLIC BUILD PULSE", svg)
        self.assertNotIn("public events", svg.lower())

    def test_month_labels_keep_readable_spacing(self):
        import re
        svg = render_contributions(self.data, THEMES["light"])
        labels = [(int(x), label) for x, label in re.findall(r'<text x="(\d+)" y="83"[^>]*>([A-Z]{3})</text>', svg)]
        self.assertGreaterEqual(len(labels), 10)
        for (left_x, _), (right_x, _) in zip(labels, labels[1:]):
            self.assertGreaterEqual(right_x - left_x, 40)

    def test_project_card_uses_live_repository_metadata(self):
        svg = render_project_card(self.data["repositories"][0], THEMES["light"])
        self.assertIn("Mnestis", svg)
        self.assertIn("50", svg)
        self.assertIn("6", svg)
        self.assertIn("TypeScript", svg)
        self.assertIn("AI-ready codebase analysis", svg)
        self.assertIn('width="1200" height="220"', svg)
        self.assertIn("STARS", svg)
        self.assertIn("FORKS", svg)
        self.assertIn("GITHUB / PUBLIC", svg)
        self.assertNotIn(">LIVE<", svg)

    def test_render_all_is_deterministic(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_paths = render_all(self.data, self.config, Path(first))
            second_paths = render_all(self.data, self.config, Path(second))
            first_hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in first_paths]
            second_hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in second_paths]
            self.assertEqual(first_hashes, second_hashes)
            self.assertEqual(len(first_paths), 8)


if __name__ == "__main__":
    unittest.main()
