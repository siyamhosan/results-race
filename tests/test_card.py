import tempfile
import unittest
from pathlib import Path

from results_race.card import CardStyle, load_logos, parse_entry, render

REC = {"site": "https://mirror.example", "ms": 1234, "result": {"status": 0, "res": {
    "name": "RAHIM UDDIN AHMED", "fname": "KARIM AHMED", "mname": "RAHIMA BEGUM", "roll_no": "100001",
    "regno": "2100000001", "session": "2022-23", "res_detail": "GPA=4.22", "board_name": "SAMPLE", "stud_group": "SCIENCE",
    "stud_type": "REGULAR", "dob": "01-01-2007", "inst_name": "SAMPLE HIGH SCHOOL", "t_name": "SADAR", "z_name": "SAMPLE",
    "display_details": "101:A ,107:A+,109:B", "display_details_ca": "147:A+"},
    "sub_details": [{"SUB_CODE": "101", "SUB_NAME": "BANGLA"}, {"SUB_CODE": "107", "SUB_NAME": "ENGLISH"},
                    {"SUB_CODE": "109", "SUB_NAME": "MATHEMATICS"}, {"SUB_CODE": "147", "SUB_NAME": "PHYSICAL EDUCATION"}]}}
# the shape HSC 2026 answers in: marks before the grade, two papers sharing one code, a 4th subject, converted marks
HSC = {"site": "https://mirror.example", "ms": 900, "result": {"status": 0, "showmarks": 1, "res": {
    **REC["result"]["res"], "res_detail": "GPA=4.50", "tot_full": "1220", "conv_1000": "700.50", "sub4th": "125-126",
    "display_details": "101-102:171=A+,107-108:076=D,275:097=A+,125-126:060+40+80=180=A+", "display_details_ca": ""},
    "sub_details": [{"SUB_CODE": c, "SUB_NAME": n} for c, n in [
        ("101", "BANGLA"), ("102", "BANGLA"), ("107", "ENGLISH"), ("108", "ENGLISH"), ("275", "ICT"), ("125", "GEOGRAPHY"),
        ("126", "GEOGRAPHY")]]}}
LOGO = "data:image/png;base64,AAAA"


class CardTest(unittest.TestCase):
    def test_shows_student_result_and_subjects(self):
        h = render(REC, "ssc", 2024)
        for text in ["RAHIM UDDIN AHMED", "100001", "4.22", "PASSED", "BANGLA", "MATHEMATICS", "PHYSICAL EDUCATION",
                     "SAMPLE HIGH SCHOOL", "SSC", "2024", "Unofficial"]:
            self.assertIn(text, h)

    def test_parse_entry_reads_every_shape_the_site_uses(self):
        self.assertEqual(parse_entry("101:A+"), ("101", "", "A+"))
        self.assertEqual(parse_entry("101-102:171=A+"), ("101-102", "171", "A+"))
        self.assertEqual(parse_entry("275:097=A+"), ("275", "97", "A+"))
        self.assertEqual(parse_entry("125-126:060+40+80=180=A"), ("125-126", "180", "A"))

    def test_marks_sheet_shows_marks_names_points_and_the_fourth_subject(self):
        h = render(HSC, "hsc", 2026)
        self.assertIn("<th class=c>Marks</th>", h)
        self.assertEqual(h.count("BANGLA"), 1)  # two papers, one row
        for text in ["101-102", ">171<", ">97<", ">180<", "4th subject", "Converted marks (out of 1000): <b>700.50</b>"]:
            self.assertIn(text, h)
        self.assertNotIn("=A+", h)  # the grade column holds the grade only
        self.assertEqual(h.count('class="c pt">5.00'), 3)
        self.assertEqual(h.count('class="c pt">1.00'), 1)

    def test_grade_only_results_have_no_marks_column(self):
        h = render(REC, "ssc", 2024)
        self.assertNotIn("Marks", h)
        self.assertNotIn("Converted", h)

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

    def test_the_site_is_shown_without_its_scheme_whatever_it_is(self):
        for site in ("https://mirror.example", "http://mirror.localhost:8081"):
            h = render({**REC, "site": site}, "ssc", 2024)
            self.assertIn(site.split("//")[1], h)
            self.assertNotIn(site.split("//")[0] + "//", h)

    def test_the_credit_line_is_shown_when_set_and_absent_otherwise(self):
        self.assertNotIn("class=credit", render(REC, "ssc", 2024))  # the library default draws none
        h = render(REC, "ssc", 2024, CardStyle(credit="BazarLab by Siyam"))
        self.assertIn('<div class=credit>BazarLab by Siyam</div>', h)

    def test_the_credit_is_escaped(self):
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", render(REC, "ssc", 2024, CardStyle(credit="<b>x</b>")))

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
