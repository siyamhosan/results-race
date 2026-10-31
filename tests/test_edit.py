"""Fixing a roll or registration number typed wrong."""
import json
import tempfile
import unittest
from pathlib import Path

from results_race.engine import Engine
from test_hedge import FakeLane

CFG = {"board": "rajshahi", "exam": "hsc", "year": "2026"}
LISTED = [("200001", "2100000001"), ("200002", "2100000002")]


def engine(out, students=LISTED):
    return Engine(None, students, CFG, out, lanes=[FakeLane("a", "https://a.test")], hedge_s=1, timeout_s=1)


class EditTest(unittest.IsolatedAsyncioTestCase):
    async def test_a_manual_student_gets_its_registration_fixed_and_is_queued_again(self):
        out = tempfile.mkdtemp()
        eng = engine(out)
        s = eng.add_student("100001", "2100000009", "ssc", "2024")
        s.status, s.msg = "failed", "No data found"
        eng.edit_student(s.id, "100001", "2100000001")
        self.assertEqual((s.reg, s.status, s.msg), ("2100000001", "pending", ""))
        again = engine(out)  # and it is still fixed after a restart
        self.assertEqual([(x.roll, x.reg) for x in again.students if x.manual], [("100001", "2100000001")])

    async def test_changing_the_roll_changes_the_id_and_deletes_the_result_saved_under_the_old_one(self):
        out = tempfile.mkdtemp()
        eng = engine(out)
        s = eng.add_student("100001", "2100000001", "ssc", "2024")
        saved = Path(out) / "manual" / f"{s.id}.json"
        saved.parent.mkdir(exist_ok=True)
        saved.write_text("{}")
        s.status = "done"
        eng.edit_student(s.id, "100002", "2100000001")
        self.assertEqual(s.id, "100002-ssc2024")
        self.assertFalse(saved.exists())
        self.assertEqual(s.status, "pending")

    async def test_a_listed_student_can_be_fixed_too_and_it_sticks_across_a_restart(self):
        out = tempfile.mkdtemp()
        eng = engine(out)
        eng.edit_student("200001", "200001", "2100000099")
        self.assertEqual(eng.students[0].reg, "2100000099")
        again = engine(out)  # the list still says the old number; the edit is applied on top
        self.assertEqual([(s.roll, s.reg) for s in again.students], [("200001", "2100000099"), ("200002", "2100000002")])
        again.edit_student("200001", "200003", "2100000099")  # a second fix of the same student, now with a new roll
        third = engine(out)
        self.assertEqual(third.students[0].roll, "200003")

    async def test_bad_numbers_a_duplicate_or_a_lookup_in_progress_are_refused(self):
        eng = engine(tempfile.mkdtemp())
        with self.assertRaisesRegex(ValueError, "Registration"):
            eng.edit_student("200001", "200001", "12")
        with self.assertRaisesRegex(ValueError, "Already"):
            eng.edit_student("200001", "200002", "2100000001")
        with self.assertRaisesRegex(ValueError, "No such"):
            eng.edit_student("999999", "200009", "2100000001")
        eng.students[0].status = "inflight"
        with self.assertRaisesRegex(ValueError, "right now"):
            eng.edit_student("200001", "200001", "2100000007")
        self.assertEqual(eng.students[0].reg, "2100000001")

    async def test_turned_off_with_the_add_option(self):
        eng = engine(tempfile.mkdtemp())
        eng.allow_manual = False
        with self.assertRaisesRegex(ValueError, "turned off"):
            eng.edit_student("200001", "200001", "2100000007")
