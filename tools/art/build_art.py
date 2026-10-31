"""Draws the README's hand-drawn diagrams as animated SVGs.   python tools/art/build_art.py [--out docs/img]

Standard library only. Lines wobble like a pen (seeded, so the output is always identical), the lettering is the
open-licensed Caveat font embedded as a data URI (so it looks the same everywhere, including GitHub), motion is CSS and
switches off for people who ask their system for reduced motion.
"""
import argparse
import base64
import math
import random
from pathlib import Path

HERE = Path(__file__).parent
PALETTE = {"paper": "#fbf7ee", "ink": "#1d2a33", "green": "#006a4e", "mint": "#bfe5d3", "red": "#f42a41",
           "blush": "#fbd0d6", "yellow": "#ffd66b", "blue": "#2f6fb0", "sky": "#cfe3f5", "grey": "#8a959d", "fog": "#e7eaec"}
P = PALETTE


def font_css():
    data = base64.b64encode((HERE / "fonts" / "caveat-600.woff2").read_bytes()).decode()
    return f"@font-face{{font-family:'Caveat';font-weight:600;src:url(data:font/woff2;base64,{data}) format('woff2')}}"


BASE_CSS = """text{font-family:'Caveat','Segoe Print','Bradley Hand','Comic Sans MS',cursive;font-weight:600}
.flow{stroke-dasharray:9 11;animation:flow 1s linear infinite}@keyframes flow{to{stroke-dashoffset:-20}}
.pk{animation:travel var(--d,5s) linear infinite;animation-delay:var(--s,0s)}
@keyframes travel{0%{offset-distance:0%;opacity:0}8%{opacity:1}92%{opacity:1}100%{offset-distance:100%;opacity:0}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}.bob{animation:bob 2.4s ease-in-out infinite}
@media (prefers-reduced-motion:reduce){*{animation:none!important}.rv{opacity:1!important}.pk{display:none}}"""


