"""Configuration. Every option has a default, so zero config works. Sources, lowest to highest priority:

    defaults  <  config file (TOML)  <  environment (RESULTS_RACE_<SECTION>_<KEY>)  <  command line

`--set section.key=value` reaches every option; a few common ones also have their own flag.
"""
import argparse
import dataclasses
import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SITES = ["https://result.rajshahiboard.gov.bd", "https://eboardresults.com",
                 "https://www.educationboardresults.gov.bd"]
SEAL_URL = "https://upload.wikimedia.org/wikipedia/commons/8/84/Government_Seal_of_Bangladesh.svg"
BOARD_LOGO_URL = "https://rajshahiboard.gov.bd/wp-content/uploads/2025/08/cropped-rb_logo-192x192.png"
FOOTER_NOTE = "Unofficial copy of the result published by the board's public service. Verify at the source before use."


class ConfigError(ValueError):
    pass


@dataclass
class Run:
    board: str = "rajshahi"  # the board's name as the result form spells it
    exam: str = "hsc"
    year: str = "2026"
    result_type: str = "1"  # 1 = individual/detailed result


@dataclass
class Sites:
    urls: list = field(default_factory=lambda: list(DEFAULT_SITES))  # mirrors running the same result app
    lanes_per_site: int = 2  # parallel browser sessions per site
    warmup_parallel: int = 0  # start this many sessions at a time (0 = all at once); lower it on a small server
    home_path: str = "/v2/home"
    captcha_path: str = "/v2/captcha"
    result_path: str = "/v2/getres"


@dataclass
class Students:
    file: str = ""  # .json / .csv / .txt list of roll + reg; empty = start empty and add students in the page
    allow_manual_add: bool = True


@dataclass
class Proxies:
    file: str = ""  # one proxy per line; empty = no proxied lanes


@dataclass
class Hedge:
    seconds: float = 1.0  # a lane silent this long is bypassed for another site; 0 turns switching off
    timeout_seconds: float = 15.0  # how long a bypassed lane may still deliver a late answer


@dataclass
class Server:
    host: str = "127.0.0.1"  # 0.0.0.0 to serve the local network
    port: int = 8000
    auth: str = ""  # "user:password" (HTTP Basic); empty = no login
    allow_open: bool = False  # permit a non-localhost host with no login (trusted networks only)


@dataclass
class Output:
    dir: str = "out"


@dataclass
class Browser:
    path: str = ""  # Chromium/Chrome binary; empty = look for chromium / google-chrome-stable on PATH
    no_sandbox: bool = False  # needed on some Linux hosts where the sandbox is unavailable


@dataclass
class Ui:
    title: str = "Results race"
    theme: str = "light"  # light | dark | auto
    captcha_min_length: int = 3


@dataclass
class Card:
    enabled: bool = True  # the printable A4 result sheet and PNG download
    logos: bool = True  # draw the seal / board logo if they are in assets_dir (see `results-race fetch-assets`)
    assets_dir: str = ""  # empty = ~/.local/share/results-race/assets
    header_line: str = "Government of the People's Republic of Bangladesh"
    sheet_title: str = "RESULT SHEET"
    footer_note: str = FOOTER_NOTE
    show_fetch_time: bool = True
    png_scale: int = 3  # 3 = 2382x3369 px
    seal_url: str = SEAL_URL  # where `fetch-assets` downloads from
    board_logo_url: str = BOARD_LOGO_URL


@dataclass
class Notify:
    command: list = field(default_factory=list)  # run once a lane is ready, e.g. ["notify-send", "Results ready", "{url}"]


@dataclass
class Config:
    run: Run = field(default_factory=Run)
    sites: Sites = field(default_factory=Sites)
    students: Students = field(default_factory=Students)
    proxies: Proxies = field(default_factory=Proxies)
    hedge: Hedge = field(default_factory=Hedge)
    server: Server = field(default_factory=Server)
    output: Output = field(default_factory=Output)
    browser: Browser = field(default_factory=Browser)
    ui: Ui = field(default_factory=Ui)
    card: Card = field(default_factory=Card)
    notify: Notify = field(default_factory=Notify)


PATH_OPTIONS = {"students.file", "proxies.file", "output.dir", "card.assets_dir", "browser.path"}
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _coerce(value, current, where):
    try:
        if isinstance(current, bool):
            if isinstance(value, bool):
                return value
            if str(value).strip().lower() in ("1", "true", "yes", "on"):
                return True
            if str(value).strip().lower() in ("0", "false", "no", "off"):
                return False
            raise ValueError
        if isinstance(current, int):
            return int(value)
        if isinstance(current, float):
            return float(value)
        if isinstance(current, list):
            if isinstance(value, list):
                return value
            text = str(value).strip()
            return json.loads(text) if text.startswith("[") else [p.strip() for p in text.split(",") if p.strip()]
        return str(value)
    except (ValueError, TypeError):
        raise ConfigError(f"{where}: cannot read {value!r} as {type(current).__name__}") from None


def _set(cfg, section, key, value, base=None):
    if not hasattr(cfg, section):
        raise ConfigError(f"unknown section [{section}]; valid: {', '.join(f.name for f in dataclasses.fields(cfg))}")
    sec = getattr(cfg, section)
    names = [f.name for f in dataclasses.fields(sec)]
    if key not in names:
        raise ConfigError(f"unknown option [{section}] {key}; valid: {', '.join(names)}")
    value = _coerce(value, getattr(sec, key), f"[{section}] {key}")
    if base and f"{section}.{key}" in PATH_OPTIONS and value and not os.path.isabs(value):
        value = str(Path(base) / value)  # paths inside a config file are relative to that file
    setattr(sec, key, value)


