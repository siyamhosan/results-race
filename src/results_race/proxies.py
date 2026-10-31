"""proxy.txt: one proxy per line. Formats: host:port | scheme://host:port | scheme://user:pass@host:port | host:port:user:pass"""
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Proxy:
    server: str  # what Chromium wants: scheme://host:port
    user: str | None = None
    password: str | None = None

    @property
    def label(self):
        return self.server.split("://")[1]


def parse(line):
    if m := re.fullmatch(r"(?:(\w+)://)?(?:([^:@/]+):([^@/]*)@)?([\w.\-]+):(\d{1,5})", line):
        scheme, user, pw, host, port = m.groups()
        return Proxy(f"{scheme or 'http'}://{host}:{port}", user, pw)
    if m := re.fullmatch(r"([\w.\-]+):(\d{1,5}):([^:]+):(.*)", line):
        host, port, user, pw = m.groups()
        return Proxy(f"http://{host}:{port}", user, pw)
    raise ValueError(f"bad proxy line: {line!r}")


def load_proxies(path):
    path = Path(path)
    if not path.exists():
        return []
    lines = (l.strip() for l in path.read_text().splitlines())
    return [parse(l) for l in lines if l and not l.startswith("#")]
