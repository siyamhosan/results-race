import unittest

from results_race.naming import content_disposition, png_filename, unique_names


class FilenameTest(unittest.TestCase):
    def test_name_result_and_roll(self):
        self.assertEqual(png_filename("MD. RAHIM UDDIN", "GPA=4.22", "100001"), "Md-Rahim-Uddin_GPA-4.22_100001.png")

    def test_failed_result_says_so_instead_of_a_zero_gpa(self):
        self.assertEqual(png_filename("RAHIM", "GPA=0.00", "7"), "Rahim_Not-Passed_7.png")

    def test_missing_pieces_are_left_out_not_shown_as_none(self):
        self.assertEqual(png_filename("", "GPA=4.00", "100001"), "Student_GPA-4.00_100001.png")
        self.assertEqual(png_filename("RAHIM", "", "100001"), "Rahim_100001.png")
        self.assertEqual(png_filename("RAHIM", None, ""), "Rahim.png")

    def test_punctuation_and_path_tricks_are_removed(self):
        name = png_filename("../../etc/passwd; MST. O'NEIL, JR.", "GPA=3.50", "1")
        self.assertEqual(name, "Etc-Passwd-Mst-Oneil-Jr_GPA-3.50_1.png")
        for bad in ("/", "\\", "..", ":", ";", "'", " "):
            self.assertNotIn(bad, name)

    def test_non_latin_names_are_kept(self):
        self.assertTrue(png_filename("রহিম উদ্দিন", "GPA=5.00", "1").startswith("রহিম-উদ্দিন_GPA-5.00"))

    def test_a_very_long_name_is_cut_short(self):
        self.assertLessEqual(len(png_filename("A" * 300, "GPA=4.00", "1")), 100)

    def test_other_result_text_is_kept_readable(self):
        self.assertEqual(png_filename("RAHIM", "Failed in 2 subjects", "1"), "Rahim_Failed-In-2-Subjects_1.png")

    def test_a_name_that_is_only_symbols_falls_back(self):
        self.assertEqual(png_filename("...///", "GPA=4.00", "1"), "Student_GPA-4.00_1.png")


class UniqueNamesTest(unittest.TestCase):
    def test_duplicates_get_a_counter_before_the_extension(self):
        self.assertEqual(unique_names(["a.png", "b.png", "a.png", "a.png"]), ["a.png", "b.png", "a-2.png", "a-3.png"])

    def test_already_unique_names_are_untouched(self):
        self.assertEqual(unique_names(["a.png", "b.png"]), ["a.png", "b.png"])


class ContentDispositionTest(unittest.TestCase):
    def test_plain_ascii_name(self):
        self.assertEqual(content_disposition("Rahim_GPA-4.22_1.png"),
                         "attachment; filename=\"Rahim_GPA-4.22_1.png\"; filename*=UTF-8''Rahim_GPA-4.22_1.png")

    def test_non_ascii_gets_an_ascii_fallback_and_the_real_name_encoded(self):
        header = content_disposition("রহিম_GPA-5.00_1.png")
        self.assertIn("filename*=UTF-8''%E0%A6%B0", header)
        ascii_part = header.split('filename="')[1].split('"')[0]
        self.assertTrue(ascii_part.isascii() and ascii_part.endswith(".png"))
        self.assertTrue(header.isascii())  # HTTP headers must be ASCII

    def test_quotes_cannot_break_out_of_the_header(self):
        self.assertNotIn('""', content_disposition('a"b.png').split("; filename*")[0].replace('filename=""', ""))
        self.assertEqual(content_disposition('a"b.png').count('"'), 2)


unittest.main() if __name__ == "__main__" else None
