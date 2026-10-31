"""Minimal Chrome DevTools Protocol client: one headless Chromium, isolated tabs (own cookies)."""
import asyncio
import atexit
import json
import os
import shutil
import socket
import subprocess
import tempfile
import urllib.request

import websockets


class Browser:
    closing = False  # set when we close the browser ourselves, so its connection ending is expected

    async def start(self, port=None, path="", no_sandbox=False):
        if port is None:  # a free port every time: a lingering old Chromium must never be mistaken for ours
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
        self.profile = tempfile.mkdtemp(prefix="results-chromium-")
        exe = path or os.environ.get("CHROME_BIN") or shutil.which("chromium") or shutil.which("google-chrome-stable") or shutil.which("google-chrome")
        if not exe:
            raise RuntimeError("no Chromium/Chrome found: install one, or set [browser] path (or CHROME_BIN)")
        flags = ["--no-sandbox", "--disable-dev-shm-usage"] if (no_sandbox or os.environ.get("CHROME_NO_SANDBOX")) else []
        self.proc = subprocess.Popen([exe, "--headless=new", f"--remote-debugging-port={port}", "--no-first-run", *flags,
                                      f"--user-data-dir={self.profile}", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        atexit.register(self._shutdown)  # never leave a headless Chromium behind
        for _ in range(50):
            try:
                url = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version"))["webSocketDebuggerUrl"]
                break
            except Exception:
                await asyncio.sleep(0.2)
        self.ws = await websockets.connect(url, max_size=None)
        self.n, self.waiters, self.listeners = 0, {}, {}
        self.reader = asyncio.create_task(self._read())

    async def _read(self):
        try:
            async for raw in self.ws:
                m = json.loads(raw)
                if f := self.waiters.pop(m.get("id"), None):
                    f.set_result(m)
                elif "method" in m:
                    for cb in self.listeners.get((m.get("sessionId"), m["method"]), []):
                        asyncio.create_task(cb(m["params"]))
        finally:
            if not self.closing:
                # the browser is gone and every lane with it: fail fast so the supervisor (pm2) restarts us cleanly
                print("lost the browser connection - exiting", flush=True)
                os._exit(1)

    async def call(self, method, session=None, **params):
        self.n += 1
        fut = self.waiters[self.n] = asyncio.get_running_loop().create_future()
        msg = {"id": self.n, "method": method, "params": params}
        if session:
            msg["sessionId"] = session
        await self.ws.send(json.dumps(msg))
        m = await fut
        if "error" in m:
            raise RuntimeError(m["error"].get("message"))
        return m["result"]

    async def new_tab(self, url, proxy=None):
        """A tab in its own browser context (own cookies), optionally behind a proxy (see proxies.Proxy)."""
        params = {"proxyServer": proxy.server} if proxy else {}
        ctx = (await self.call("Target.createBrowserContext", **params))["browserContextId"]
        tid = (await self.call("Target.createTarget", url="about:blank", browserContextId=ctx))["targetId"]
        sid = (await self.call("Target.attachToTarget", targetId=tid, flatten=True))["sessionId"]
        tab = Tab(self, sid, tid, ctx)
        if proxy and proxy.user:
            await tab.answer_proxy_auth(proxy.user, proxy.password or "")
        await tab.goto(url)
        return tab

    def _shutdown(self):
        self.closing = True
        self.proc.terminate()

    async def close(self):
        self._shutdown()
        shutil.rmtree(self.profile, ignore_errors=True)


class Tab:
    def __init__(self, browser, session, target_id, context_id):
        self.b, self.s, self.tid, self.ctx = browser, session, target_id, context_id

    async def call(self, method, **params):
        return await self.b.call(method, self.s, **params)

    async def close(self):
        await self.b.call("Target.closeTarget", targetId=self.tid)
        await self.b.call("Target.disposeBrowserContext", browserContextId=self.ctx)

    async def answer_proxy_auth(self, user, password):
        async def paused(p):
            await self.call("Fetch.continueRequest", requestId=p["requestId"])

        async def auth(p):
            await self.call("Fetch.continueWithAuth", requestId=p["requestId"], authChallengeResponse={
                "response": "ProvideCredentials", "username": user, "password": password})
        self.b.listeners.setdefault((self.s, "Fetch.requestPaused"), []).append(paused)
        self.b.listeners.setdefault((self.s, "Fetch.authRequired"), []).append(auth)
        await self.call("Fetch.enable", handleAuthRequests=True, patterns=[{"urlPattern": "*"}])

    async def goto(self, url):
        await self.b.call("Page.navigate", self.s, url=url)

    async def eval(self, js):
        r = await self.b.call("Runtime.evaluate", self.s, expression=js, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError(r["exceptionDetails"]["text"])
        return r["result"].get("value")
