"""`results-race demo`: try the whole app with no real site and no real student.

It starts three fake mirror sites on localhost (one of them slow, so you can watch the app switch away from it) and a
list of made-up students. The captcha is a picture of four digits and a lookup needs them typed correctly, exactly like
the real thing, but the digits are also written in the picture's <desc>, so a script (or a test) can read them.
"""
import base64
import html
import http.server
import json
import random
import re
import threading
import time
import urllib.parse
import uuid
from pathlib import Path

# (roll, registration, name): all invented
DEMO_STUDENTS = [
    ("200001", "2200000001", "ANIKA RAHMAN"), ("200002", "2200000002", "TANVIR HOSSAIN"),
    ("200003", "2200000003", "NUSRAT JAHAN"), ("200004", "2200000004", "FAHIM CHOWDHURY"),
    ("200005", "2200000005", "SADIA ISLAM"), ("200006", "2200000006", "RAFI AHMED"),
    ("200007", "2200000007", "MEHERUN NESA"), ("200008", "2200000008", "ARIF KHAN"),
    ("200009", "2200000009", "TAHMINA AKTER"), ("200010", "2200000010", "IMRAN SARKER"),
    ("200011", "2200000011", "LABONI DAS"), ("200012", "2200000012", "SHAKIB MONDAL"),
]
FAILING = "200008"  # one student who did not pass, so the sheet's "not passed" look is part of the demo
SUBJECTS = [("101", "BANGLA"), ("107", "ENGLISH"), ("109", "MATHEMATICS"), ("111", "ISLAM AND MORAL EDUCATION"),
            ("150", "BANGLADESH AND GLOBAL STUDIES"), ("136", "PHYSICS"), ("137", "CHEMISTRY"), ("138", "BIOLOGY"),
            ("154", "INFORMATION AND COMMUNICATION TECHNOLOGY"), ("126", "HIGHER MATHEMATICS")]
CO_CURRICULAR = [("147", "PHYSICAL EDUCATION, HEALTH & SPORTS"), ("156", "CAREER EDUCATION")]
POINTS = {"A+": 5, "A": 4, "A-": 3.5, "B": 3, "C": 2, "D": 1, "F": 0}
BAD_CAPTCHA = "Could not validate your provided Security Key / CAPTCHA. Please check and try again."
NOT_FOUND = "Result not found. Please check the roll and registration number."


def demo_result(roll, reg, exam, year):
    """The made-up result for a demo student (None if roll and reg do not match one). Same input, same output."""
    found = next((s for s in DEMO_STUDENTS if s[0] == str(roll) and s[1] == str(reg)), None)
    if not found:
        return None
    rnd = random.Random(int(roll))
    grades = [rnd.choices(["A+", "A", "A-", "B", "C"], weights=[5, 6, 3, 2, 1])[0] for _ in SUBJECTS]
    if roll == FAILING:
        grades[rnd.randrange(len(grades))] = "F"
    gpa = 0.0 if "F" in grades else round(sum(POINTS[g] for g in grades) / len(grades), 2)
    ca = [rnd.choice(["A+", "A"]) for _ in CO_CURRICULAR]
    def show(pairs, gs):
        return ",".join(f"{code}:{g:<2}" for (code, _), g in zip(pairs, gs))
    return {"status": 0, "msg": "Success", "res": {
        "name": found[2], "fname": "A DEMO FATHER", "mname": "A DEMO MOTHER", "roll_no": roll, "regno": reg,
        "session": "2022-23", "res_detail": f"GPA={gpa:.2f}", "board_name": "DEMO", "stud_group": "SCIENCE",
        "stud_type": "REGULAR", "dob": f"{1 + int(roll) % 27:02d}-0{1 + int(roll) % 9}-2008", "inst_name": "SAMPLE HIGH SCHOOL",
        "t_name": "SADAR", "z_name": "SAMPLE", "display_details": show(SUBJECTS, grades),
        "display_details_ca": show(CO_CURRICULAR, ca)},
        "sub_details": [{"SUB_CODE": c, "SUB_NAME": n} for c, n in SUBJECTS + CO_CURRICULAR]}


