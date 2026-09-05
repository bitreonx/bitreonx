import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.github_data import load_profile_config, normalize_graphql_payload
from scripts.motion_profile import render_motion_assets

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
        self.assertEqual(len(self.paths), 16)
        self.assertEqual(sum(p.suffix == ".gif" for p in self.paths), 8)
        self.assertEqual(sum(p.suffix == ".png" for p in self.paths), 8)

    def test_gifs_are_actually_animated_and_full_width(self):
        for path in [p for p in self.paths if p.suffix == ".gif"]:
            with Image.open(path) as image:
                self.assertGreaterEqual(getattr(image, "n_frames", 1), 20, path.name)
                self.assertEqual(image.width, 1200)

    def test_contribution_animation_preserves_real_total_metadata(self):
        with Image.open(self.temp / "contributions-light.gif") as image:
            comment = image.info.get("comment", b"")
            if isinstance(comment, bytes):
                comment = comment.decode("utf-8")
            self.assertIn("totalContributions=179", comment)
            self.assertIn("source=GitHub contributionCalendar", comment)

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
