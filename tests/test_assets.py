import tempfile
import unittest
from pathlib import Path

from results_race.assets import fetch_assets


class FetchAssetsTest(unittest.TestCase):
    def test_downloads_both_logos_into_the_folder(self):
        d = Path(tempfile.mkdtemp())
        said = []
        got = fetch_assets({"seal": "https://x.test/a.svg", "board-logo": "https://x.test/b.png"}, d,
                           fetch=lambda url: b"DATA:" + url.encode(), say=said.append)
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["board-logo.png", "seal.svg"])
        self.assertEqual((d / "seal.svg").read_bytes(), b"DATA:https://x.test/a.svg")
        self.assertEqual(got, 2)

    def test_one_failure_does_not_stop_the_other(self):
        d = Path(tempfile.mkdtemp())
        said = []

        def fetch(url):
            if "a.svg" in url:
                raise OSError("offline")
            return b"ok"
        got = fetch_assets({"seal": "https://x.test/a.svg", "board-logo": "https://x.test/b.png"}, d, fetch=fetch, say=said.append)
        self.assertEqual(got, 1)
        self.assertTrue((d / "board-logo.png").exists())
        self.assertTrue(any("offline" in s for s in said))

    def test_an_empty_url_is_skipped(self):
        d = Path(tempfile.mkdtemp())
        self.assertEqual(fetch_assets({"seal": "", "board-logo": ""}, d, fetch=lambda u: b"x", say=lambda s: None), 0)


unittest.main() if __name__ == "__main__" else None
