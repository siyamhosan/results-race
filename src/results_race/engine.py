"""Race several result sites at once. Each lane is one isolated browser session on one site;
a human types the captcha, the lane submits it in the background."""
import asyncio
import base64
import json
import re
import time
from pathlib import Path

from .card import render
from .config import DEFAULT_SITES
from .naming import png_filename, unique_names

SITES = DEFAULT_SITES
DEFAULT_PATHS = {"home": "/v2/home", "captcha": "/v2/captcha", "result": "/v2/getres"}

FETCH_CAPTCHA = """(async()=>{const r=await fetch('__CAPTCHA__?t='+Date.now(),{credentials:'same-origin'});
const b=await r.blob();if(!r.ok||!b.type.startsWith('image'))throw new Error('captcha http '+r.status);
return await new Promise(ok=>{const f=new FileReader();f.onload=()=>ok(f.result);f.readAsDataURL(b)})})()"""

SUBMIT = """(async()=>{const ctl=new AbortController();setTimeout(()=>ctl.abort(),%d);
const r=await fetch('__RESULT__',{method:'POST',credentials:'same-origin',signal:ctl.signal,
headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With':'XMLHttpRequest'},
body:new URLSearchParams(%s).toString()});
return JSON.stringify({http:r.status,body:await r.text()})})()"""


def classify(http, body):
    """-> ('ok', data) | ('bad_captcha', msg) | ('not_yet', msg) | ('site_error', msg) | ('rejected', msg)"""
    if http >= 500 or http in (0, 429, 502, 503, 504):
        return "site_error", f"HTTP {http}"
    try:
        d = json.loads(body)
    except ValueError:
        return "site_error", f"HTTP {http}, not JSON"  # error pages / overload pages
    if isinstance(d, dict) and d.get("status") == 0:
        return "ok", d
    msg = str(d.get("msg", d)) if isinstance(d, dict) else str(d)
    low = msg.lower()
    return ("bad_captcha" if "captcha" in low else "not_yet" if "not published" in low else "rejected"), msg


def next_offer(lanes, students):
    """First student nobody is working on, paired with the fastest ready lane, avoiding sites that were just slow for them."""
    pending = [s for s in students if s.status == "pending"]
    if not pending:
        return None
    ready = sorted((l for l in lanes if l.status == "ready"), key=lambda l: (l.site in pending[0].avoid, l.latency))
    return (ready[0], pending[0]) if ready else None


class Student:
    def __init__(self, roll, reg, exam=None, year=None, manual=False):
        self.roll, self.reg, self.exam, self.year, self.manual = str(roll), str(reg), exam, year, manual
        self.id = f"{self.roll}-{exam}{year}" if manual else self.roll  # manual entries may reuse a roll from another exam
        self.reset()

    def reset(self):
        self.status, self.msg, self.site, self.ms, self.name, self.gpa, self.res_detail = "pending", "", "", 0, "", "", ""
        self.inflight, self.attempt, self.first_t, self.avoid = 0, 0, 0.0, set()

    def png_name(self):
        return png_filename(self.name, self.res_detail, self.roll)

    def view(self):
        return {"id": self.id, "manual": self.manual, "exam": self.exam, "year": self.year,
                "roll": self.roll, "reg": self.reg, "status": self.status, "msg": self.msg, "site": self.site, "ms": self.ms,
                "name": self.name, "gpa": self.gpa,
                "png_name": self.png_name() if self.status == "done" else ""}


