import tempfile
import unittest
from pathlib import Path

from results_race.cli import card_style
from results_race.config import Config, load


class CardStyleTest(unittest.TestCase):
    def test_the_configured_texts_reach_the_sheet(self):
        cfg = Config()
        cfg.card.header_line, cfg.card.board_title, cfg.card.sheet_title = "Line one", "A Board", "MARKSHEET"
        cfg.card.footer_note, cfg.card.show_fetch_time, cfg.card.assets_dir = "Note.", False, tempfile.mkdtemp()
        style = card_style(cfg)
        self.assertEqual((style.header_line, style.board_title, style.sheet_title, style.footer_note, style.show_fetch_time),
                         ("Line one", "A Board", "MARKSHEET", "Note.", False))

    def test_the_credit_reaches_the_sheet_and_can_be_blanked(self):
        cfg = Config()
        cfg.card.assets_dir = tempfile.mkdtemp()
        self.assertEqual(card_style(cfg).credit, "BazarLab by Siyam")
        cfg.card.credit = ""
        self.assertEqual(card_style(cfg).credit, "")

    def test_logos_come_from_the_assets_folder_and_can_be_off(self):
        cfg = Config()
        cfg.card.assets_dir = tempfile.mkdtemp()
        (Path(cfg.card.assets_dir) / "seal.svg").write_text("<svg/>")
        self.assertTrue(card_style(cfg).seal)
        cfg.card.logos = False
        self.assertEqual(card_style(cfg).seal, "")


class DemoCommandTest(unittest.TestCase):
    def test_demo_is_a_command(self):
        self.assertEqual(load(["demo"])[1].command, "demo")


unittest.main() if __name__ == "__main__" else None
