import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.github_data import load_profile_config, normalize_graphql_payload
from scripts.motion_profile import (
    _calendar_month_labels,
    _calendar_summary,
    _weekly_totals,
    render_motion_assets,
)

ROOT = Path(__file__).resolve().parents[1]


class MotionProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_profile_config(ROOT / "profile.json")
        payload = json.loads((ROOT / "tests/fixtures/github_profile_graphql.json").read_text())
        cls.data = normalize_graphql_payload(payload, cls.config)
        cls.temp = Path(tempfile.mkdtemp())
        cls.paths = render_motion_assets(cls.data, cls.config, cls.temp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp, ignore_errors=True)

    def test_renders_gif_and_png_pairs(self):
        self.assertEqual(len(self.paths), 12)
        self.assertEqual(sum(p.suffix == ".gif" for p in self.paths), 4)
        self.assertEqual(sum(p.suffix == ".png" for p in self.paths), 8)
        self.assertFalse((self.temp / "mnestis-light.gif").exists())
        self.assertFalse((self.temp / "rune-light.gif").exists())

    def test_gifs_are_actually_animated_and_full_width(self):
        gifs = [p for p in self.paths if p.suffix == ".gif"]
        self.assertEqual({p.stem.rsplit("-", 1)[0] for p in gifs}, {"hero", "contributions"})
        for path in gifs:
            with Image.open(path) as image:
                self.assertGreaterEqual(getattr(image, "n_frames", 1), 20, path.name)
                self.assertEqual(image.width, 1200)
                durations = []
                for index in range(image.n_frames):
                    image.seek(index)
                    durations.append(int(image.info.get("duration") or 0))
                self.assertLessEqual(max(durations), 110, (path.name, max(durations)))
        self.assertLess(sum(p.stat().st_size for p in gifs), 1_800_000)

    def test_contribution_animation_preserves_real_total_metadata(self):
        with Image.open(self.temp / "contributions-light.gif") as image:
            comment = image.info.get("comment", b"")
            if isinstance(comment, bytes):
                comment = comment.decode("utf-8")
            self.assertIn("totalContributions=181", comment)
            self.assertIn("source=GitHub contributionCalendar", comment)


    def test_contribution_calendar_exposes_month_and_week_context(self):
        labels = _calendar_month_labels(self.data["calendar"])
        self.assertGreaterEqual(len(labels), 12)
        self.assertEqual(labels[0][1], "SEP")
        self.assertEqual(labels[-1][1], "SEP")

        weekly = _weekly_totals(self.data["calendar"]["weeks"])
        self.assertEqual(len(weekly), 53)
        self.assertEqual(sum(item["count"] for item in weekly), 181)
        self.assertEqual(max(item["count"] for item in weekly), 107)

        summary = _calendar_summary(self.data["calendar"]["weeks"])
        self.assertEqual(summary["best_week_count"], 107)
        self.assertEqual(summary["best_month_count"], 116)
        self.assertEqual(summary["best_month_label"], "AUG 2026")
        self.assertEqual(summary["active_days"], 28)
        self.assertEqual(summary["active_weeks"], 10)

    def test_frame_generation_is_deterministic(self):
        from scripts.motion_profile import THEMES, render_hero_frames
        first = render_hero_frames(self.data, self.config, THEMES["light"], frame_count=6)
        second = render_hero_frames(self.data, self.config, THEMES["light"], frame_count=6)
        self.assertEqual(
            [hashlib.sha256(frame.tobytes()).hexdigest() for frame in first],
            [hashlib.sha256(frame.tobytes()).hexdigest() for frame in second],
        )



if __name__ == "__main__":
    unittest.main()