def _apply_file(cfg, path):
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"cannot read config {path}: {e}") from None
    for section, table in data.items():
        if not isinstance(table, dict):
            raise ConfigError(f"{path}: top-level key {section!r} must be a [section]")
        for key, value in table.items():
            _set(cfg, section, key, value, base=Path(path).resolve().parent)


def _apply_env(cfg, env):
    for sec in dataclasses.fields(cfg):
        for f in dataclasses.fields(getattr(cfg, sec.name)):
            name = f"RESULTS_RACE_{sec.name}_{f.name}".upper()
            if name in env:
                _set(cfg, sec.name, f.name, env[name])
    if env.get("RESULTS_AUTH"):  # original name, kept as an alias
        cfg.server.auth = env["RESULTS_AUTH"]


def validate(cfg):
    if cfg.ui.theme not in ("light", "dark", "auto"):
        raise ConfigError("[ui] theme must be light, dark or auto")
    if cfg.sites.lanes_per_site < 1 or not cfg.sites.urls:
        raise ConfigError("[sites] needs at least one url and lanes_per_site >= 1")
    if not 0 < cfg.server.port < 65536:
        raise ConfigError("[server] port must be 1-65535")
    if cfg.server.auth and ":" not in cfg.server.auth:
        raise ConfigError('[server] auth must look like "user:password"')
    if cfg.hedge.seconds < 0 or cfg.hedge.timeout_seconds <= 0:
        raise ConfigError("[hedge] seconds must be >= 0 and timeout_seconds > 0")
    if not 1 <= cfg.card.png_scale <= 4:
        raise ConfigError("[card] png_scale must be 1-4")
    if cfg.sites.warmup_parallel < 0:
        raise ConfigError("[sites] warmup_parallel must be >= 0")
    if cfg.ui.captcha_min_length < 1:
        raise ConfigError("[ui] captcha_min_length must be >= 1")
    if cfg.server.host not in LOOPBACK and not cfg.server.auth and not cfg.server.allow_open:
        raise ConfigError("refusing to listen beyond localhost without a login: set [server] auth = \"user:password\" "
                          "(or RESULTS_AUTH), or --no-auth on a network you trust")


def parser():
    p = argparse.ArgumentParser(prog="results-race", description="Race several result sites at once; you type the captchas.")
    p.add_argument("command", nargs="?", default="run", choices=["run", "fetch-assets", "print-config", "init-config"],
                   help="run (default) | fetch-assets (download the logos) | print-config | init-config")
    p.add_argument("--config", help="TOML file (default: $RESULTS_RACE_CONFIG, ./results-race.toml, ~/.config/results-race/config.toml)")
    p.add_argument("--students", help="[students] file")
    p.add_argument("--proxies", help="[proxies] file")
    p.add_argument("--board", help="[run] board")
    p.add_argument("--exam", help="[run] exam: ssc, hsc, jsc ...")
    p.add_argument("--year", help="[run] year")
    p.add_argument("--lanes", type=int, help="[sites] lanes_per_site")
    p.add_argument("--out", help="[output] dir")
    p.add_argument("--host", help="[server] host (0.0.0.0 = local network)")
    p.add_argument("--port", type=int, help="[server] port")
    p.add_argument("--hedge", type=float, help="[hedge] seconds (0 = never switch)")
    p.add_argument("--timeout", type=float, help="[hedge] timeout_seconds")
    p.add_argument("--no-auth", action="store_true", help="[server] allow_open = true")
    p.add_argument("--set", action="append", default=[], metavar="SECTION.KEY=VALUE", help="set any option; repeatable")
    return p


FLAGS = {"students": "students.file", "proxies": "proxies.file", "board": "run.board", "exam": "run.exam", "year": "run.year",
         "lanes": "sites.lanes_per_site", "out": "output.dir", "host": "server.host", "port": "server.port",
         "hedge": "hedge.seconds", "timeout": "hedge.timeout_seconds"}


def find_config(explicit, env):
    wanted = explicit or env.get("RESULTS_RACE_CONFIG")
    if wanted:
        if not Path(wanted).is_file():
            raise ConfigError(f"config file not found: {wanted}")
        return Path(wanted)
    for candidate in (Path("results-race.toml"), Path.home() / ".config/results-race/config.toml"):
        if candidate.is_file():
            return candidate
    return None


def load(argv=None, env=None):
    """-> (Config, parsed args). Raises ConfigError with a message fit to show the user."""
    env = os.environ if env is None else env
    args = parser().parse_args(argv)
    cfg = Config()
    if path := find_config(args.config, env):
        _apply_file(cfg, path)
    _apply_env(cfg, env)
    for flag, target in FLAGS.items():
        if (value := getattr(args, flag)) is not None:
            section, key = target.split(".")
            _set(cfg, section, key, value)
    if args.no_auth:
        cfg.server.allow_open = True
    for item in args.set:
        if "=" not in item or "." not in item.split("=", 1)[0]:
            raise ConfigError(f"--set wants SECTION.KEY=VALUE, got {item!r}")
        target, value = item.split("=", 1)
        section, key = target.split(".", 1)
        _set(cfg, section, key, value)
    validate(cfg)
    return cfg, args


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(json.dumps(x) for x in v) + "]"
    return json.dumps(v, ensure_ascii=False)


def dump(cfg):
    """The effective configuration as TOML."""
    out = []
    for sec in dataclasses.fields(cfg):
        out.append(f"[{sec.name}]")
        for f in dataclasses.fields(getattr(cfg, sec.name)):
            out.append(f"{f.name} = {_toml_value(getattr(getattr(cfg, sec.name), f.name))}")
        out.append("")
    return "\n".join(out)
