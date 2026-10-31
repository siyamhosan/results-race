import tempfile
import unittest
from pathlib import Path

from results_race.card import CardStyle, load_logos, render

REC = {"site": "https://mirror.example", "ms": 1234, "result": {"status": 0, "res": {
    "name": "RAHIM UDDIN AHMED", "fname": "KARIM AHMED", "mname": "RAHIMA BEGUM", "roll_no": "100001",
    "regno": "2100000001", "session": "2022-23", "res_detail": "GPA=4.22", "board_name": "SAMPLE", "stud_group": "SCIENCE",
    "stud_type": "REGULAR", "dob": "01-01-2007", "inst_name": "SAMPLE HIGH SCHOOL", "t_name": "SADAR", "z_name": "SAMPLE",
    "display_details": "101:A ,107:A+,109:B", "display_details_ca": "147:A+"},
    "sub_details": [{"SUB_CODE": "101", "SUB_NAME": "BANGLA"}, {"SUB_CODE": "107", "SUB_NAME": "ENGLISH"},
                    {"SUB_CODE": "109", "SUB_NAME": "MATHEMATICS"}, {"SUB_CODE": "147", "SUB_NAME": "PHYSICAL EDUCATION"}]}}
LOGO = "data:image/png;base64,AAAA"


class CardTest(unittest.TestCase):
    def test_shows_student_result_and_subjects(self):
        h = render(REC, "ssc", 2024)
        for text in ["RAHIM UDDIN AHMED", "100001", "4.22", "PASSED", "BANGLA", "MATHEMATICS", "PHYSICAL EDUCATION",
                     "SAMPLE HIGH SCHOOL", "SSC", "2024", "Unofficial"]:
            self.assertIn(text, h)

    def test_logos_are_optional(self):
        self.assertNotIn("<img", render(REC, "ssc", 2024))  # nothing bundled, nothing drawn
        with_logos = render(REC, "ssc", 2024, CardStyle(seal=LOGO, board_logo=LOGO))
        self.assertEqual(with_logos.count(LOGO), 3)  # seal, board logo, watermark
        self.assertNotIn("http://", with_logos.replace("http://www.w3.org", ""))  # nothing fetched at render time

    def test_the_fonts_travel_inside_the_sheet(self):
        self.assertIn("data:font/woff2;base64,", render(REC, "ssc", 2024))

    def test_texts_are_configurable(self):
        h = render(REC, "ssc", 2024, CardStyle(header_line="Sample Republic", sheet_title="MARKSHEET", footer_note="Custom note."))
        for text in ["Sample Republic", "MARKSHEET", "Custom note."]:
            self.assertIn(text, h)
        self.assertNotIn("Unofficial", h)

    def test_fetch_time_can_be_hidden(self):
        self.assertIn("1.2s", render(REC, "ssc", 2024))
        self.assertNotIn("1.2s", render(REC, "ssc", 2024, CardStyle(show_fetch_time=False)))

    def test_text_is_escaped(self):
        rec = {**REC, "result": {**REC["result"], "res": {**REC["result"]["res"], "name": "<script>x</script>"}}}
        self.assertNotIn("<script>x", render(rec, "ssc", 2024))

    def test_failed_result_is_not_labelled_passed(self):
        rec = {**REC, "result": {**REC["result"], "res": {**REC["result"]["res"], "res_detail": "GPA=0.00"}}}
        h = render(rec, "ssc", 2024)
        self.assertIn("NOT PASSED", h)
        self.assertNotIn(">PASSED<", h)

    def test_grade_points_are_listed(self):
        h = render(REC, "ssc", 2024)
        self.assertIn(">5.00<", h)
        self.assertIn(">3.00<", h)


class LogoLoadingTest(unittest.TestCase):
    def folder(self, files=None):
        d = Path(tempfile.mkdtemp())
        for name, data in (files or {}).items():
            (d / name).write_bytes(data)
        return d

    def test_finds_logos_by_name_and_makes_data_uris(self):
        d = self.folder({"seal.svg": b"<svg/>", "board-logo.png": b"PNG"})
        style = load_logos(d)
        self.assertTrue(style.seal.startswith("data:image/svg+xml;base64,"))
        self.assertTrue(style.board_logo.startswith("data:image/png;base64,"))

    def test_missing_files_or_folder_just_mean_no_logos(self):
        self.assertEqual((load_logos(self.folder()).seal, load_logos(Path("/nonexistent")).board_logo), ("", ""))

    def test_can_be_switched_off(self):
        self.assertEqual(load_logos(self.folder({"seal.svg": b"<svg/>"}), enabled=False).seal, "")


unittest.main() if __name__ == "__main__" else None
