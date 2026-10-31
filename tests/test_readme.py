"""The README's pictures: they exist, stay small, and the generated ones match their generator."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools" / "art"))
import build_art  # noqa: E402


class ReadmePicturesTest(unittest.TestCase):
    def test_every_image_the_readme_shows_exists_and_is_not_huge(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        refs = set(re.findall(r'src="(docs/img/[^"]+)"', readme))
        self.assertGreaterEqual(len(refs), 8)
        for ref in refs:
            f = ROOT / ref
            self.assertTrue(f.is_file(), f"README shows {ref} but it is missing")
            self.assertLess(f.stat().st_size, 1_000_000, f"{ref} is too big for a README")

    def test_every_image_has_alt_text(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for tag in re.findall(r"<img [^>]*>", readme):
            self.assertRegex(tag, r'alt="[^"]{8,}"', tag)

    def test_the_committed_diagrams_are_what_the_generator_makes(self):
        for name, svg in build_art.build_all().items():
            self.assertEqual((ROOT / "docs" / "img" / name).read_text(encoding="utf-8"), svg,
                             f"{name} is stale: run python tools/art/build_art.py")

    def test_the_generated_art_names_no_country_or_board_and_the_credits_say_demo_data(self):
        # the screenshots are PNGs and cannot be grepped: look at them when regenerating. Here: the SVG text and the credits note
        credits = (ROOT / "docs" / "img" / "CREDITS.txt").read_text()
        self.assertIn("made up", credits)
        for name in build_art.build_all():
            self.assertNotRegex((ROOT / "docs" / "img" / name).read_text(), r"(?i)bangladesh|rajshahi|government")


unittest.main() if __name__ == "__main__" else None
