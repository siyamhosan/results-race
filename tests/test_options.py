"""Every behaviour that can be switched off or pointed elsewhere."""
import asyncio
import tempfile
import unittest

from results_race.card import CardStyle
from types import SimpleNamespace as NS

from results_race.engine import Engine, Lane, build_lanes
from test_hedge import FakeLane

CFG = {"board": "rajshahi", "exam": "ssc", "year": "2024"}
OK = ("ok", {"status": 0, "res": {"name": "N", "res_detail": "GPA=4.00", "board_name": "B", "roll_no": "111"}})


def engine(lanes, **kw):
    return Engine(None, [("111", "9")], CFG, tempfile.mkdtemp(), lanes=lanes, timeout_s=1, **kw)


class OptionsTest(unittest.IsolatedAsyncioTestCase):
    async def test_switching_can_be_turned_off(self):
        slow = FakeLane("slow", "https://a.test", delay=0.2, outcome=OK)
        eng = engine([slow, FakeLane("other", "https://b.test")], hedge_s=0)
        eng.solve("slow", "111", "1234")
        await asyncio.sleep(0.1)
        self.assertEqual(eng.students[0].status, "inflight")  # still waiting, not handed to another site
        await asyncio.sleep(0.2)
        self.assertEqual(eng.students[0].status, "done")

    async def test_manual_adding_can_be_turned_off(self):
        eng = engine([FakeLane("a", "https://a.test")], hedge_s=1, allow_manual=False)
        with self.assertRaises(ValueError):
            eng.add_student("100001", "2100000001", "ssc", "2024")

    async def test_the_result_type_and_board_come_from_the_run_settings(self):
        lane = FakeLane("a", "https://a.test", outcome=OK)
        eng = Engine(None, [("111", "9")], {**CFG, "result_type": "3"}, tempfile.mkdtemp(), lanes=[lane], hedge_s=1, timeout_s=1)
        eng.solve("a", "111", "1234")
        await asyncio.sleep(0.05)
        self.assertEqual((lane.fields["board"], lane.fields["result_type"]), ("rajshahi", "3"))

    async def test_sheet_uses_the_configured_style_and_can_be_disabled(self):
        lane = FakeLane("a", "https://a.test", outcome=OK)
        eng = engine([lane], hedge_s=1, card_style=CardStyle(header_line="My Republic"))
        eng.solve("a", "111", "1234")
        await asyncio.sleep(0.05)
        self.assertIn("My Republic", eng.card_html("111"))
        off = engine([FakeLane("a", "https://a.test", outcome=OK)], hedge_s=1, card_enabled=False)
        off.solve("a", "111", "1234")
        await asyncio.sleep(0.05)
        self.assertIsNone(off.card_html("111"))


class LaneConfigTest(unittest.TestCase):
    def test_sites_and_paths_are_taken_from_configuration(self):
        paths = {"home": "/x/home", "captcha": "/x/cap", "result": "/x/res"}
        lanes = build_lanes(None, ["https://one.test", "https://two.test"], 1, [], paths)
        self.assertEqual([l.site for l in lanes], ["https://one.test", "https://two.test"])
        self.assertIn("'/x/cap?t='", lanes[0].captcha_js)
        self.assertIn("'/x/res'", lanes[0].submit_js(1000, {"a": "b"}))
        self.assertEqual(lanes[0].home_url, "https://one.test/x/home")

    def test_load_timeout_reaches_every_lane_including_proxied_twins(self):
        lanes = build_lanes(None, ["https://one.test"], 1, ["h:1"], load_s=75)
        self.assertEqual([l.load_s for l in lanes], [75, 75])
        self.assertEqual(Lane(None, "https://one.test", 0).load_s, 20)

    def test_default_paths_match_the_known_result_app(self):
        lane = Lane(None, "https://one.test", 0)
        self.assertEqual(lane.home_url, "https://one.test/v2/home")
        self.assertIn("/v2/captcha", lane.captcha_js)





