"""Engine behaviour through its public calls (offer / solve / state), with fake lanes standing in for the network."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from results_race.engine import Engine


class FakeLane:
    def __init__(self, id, site, delay=0.0, outcome=("ok", {"status": 0, "res": {"name": "X"}}), latency=0.1):
        self.id, self.site, self.delay, self.outcome, self.latency = id, site, delay, outcome, latency
        self.status, self.img, self.ver, self.msg, self.proxy = "ready", "img", 1, "", None

    async def submit(self, fields, timeout_ms=0):
        self.fields = fields
        await asyncio.sleep(self.delay)
        return self.outcome

    def reload(self):
        self.reloaded = getattr(self, "reloaded", 0) + 1

    async def refresh(self):
        self.ver += 1
        self.status = "ready"

    async def fail(self, msg):
        self.status = "ready"


def make(lanes, hedge_s=0.05):
    out = tempfile.mkdtemp()
    return Engine(None, [("111", "9")], {"exam": "ssc", "year": "2024"}, out, lanes=lanes, hedge_s=hedge_s, timeout_s=1), Path(out)


class HedgeTest(unittest.IsolatedAsyncioTestCase):
    async def test_fast_result_is_saved(self):
        a = FakeLane("a", "https://a.test")
        eng, out = make([a])
        eng.solve("a", "111", "1234")
        await asyncio.sleep(0.05)
        self.assertEqual(eng.students[0].status, "done")
        self.assertEqual(json.loads((out / "111.json").read_text())["site"], "https://a.test")

    async def test_slow_lane_frees_student_for_another_site_after_hedge_delay(self):
        slow, other = FakeLane("slow", "https://a.test", delay=0.5), FakeLane("other", "https://b.test")
        eng, _ = make([slow, other])
        eng.solve("slow", "111", "1234")
        self.assertEqual(eng.students[0].status, "inflight")
        await asyncio.sleep(0.12)
        self.assertEqual(eng.students[0].status, "pending")
        self.assertEqual(eng.offer()["lane"], "other")

    async def test_offer_avoids_the_slow_site_even_if_its_other_lane_is_faster(self):
        slow = FakeLane("slow", "https://a.test", delay=0.5)
        sameSiteFast = FakeLane("same", "https://a.test", latency=0.01)
        otherSiteSlower = FakeLane("diff", "https://b.test", latency=0.9)
        eng, _ = make([slow, sameSiteFast, otherSiteSlower])
        eng.solve("slow", "111", "1234")
        await asyncio.sleep(0.12)
        self.assertEqual(eng.offer()["lane"], "diff")

    async def test_late_result_from_first_lane_is_used_when_nothing_else_arrived(self):
        slow = FakeLane("slow", "https://a.test", delay=0.25)
        eng, out = make([slow])
        eng.solve("slow", "111", "1234")
        await asyncio.sleep(0.12)
        self.assertEqual(eng.students[0].status, "pending")
        await asyncio.sleep(0.3)
        self.assertEqual(eng.students[0].status, "done")
        self.assertEqual(json.loads((out / "111.json").read_text())["site"], "https://a.test")

    async def test_late_loser_does_not_overwrite_the_winner(self):
        slow, fast = FakeLane("slow", "https://a.test", delay=0.3), FakeLane("fast", "https://b.test")
        eng, out = make([slow, fast])
        eng.solve("slow", "111", "1234")
        await asyncio.sleep(0.12)
        eng.solve("fast", "111", "5678")
        await asyncio.sleep(0.05)
        self.assertEqual(eng.students[0].status, "done")
        await asyncio.sleep(0.4)  # the slow one finally answers
        self.assertEqual(json.loads((out / "111.json").read_text())["site"], "https://b.test")

    async def test_failure_of_hedged_attempt_does_not_clobber_newer_attempt(self):
        slow = FakeLane("slow", "https://a.test", delay=0.2, outcome=("site_error", "HTTP 503"))
        other = FakeLane("other", "https://b.test", delay=0.4)
        eng, _ = make([slow, other])
        eng.solve("slow", "111", "1234")
        await asyncio.sleep(0.12)
        eng.solve("other", "111", "5678")
        await asyncio.sleep(0.15)  # slow failed at 0.2; the newer attempt is still running
        self.assertIn(eng.students[0].status, ("inflight", "pending"))
        self.assertNotEqual(eng.students[0].status, "failed")
        await asyncio.sleep(0.4)
        self.assertEqual(eng.students[0].status, "done")

    async def test_new_captcha_replaces_the_offered_image(self):
        a = FakeLane("a", "https://a.test")
        eng, _ = make([a])
        before = eng.offer()["ver"]
        eng.reload("a")
        await asyncio.sleep(0.02)
        self.assertGreater(eng.offer()["ver"], before)
        self.assertEqual(eng.students[0].status, "pending")  # nobody was charged for skipping


unittest.main() if __name__ == "__main__" else None