class Lane:
    """One isolated browser session on one site, optionally behind a proxy."""

    def __init__(self, browser, site, k, proxy=None, n=0, paths=None, load_s=20):
        host = site.split("//")[1].replace("www.", "").split(".")[0]
        self.b, self.site, self.proxy = browser, site, proxy
        self.paths = {**DEFAULT_PATHS, **(paths or {})}
        self.load_s = load_s  # how long a page or captcha may take to load
        self.home_url = site + self.paths["home"]
        self.captcha_js = FETCH_CAPTCHA.replace("__CAPTCHA__", self.paths["captcha"])
        self.id = f"{host}-{k}" + (f"-p{n}" if proxy else "")  # n: which proxy, since several can share one gateway
        self.status, self.msg, self.latency = "warming", "", 9.9
        self.img, self.ver, self.fails, self.fetched, self.tab = None, 0, 0, 0.0, None
        self._task = None

    def start(self):
        self._task = asyncio.create_task(self.warm())

    def reload(self):
        """Fresh captcha if the lane is ready; a rebuilt browser session if it is stuck warming or cooling down.
        (A busy lane is waiting on a submitted lookup and is left alone by the caller.)"""
        if self.status == "ready":
            self.status = "warming"
            asyncio.create_task(self.refresh())
        elif self.status in ("warming", "cooldown"):
            asyncio.create_task(self._restart())

    async def _restart(self):
        if self._task:
            self._task.cancel()  # stops the retry loop that was holding this lane down
        old, self.tab, self.fails, self.msg = self.tab, None, 0, ""
        if old:
            try:
                await old.close()
            except Exception:  # noqa: BLE001 - a dead tab is exactly why we are here
                pass
        self.status = "warming"
        self.start()

    def submit_js(self, timeout_ms, fields):
        return (SUBMIT % (timeout_ms, json.dumps(fields))).replace("__RESULT__", self.paths["result"])

    async def warm(self):
        try:
            self.status = "warming"
            self.tab = self.tab or await self.b.new_tab(self.home_url, self.proxy)
            for _ in range(int(self.load_s * 4)):  # the site's own bot check redirects to /v2/home once it passes
                await asyncio.sleep(0.4)
                if await self.tab.eval(f"location.pathname=={json.dumps(self.paths['home'])}&&!!document.getElementById('form')"):
                    return await self.refresh()
            raise RuntimeError("bot check did not finish")
        except Exception as e:
            await self.recover(f"warm: {e}")

    async def refresh(self):
        t = time.time()
        try:
            self.img = await asyncio.wait_for(self.tab.eval(self.captcha_js), self.load_s)
            self.latency, self.fetched, self.fails = time.time() - t, time.time(), 0
            self.ver += 1
            self.status, self.msg = "ready", ""
        except Exception as e:
            await self.recover(f"captcha: {e}")

    async def recover(self, msg):
        """Back off and retry until the lane works again (iterative: no recursion however long a site is down)."""
        while True:
            self.fails += 1
            wait = min(2 ** self.fails, 30)
            self.status, self.msg = "cooldown", f"{msg} (retry {wait}s)"
            await asyncio.sleep(wait)
            try:
                if self.tab is None or self.fails >= 4:
                    self.tab = None
                    self.status = "warming"
                    self.tab = await self.b.new_tab(self.home_url, self.proxy)
                    await asyncio.sleep(2)
                self.img = await asyncio.wait_for(self.tab.eval(self.captcha_js), self.load_s)
                self.fetched, self.fails, self.ver, self.status, self.msg = time.time(), 0, self.ver + 1, "ready", ""
                return
            except Exception as e:
                msg = str(e)[:80]

    fail = recover

    async def submit(self, fields, timeout_ms=15000):
        js = self.submit_js(timeout_ms, fields)
        try:
            r = json.loads(await asyncio.wait_for(self.tab.eval(js), timeout_ms / 1000 + 5))
            return classify(r["http"], r["body"])
        except Exception as e:
            return "site_error", str(e)[:80]


def build_lanes(browser, sites, per_site, proxies, paths=None, load_s=20):
    """Direct lanes first; then every lane gets one extra twin per proxy."""
    base = [(s, k) for s in sites for k in range(per_site)]
    return [Lane(browser, s, k, paths=paths, load_s=load_s) for s, k in base] + \
           [Lane(browser, s, k, p, n, paths, load_s) for n, p in enumerate(proxies, 1) for s, k in base]


