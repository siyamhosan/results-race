"""The page you type captchas into, and the small JSON API behind it."""
import asyncio
import html as htmllib
import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .assets import default_dir
from .auth import authorized

STATIC = Path(__file__).parent / "static"


def render_page(cfg):
    """The one HTML file, with the user's title / theme / captcha length filled in."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    values = {"__TITLE__": htmllib.escape(cfg.ui.title), "__THEME__": cfg.ui.theme, "__MINLEN__": str(int(cfg.ui.captcha_min_length))}
    for key, value in values.items():  # theme is validated to light/dark/auto and the length to an int, so only the title needs escaping
        html = html.replace(key, value)
    return html.encode("utf-8")


class App:
    def __init__(self, cfg, engine=None, loop=None):
        self.cfg, self.engine = cfg, engine
        self.loop = loop or asyncio.new_event_loop()
        self.page = render_page(cfg)
        self.assets = Path(cfg.card.assets_dir) if cfg.card.assets_dir else default_dir()

    def seal_file(self):
        return next((f for f in (self.assets / "seal.svg", self.assets / "seal.png") if f.is_file()), None) \
            if self.cfg.card.logos else None

    def handler(self):
        app = self

        class H(BaseHTTPRequestHandler):
            def reply(self, body, ctype="application/json", code=200):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)

            def denied(self):
                """With a login configured, every request must carry it (browsers remember it after the first prompt)."""
                if not app.cfg.server.auth or authorized(self.headers.get("Authorization"), app.cfg.server.auth):
                    return False
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="results-race", charset="UTF-8"')
                self.send_header("Content-Length", "0")
                self.end_headers()
                return True

            def do_GET(self):
                if self.denied():
                    return
                eng, path = app.engine, self.path
                if path == "/":
                    self.reply(app.page, "text/html; charset=utf-8")
                elif path == "/state":
                    body = {**eng.state(), "offer": eng.offer()} if eng else {"students": [], "lanes": [], "offer": None,
                                                                              "card": False, "can_add": False, "cfg": {}}
                    self.reply(json.dumps(body).encode())
                elif path == "/assets/seal" and (f := app.seal_file()):
                    self.reply(f.read_bytes(), "image/svg+xml" if f.suffix == ".svg" else "image/png")
                elif path.startswith("/result/") and eng:
                    html = eng.card_html(path[8:])
                    self.reply((html or "not found").encode(), "text/html; charset=utf-8", 200 if html else 404)
                elif path.startswith("/png/") and eng and eng.card_html(path[5:]) is not None:
                    sid, t0 = path[5:], time.time()
                    png = asyncio.run_coroutine_threadsafe(eng.card_png(sid), app.loop).result(60)
                    self.send_response(200)
                    self.send_header("X-Render-Ms", str(int((time.time() - t0) * 1000)))
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Disposition", f'attachment; filename="result-{Path(sid).name}.png"')
                    self.end_headers()
                    self.wfile.write(png)
                else:
                    self.reply(b"{}", code=404)

            def do_POST(self):
                if self.denied():
                    return
                try:
                    b = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                except ValueError:
                    return self.reply(b'{"error":"bad json"}', code=400)
                eng, path = app.engine, self.path
                if not eng or path not in ("/add", "/reload", "/lanes/reload", "/solve", "/reset"):
                    return self.reply(b"{}", code=404)
                if path == "/add":
                    async def add():
                        return eng.add_student(b.get("roll", ""), b.get("reg", ""), b.get("exam", ""), b.get("year", "")).id
                    try:
                        sid = asyncio.run_coroutine_threadsafe(add(), app.loop).result(5)
                        return self.reply(json.dumps({"ok": True, "id": sid}).encode())
                    except ValueError as err:
                        return self.reply(json.dumps({"ok": False, "error": str(err)}).encode())
                if path == "/lanes/reload":
                    app.loop.call_soon_threadsafe(eng.reload_lanes)
                elif path == "/reload":
                    app.loop.call_soon_threadsafe(eng.reload, str(b.get("lane", "")))
                elif path == "/solve":
                    app.loop.call_soon_threadsafe(eng.solve, str(b.get("lane", "")), str(b.get("id") or b.get("roll", "")),
                                                  str(b.get("captcha", "")).strip())
                elif path == "/reset":
                    app.loop.call_soon_threadsafe(eng.reset, bool(b.get("all")))
                self.reply(b"{}")

            def log_message(self, *args):
                pass

        return H

    def serve_in_thread(self):
        httpd = ThreadingHTTPServer((self.cfg.server.host, self.cfg.server.port), self.handler())
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd

    def notify_when_ready(self, url):
        """Optional: run the user's command once the first lane is ready."""
        command = [part.replace("{url}", url) for part in self.cfg.notify.command]
        if not command:
            return

        async def wait():
            while not any(l.status == "ready" for l in self.engine.lanes):
                await asyncio.sleep(1)
            try:
                subprocess.run(command, check=False, timeout=15)
            except (OSError, subprocess.SubprocessError):
                pass  # a broken notifier must never take the app down
        self.loop.create_task(wait())