class Sketch:
    """A little pen: every shape is drawn twice with a shaky hand."""

    def __init__(self, w, h, seed=1):
        self.w, self.h, self.rnd = w, h, random.Random(seed)
        self.body, self.css, self.defs, self.ids = [], [], [], 0

    # -- strokes -------------------------------------------------------------------------------
    def j(self, a):
        return self.rnd.uniform(-a, a)

    def rough_path(self, pts, wobble=1.6):
        """A path through the points with a pen's shake: jittered ends, bowed segments."""
        pts = [(x + self.j(wobble * .6), y + self.j(wobble * .6)) for x, y in pts]
        d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            length = math.hypot(x2 - x1, y2 - y1) or 1
            bow = self.j(min(wobble * 1.5, length / 8))
            cx, cy = (x1 + x2) / 2 - (y2 - y1) / length * bow, (y1 + y2) / 2 + (x2 - x1) / length * bow
            d += f" Q{cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}"
        return d

    def stroke(self, pts, color, width=3.2, dash=None, cls="", fill="none", opacity=1.0, passes=2):
        out = []
        for i in range(passes):
            attrs = f'fill="{fill if i == 0 else "none"}" stroke="{color}" stroke-width="{width if i == 0 else width * .55:.1f}" ' \
                    f'stroke-linecap="round" stroke-linejoin="round" opacity="{opacity if i == 0 else opacity * .6:.2f}"'
            if dash:
                attrs += f' stroke-dasharray="{dash}"'
            if cls and i == 0:
                attrs += f' class="{cls}"'
            out.append(f'<path d="{self.rough_path(pts)}" {attrs}/>')
        self.body.extend(out)

    # -- shapes ----------------------------------------------------------------------------------
    def rect(self, x, y, w, h, stroke=P["ink"], fill=None, width=3.2, dash=None, r=12, opacity=1.0):
        r = min(r, w / 3, h / 3)
        pts = [(x + r, y), (x + w - r, y), (x + w, y + r), (x + w, y + h - r), (x + w - r, y + h), (x + r, y + h),
               (x, y + h - r), (x, y + r), (x + r + 6, y - 1)]
        if fill:
            self.body.append(f'<path d="{self.rough_path(pts[:-1], .6)} Z" fill="{fill}" stroke="none" opacity=".92"/>')
        self.stroke(pts, stroke, width, dash, opacity=opacity)

    def ellipse(self, cx, cy, rx, ry, stroke=P["ink"], fill=None, width=3.2, dash=None):
        pts = [(cx + (rx + self.j(1.8)) * math.cos(a), cy + (ry + self.j(1.8)) * math.sin(a))
               for a in [i * 2 * math.pi / 18 for i in range(19)]]
        if fill:
            self.body.append(f'<path d="{self.rough_path(pts[:-1], .5)} Z" fill="{fill}" stroke="none" opacity=".92"/>')
        self.stroke(pts, stroke, width, dash)

    def hatch(self, x, y, w, h, color=P["ink"], gap=11, opacity=.22):
        self.ids += 1
        cid = f"clip{self.ids}x"
        self.defs.append(f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>')
        lines = "".join(f"M{x + i - 4} {y + h + 4} L{x + i + h + 4} {y - 4}" for i in range(-h, int(w) + 1, gap))
        self.body.append(f'<path d="{lines}" stroke="{color}" stroke-width="1.6" opacity="{opacity}" clip-path="url(#{cid})"/>')

    def arrow(self, pts, color=P["ink"], width=3.4, dash=None, flow=False, head=True):
        self.stroke(pts, color, width, dash, cls="flow" if flow else "")
        if head:
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            a = math.atan2(y2 - y1, x2 - x1)
            for da in (2.55, -2.55):
                self.stroke([(x2, y2), (x2 + 15 * math.cos(a + da), y2 + 15 * math.sin(a + da))], color, width, passes=1)

    def text(self, x, y, s, size=30, color=P["ink"], anchor="start", rotate=0):
        t = f' transform="rotate({rotate} {x} {y})"' if rotate else ""
        s = s.replace("&", "&amp;").replace("<", "&lt;")
        self.body.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}"{t}>{s}</text>')

    def number(self, x, y, n, color=P["green"]):
        self.ellipse(x, y, 17, 17, color, P["paper"], 3)
        self.text(x, y + 9, str(n), 27, color, "middle")

    # -- motion ----------------------------------------------------------------------------------
    def packet(self, d, color=P["red"], dur=5, delay=0, r=7):
        self.body.append(f'<circle r="{r}" fill="{color}" stroke="{P["ink"]}" stroke-width="2" class="pk" '
                         f'style="offset-path:path(\'{d}\');--d:{dur}s;--s:{delay}s"/>')

    def reveal(self, start, total):
        """Context manager: what is drawn inside appears `start` seconds into a `total`-second loop."""
        sketch = self
        sketch.ids += 1
        name = f"rv{sketch.ids}x"

        class Scope:
            def __enter__(self):
                a, b = start / total * 100, start / total * 100 + .6
                sketch.css.append(f"@keyframes {name}{{0%,{a:.2f}%{{opacity:0}}{b:.2f}%,93%{{opacity:1}}100%{{opacity:0}}}}"
                                  f".{name}{{animation:{name} {total}s infinite}}")
                sketch.body.append(f'<g class="rv {name}">')

            def __exit__(self, *exc):
                sketch.body.append("</g>")
        return Scope()

    def sweep(self, x0, x1, y0, y1, total, color=P["blue"]):
        """A dashed 'now' line crossing the picture once per loop."""
        self.ids += 1
        name = f"sw{self.ids}x"
        self.css.append(f"@keyframes {name}{{0%{{transform:translateX(0)}}93%,100%{{transform:translateX({x1 - x0}px)}}}}"
                        f".{name}{{animation:{name} {total}s linear infinite}}")
        self.body.append(f'<g class="{name}"><path d="M{x0} {y0} L{x0} {y1}" stroke="{color}" stroke-width="3" '
                         f'stroke-dasharray="3 9" stroke-linecap="round"/></g>')

    # -- output ----------------------------------------------------------------------------------
    def svg(self, title, desc):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-labelledby="t d"><title id="t">{title}</title><desc id="d">{desc}</desc>'
                f'<style>{font_css()}{BASE_CSS}{"".join(self.css)}</style><defs>{"".join(self.defs)}</defs>'
                f'<rect width="{self.w}" height="{self.h}" fill="{P["paper"]}"/>{"".join(self.body)}</svg>\n')


def frame(s, inset=10):
    s.rect(inset, inset, s.w - 2 * inset, s.h - 2 * inset, P["ink"], None, 2.6, r=18, opacity=.55)