class Engine:
    def __init__(self, browser, students, cfg, out_dir, lanes_per_site=2, proxies=(), lanes=None,
                 hedge_s=1.0, timeout_s=15, *, sites=None, paths=None, card_style=None, card_enabled=True,
                 png_scale=3, allow_manual=True, warmup_parallel=0, warmup_wait_s=30.0, load_s=20):
        """cfg: {"board", "exam", "year", optional "result_type"}. hedge_s=0 turns switching off."""
        self.browser, self.cfg, self.out = browser, cfg, Path(out_dir)
        self.hedge_s, self.timeout_s = hedge_s, timeout_s
        self.warmup_parallel, self.warmup_wait_s = warmup_parallel, warmup_wait_s
        self._png_cache = {}  # student id -> ((mtime, size, scale), png): rendering costs about a second
        self.card_style, self.card_enabled, self.png_scale, self.allow_manual = card_style, card_enabled, png_scale, allow_manual
        self.students = [Student(*s) for s in students]
        self.lanes = lanes if lanes is not None else build_lanes(browser, sites or SITES, lanes_per_site, list(proxies), paths, load_s)
        self.out.mkdir(parents=True, exist_ok=True)
        self.manual_file = self.out / "manual.json"
        if self.manual_file.exists():  # manually added students come first, newest first, as saved
            self.students = [Student(m["roll"], m["reg"], m["exam"], m["year"], True)
                             for m in json.loads(self.manual_file.read_text())] + self.students
        for s in self.students:
            if self.path(s).exists():
                s.status, s.msg = "done", "already saved"
                self._fill(s, json.loads(self.path(s).read_text()))

    def path(self, stu):
        """Manual results live apart from the regular list: out/manual/<id>.json."""
        return self.out / "manual" / f"{stu.id}.json" if stu.manual else self.out / f"{stu.id}.json"

    def add_student(self, roll, reg, exam, year):
        if not self.allow_manual:
            raise ValueError("Adding students is turned off")
        roll, reg, exam, year = str(roll).strip(), str(reg).strip(), str(exam).strip().lower(), str(year).strip()
        if not re.fullmatch(r"\d{3,12}", roll):
            raise ValueError("Roll must be 3-12 digits")
        if not re.fullmatch(r"\d{4,15}", reg):
            raise ValueError("Registration must be 4-15 digits")
        if exam not in {"ssc", "hsc", "jsc", self.cfg["exam"]}:
            raise ValueError("Unknown exam")
        if not re.fullmatch(r"(19|20)\d{2}", year):
            raise ValueError("Year must look like 2026")
        stu = Student(roll, reg, exam, year, True)
        if any(s.id == stu.id for s in self.students):
            raise ValueError("Already in the list")
        self.students.insert(0, stu)
        self.manual_file.write_text(json.dumps([{"roll": s.roll, "reg": s.reg, "exam": s.exam, "year": s.year}
                                                for s in self.students if s.manual], indent=1))
        return stu

    @staticmethod
    def _fill(stu, rec):
        res = rec.get("result", {}).get("res", {})
        stu.ms, stu.site = rec.get("ms", 0), rec.get("site", "")
        stu.res_detail = res.get("res_detail") or ""
        stu.name, stu.gpa = res.get("name", ""), stu.res_detail.replace("GPA=", "")

    async def run(self):
        """Start the lanes - all at once, or in batches of `warmup_parallel` (each browser session costs memory, so
        a small server may need the limit). A batch is done when every lane is ready or cooling down; a lane that
        keeps failing never holds the next batch back for longer than `warmup_wait_s`."""
        n = self.warmup_parallel
        for batch in ([self.lanes[i:i + n] for i in range(0, len(self.lanes), n)] if n > 0 else [self.lanes]):
            for l in batch:
                l.start() if hasattr(l, "start") else asyncio.create_task(l.warm())
            waited = 0.0
            while any(l.status == "warming" for l in batch) and waited < self.warmup_wait_s:
                await asyncio.sleep(0.05)
                waited += 0.05
        while True:  # keep idle captchas fresh
            await asyncio.sleep(5)
            for l in self.lanes:
                if l.status == "ready" and time.time() - l.fetched > 150 and l is not self._offered_lane():
                    await l.refresh()

    def _offered_lane(self):
        o = next_offer(self.lanes, self.students)
        return o[0] if o else None

    def offer(self):
        o = next_offer(self.lanes, self.students)
        return o and {"lane": o[0].id, "id": o[1].id, "roll": o[1].roll, "reg": o[1].reg, "manual": o[1].manual, "exam": o[1].exam or self.cfg["exam"], "year": o[1].year or self.cfg["year"], "ver": o[0].ver, "img": o[0].img,
                      "site": o[0].site, "proxy": bool(o[0].proxy), "retry": bool(o[1].avoid)}

    def solve(self, lane_id, sid, text):
        lane = next((l for l in self.lanes if l.id == lane_id and l.status == "ready"), None)
        stu = next((s for s in self.students if s.id == sid and s.status == "pending"), None)
        if not (lane and stu):
            return
        lane.status, stu.status = "busy", "inflight"
        stu.inflight += 1
        stu.attempt += 1
        stu.first_t = stu.first_t or time.time()
        if self.hedge_s > 0:
            asyncio.create_task(self._hedge(stu, stu.attempt, lane.site))
        asyncio.create_task(self._submit(lane, stu, text))

    def reload_lanes(self):
        """Recover without a restart: every lane except one mid-lookup gets a fresh captcha or a rebuilt session."""
        lanes = [l for l in self.lanes if l.status != "busy"]
        for l in lanes:
            l.reload()
        return len(lanes)

    def reload(self, lane_id):
        """Skip an unreadable captcha: get a fresh one for the same lane."""
        lane = next((l for l in self.lanes if l.id == lane_id and l.status == "ready"), None)
        if lane:
            lane.status = "warming"
            asyncio.create_task(lane.refresh())

    async def _hedge(self, stu, attempt, site):
        """No answer within hedge_s: put the student back in the queue for another site, keep waiting on this one."""
        await asyncio.sleep(self.hedge_s)
        if stu.status == "inflight" and stu.attempt == attempt:
            stu.status, stu.msg = "pending", f"slow on {site.split('//')[1]} - try another"
            stu.avoid.add(site)

    async def _submit(self, lane, stu, text):
        fields = {**self.cfg, "exam": stu.exam or self.cfg["exam"], "year": stu.year or self.cfg["year"],
                  "result_type": self.cfg.get("result_type", "1"), "roll": stu.roll, "reg": stu.reg, "eiin": "", "dcode": "", "ccode": "",
                  "captcha": text}
        kind, data = await lane.submit(fields, int(self.timeout_s * 1000))
        stu.inflight -= 1
        if kind == "ok" and stu.status != "done":  # first answer wins, whether it came fast or late
            rec = {"exam": fields["exam"], "year": fields["year"], "ms": int((time.time() - stu.first_t) * 1000),
                   "site": lane.site, "roll": stu.roll, "reg": stu.reg, "result": data}
            self.path(stu).parent.mkdir(exist_ok=True)
            self.path(stu).write_text(json.dumps(rec, indent=2, ensure_ascii=False))
            self._fill(stu, rec)
            stu.status, stu.msg = "done", "saved"
        elif kind != "ok" and stu.status != "done":
            stu.msg = str(data)
            if kind == "rejected":  # wrong roll/reg etc.: retyping won't change it
                stu.status = "failed"
            elif stu.inflight == 0 and stu.status == "inflight":  # bad captcha, results not out, site error
                stu.status = "pending"
        await (lane.fail(str(data)) if kind == "site_error" else lane.refresh())

    def card_html(self, sid):
        stu = self._student(sid)
        if not self.card_enabled or not stu or not self.path(stu).exists():
            return None
        rec = json.loads(self.path(stu).read_text())
        return render(rec, rec.get("exam", self.cfg["exam"]), rec.get("year", self.cfg["year"]), self.card_style)

    def _student(self, sid):
        return next((s for s in self.students if s.id == sid), None)  # a lookup, never a path built from a request

    def png_name(self, sid):
        """e.g. Md-Rahim-Uddin_GPA-4.22_100001.png - or None while the student has no result."""
        stu = self._student(sid)
        return stu.png_name() if stu and stu.status == "done" else None

    async def card_png(self, sid, scale=None):
        """High-quality PNG: screenshot the A4 card in the headless browser (png_scale x pixel density). Cached until
        the saved result changes."""
        stu = self._student(sid)
        if not self.card_enabled or not stu or not self.path(stu).exists():
            return None
        scale = scale or self.png_scale
        stat = self.path(stu).stat()
        key = (stat.st_mtime_ns, stat.st_size, scale)
        if (hit := self._png_cache.get(sid)) and hit[0] == key:
            return hit[1]
        html = self.card_html(sid)
        tab = await self.browser.new_tab("data:text/html;charset=utf-8;base64," + base64.b64encode(html.encode()).decode())
        try:
            await asyncio.sleep(0.7)
            await tab.call("Emulation.setDeviceMetricsOverride", width=794, height=1123, deviceScaleFactor=scale, mobile=False)
            await asyncio.sleep(0.3)
            shot = await tab.call("Page.captureScreenshot", format="png",
                                  clip={"x": 0, "y": 0, "width": 794, "height": 1123, "scale": 1})
            png = base64.b64decode(shot["data"])
        finally:
            await tab.close()
        self._png_cache[sid] = (key, png)
        return png

    async def card_png_all(self):
        """[(file name, png)] for every finished student, in list order, one at a time (each render opens a browser tab).
        Names are taken up front and a result that vanishes meanwhile (e.g. Reset all) is skipped, not fatal."""
        if not self.card_enabled:
            return []
        ready = [(s.id, s.png_name()) for s in self.students if s.status == "done" and self.path(s).exists()]
        rendered = [(name, png) for sid, name in ready if (png := await self.card_png(sid)) is not None]
        return list(zip(unique_names([n for n, _ in rendered]), [p for _, p in rendered]))

    def reset(self, everything=False):
        """Failed -> pending; with everything, also forget saved results (files deleted) so a test can rerun."""
        for s in self.students:
            if s.status == "failed" or (everything and s.status in ("done", "pending")):
                if s.status == "done":
                    self.path(s).unlink(missing_ok=True)
                s.reset()

    def state(self):
        return {"cfg": self.cfg, "card": self.card_enabled, "can_add": self.allow_manual, "students": [s.view() for s in self.students],
                "lanes": [{"id": l.id, "status": l.status, "msg": l.msg, "ms": int(l.latency * 1000),
                           "proxy": l.proxy.label if l.proxy else "", "site": l.site} for l in self.lanes]}
