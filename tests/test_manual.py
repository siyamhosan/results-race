"""Manually added students: own file, own exam/year, survive a restart."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from results_race.engine import Engine
from test_hedge import FakeLane

CFG = {"board": "rajshahi", "exam": "hsc", "year": "2026"}


def engine(out, lanes=None):
    return Engine(None, [("111", "9")], CFG, out, lanes=lanes or [FakeLane("a", "https://a.test")], hedge_s=1, timeout_s=1)


class ManualTest(unittest.IsolatedAsyncioTestCase):
    async def test_added_student_is_queued_first_and_marked_manual(self):
        eng = engine(tempfile.mkdtemp())
        s = eng.add_student("100001", "2100000001", "ssc", "2024")
        self.assertEqual(eng.students[0].id, s.id)
        self.assertEqual(eng.offer()["id"], s.id)
        self.assertTrue(eng.state()["students"][0]["manual"])

    async def test_survives_restart(self):
        out = tempfile.mkdtemp()
        engine(out).add_student("100001", "2100000001", "ssc", "2024")
        again = engine(out)
        self.assertEqual([(s.roll, s.reg, s.exam, s.year) for s in again.students if s.manual],
                         [("100001", "2100000001", "ssc", "2024")])

    async def test_duplicate_is_not_added_twice_but_same_roll_other_exam_is(self):
        eng = engine(tempfile.mkdtemp())
        eng.add_student("100001", "2100000001", "ssc", "2024")
        with self.assertRaises(ValueError):
            eng.add_student("100001", "2100000001", "ssc", "2024")
        eng.add_student("100001", "2100000001", "hsc", "2026")
        self.assertEqual(len([s for s in eng.students if s.manual]), 2)

    async def test_bad_input_is_rejected(self):
        eng = engine(tempfile.mkdtemp())
        for roll, reg, exam, year in [("12a", "1", "ssc", "2024"), ("123", "", "ssc", "2024"), ("123", "1", "xyz", "2024"),
                                      ("123", "1", "ssc", "24")]:
            with self.assertRaises(ValueError, msg=(roll, reg, exam, year)):
                eng.add_student(roll, reg, exam, year)

    async def test_looks_up_with_its_own_exam_and_saves_in_a_separate_place(self):
        out = Path(tempfile.mkdtemp())
        lane = FakeLane("a", "https://a.test", outcome=("ok", {"status": 0, "res": {"name": "N", "res_detail": "GPA=4.00"}}))
        eng = engine(out, [lane])
        s = eng.add_student("100001", "2100000001", "ssc", "2024")
        eng.solve("a", s.id, "1234")
        await asyncio.sleep(0.05)
        self.assertEqual((lane.fields["exam"], lane.fields["year"], lane.fields["roll"], lane.fields["reg"]),
                         ("ssc", "2024", "100001", "2100000001"))
        self.assertEqual(s.status, "done")
        self.assertTrue((out / "manual" / f"{s.id}.json").exists())
        self.assertFalse((out / "100001.json").exists())
        self.assertEqual(json.loads((out / "manual" / f"{s.id}.json").read_text())["exam"], "ssc")
        self.assertIn("N", eng.card_html(s.id))  # the sheet is served from that file

    async def test_regular_students_are_unchanged(self):
        out = Path(tempfile.mkdtemp())
        eng = engine(out)
        eng.solve("a", "111", "1234")
        await asyncio.sleep(0.05)
        self.assertTrue((out / "111.json").exists())


unittest.main() if __name__ == "__main__" else None
