"""Command line: `results-race [run]`, `demo`, `fetch-assets`, `print-config`, `init-config`."""
import asyncio
import signal
import socket
import sys
import tempfile
from pathlib import Path

from . import __version__
from .assets import default_dir, fetch_assets
from .card import load_logos
from .cdp import Browser
from .config import ConfigError, dump, load
from .demo import apply_demo
from .engine import Engine
from .proxies import load_proxies
from .server import App
from .students import load_students

EXAMPLE = Path(__file__).parent / "config.example.toml"


def fail(message, code=2):
    print(f"error: {message}", file=sys.stderr)
    return code


def lan_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent; this just picks the outgoing interface
            return s.getsockname()[0]
    except OSError:
        return "this-machine"


def card_style(cfg):
    """How the result sheet looks: the configured texts, plus whichever logos are in the assets folder."""
    assets = Path(cfg.card.assets_dir) if cfg.card.assets_dir else default_dir()
    return load_logos(assets, cfg.card.logos, header_line=cfg.card.header_line, board_title=cfg.card.board_title,
                      sheet_title=cfg.card.sheet_title, footer_note=cfg.card.footer_note, show_fetch_time=cfg.card.show_fetch_time,
                      credit=cfg.card.credit)


def build_engine(cfg, browser, students, proxies, style=None):
    """The engine for a config: sites, lanes, hedging, and the result sheet's look (`style` if already built)."""
    return Engine(
        browser, students, {"board": cfg.run.board, "exam": cfg.run.exam, "year": cfg.run.year, "result_type": cfg.run.result_type},
        cfg.output.dir, cfg.sites.lanes_per_site, proxies, hedge_s=cfg.hedge.seconds, timeout_s=cfg.hedge.timeout_seconds,
        sites=cfg.sites.urls, paths={"home": cfg.sites.home_path, "captcha": cfg.sites.captcha_path, "result": cfg.sites.result_path},
        warmup_parallel=cfg.sites.warmup_parallel, load_s=cfg.sites.load_timeout_seconds,
        warmup_wait_s=max(30.0, cfg.sites.load_timeout_seconds * 1.5), card_style=style or card_style(cfg), card_enabled=cfg.card.enabled,
        png_scale=cfg.card.png_scale, allow_manual=cfg.students.allow_manual_add)


def run(cfg):
    try:
        students = load_students(cfg.students.file)
        if cfg.proxies.file and not Path(cfg.proxies.file).is_file():
            raise ValueError(f"proxy file not found: {cfg.proxies.file}")
        proxies = load_proxies(cfg.proxies.file) if cfg.proxies.file else []
    except ValueError as e:
        return fail(e)

    style = card_style(cfg)
    app = App(cfg)
    loop = app.loop
    host = cfg.server.host
    shown = lan_address() if host in ("0.0.0.0", "::") else host
    url = f"http://{shown}:{cfg.server.port}"

    async def main():
        browser = Browser()
        await browser.start(path=cfg.browser.path, no_sandbox=cfg.browser.no_sandbox)
        app.engine = build_engine(cfg, browser, students, proxies, style)
        app.notify_when_ready(url)
        await app.engine.run()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: sys.exit(0))  # run atexit, so the headless browser is closed too
    try:
        app.serve_in_thread()
    except OSError as e:
        return fail(f"cannot listen on {host}:{cfg.server.port}: {e.strerror}", 1)
    logos = "with logos" if style.seal or style.board_logo else "no logos (run `results-race fetch-assets` to add them)"
    print(f"results-race {__version__}  {url}\n  {len(students)} students, {len(cfg.sites.urls)} sites x {cfg.sites.lanes_per_site}"
          f" lanes{f' + {len(proxies)} proxies' if proxies else ''}, {cfg.run.exam} {cfg.run.year} {cfg.run.board}, {logos}"
          f"{', login required' if cfg.server.auth else ''}", flush=True)
    try:
        loop.run_until_complete(main())
    except RuntimeError as e:  # e.g. no Chromium found
        return fail(e, 1)
    return 0


def main(argv=None):
    try:
        cfg, args = load(argv)
    except ConfigError as e:
        return fail(e)
    if args.command == "print-config":
        print(dump(cfg))
        return 0
    if args.command == "init-config":
        target = Path("results-race.toml")
        if target.exists():
            return fail(f"{target} already exists")
        target.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"wrote {target}: every option at its default, with a comment each")
        return 0
    if args.command == "fetch-assets":
        folder = Path(cfg.card.assets_dir) if cfg.card.assets_dir else default_dir()
        print(f"downloading logos into {folder}")
        saved = fetch_assets({"seal": cfg.card.seal_url, "board-logo": cfg.card.board_logo_url}, folder)
        return 0 if saved else 1
    if args.command == "demo":
        workdir = tempfile.mkdtemp(prefix="results-race-demo-")
        mirrors = apply_demo(cfg, workdir)
        print(f"DEMO: fake mirror sites {', '.join(m.name for m in mirrors)} (one is slow on purpose) and made-up students.\n"
              f"  Read the 4 digits in each captcha picture and type them. Files go to {workdir}")
        try:
            return run(cfg)
        finally:
            for m in mirrors:
                m.stop()
    return run(cfg)
