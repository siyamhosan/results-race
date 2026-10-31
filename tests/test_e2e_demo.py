"""The whole app against the demo mirrors with a real headless Chromium: captcha -> lookup -> saved result -> A4 PNG.
Skipped when there is no Chromium (everything else in the suite needs no browser)."""
import asyncio
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from results_race.cdp import Browser
from results_race.cli import build_engine
from results_race.config import Config
from results_race.demo import DEMO_STUDENTS, apply_demo, captcha_digits
from results_race.students import load_students

CHROME = shutil.which("chromium") or shutil.which("google-chrome-stable") or shutil.which("google-chrome")


@unittest.skipUnless(CHROME, "needs Chromium or Chrome")
class EndToEndTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cfg = Config()
        self.mirrors = apply_demo(self.cfg, tempfile.mkdtemp())
        self.browser = Browser()
        await self.browser.start()
        self.engine = build_engine(self.cfg, self.browser, load_students(self.cfg.students.file), [])
        self.runner = asyncio.create_task(self.engine.run())

    async def asyncTearDown(self):
        self.runner.cancel()
        self.browser.closing = True
        await self.browser.close()
        for m in self.mirrors:
            m.stop()

    async def until(self, cond, seconds=40):
        for _ in range(int(seconds * 10)):
            if cond():
                return True
            await asyncio.sleep(0.1)
        return False

    async def type_captcha(self):
        """Do what a person does: look at the offered captcha, read the digits, type them."""
        self.assertTrue(await self.until(lambda: self.engine.offer()))
        offer = self.engine.offer()
        self.engine.solve(offer["lane"], offer["id"], captcha_digits(offer["img"]))
        return offer

    async def test_a_lookup_goes_from_captcha_to_a_saved_result_and_an_a4_png(self):
        roll, _, name = DEMO_STUDENTS[0]
        offer = await self.type_captcha()
        self.assertEqual(offer["id"], roll)
        self.assertTrue(await self.until(lambda: self.engine.students[0].status == "done"))
        stu = self.engine.students[0]
        self.assertEqual(stu.name, name)
        self.assertTrue((Path(self.cfg.output.dir) / f"{roll}.json").exists())
        self.assertTrue(re.fullmatch(r"[A-Z][a-z]+(-[A-Z][a-z]+)*_GPA-\d\.\d\d_200001\.png", self.engine.png_name(roll)))
        png = await self.engine.card_png(roll)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertGreater(len(png), 20_000)

    async def test_the_credit_is_visible_on_the_sheet_inside_the_page_and_clear_of_the_footer_text(self):
        """Measured in a real browser, for a normal sheet and a crowded one (14 subjects)."""
        import base64
        import json
        from results_race.card import render
        from results_race.demo import demo_result
        res = demo_result(*DEMO_STUDENTS[0][:2], "ssc", "2024")
        crowded = json.loads(json.dumps(res))
        extra = [(str(300 + i), f"EXTRA SUBJECT NUMBER {i}") for i in range(4)]
        crowded["sub_details"] += [{"SUB_CODE": c, "SUB_NAME": n} for c, n in extra]
        crowded["res"]["display_details"] += "," + ",".join(f"{c}:A+" for c, _ in extra)
        for result in (res, crowded):
            html = render({"site": "http://m.localhost:1", "ms": 900, "result": result}, "ssc", 2024, self.engine.card_style)
            tab = await self.browser.new_tab("data:text/html;charset=utf-8;base64," + base64.b64encode(html.encode()).decode())
            await asyncio.sleep(0.8)
            m = json.loads(await tab.eval("""(()=>{const r=e=>{const b=document.querySelector(e).getBoundingClientRect();return [b.top,b.bottom]};
              const spans=[...document.querySelectorAll('.foot span')].map(s=>{const b=s.getBoundingClientRect();return b.bottom});
              return JSON.stringify({page:document.querySelector('.page').scrollHeight,credit:r('.credit'),footBottom:Math.max(...spans),
                                     text:document.querySelector('.credit').textContent})})()"""))
            await tab.close()
            self.assertEqual(m["text"], "BazarLab by Siyam")
            self.assertEqual(m["page"], 1123)  # still exactly one A4 page
            self.assertLessEqual(m["credit"][1], 1123)  # inside it
            self.assertGreaterEqual(m["credit"][0], m["footBottom"])  # and not on top of the footer text

    async def test_a_wrong_captcha_is_retried_not_lost(self):
        self.assertTrue(await self.until(lambda: self.engine.offer()))
        offer = self.engine.offer()
        self.engine.solve(offer["lane"], offer["id"], "0000")  # the digits are four random ones: this is wrong (or 1 in 10000)
        stu = self.engine.students[0]
        # the site's rejection can take a while (the slow mirror needs 3 s), and in between the app may already have
        # switched the student to another site ("slow on ... try another"): wait for the rejection itself
        self.assertTrue(await self.until(lambda: "Security Key" in stu.msg or stu.status == "done"))
        self.assertIn(stu.status, ("pending", "done"))  # back in the queue, never lost or failed
        if stu.status == "pending":
            self.assertTrue(await self.until(lambda: self.engine.offer()))  # and a fresh captcha is waiting


    async def test_a_wrong_captcha_on_the_slow_mirror_switches_sites_first_then_is_rejected(self):
        slow = next(l for l in self.engine.lanes if l.id.startswith("mirror-c"))
        self.assertTrue(await self.until(lambda: slow.status == "ready"))
        stu = self.engine.students[0]
        self.engine.solve(slow.id, stu.id, "0000")
        self.assertTrue(await self.until(lambda: stu.msg.startswith("slow on"), 10))  # after 1 s: try another site
        self.assertEqual(stu.status, "pending")  # back in the queue while the slow lane is still thinking
        self.assertTrue(await self.until(lambda: "Security Key" in stu.msg, 15))  # 3 s later the rejection arrives
        self.assertEqual(stu.status, "pending")  # still queued, nothing lost


unittest.main() if __name__ == "__main__" else None