# ------------------------------------------------------------------------------------------------------------
def banner():
    s = Sketch(1200, 300, seed=11)
    frame(s)
    s.text(62, 148, "results-race", 118, P["green"])
    s.stroke([(62, 170), (200, 164), (330, 174), (470, 163), (610, 172)], P["green"], 5)  # wavy underline
    s.stroke([(630, 168), (630, 98)], P["ink"], 4)  # a flag at the end of it
    s.body.append(f'<path d="{s.rough_path([(632, 98), (690, 112), (632, 134)], .8)} Z" fill="{P["red"]}" stroke="{P["ink"]}" stroke-width="3" stroke-linejoin="round"/>')
    s.text(66, 214, "you type the captchas - it wins the race", 46, P["ink"])
    s.text(66, 258, "many sites . one list of students . zero waiting", 32, P["grey"])
    # the captcha you type
    s.rect(800, 30, 170, 56, P["ink"], P["yellow"], 3, r=10)
    s.text(885, 72, "4  7  1  3", 42, P["ink"], "middle", -3)
    s.text(992, 66, "<- you type this", 30, P["blue"])
    # three lanes, three racers
    for i, (y, color, label, cls) in enumerate([(132, P["blush"], "A", "ra"), (184, P["mint"], "B", "rb"), (236, P["sky"], "C", "rc")]):
        s.stroke([(790, y + 20), (1130, y + 20)], P["grey"], 2.6, dash="4 9")
        s.stroke([(1136, y - 14), (1136, y + 24)], P["ink"], 3.2)  # finish line
        s.text(762, y + 16, label, 32, P["ink"], "middle")
        s.body.append(f'<g class="{cls}">')
        s.ellipse(812, y + 4, 17, 17, P["ink"], color, 3)
        s.text(812, y + 14, label.lower(), 25, P["ink"], "middle")
        s.body.append("</g>")
    s.css.append("@keyframes ra{0%{transform:translateX(0)}35%,60%{transform:translateX(95px)}100%{transform:translateX(95px)}}"
                 "@keyframes rb{0%{transform:translateX(0)}100%{transform:translateX(298px)}}"
                 "@keyframes rc{0%{transform:translateX(0)}100%{transform:translateX(205px)}}"
                 ".ra{animation:ra 6s ease-in-out infinite}.rb{animation:rb 6s ease-in infinite}.rc{animation:rc 6s linear infinite}")
    s.text(1158, 154, "...", 30, P["red"], "middle")
    s.stroke([(1120, 208), (1136, 222), (1166, 184)], P["green"], 5)  # B wins
    return s.svg("results-race", "Hand-drawn banner: results-race. You type the captchas and it wins the race. "
                 "Three racers on three lanes; the second one reaches the finish line first.")