def captcha_svg(digits, rnd):
    """A 160x70 picture of the digits with a gradient, noise lines and a little jitter. The digits are also in <desc>."""
    c1, c2 = (f"hsl({rnd.randrange(360)},35%,{rnd.randrange(55, 80)}%)" for _ in range(2))
    noise = "".join(f'<path d="M{rnd.randrange(160)} {rnd.randrange(70)} Q{rnd.randrange(160)} {rnd.randrange(70)} '
                    f'{rnd.randrange(160)} {rnd.randrange(70)}" stroke="hsl({rnd.randrange(360)},40%,30%)" stroke-width="1.4" fill="none"/>'
                    for _ in range(6))
    glyphs = "".join(f'<text x="{18 + i * 34}" y="{47 + rnd.randrange(-6, 7)}" font-size="{rnd.randrange(34, 42)}" font-weight="700" '
                     f'font-family="Verdana,DejaVu Sans,sans-serif" fill="#fff" stroke="#222" stroke-width="1.1" '
                     f'transform="rotate({rnd.randrange(-18, 19)} {28 + i * 34} 40)">{d}</text>' for i, d in enumerate(digits))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="70" viewBox="0 0 160 70"><desc>{digits}</desc>'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/>'
            f'<stop offset="1" stop-color="{c2}"/></linearGradient></defs><rect width="160" height="70" fill="url(#g)"/>'
            f'{noise}{glyphs}</svg>')


def captcha_digits(img):
    """The four digits of a demo captcha, from the SVG text or from the data: URL the app offers. Demo only: the real
    sites' captchas are never read by the app, a person reads them."""
    if img.startswith("data:"):
        img = base64.b64decode(img.split(",", 1)[1]).decode()
    found = re.search(r"<desc>(\d{4})</desc>", img)
    if not found:
        raise ValueError("no digits in this picture")
    return found.group(1)


class Mirror:
    """One fake result site: /v2/home, /v2/captcha and /v2/getres, like the real result app. `delay` makes it slow."""

    def __init__(self, name, delay=0.0):
        self.name, self.delay = name, delay
        self.port = None
        self._digits = {}  # visitor cookie -> the digits of the captcha they were last shown
        self._lock = threading.Lock()
        self._rnd = random.Random()

    @property
    def url(self):
        # *.localhost resolves to this machine in Chromium, and gives every mirror its own name (so its own lane id)
        return f"http://{self.name}.localhost:{self.port}"

    def start(self):
        mirror = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def sid(self):
                for part in (self.headers.get("Cookie") or "").split(";"):
                    k, _, v = part.strip().partition("=")
                    if k == "sid" and v:
                        return v, False
                return uuid.uuid4().hex, True

            def send(self, body, ctype, sid=None, fresh=False, code=200):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                if fresh:
                    self.send_header("Set-Cookie", f"sid={sid}; Path=/; HttpOnly")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urllib.parse.urlsplit(self.path).path
                sid, fresh = self.sid()
                if path == "/v2/home":
                    page = (f'<!doctype html><title>{html.escape(mirror.name)} - demo result site</title>'
                            f'<form id="form"><p>Demo result site "{html.escape(mirror.name)}". Not a real site.</p></form>')
                    self.send(page.encode(), "text/html; charset=utf-8", sid, fresh)
                elif path == "/v2/captcha":
                    with mirror._lock:
                        digits = "".join(str(mirror._rnd.randrange(10)) for _ in range(4))
                        mirror._digits[sid] = digits
                        svg = captcha_svg(digits, mirror._rnd)
                    self.send(svg.encode(), "image/svg+xml", sid, fresh)
                else:
                    self.send(b"{}", "application/json", code=404)

            def do_POST(self):
                if urllib.parse.urlsplit(self.path).path != "/v2/getres":
                    return self.send(b"{}", "application/json", code=404)
                form = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode())
                def field(k):
                    return (form.get(k) or [""])[0].strip()
                time.sleep(mirror.delay)
                sid, _ = self.sid()
                with mirror._lock:
                    expected = mirror._digits.pop(sid, None)  # a captcha works once
                if expected is None or field("captcha") != expected:
                    body = {"status": 1, "msg": BAD_CAPTCHA}
                else:
                    body = demo_result(field("roll"), field("reg"), field("exam"), field("year")) or {"status": 1, "msg": NOT_FOUND}
                self.send(json.dumps(body).encode(), "application/json")

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self.url

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def apply_demo(cfg, workdir):
    """Point a config at fake mirrors and made-up students (in `workdir`). Returns the running mirrors; stop them when done."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    mirrors = [Mirror("mirror-a", delay=0.35), Mirror("mirror-b", delay=0.6), Mirror("mirror-c", delay=3.0)]  # c is slower than the 1 s switch, so the app visibly moves on
    cfg.sites.urls = [m.start() for m in mirrors]
    cfg.sites.lanes_per_site = 1
    (workdir / "students.json").write_text(json.dumps([{"roll": r, "reg": g} for r, g, _ in DEMO_STUDENTS], indent=1))
    cfg.students.file = str(workdir / "students.json")
    cfg.output.dir = str(workdir / "out")
    cfg.proxies.file = ""
    cfg.run.board, cfg.run.exam, cfg.run.year = "demo", "ssc", "2024"
    cfg.card.logos = False
    cfg.card.header_line = "Demonstration - every name and result here is made up"
    cfg.card.board_title = "Sample Examination Board"
    cfg.card.footer_note = "Demo data. Not a real result."
    return mirrors
