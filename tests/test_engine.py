import json
import unittest
from types import SimpleNamespace as N

from results_race.engine import Student, classify, next_offer


class T(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(classify(200, json.dumps({"status": 0, "res": {}}))[0], "ok")
        self.assertEqual(classify(200, json.dumps({"status": 1, "msg": "Invalid Captcha"}))[0], "bad_captcha")
        self.assertEqual(classify(200, json.dumps({"status": 1, "msg": "Result not found"}))[0], "rejected")
        self.assertEqual(classify(200, json.dumps({"status": 1, "msg": "Result of HSC ... is not published/available (yet)."}))[0], "not_yet")
        self.assertEqual(classify(503, "<html>busy")[0], "site_error")
        self.assertEqual(classify(200, "<html>proxy error")[0], "site_error")

    def test_offer_prefers_fast_lane_and_first_pending(self):
        a, b = N(id="a", site="x", status="ready", latency=2), N(id="b", site="x", status="ready", latency=1)
        c = N(id="c", site="x", status="busy", latency=0.1)
        s1, s2 = Student(1, 1), Student(2, 2)
        s1.status = "done"
        self.assertEqual(next_offer([a, b, c], [s1, s2]), (b, s2))
        self.assertIsNone(next_offer([c], [s2]))


unittest.main() if __name__ == "__main__" else None
