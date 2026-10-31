"""The demo: fake mirror sites and fictional students, so the app can be tried (and photographed) with no real site."""
import http.cookiejar
import json
import re
import tempfile
import time
import unittest
import urllib.parse
import urllib.request

from results_race.card import render
from results_race.config import Config
from results_race.demo import DEMO_STUDENTS, Mirror, apply_demo, captcha_digits, demo_result
from results_race.engine import classify
from results_race.students import load_students


class Client:
    """One browser-like visitor: keeps its own cookies, so its captcha is its own."""

    def __init__(self, mirror):
        self.base = f"http://127.0.0.1:{mirror.port}"
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(self, path):
        with self.opener.open(self.base + path, timeout=10) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()

    def digits(self):
        _, ctype, body = self.get("/v2/captcha?t=1")
        assert ctype.startswith("image/"), ctype  # the app only accepts an image
        return captcha_digits(body.decode())

    def lookup(self, roll, reg, captcha, exam="ssc", year="2024"):
        data = urllib.parse.urlencode({"board": "demo", "exam": exam, "year": year, "result_type": "1", "roll": roll,
                                       "reg": reg, "captcha": captcha}).encode()
        with self.opener.open(self.base + "/v2/getres", data, timeout=10) as r:
            return r.status, r.read().decode()


class CaptchaDigitsTest(unittest.TestCase):
    """The demo writes its digits in the picture's <desc>, so scripts and tests can 'type' them. Demo only."""

    def test_reads_the_digits_from_raw_svg_or_from_the_data_url_the_app_offers(self):
        import base64
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><desc>4713</desc></svg>'
        self.assertEqual(captcha_digits(svg), "4713")
        self.assertEqual(captcha_digits("data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()), "4713")

    def test_a_picture_without_digits_is_an_error_not_a_guess(self):
        with self.assertRaises(ValueError):
            captcha_digits("<svg xmlns='http://www.w3.org/2000/svg'/>")


class MirrorTest(unittest.TestCase):
    def setUp(self):
        self.mirror = Mirror("mirror-a")
        self.mirror.start()
        self.addCleanup(self.mirror.stop)
        self.roll, self.reg, _ = DEMO_STUDENTS[0]

    def test_home_page_has_the_form_the_app_waits_for(self):
        _, ctype, body = Client(self.mirror).get("/v2/home")
        self.assertIn("text/html", ctype)
        self.assertIn(b'id="form"', body)

    def test_the_right_digits_give_a_result_the_app_accepts(self):
        c = Client(self.mirror)
        kind, data = classify(*c.lookup(self.roll, self.reg, c.digits()))
        self.assertEqual(kind, "ok")
        self.assertEqual(data["res"]["roll_no"], self.roll)

    def test_wrong_digits_are_a_bad_captcha_not_a_missing_result(self):
        c = Client(self.mirror)
        c.digits()
        self.assertEqual(classify(*c.lookup(self.roll, self.reg, "0000x"))[0], "bad_captcha")

    def test_a_captcha_works_once(self):
        c = Client(self.mirror)
        digits = c.digits()
        self.assertEqual(classify(*c.lookup(self.roll, self.reg, digits))[0], "ok")
        self.assertEqual(classify(*c.lookup(self.roll, self.reg, digits))[0], "bad_captcha")

    def test_visitors_have_separate_captchas(self):
        a, b = Client(self.mirror), Client(self.mirror)
        da, db = a.digits(), b.digits()
        self.assertEqual(classify(*a.lookup(self.roll, self.reg, da))[0], "ok")
        self.assertEqual(classify(*b.lookup(self.roll, self.reg, db))[0], "ok")

    def test_an_unknown_roll_or_wrong_reg_is_rejected(self):
        c = Client(self.mirror)
        self.assertEqual(classify(*c.lookup("999999", "1", c.digits()))[0], "rejected")
        self.assertEqual(classify(*c.lookup(self.roll, "0000000", c.digits()))[0], "rejected")

    def test_a_slow_mirror_really_is_slow(self):
        slow = Mirror("mirror-c", delay=0.4)
        slow.start()
        self.addCleanup(slow.stop)
        c = Client(slow)
        digits = c.digits()
        t0 = time.time()
        c.lookup(self.roll, self.reg, digits)
        self.assertGreaterEqual(time.time() - t0, 0.35)  # slept 0.4 s; allow for clock rounding

    def test_the_url_is_a_localhost_subdomain_so_each_mirror_gets_its_own_lane_name(self):
        self.assertRegex(self.mirror.url, r"^http://mirror-a\.localhost:\d+$")


class DemoDataTest(unittest.TestCase):
    def test_students_are_fictional_and_unique(self):
        rolls = [r for r, _, _ in DEMO_STUDENTS]
        self.assertEqual(len(rolls), len(set(rolls)))
        self.assertGreaterEqual(len(rolls), 10)

    def test_results_are_deterministic_and_include_a_failure(self):
        results = [demo_result(r, g, "ssc", "2024") for r, g, _ in DEMO_STUDENTS]
        self.assertEqual(results, [demo_result(r, g, "ssc", "2024") for r, g, _ in DEMO_STUDENTS])
        gpas = [x["res"]["res_detail"] for x in results]
        self.assertTrue(any(g == "GPA=0.00" for g in gpas))
        self.assertTrue(sum(g != "GPA=0.00" for g in gpas) >= 8)

    def test_every_demo_result_renders_as_a_sheet(self):
        for roll, reg, name in DEMO_STUDENTS:
            rec = {"site": "mirror-a.localhost", "ms": 900, "result": demo_result(roll, reg, "ssc", "2024")}
            html = render(rec, "ssc", 2024)
            self.assertIn(name, html)

    def test_apply_demo_points_the_config_at_the_mirrors_and_lists_the_students(self):
        cfg = Config()
        mirrors = apply_demo(cfg, tempfile.mkdtemp())
        self.addCleanup(lambda: [m.stop() for m in mirrors])
        self.assertEqual(len(cfg.sites.urls), 3)
        self.assertTrue(all(".localhost:" in u for u in cfg.sites.urls))
        self.assertEqual((cfg.proxies.file, cfg.card.logos), ("", False))
        self.assertEqual(len(load_students(cfg.students.file)), len(DEMO_STUDENTS))
        self.assertTrue(any(m.delay > 0 for m in mirrors))  # one slow mirror, so switching can be seen


unittest.main() if __name__ == "__main__" else None