class WarmupTest(unittest.IsolatedAsyncioTestCase):
    """Starting every browser session at once can exhaust a small server's memory, so it can be bounded."""

    class SlowWarm:
        running = peak = 0

        def __init__(self, id):
            self.id, self.site, self.status, self.latency, self.fetched = id, "https://a.test", "warming", 0, 0

        async def warm(self):
            cls = WarmupTest.SlowWarm
            cls.running += 1
            cls.peak = max(cls.peak, cls.running)
            await asyncio.sleep(0.05)
            cls.running -= 1
            self.status = "ready"

    async def started(self, parallel):
        WarmupTest.SlowWarm.running = WarmupTest.SlowWarm.peak = 0
        lanes = [WarmupTest.SlowWarm(f"l{i}") for i in range(6)]
        eng = Engine(None, [], CFG, tempfile.mkdtemp(), lanes=lanes, warmup_parallel=parallel)
        task = asyncio.create_task(eng.run())
        for _ in range(100):
            if all(l.status == "ready" for l in lanes):
                break
            await asyncio.sleep(0.02)
        task.cancel()
        return lanes, WarmupTest.SlowWarm.peak

    async def test_unbounded_by_default_everything_starts_together(self):
        lanes, peak = await self.started(0)
        self.assertEqual((peak, [l.status for l in lanes].count("ready")), (6, 6))

    async def test_bounded_batches_never_exceed_the_limit_and_still_finish(self):
        lanes, peak = await self.started(2)
        self.assertEqual((peak, [l.status for l in lanes].count("ready")), (2, 6))

    async def test_a_lane_that_never_settles_does_not_stall_the_rest(self):
        class Stuck(WarmupTest.SlowWarm):
            async def warm(self):
                await asyncio.sleep(60)  # e.g. a site that is down: this lane keeps retrying
        eng = Engine(None, [], CFG, tempfile.mkdtemp(), lanes=[Stuck("s"), WarmupTest.SlowWarm("ok")], warmup_parallel=1,
                     warmup_wait_s=0.2)
        task = asyncio.create_task(eng.run())
        await asyncio.sleep(0.6)
        task.cancel()
        self.assertEqual(eng.lanes[1].status, "ready")


class ReloadLanesTest(unittest.IsolatedAsyncioTestCase):
    async def test_every_lane_except_a_busy_one_is_reloaded(self):
        ready, stuck, busy = (FakeLane(n, "https://a.test") for n in "rsb")
        stuck.status, busy.status = "cooldown", "busy"
        eng = engine([ready, stuck, busy], hedge_s=1)
        self.assertEqual(eng.reload_lanes(), 2)
        self.assertEqual([getattr(l, "reloaded", 0) for l in (ready, stuck, busy)], [1, 1, 0])

    async def test_a_stuck_lane_gets_a_brand_new_session_and_becomes_ready(self):
        made, closed = [], []

        class Tab:
            def __init__(self, n):
                self.n = n

            async def eval(self, js):
                return True if "location.pathname" in js else "data:image/png;base64,AA"

            async def close(self):
                closed.append(self.n)

        class Browser:
            async def new_tab(self, url, proxy=None):
                made.append(url)
                return Tab(len(made))

        lane = Lane(Browser(), "https://a.test", 0)
        lane.tab, lane.status, lane.fails = Tab(0), "cooldown", 3
        lane.reload()
        for _ in range(60):
            if lane.status == "ready":
                break
            await asyncio.sleep(0.05)
        self.assertEqual((lane.status, lane.fails, closed, len(made)), ("ready", 0, [0], 1))  # old tab closed, one new session

    async def test_a_ready_lane_just_gets_a_fresh_captcha(self):
        class Tab:
            async def eval(self, js):
                return "data:image/png;base64,NEW"

        lane = Lane(None, "https://a.test", 0)
        lane.tab, lane.status, lane.img, lane.ver = Tab(), "ready", "OLD", 1
        lane.reload()
        for _ in range(40):
            if lane.status == "ready" and lane.img == "data:image/png;base64,NEW":
                break
            await asyncio.sleep(0.02)
        self.assertEqual((lane.img, lane.ver), ("data:image/png;base64,NEW", 2))


unittest.main() if __name__ == "__main__" else None
