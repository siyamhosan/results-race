"""A stand-in browser: 'screenshots' are a short fingerprint of the page it was asked to show."""
import base64
import hashlib


class FakeTab:
    def __init__(self, browser, html):
        self.browser, self.html = browser, html

    async def eval(self, js):
        return None

    async def call(self, method, **params):
        if method == "Page.captureScreenshot":
            png = b"PNG:" + hashlib.md5(self.html).hexdigest()[:8].encode()
            return {"data": base64.b64encode(png).decode()}
        return {}

    async def close(self):
        self.browser.closed += 1


class FakeBrowser:
    def __init__(self):
        self.opened = self.closed = 0

    async def new_tab(self, url, proxy=None):
        self.opened += 1
        html = base64.b64decode(url.split("base64,", 1)[1]) if "base64," in url else b""
        return FakeTab(self, html)
