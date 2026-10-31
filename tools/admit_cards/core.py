"""Fetch admit cards from the Rajshahi board's public admit-card page; captchas are solved by a human."""
import http.cookiejar
import json
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://app.rajshahiboard.gov.bd"
FORM = {"board": "2", "exam": "hsc", "exam_year": "2026", "district": "rajshahi", "type": "public"}  # defaults; see app.py flags


class Slot:
    """One reg number with its own session, so its captcha stays valid while others are solved."""

    def __init__(self, reg, out_dir, form=None, base=BASE):
        self.reg, self.out, self.form, self.base = str(reg), Path(out_dir), {**FORM, **(form or {})}, base.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.opener.addheaders = [("User-Agent", "Mozilla/5.0")]
        self.captcha = None
        self.status = "loading"  # loading | ready | submitting | done | skipped | failed
        self.msg = ""
        self.lock = threading.Lock()

    def load_captcha(self):
        for attempt in range(6):  # the site answers 429 when hit too fast: back off and retry
            try:
                with self.opener.open(f"{self.base}/ajax/captcha.php?t={id(self)}", timeout=20) as r:
                    self.captcha = r.read()
                self.status = "ready"
                return
            except Exception as e:
                self.status, self.msg = "failed", f"captcha fetch: {e}"
                time.sleep(2 * (attempt + 1))

    def submit(self, text):
        """Post the typed captcha. Wrong captcha -> fresh captcha, status ready again."""
        self.status = "submitting"
        data = urllib.parse.urlencode({**self.form, "reg_no": self.reg, "captcha": text}).encode()
        try:
            with self.opener.open(f"{self.base}/eservice/archive/get_admit_card.php", data, timeout=60) as r:
                resp = json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            self.msg = f"request: {e}"
            return self.load_captcha()
        if isinstance(resp, dict) and resp.get("err"):
            self.msg = resp.get("msg", "error")
            if "Security Key" in self.msg:
                return self.load_captcha()
            self.status = "skipped" if "No data found" in self.msg else "failed"  # retyping the captcha won't help
            return
        html = f'<base href="{self.base}/">' + (resp if isinstance(resp, str) else json.dumps(resp))
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / f"{self.reg}.html").write_text(html, encoding="utf-8")
        self.status, self.msg = "done", "saved"
