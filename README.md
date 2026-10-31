<p align="center">
  <img src="docs/img/banner.svg" alt="results-race: you type the captchas, it wins the race" width="900">
</p>

<p align="center">
  <b>Look students up on several result sites at once. You type the captchas; it wins the race.</b><br>
  <sub>From BazarLab by Siyam</sub>
</p>

Exam results go live and every site slows to a crawl. **results-race** looks your students up on several
mirror sites at once, shows you each captcha, and saves whichever site answers first.
You type the captchas; everything else is automatic.

> **Try it in a minute, with no real site and no real student:**
> ```sh
> pip install .            # from a clone; needs Python 3.11+ and a Chromium/Chrome
> results-race demo        # then open http://127.0.0.1:8000 and type the digits you see
> ```
> It starts three fake mirror sites (one slow on purpose, so you can watch the app move on from it) and twelve
> made-up students. Everything in the pictures below came from exactly this.
>
> One honest detail: the demo's captcha pictures also carry their digits as text, so the screenshot script and the tests
> can "type" them. That is demo-only; the app never reads a real site's captcha, a person does.

## What it looks like

<p align="center">
  <img src="docs/img/app-light.png" alt="The page in light mode: captcha to type on the left, the student list on the right with results and one lane being switched" width="900">
</p>

<table>
  <tr>
    <td width="50%"><img src="docs/img/app-dark.png" alt="The same page in dark mode"></td>
    <td width="50%"><img src="docs/img/result-dialog.png" alt="A student's A4 result sheet opened in a dialog, with download and print buttons"></td>
  </tr>
  <tr>
    <td align="center"><sub><b>Dark mode</b> (or light, or follow the system). The yellow <i>Switch lane</i> pill: a site was slow, so the student was handed to another one.</sub></td>
    <td align="center"><sub><b>Click a finished student</b> for the A4 sheet. Download it as a PNG, print it, or <i>Download all A4 PNGs</i> in one zip.</sub></td>
  </tr>
</table>

<table>
  <tr>
    <td width="30%" valign="top"><img src="docs/img/app-phone.png" alt="The page on a phone"></td>
    <td width="70%" valign="top" align="center">
      <img src="docs/img/sheet-sample.png" alt="A sample A4 result sheet" width="430"><br>
      <sub><b>The A4 sheet</b> (demo data): fonts embedded, logos optional, every text configurable, and a small
      credit line at the bottom you can change or remove.
      The download is a PNG (2382 x 3369 px by default; this picture is a smaller 2x export) named after
      the student and the result, e.g. <code>Fahim-Chowdhury_GPA-4.25_200004.png</code>.</sub>
    </td>
  </tr>
  <tr>
    <td align="center"><sub><b>On a phone</b> it stacks into one column.</sub></td>
    <td></td>
  </tr>
</table>

## How it works

<p align="center">
  <img src="docs/img/architecture.svg" alt="Diagram: your browser talks to the results-race server and its engine, which drives headless Chromium sessions (lanes), each asking one mirror site, optionally through a proxy" width="900">
</p>

1. You read the captcha in the page and type its digits.
2. The engine submits them on **that captcha's own lane**: a separate Chromium session on one mirror site
   (or one session per proxy). Every lane already has its next captcha loaded, so you never wait for the network.
3. The site answers. The first good answer is saved as JSON, drawn as an A4 sheet, and shown in the list.
4. The next student's captcha is already waiting.

### Why it races

<p align="center">
  <img src="docs/img/race.svg" alt="Timeline: mirror A does not answer within one second, so the app asks for mirror B's captcha; B answers fast and the result is saved; A's late answer is ignored" width="900">
</p>

