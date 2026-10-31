"""Takes the README's screenshots by running `results-race demo` for real and photographing it.
    python tools/art/make_screenshots.py [--out docs/img]
Needs the package installed (pip install -e .) and a Chromium. Everything shown is the demo's made-up data."""
import argparse
import asyncio
import base64
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from results_race.cdp import Browser
from results_race.demo import captcha_digits

ROOT = Path(__file__).resolve().parents[2]


class App:
    """The demo app, running as a child process."""

    def __init__(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc = subprocess.Popen([sys.executable, "-m", "results_race", "demo", "--port", str(self.port),
                                      "--set", "card.png_scale=2", "--set", "ui.credit=BazarLab by Siyam"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT)

    def call(self, path, body=None, raw=False):
        req = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode())
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        return data if raw else json.loads(data)

    def state(self):
        return self.call("/state")

    def wait(self, cond, seconds=60, what="the app"):
        end = time.time() + seconds
        while time.time() < end:
            try:
                if cond(self.state()):
                    return
            except OSError:
                pass
            time.sleep(0.25)
        raise SystemExit(f"timed out waiting for {what}")

    def type_captcha(self):
        """What a person does: look at the offered captcha, type its digits."""
        self.wait(lambda s: s["offer"], what="a captcha")
        offer = self.state()["offer"]
        self.call("/solve", {"lane": offer["lane"], "id": offer["id"], "captcha": captcha_digits(offer["img"])})
        return offer

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


async def page(browser, app, width, height, mobile=False, scale=1.5):
    tab = await browser.new_tab("about:blank")
    await tab.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=scale, mobile=mobile)
    await tab.goto(app.base + "/")
    await asyncio.sleep(2)
    return tab


async def shoot(tab, path):
    await tab.eval("window.scrollTo(0, 0)")
    await asyncio.sleep(0.3)
    shot = await tab.call("Page.captureScreenshot", format="png")
    Path(path).write_bytes(base64.b64decode(shot["data"]))
    print(f"wrote {path}  ({Path(path).stat().st_size // 1024} KB)")


async def main(out):
    out.mkdir(parents=True, exist_ok=True)
    app = App()
    browser = Browser()
    try:
        app.wait(lambda s: sum(l["status"] == "ready" for l in s["lanes"]) == 3, what="the three lanes")
        await browser.start()
        light = await page(browser, app, 1280, 780)  # open the page first: the slow moment is over in a couple of seconds
        for _ in range(8):  # eight students done, the way you would: type, wait for it to land (one of them failed)
            n = sum(s["status"] == "done" for s in app.state()["students"])
            app.type_captcha()
            app.wait(lambda s: sum(x["status"] == "done" for x in s["students"]) > n, what="a result")

        # catch the app switching away from the slow mirror: type a captcha for it, wait out the 1 s
        for _ in range(30):
            app.wait(lambda s: s["offer"], what="a captcha")
            if app.state()["offer"]["lane"].startswith("mirror-c"):
                break
            app.call("/reload", {"lane": app.state()["offer"]["lane"]})
            time.sleep(0.5)
        slow = app.type_captcha()
        app.wait(lambda s: any(x["id"] == slow["id"] and x["status"] == "pending" and x["msg"] for x in s["students"]), 20, "the switch")
        time.sleep(0.9)  # the page polls twice a second
        await shoot(light, out / "app-light.png")
        await light.eval("localStorage.theme='dark';document.documentElement.dataset.theme='dark'")
        await shoot(light, out / "app-dark.png")
        await light.eval("localStorage.theme='light';document.documentElement.dataset.theme='light'")

        app.wait(lambda s: all(x["id"] != slow["id"] or x["status"] == "done" for x in s["students"]), 30, "the slow answer")
        phone = await page(browser, app, 390, 1180, mobile=True, scale=2)
        await shoot(phone, out / "app-phone.png")

        best = max((s for s in app.state()["students"] if s["status"] == "done" and s["gpa"] and float(s["gpa"]) > 0),
                   key=lambda s: float(s["gpa"]))
        dialog = await page(browser, app, 1280, 780)
        await dialog.eval(f"openResult('{best['id']}')")
        await asyncio.sleep(2.2)
        await shoot(dialog, out / "result-dialog.png")

        (out / "sheet-sample.png").write_bytes(app.call(f"/png/{best['id']}", raw=True))
        print(f"wrote {out / 'sheet-sample.png'}  ({(out / 'sheet-sample.png').stat().st_size // 1024} KB)")
    finally:
        browser.closing = True
        try:
            await browser.close()
        except Exception:  # noqa: BLE001 - it may never have started
            pass
        app.stop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "docs" / "img"))
    asyncio.run(main(Path(ap.parse_args().out)))
