"""Download-all and file names, through the engine's public calls (fake lanes, fake browser)."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from fakes import FakeBrowser
from results_race.engine import Engine
from test_hedge import FakeLane

CFG = {"board": "rajshahi", "exam": "ssc", "year": "2024"}


def result(name="RAHIM UDDIN AHMED", gpa="GPA=4.00"):
    return ("ok", {"status": 0, "res": {"name": name, "res_detail": gpa, "board_name": "B", "roll_no": "111",
                                         "display_details": "101:A", "fname": "F", "mname": "M"}, "sub_details": []})


def engine(students, outcome=None, browser=None, **kw):
    lane = FakeLane("a", "https://a.test", outcome=outcome or result())
    eng = Engine(browser, students, CFG, tempfile.mkdtemp(), lanes=[lane], hedge_s=0, timeout_s=1, **kw)
    return eng, lane


async def solve_all(eng, ids):
    for sid in ids:
        eng.solve("a", sid, "1234")
        await asyncio.sleep(0.05)
        eng.lanes[0].status = "ready"


class PngAllTest(unittest.IsolatedAsyncioTestCase):
    async def test_the_file_name_has_the_name_the_result_and_the_roll(self):
        eng, _ = engine([("111", "9")])
        await solve_all(eng, ["111"])
        self.assertEqual(eng.png_name("111"), "Rahim-Uddin-Ahmed_GPA-4.00_111.png")
        self.assertEqual(eng.state()["students"][0]["png_name"], "Rahim-Uddin-Ahmed_GPA-4.00_111.png")

    async def test_a_student_without_a_result_has_no_file_name(self):
        eng, _ = engine([("111", "9")])
        self.assertIsNone(eng.png_name("111"))
        self.assertEqual(eng.state()["students"][0]["png_name"], "")

    async def test_all_collects_only_finished_students_in_list_order(self):
        eng, _ = engine([("111", "1"), ("222", "2"), ("333", "3")], browser=FakeBrowser())
        await solve_all(eng, ["333", "111"])  # 222 never gets a result
        got = await eng.card_png_all()
        self.assertEqual([n for n, _ in got], ["Rahim-Uddin-Ahmed_GPA-4.00_111.png", "Rahim-Uddin-Ahmed_GPA-4.00_333.png"])
        self.assertTrue(all(png.startswith(b"PNG:") for _, png in got))

    async def test_names_in_the_collection_are_unique(self):
        eng, _ = engine([("111", "1")], browser=FakeBrowser())
        await solve_all(eng, ["111"])
        eng.add_student("111", "100001", "hsc", "2026")  # same roll, name and GPA, another exam
        m = eng.students[0]
        eng.lanes[0].status = "ready"
        eng.solve("a", m.id, "1234")
        await asyncio.sleep(0.05)
        names = [n for n, _ in await eng.card_png_all()]
        self.assertEqual(len(names), 2)
        self.assertEqual(len(set(names)), 2)

    async def test_repeat_downloads_reuse_the_render_but_a_changed_result_is_rendered_again(self):
        browser = FakeBrowser()
        eng, _ = engine([("111", "1")], browser=browser)
        await solve_all(eng, ["111"])
        first = await eng.card_png("111")
        opened = browser.opened
        self.assertEqual(await eng.card_png("111"), first)
        self.assertEqual(browser.opened, opened)  # served from the cache: no browser tab opened
        path = Path(eng.out) / "111.json"
        rec = json.loads(path.read_text())
        rec["result"]["res"]["res_detail"] = "GPA=3.00"
        path.write_text(json.dumps(rec))
        self.assertNotEqual(await eng.card_png("111"), first)

    async def test_a_result_that_disappears_mid_collection_is_skipped_not_fatal(self):
        class ResetWhileRendering(FakeBrowser):
            async def new_tab(self, url, proxy=None):
                (Path(eng.out) / "222.json").unlink(missing_ok=True)  # someone pressed Reset all mid-render
                return await super().new_tab(url, proxy)
        eng, _ = engine([("111", "1"), ("222", "2")], browser=ResetWhileRendering())
        await solve_all(eng, ["111", "222"])
        got = await eng.card_png_all()
        self.assertEqual([n for n, _ in got], ["Rahim-Uddin-Ahmed_GPA-4.00_111.png"])

    async def test_nothing_to_collect_when_the_sheet_is_switched_off(self):
        eng, _ = engine([("111", "1")], browser=FakeBrowser(), card_enabled=False)
        await solve_all(eng, ["111"])
        self.assertEqual(await eng.card_png_all(), [])


unittest.main() if __name__ == "__main__" else None