def architecture():
    s = Sketch(1200, 660, seed=23)
    frame(s)
    s.text(600, 62, "how it fits together", 50, P["green"], "middle")
    s.stroke([(470, 76), (600, 82), (730, 75)], P["green"], 4)

    # 1. you and the page
    s.ellipse(110, 168, 24, 24, P["ink"], P["paper"])
    s.stroke([(110, 192), (110, 262)], P["ink"], 4)
    s.stroke([(70, 220), (110, 208), (152, 222)], P["ink"], 4)
    s.stroke([(110, 262), (84, 316)], P["ink"], 4)
    s.stroke([(110, 262), (138, 316)], P["ink"], 4)
    s.text(150, 150, "reads + types", 28, P["blue"])
    s.text(150, 178, "the digits", 28, P["blue"])
    s.rect(45, 340, 270, 220, P["ink"], P["sky"], 3.2)
    s.rect(45, 340, 270, 40, P["ink"], P["fog"], 3.2)
    for i, c in enumerate((P["red"], P["yellow"], P["green"])):
        s.ellipse(70 + i * 24, 360, 7, 7, P["ink"], c, 2)
    s.text(214, 368, "your browser", 28, P["ink"], "middle")
    s.rect(70, 396, 120, 50, P["ink"], P["yellow"], 2.8, r=8)
    s.text(130, 432, "4 7 1 3", 34, P["ink"], "middle", -3)
    s.rect(206, 396, 84, 50, P["ink"], P["paper"], 2.8, r=8)
    s.text(248, 430, "1 2 _", 28, P["grey"], "middle")
    s.rect(70, 462, 100, 34, P["green"], P["mint"], 2.6, r=8)
    s.text(120, 487, "students", 24, P["green"], "middle")
    s.rect(182, 462, 108, 34, P["ink"], P["paper"], 2.6, r=8)
    s.text(236, 487, "reload lanes", 22, P["ink"], "middle")
    s.text(180, 526, "the page: captcha, list, sheets", 24, P["grey"], "middle")
    s.arrow([(110, 322), (110, 336)], P["blue"])

    # 2. results-race server + engine
    s.rect(392, 232, 300, 330, P["ink"], P["fog"], 3.4)
    s.hatch(392, 232, 300, 330, P["ink"], 13, .10)
    s.text(542, 272, "results-race", 40, P["green"], "middle")
    s.text(542, 298, "(python, one process)", 24, P["grey"], "middle")
    s.rect(414, 318, 256, 130, P["green"], P["mint"], 3, r=14)
    s.text(542, 354, "engine", 34, P["green"], "middle")
    for i, line in enumerate(("queue + lanes", "1 s: switch to another site", "late answer still counts")):
        s.text(436, 388 + i * 28, "- " + line, 24, P["ink"])
    s.rect(414, 464, 120, 74, P["ink"], P["paper"], 2.8, r=8)
    s.text(474, 494, "out/*.json", 25, P["ink"], "middle")
    s.text(474, 522, "saved results", 21, P["grey"], "middle")
    s.rect(548, 464, 122, 74, P["ink"], P["yellow"], 2.8, r=8)
    s.text(609, 494, "A4 sheet", 26, P["ink"], "middle")
    s.text(609, 522, "+ PNG / zip", 21, P["ink"], "middle")
    s.arrow([(474, 450), (474, 462)], P["ink"], head=True)
    s.arrow([(609, 450), (609, 462)], P["ink"], head=True)

    # config note on top
    s.rect(392, 112, 300, 70, P["ink"], P["yellow"], 3, r=10)
    s.text(542, 146, "results-race.toml", 32, P["ink"], "middle")
    s.text(542, 172, "env vars . flags", 24, P["ink"], "middle")
    s.arrow([(542, 184), (542, 230)], P["ink"], dash="3 8")
    s.text(560, 212, "everything optional", 22, P["grey"])

    # 3. headless chromium with lanes
    s.rect(780, 132, 210, 430, P["ink"], P["sky"], 3.4)
    s.text(885, 172, "headless Chromium", 29, P["blue"], "middle")
    s.text(885, 198, "one session per lane", 22, P["grey"], "middle")
    lanes = [("lane a", P["blush"], None), ("lane b", P["mint"], None), ("lane c", P["fog"], None), ("lane a + proxy", P["paper"], "6 7")]
    for i, (name, fill, dash) in enumerate(lanes):
        y = 222 + i * 80
        s.rect(802, y, 166, 58, P["ink"], fill, 2.8, dash, r=10)
        s.text(885, y + 38, name, 27, P["ink"], "middle")

    # 4. the mirror sites
    s.text(1100, 118, "mirror sites", 34, P["red"], "middle")
    for i, (name, fill, note) in enumerate([("mirror A", P["blush"], ""), ("mirror B", P["mint"], ""), ("mirror C", P["fog"], "slow today")]):
        y = 140 + i * 130
        s.rect(1040, y, 128, 84, P["ink"], fill, 3.2)
        s.text(1104, y + 44, name, 28, P["ink"], "middle")
        if note:
            s.text(1104, y + 72, note, 22, P["red"], "middle")
    s.stroke([(1056, 556), (1104, 548), (1152, 558)], P["ink"], 3)
    s.text(1104, 584, "the same result app,", 24, P["grey"], "middle")
    s.text(1104, 608, "several addresses", 24, P["grey"], "middle")

    # arrows
    s.arrow([(316, 400), (390, 400)], P["blue"], 3.6, flow=True)
    s.arrow([(392, 470), (318, 470)], P["green"], 3.6, flow=True)
    s.text(353, 390, "digits", 24, P["blue"], "middle")
    s.text(353, 500, "captchas,", 22, P["green"], "middle")
    s.text(353, 522, "results", 22, P["green"], "middle")
    s.arrow([(692, 352), (778, 352)], P["ink"], 3.6, flow=True)
    s.text(735, 338, "CDP", 26, P["ink"], "middle")
    for i, y in enumerate((250, 330, 410)):
        s.arrow([(968, y), (1038, 182 + i * 130)], P["ink"], 3.2, flow=True)
    s.arrow([(968, 490), (1036, 408)], P["ink"], 3.2, dash="2 9", flow=True)
    s.text(1002, 526, "via proxy", 23, P["grey"], "middle")

    # numbered story
    s.number(353, 360, 1, P["blue"])
    s.number(735, 294, 2, P["ink"])
    s.number(1020, 150, 3, P["red"])
    s.number(353, 436, 4, P["green"])
    s.packet("M316 400 L392 400 L692 352 L778 352 L968 250 L1038 182", P["red"], 5.5, 0)
    s.packet("M1038 182 L968 250 L778 352 L692 352 L474 470 L318 470", P["green"], 5.5, 2.7, 6)
    return s.svg("How results-race fits together",
                 "Diagram: you read the captcha in your browser and type its digits; the results-race server and its engine hand "
                 "the lookup to a headless Chromium lane, which asks one of several mirror sites (optionally through a proxy). "
                 "The first answer is saved as a JSON file and can be drawn as an A4 sheet or PNG.")