When results come out, some sites stall. If a lane has not answered in **1 second**, the student goes back in the queue
for another site (you type that site's captcha), while the slow lane keeps waiting. The first answer wins; a late one is
dropped, unless nothing else answered within 15 seconds, then it is used. Both numbers are in `[hedge]`
(`seconds = 0` turns switching off).

It uses a real headless Chromium, so each site's own checks run exactly as they would for a person using a browser.

## What it does not do

- It does **not** solve captchas. A human reads and types every one. That is deliberate.
- It does not bypass, spoof or script around any site's checks.
- It is not an official document source: the sheet it draws is marked *unofficial copy*. Verify results at the source.

## Install

Requires Python 3.11+ and a Chromium or Chrome.

```sh
git clone <this repo> && cd results-race
pip install .                     # not on PyPI yet
```

No Chromium on the machine? Let Playwright download one:

```sh
pip install ".[browser]"
playwright install chromium       # note where it lands, then set [browser] path in the config
```

## Quick start

```sh
results-race init-config          # writes results-race.toml: every option, at its default, commented
$EDITOR results-race.toml         # set [run] exam / year / board, and [students] file
results-race fetch-assets         # optional: download the logos used on the result sheet
results-race                      # then open http://127.0.0.1:8000
```

It works with no config at all: it starts empty and you add students with **Add student** in the page.

## In the page

| Control | What it does |
|---|---|
| type digits + Enter | submit the captcha; the next student's is already loaded |
| **New captcha** (or Esc) | swap one unreadable captcha for a fresh one |
| **Reload lanes** | fresh captchas on every ready lane, and rebuilds lanes stuck warming or cooling down (use it when a site hiccups; no restart needed). A lane mid-lookup is left alone |
| **Add student** | look someone up for any exam and year; saved separately |
| **Reset failed** / **Reset all** | requeue failures / forget everything and delete saved results |
| click a finished student | the A4 sheet, with PNG download and print |
| **Download all A4 PNGs** | one zip with every finished student's A4 PNG (renders are cached, so a second click is instant) |

## Configuration

Highest priority wins:

1. command-line flags (`--exam ssc`, or `--set section.key=value` for anything)
2. environment variables: `RESULTS_RACE_<SECTION>_<KEY>`, e.g. `RESULTS_RACE_RUN_EXAM=ssc`
3. the config file: `--config FILE`, `$RESULTS_RACE_CONFIG`, `./results-race.toml`, or `~/.config/results-race/config.toml`
4. built-in defaults

Relative paths inside a config file are relative to that file. `results-race print-config` shows the effective result.
Unknown options and bad values are reported by name, never silently ignored.

| Section | What you can set |
|---|---|
| `[run]` | `board`, `exam`, `year`, `result_type` |
| `[sites]` | `urls` (the mirrors), `lanes_per_site`, `warmup_parallel`, and the three endpoint paths |
| `[students]` | `file` (`.json`, `.csv` or `.txt`), `allow_manual_add` |
| `[proxies]` | `file`: every lane gets a proxied twin per proxy |
| `[hedge]` | `seconds` (0 = never switch sites), `timeout_seconds` |
| `[server]` | `host`, `port`, `auth` (`user:password`), `allow_open` |
| `[output]` | `dir` |
| `[browser]` | `path`, `no_sandbox` |
| `[ui]` | `title`, `theme` (`light`/`dark`/`auto`), `captcha_min_length`, `credit` (the line at the bottom of the page; empty hides it) |
| `[card]` | `enabled`, `logos`, `assets_dir`, header/title/footer texts, `show_fetch_time`, `credit` (the line at the very bottom of the sheet and PNG; empty hides it), `png_scale` |
| `[notify]` | `command`, run once a lane is ready |

[`config.example.toml`](config.example.toml) lists every option with a comment, and a test keeps it equal to the real defaults.

### Student lists

```
# students.txt          roll,reg per line (comma, space or tab)
100001 2100000001
```
`.csv` (with or without a `roll,reg` header) and `.json` (`[{"roll": "100001", "reg": "2100000001"}]`) work too.
See [`examples/`](examples).

### Proxies

One per line: `host:port`, `scheme://host:port`, `scheme://user:password@host:port` or `host:port:user:password`.
Keep the file out of git (it is in `.gitignore`).

## Serving the local network

By default the page listens on `127.0.0.1` only. To open it to your network set `[server] host = "0.0.0.0"` and
**also** a login:

```toml
[server]
host = "0.0.0.0"
auth = "me:a-long-password"      # or the RESULTS_AUTH environment variable
```

The app refuses to start beyond localhost without a login. On a network you fully trust you can opt out with
`--no-auth` (`allow_open = true`). The login is plain HTTP Basic: put it behind HTTPS before exposing it beyond
a LAN. The page shows students' names and personal details, so treat it accordingly.

## Running it as a service

Examples for pm2 and systemd are in [`examples/`](examples). If its browser dies the app exits, so the supervisor
restarts it cleanly.

## Output

```
out/<roll>.json                 one file per looked-up student (the whole result, plus site and timing)
out/manual/<roll>-<exam><year>.json   students added in the page
out/manual.json                 the list of students added in the page (they come back after a restart)
```
Restarting skips anyone already saved. **Reset all** in the page deletes the saved results.

## The result sheet

Downloaded PNGs are named after the student and the result, e.g. `Md-Rahim-Uddin_GPA-4.22_100001.png`
(`..._Not-Passed_...` for a fail). Non-Latin names are kept, and the zip never has two files with one name.

Fonts (IBM Plex, OFL) are bundled. The **logos are not**: they are a government's and a board's marks, so each user
downloads them onto their own machine with `results-race fetch-assets` (sources are configurable under `[card]`).
Without them the sheet simply has no logos. Restart after fetching. All the sheet's texts are configurable (including the credit line at the bottom, `[card] credit`), and
`[card] enabled = false` turns the sheet and PNG off.

## Tuning

- `lanes_per_site`: more lanes = more captchas ready, but more load on the sites **and more memory** (each lane is a browser
  session, roughly 200-300 MB). On a small server keep the total modest and set `[sites] warmup_parallel = 4` (or similar) so
  startup brings sessions up in batches instead of all at once. Proxies multiply the lane count.
- `[hedge] seconds = 0` keeps every lookup on the lane you typed for.
- A site answering HTTP 429 (too many requests) is backed off automatically.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `no Chromium/Chrome found` | install one, or set `[browser] path` / `CHROME_BIN` |
| Chromium aborts with `No usable sandbox` | `[browser] no_sandbox = true` (some Linux hosts block the sandbox) |
| every lane says `cooldown` | the site is down or throttling; it keeps retrying with backoff |
| `lost the browser connection - exiting` | the browser died; a supervisor restarts the app |
| nothing happens on Enter | the captcha is shorter than `[ui] captcha_min_length` |

## Responsible use

This project is not affiliated with any examination board. Use it for results you are entitled to look up (your own,
or those of students who asked you to), at a polite rate, and in line with each site's terms. The results it saves
are personal data: keep `out/` private, and never commit it (the provided `.gitignore` already excludes it).

## Development

```sh
pip install -e .
python -m unittest discover -s tests      # needs no network; one end-to-end test drives a real Chromium
                                          # against the demo and is skipped when there is none
```

```
src/results_race/   config, engine (lanes, hedging), cdp (browser), server, card (A4 sheet), demo, static/ (the page)
tests/              unit and HTTP tests, with fake lanes standing in for the network
examples/           student lists, proxy list, pm2 and systemd files
tools/admit_cards/  a separate small tool for the Rajshahi board's admit-card page
tools/art/          builds the README's diagrams and screenshots
docs/img/           those pictures
```

## The pictures

The hand-drawn diagrams are generated, not drawn by hand in an editor, so they stay in step with the code:

```sh
python tools/art/build_art.py          # the three animated SVGs in docs/img/
python tools/art/make_screenshots.py   # runs `results-race demo` and photographs it
```

The diagram lettering is [Caveat](https://github.com/googlefonts/caveat) (SIL Open Font License, embedded in each SVG);
the screenshots show demo data only. The SVG animations stop for anyone who prefers reduced motion.

## License

[MIT](LICENSE). Bundled fonts: IBM Plex (`src/results_race/fonts/OFL.txt`) and, in the diagrams, Caveat
(`tools/art/fonts/OFL.txt`), both SIL Open Font License 1.1.
