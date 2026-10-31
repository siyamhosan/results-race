import json
import tempfile
import unittest
from unittest import mock

import core


def fake_open(responses):
    class R:
        def __init__(self, b): self.b = b
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): pass
    it = iter(responses)
    return lambda *a, **k: R(next(it))


class SlotTest(unittest.TestCase):
    def slot(self, responses):
        s = core.Slot(2100000001, tempfile.mkdtemp())
        s.opener = mock.Mock(open=fake_open(responses))
        return s

    def test_success_saves_file(self):
        s = self.slot([json.dumps("<html>card</html>").encode()])
        s.submit("abcd")
        self.assertEqual(s.status, "done")
        self.assertIn("card", (s.out / "2100000001.html").read_text())

    def test_wrong_captcha_reloads(self):
        s = self.slot([json.dumps({"err": 1, "msg": "Please Enter Security Key Correctly."}).encode(), b"jpg"])
        s.submit("bad")
        self.assertEqual((s.status, s.captcha), ("ready", b"jpg"))

    def test_other_error_fails(self):
        s = self.slot([json.dumps({"err": 1, "msg": "No record found"}).encode()])
        s.submit("abcd")
        self.assertEqual((s.status, s.msg), ("failed", "No record found"))

    def test_form_and_base_are_configurable(self):
        s = core.Slot(1, tempfile.mkdtemp(), {"exam": "ssc", "exam_year": "2024"}, base="https://example.test/")
        self.assertEqual((s.form["exam"], s.form["exam_year"], s.form["district"], s.base), ("ssc", "2024", "rajshahi", "https://example.test"))

    def test_no_data_is_skipped(self):
        s = self.slot([json.dumps({"err": 1, "msg": "No data found"}).encode()])
        s.submit("abcd")
        self.assertEqual(s.status, "skipped")


unittest.main() if __name__ == "__main__" else None
