"""The HTTP layer, against a real engine with fake lanes."""
import asyncio
import base64
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import io
import zipfile
from pathlib import Path

from fakes import FakeBrowser
from results_race.config import Config
from results_race.engine import Engine
from results_race.server import App, render_page
from test_hedge import FakeLane


def OK(name, gpa):
    return ("ok", {"status": 0, "res": {"name": name, "res_detail": gpa, "board_name": "B", "roll_no": "111",
                                         "display_details": "101:A"}, "sub_details": []})


def basic(user, pw):
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()}


class Fixture:
    def __init__(self, cfg=None, browser=None, outcome=None, **engine_kw):
        self.cfg = cfg or Config()
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.loop_thread.start()
        lane = FakeLane("a", "https://a.test", **({"outcome": outcome} if outcome else {}))
        self.engine = Engine(browser, [("111", "9"), ("222", "8")], {"board": "b", "exam": "ssc", "year": "2024"}, tempfile.mkdtemp(),
                             lanes=[lane], hedge_s=1, timeout_s=1, **engine_kw)
        self.app = App(self.cfg, self.engine, self.loop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.http_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.http_thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def call(self, path, body=None, headers=None, with_headers=False, timeout=5):
        req = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return (r.status, r.read(), dict(r.headers)) if with_headers else (r.status, r.read())
        except urllib.error.HTTPError as e:
            return (e.code, e.read(), dict(e.headers)) if with_headers else (e.code, e.read())

    def finish(self, sid):
        """Give a student a saved result, the way a lookup would."""
        self.engine.lanes[0].status = "ready"
        self.loop.call_soon_threadsafe(self.engine.solve, "a", sid, "1234")
        for _ in range(100):
            if next(s for s in self.engine.students if s.id == sid).status == "done":
                return
            threading.Event().wait(0.02)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.http_thread.join(5)
        async def cancel_pending():
            for task in asyncio.all_tasks() - {asyncio.current_task()}:
                task.cancel()
        asyncio.run_coroutine_threadsafe(cancel_pending(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop_thread.join(5)
        self.loop.close()


class ServerTest(unittest.TestCase):
    def test_page_and_state(self):
        f = Fixture()
        self.addCleanup(f.close)
        code, body = f.call("/")
        self.assertEqual(code, 200)
        self.assertIn(b"Results race", body)
        state = json.loads(f.call("/state")[1])
        self.assertEqual([s["roll"] for s in state["students"]], ["111", "222"])
        self.assertEqual(state["offer"]["lane"], "a")

    def test_title_theme_and_captcha_length_come_from_configuration(self):
        cfg = Config()
        cfg.ui.title, cfg.ui.theme, cfg.ui.captcha_min_length = "Class of <2026>", "dark", 5
        page = render_page(cfg).decode()
        self.assertIn("Class of &lt;2026&gt;", page)
        self.assertNotIn("<2026>", page)
        self.assertIn("'dark'", page)
        self.assertNotIn("__", page.replace("__proto__", ""))  # every placeholder was filled

    def test_login_is_enforced_when_configured_and_absent_when_not(self):
        cfg = Config()
        cfg.server.auth = "me:pw"
        f = Fixture(cfg)
        self.addCleanup(f.close)
        self.assertEqual(f.call("/")[0], 401)
        self.assertEqual(f.call("/state", headers=basic("me", "bad"))[0], 401)
        self.assertEqual(f.call("/reset", {}, headers=None)[0], 401)  # writes are protected too
        self.assertEqual(f.call("/state", headers=basic("me", "pw"))[0], 200)
        open_ = Fixture()
        self.addCleanup(open_.close)
        self.assertEqual(open_.call("/state")[0], 200)

    def test_adding_a_student_through_the_api_and_its_validation(self):
        f = Fixture()
        self.addCleanup(f.close)
        ok = json.loads(f.call("/add", {"roll": "100001", "reg": "2100000001", "exam": "ssc", "year": "2024"})[1])
        self.assertTrue(ok["ok"])
        bad = json.loads(f.call("/add", {"roll": "x", "reg": "1", "exam": "ssc", "year": "2024"})[1])
        self.assertFalse(bad["ok"])

    def test_adding_can_be_disabled(self):
        f = Fixture(allow_manual=False)
        self.addCleanup(f.close)
        self.assertFalse(json.loads(f.call("/add", {"roll": "100001", "reg": "2100000001", "exam": "ssc", "year": "2024"})[1])["ok"])
        self.assertFalse(json.loads(f.call("/state")[1])["can_add"])

    def test_sheet_routes_are_off_when_the_card_is_disabled(self):
        f = Fixture(card_enabled=False)
        self.addCleanup(f.close)
        self.assertEqual(f.call("/result/111")[0], 404)
        self.assertEqual(f.call("/png/111")[0], 404)
        self.assertFalse(json.loads(f.call("/state")[1])["card"])

    def test_png_download_is_named_after_the_student_and_result(self):
        f = Fixture(browser=FakeBrowser(), outcome=OK("RAHIM UDDIN AHMED", "GPA=4.22"))
        self.addCleanup(f.close)
        f.finish("111")
        code, body, headers = f.call("/png/111", with_headers=True, timeout=20)
        self.assertEqual(code, 200)
        self.assertTrue(body.startswith(b"PNG:"))
        self.assertIn('filename="Rahim-Uddin-Ahmed_GPA-4.22_111.png"', headers["Content-Disposition"])

    def test_download_all_is_a_zip_of_every_finished_students_png(self):
        f = Fixture(browser=FakeBrowser(), outcome=OK("RAHIM UDDIN AHMED", "GPA=4.22"))
        self.addCleanup(f.close)
        f.finish("111")  # 222 stays pending
        code, body, headers = f.call("/png-all", with_headers=True, timeout=30)
        self.assertEqual((code, headers["Content-Type"]), (200, "application/zip"))
        self.assertIn("-A4-PNGs.zip", headers["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.namelist(), ["Rahim-Uddin-Ahmed_GPA-4.22_111.png"])
            self.assertTrue(z.read(z.namelist()[0]).startswith(b"PNG:"))

    def test_download_all_with_nothing_finished_or_the_sheet_off_is_a_404(self):
        f = Fixture(browser=FakeBrowser())
        self.addCleanup(f.close)
        self.assertEqual(f.call("/png-all")[0], 404)
        off = Fixture(browser=FakeBrowser(), outcome=OK("X", "GPA=4.00"), card_enabled=False)
        self.addCleanup(off.close)
        off.finish("111")
        self.assertEqual(off.call("/png-all")[0], 404)

    def test_a_failing_render_is_a_clean_error_not_a_dropped_connection(self):
        class BrokenBrowser(FakeBrowser):
            async def new_tab(self, url, proxy=None):
                raise RuntimeError("browser exploded")
        f = Fixture(browser=BrokenBrowser(), outcome=OK("X", "GPA=4.00"))
        self.addCleanup(f.close)
        f.finish("111")
        self.assertEqual(f.call("/png-all", timeout=20)[0], 500)
        self.assertEqual(f.call("/png/111", timeout=20)[0], 500)

    def test_download_all_needs_the_login_too(self):
        cfg = Config()
        cfg.server.auth = "me:pw"
        f = Fixture(cfg, browser=FakeBrowser(), outcome=OK("X", "GPA=4.00"))
        self.addCleanup(f.close)
        self.assertEqual(f.call("/png-all")[0], 401)

    def test_reload_lanes_endpoint(self):
        f = Fixture()
        self.addCleanup(f.close)
        self.assertEqual(f.call("/lanes/reload", {})[0], 200)
        for _ in range(50):
            if getattr(f.engine.lanes[0], "reloaded", 0):
                break
            threading.Event().wait(0.02)
        self.assertEqual(f.engine.lanes[0].reloaded, 1)

    def test_unknown_routes_and_bad_bodies(self):
        f = Fixture()
        self.addCleanup(f.close)
        self.assertEqual(f.call("/nope")[0], 404)
        self.assertEqual(f.call("/nope", {})[0], 404)
        req = urllib.request.Request(f.base + "/solve", data=b"{not json")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(cm.exception.code, 400)

    def test_path_tricks_never_reach_the_filesystem(self):
        f = Fixture()
        self.addCleanup(f.close)
        for path in ("/result/../../etc/passwd", "/result/%2e%2e/%2e%2e/etc/passwd", "/png/../x", "/assets/../../etc/passwd"):
            self.assertEqual(f.call(path)[0], 404, path)

    def test_the_seal_is_served_only_if_present_and_enabled(self):
        cfg = Config()
        cfg.card.assets_dir = tempfile.mkdtemp()
        f = Fixture(cfg)
        self.addCleanup(f.close)
        self.assertEqual(f.call("/assets/seal")[0], 404)
        (f.app.assets / "seal.svg").write_text("<svg/>")
        self.assertEqual(f.call("/assets/seal")[0], 200)
        cfg.card.logos = False
        self.assertEqual(f.call("/assets/seal")[0], 404)


unittest.main() if __name__ == "__main__" else None