def race():
    s = Sketch(1200, 600, seed=37)
    frame(s)
    total = 12
    s.text(600, 62, "one lookup, three sites, first answer wins", 48, P["green"], "middle")
    x0, per = 190, 92  # x at t=0 and pixels per second
    X = lambda t: x0 + t * per  # noqa: E731
    rows = [(150, "mirror A", P["blush"]), (272, "mirror B", P["mint"]), (392, "mirror C", P["fog"])]
    for y, name, fill in rows:
        s.rect(40, y - 34, 124, 62, P["ink"], fill, 3, r=10)
        s.text(102, y + 8, name, 28, P["ink"], "middle")
        s.stroke([(x0, y), (X(10.2), y)], P["grey"], 2.4, dash="2 9")
    s.stroke([(x0, 462), (X(10.4), 462)], P["ink"], 3.2)
    for t in range(0, 11, 2):
        s.stroke([(X(t), 454), (X(t), 470)], P["ink"], 3)
        s.text(X(t), 500, f"{t} s", 26, P["ink"], "middle")
    s.sweep(x0, X(10.4), 100, 462, total)

    with s.reveal(0.2, total):  # you type, A starts
        s.rect(X(0) - 6, 76, 150, 40, P["ink"], P["yellow"], 2.6, r=8)
        s.text(X(0) + 69, 105, "you type A's", 26, P["ink"], "middle")
        s.arrow([(X(0), 120), (X(0), 142)], P["ink"], 3)
        s.arrow([(X(0) + 6, 150), (X(5.7), 150)], P["red"], 5, flow=True, head=False)
        s.text(X(2.9), 138, "waiting ... waiting ...", 28, P["red"], "middle")
    with s.reveal(1.6, total):  # one second passes
        s.stroke([(X(1), 112), (X(1), 330)], P["red"], 3.4, dash="7 9")
        s.rect(X(1) + 10, 176, 252, 60, P["red"], P["blush"], 3, r=10)
        s.text(X(1) + 136, 202, "1 s and no answer:", 27, P["ink"], "middle")
        s.text(X(1) + 136, 228, "try another site", 27, P["ink"], "middle")
    with s.reveal(3.4, total):  # you type B's
        s.rect(X(1.6), 300, 168, 40, P["ink"], P["yellow"], 2.6, r=8)
        s.text(X(1.6) + 84, 328, "you type B's", 26, P["ink"], "middle")
        s.arrow([(X(2.3), 298), (X(2.3), 282)], P["ink"], 3)
    with s.reveal(4.5, total):  # B answers fast
        s.arrow([(X(2.4), 272), (X(2.8), 272)], P["green"], 6, head=False)
        s.stroke([(X(2.95), 270), (X(3.08), 286), (X(3.35), 248)], P["green"], 7)
        s.rect(X(4.0), 246, 330, 64, P["green"], P["mint"], 3, r=12)
        s.text(X(4.0) + 165, 274, "result! saved.", 33, P["green"], "middle")
        s.text(X(4.0) + 165, 300, "the first answer wins", 25, P["ink"], "middle")
    with s.reveal(8.0, total):  # A answers late
        s.stroke([(X(5.7), 138), (X(5.7), 162)], P["grey"], 5)
        s.rect(X(5.8), 112, 270, 70, P["grey"], P["fog"], 3, r=12)
        s.text(X(5.8) + 135, 140, "late answer from A:", 26, P["ink"], "middle")
        s.text(X(5.8) + 135, 168, "ignored, B already won", 26, P["ink"], "middle")
    with s.reveal(9.4, total):
        s.rect(250, 524, 700, 52, P["blue"], P["sky"], 3, r=12)
        s.text(600, 560, "nobody else answered in 15 s?  then A's late answer is used.", 30, P["ink"], "middle")
    return s.svg("How one lookup races across sites",
                 "Timeline: you type the captcha for mirror A. After one second with no answer the app asks you for mirror B's "
                 "captcha instead. B answers quickly and the result is saved. A's late answer arrives later and is ignored, "
                 "unless nothing else answered within fifteen seconds.")


def build_all():
    return {"banner.svg": banner(), "architecture.svg": architecture(), "race.svg": race()}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(HERE.parent.parent / "docs" / "img"))
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    for name, svg in build_all().items():
        (out / name).write_text(svg, encoding="utf-8")
        print(f"wrote {out / name}  ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
