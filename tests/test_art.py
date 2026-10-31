"""The README's hand-drawn diagrams: built by tools/art/build_art.py, checked as files (not as pixels: look at them too)."""
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "art"))
import build_art  # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"
EXPECTED = {"banner.svg": ["results-race", "captcha"],
            "architecture.svg": ["your browser", "results-race", "engine", "headless Chromium", "mirror"],
            "race.svg": ["1 s", "late", "saved"]}


class ArtTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.art = build_art.build_all()

    def test_the_expected_files_are_built(self):
        self.assertEqual(sorted(self.art), sorted(EXPECTED))

    def test_each_is_well_formed_svg_with_a_title_and_description_for_screen_readers(self):
        for name, svg in self.art.items():
            root = ET.fromstring(svg)
            self.assertEqual(root.tag, SVG + "svg", name)
            self.assertTrue(root.get("viewBox"), name)
            self.assertEqual(root.get("role"), "img", name)
            self.assertTrue((root.find(SVG + "title").text or "").strip(), name)
            self.assertTrue((root.find(SVG + "desc").text or "").strip(), name)

    def test_nothing_is_fetched_and_nothing_runs(self):
        for name, svg in self.art.items():
            self.assertNotRegex(svg, r"(?i)<script|<image|<foreignObject|<iframe", name)
            self.assertNotRegex(svg, r"""(?i)(href|src)\s*=\s*["']https?:""", name)
            self.assertNotRegex(svg, r"(?i)url\(\s*['\"]?https?:", name)
            self.assertNotRegex(svg, r"(?i)\son\w+\s*=", name)  # no onclick & co

    def test_the_handwriting_font_travels_inside_each_file(self):
        for name, svg in self.art.items():
            self.assertIn("data:font/woff2;base64,", svg, name)

    def test_they_move_but_respect_reduced_motion(self):
        for name, svg in self.art.items():
            self.assertIn("@keyframes", svg, name)
            self.assertIn("prefers-reduced-motion", svg, name)

    def test_each_says_what_it_is_about(self):
        for name, words in EXPECTED.items():
            text = " ".join(t.strip() for t in ET.fromstring(self.art[name]).itertext() if t.strip() and "base64" not in t)
            for w in words:
                self.assertIn(w, text, f"{name} should mention {w!r}")

    def test_building_twice_gives_the_same_bytes(self):
        self.assertEqual(self.art, build_art.build_all())

    def test_they_stay_small_enough_for_a_readme(self):
        for name, svg in self.art.items():
            self.assertLess(len(svg.encode()), 90_000, name)

    def test_the_colours_come_from_one_palette(self):
        allowed = {c.lower() for c in build_art.PALETTE.values()} | {"#fff", "#ffffff", "none", "currentcolor"}
        for name, svg in self.art.items():
            used = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{3,6}\b", svg)}
            stray = {c for c in used if c not in allowed and not re.fullmatch(r"#[0-9a-f]{3,4}", c)}
            self.assertFalse(stray, f"{name} uses colours outside the palette: {stray}")


class RoughStrokeTest(unittest.TestCase):
    def test_a_hand_drawn_line_wobbles_but_reaches_its_ends(self):
        s = build_art.Sketch(400, 200, seed=1)
        d = s.rough_path([(10, 10), (310, 10)])
        nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", d)]
        self.assertAlmostEqual(nums[0], 10, delta=3)
        self.assertAlmostEqual(nums[-2], 310, delta=3)
        ys = nums[1::2]
        self.assertGreater(max(ys) - min(ys), 0.3)  # not ruler-straight

    def test_the_same_seed_draws_the_same_line(self):
        a, b = build_art.Sketch(100, 100, seed=7), build_art.Sketch(100, 100, seed=7)
        self.assertEqual(a.rough_path([(0, 0), (50, 50)]), b.rough_path([(0, 0), (50, 50)]))
        self.assertNotEqual(a.rough_path([(0, 0), (50, 50)]), build_art.Sketch(100, 100, seed=8).rough_path([(0, 0), (50, 50)]))


unittest.main() if __name__ == "__main__" else None
