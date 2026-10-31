import tempfile
import unittest
from pathlib import Path

from results_race.students import load_students


def f(name, text):
    p = Path(tempfile.mkdtemp()) / name
    p.write_text(text)
    return p


class StudentsFileTest(unittest.TestCase):
    def test_json_list_of_objects(self):
        self.assertEqual(load_students(f("s.json", '[{"roll": 100001, "reg": "2100000001"}, {"roll": "100002", "reg": "2100000002"}]')),
                         [("100001", "2100000001"), ("100002", "2100000002")])

    def test_csv_with_or_without_header(self):
        want = [("100001", "2100000001"), ("100002", "2100000002")]
        self.assertEqual(load_students(f("s.csv", "roll,reg\n100001,2100000001\n100002,2100000002\n")), want)
        self.assertEqual(load_students(f("s.csv", "100001,2100000001\n100002,2100000002\n")), want)
        self.assertEqual(load_students(f("s.csv", "reg,roll\n2100000001,100001\n2100000002,100002\n")), want)  # header decides the order

    def test_text_lines_with_comments_and_any_separator(self):
        text = "# my class\n100001 2100000001\n\n100002,2100000002   # trailing note\n100003\t2100000003\n"
        self.assertEqual(load_students(f("s.txt", text)), [("100001", "2100000001"), ("100002", "2100000002"), ("100003", "2100000003")])

    def test_duplicates_are_dropped_keeping_the_first(self):
        self.assertEqual(load_students(f("s.txt", "100001 1\n100001 2\n")), [("100001", "1")])

    def test_a_bad_line_is_reported_with_its_number(self):
        with self.assertRaises(ValueError) as cm:
            load_students(f("s.txt", "100001 2100000001\nhello\n"))
        self.assertIn("line 2", str(cm.exception))

    def test_missing_file_and_empty_path(self):
        with self.assertRaises(ValueError):
            load_students(Path("/nonexistent/students.json"))
        self.assertEqual(load_students(""), [])  # no file configured = start empty

    def test_unknown_extension_is_read_as_text(self):
        self.assertEqual(load_students(f("list", "100001 2100000001\n")), [("100001", "2100000001")])


unittest.main() if __name__ == "__main__" else None
