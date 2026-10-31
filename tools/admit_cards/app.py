"""Usage: python3 app.py FIRST_REG LAST_REG [--exam hsc --year 2026 --district rajshahi --board 2] [--out out] [--port 8000]
Open the page, type each captcha, and every admit card is saved as <reg>.html in --out."""
import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core import Slot

p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
p.add_argument("first", type=int, help="first registration number")
p.add_argument("last", type=int, help="last registration number (inclusive)")
p.add_argument("--exam", default="hsc"), p.add_argument("--year", default="2026"), p.add_argument("--district", default="rajshahi")
p.add_argument("--board", default="2", help="the board's id in the admit form (2 = Rajshahi)")
p.add_argument("--out", default="out"), p.add_argument("--port", type=int, default=8000)
args = p.parse_args()
first, last, OUT = args.first, args.last, Path(args.out)
FORM = {"board": args.board, "exam": args.exam, "exam_year": args.year, "district": args.district, "type": "public"}
slots = {str(r): Slot(r, OUT, FORM) for r in range(first, last + 1)}
pool = ThreadPoolExecutor(2)
for s in slots.values():
    if (OUT / f"{s.reg}.html").exists():
        s.status, s.msg = "done", "already saved"
    else:
        pool.submit(s.load_captcha)

PAGE = (Path(__file__).parent / "index.html").read_bytes()


class H(BaseHTTPRequestHandler):
    def reply(self, body, ctype="application/json", code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.reply(PAGE, "text/html")
        elif self.path == "/state":
            self.reply(json.dumps([{"reg": s.reg, "status": s.status, "msg": s.msg, "v": id(s.captcha)}
                                   for s in slots.values()]).encode())
        elif self.path.startswith("/captcha/") and (s := slots.get(self.path[9:].split("?")[0])) and s.captcha:
            self.reply(s.captcha, "image/jpeg")
        else:
            self.reply(b"{}", code=404)

    def do_POST(self):
        if self.path not in ('/solve', '/reload'):
            return self.reply(b'{}', code=404)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        s = slots.get(body.get("reg"))
        if s and s.status == "ready" and self.path == "/reload":
            s.status = "loading"
            pool.submit(s.load_captcha)
        elif s and s.status == "ready":
            s.status = "submitting"
            threading.Thread(target=s.submit, args=(body["captcha"].strip(),), daemon=True).start()
        self.reply(b"{}")

    def log_message(self, *a):
        pass


print(f"{len(slots)} regs, saving to {OUT}\nopen http://localhost:{args.port}")
ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()
