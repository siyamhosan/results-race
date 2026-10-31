"""Render a saved result as one A4 page (794x1123 CSS px = 210x297 mm at 96 dpi).
Fonts and logos are embedded in the page, so it renders the same offline. Logos are optional (see CardStyle)."""
import base64
import re
from dataclasses import dataclass
from html import escape as e
from pathlib import Path

from .config import FOOTER_NOTE

FONT_DIR = Path(__file__).parent / "fonts"
LOGO_FILES = {"seal": ("seal.svg", "seal.png"), "board_logo": ("board-logo.png", "board-logo.jpg", "board-logo.svg")}
MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


@dataclass
class CardStyle:
    seal: str = ""  # data: URI; empty = not drawn
    board_logo: str = ""
    header_line: str = "Government of the People's Republic of Bangladesh"
    board_title: str = "Board of Intermediate and Secondary Education"
    sheet_title: str = "RESULT SHEET"
    footer_note: str = FOOTER_NOTE
    show_fetch_time: bool = True
    credit: str = ""  # a small line at the very bottom; empty = none


def _data_uri(path):
    return f"data:{MIME[path.suffix.lower()]};base64," + base64.b64encode(path.read_bytes()).decode()


def load_logos(folder, enabled=True, **style):
    """A CardStyle with whichever logos exist in `folder` (seal.svg|png, board-logo.png|jpg|svg). None found = none drawn."""
    found = {}
    if enabled and folder and Path(folder).is_dir():
        for key, names in LOGO_FILES.items():
            path = next((Path(folder) / n for n in names if (Path(folder) / n).is_file()), None)
            found[key] = _data_uri(path) if path else ""
    return CardStyle(**{**found, **style})

POINTS = {"A+": 5, "A": 4, "A-": 3.5, "B": 3, "C": 2, "D": 1, "F": 0}
EXAMS = {"ssc": "Secondary School Certificate (SSC)", "hsc": "Higher Secondary Certificate (HSC)",
         "jsc": "Junior School Certificate (JSC)"}
GRADE_OF_GPA = [(5, "A+"), (4, "A"), (3.5, "A-"), (3, "B"), (2, "C"), (1, "D")]

def _font(name, file, weight):
    data = base64.b64encode((FONT_DIR / file).read_bytes()).decode()
    return f"@font-face{{font-family:'{name}';font-weight:{weight};src:url(data:font/woff2;base64,{data}) format('woff2')}}"


FONTS = _font("Plex Sans", "plex-sans-400.woff2", 400) + _font("Plex Sans", "plex-sans-600.woff2", 600) + \
    _font("Plex Serif", "plex-serif-600.woff2", 600)

CSS = FONTS + """@page{size:A4;margin:0}*{box-sizing:border-box;margin:0;padding:0}
body{background:#fff;font:13.5px/1.45 'Plex Sans',system-ui,sans-serif;color:#1d2a33;font-variant-numeric:tabular-nums lining-nums;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.serif{font-family:'Plex Serif',Georgia,serif;font-weight:600}
.page{width:794px;height:1123px;position:relative;overflow:hidden;background:#fff;display:flex;flex-direction:column}
.top{height:9px;background:linear-gradient(90deg,#006a4e 0 82%,#f42a41 82% 100%)}
.wm{position:absolute;left:50%;top:575px;width:540px;height:540px;transform:translate(-50%,-50%);opacity:.05;object-fit:contain}
.head{display:grid;grid-template-columns:84px 1fr 84px;align-items:center;gap:18px;padding:18px 46px 12px;position:relative}
.head img{width:84px;height:84px;object-fit:contain}.head .c{text-align:center}
.gov{font-size:10px;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:#53636f}
.head h1{font-size:22px;line-height:1.22;color:#0b3d2e;margin:5px 0 3px}
.head h2{font-size:13px;font-weight:600;letter-spacing:.46em;color:#006a4e;text-indent:.46em}
.rule{margin:0 46px;height:5px;border-top:2px solid #006a4e;border-bottom:1px solid #006a4e;position:relative}
.title{text-align:center;margin:14px 46px 0;position:relative}
.title b{display:block;font-size:19px;letter-spacing:.34em;text-indent:.34em;color:#0b3d2e}
.title span{display:block;margin-top:3px;color:#53636f;font-size:12.5px}
.body{padding:14px 46px 0;flex:1;display:flex;flex-direction:column;gap:14px;position:relative}
.strip{display:grid;grid-template-columns:1.25fr 1fr 1.25fr;border-top:1.5px solid #006a4e;border-bottom:1.5px solid #006a4e;background:#fff}
.strip>div{padding:11px 18px 12px;border-left:1px solid #d3ddd8}.strip>div:first-child{border-left:0;padding-left:2px}
.strip small{display:block;font-size:9.5px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:#53636f}
.strip .v{display:flex;align-items:baseline;gap:7px;font-size:32px;line-height:1.15;margin-top:3px;color:#0b3d2e}.strip .v i{font:400 13px 'Plex Sans';color:#53636f;font-style:normal}
.strip .ok{color:#0b7a4b}.strip .no{color:#b42626}.strip .res{display:flex;align-items:center;gap:8px;font-size:24px;margin-top:6px;letter-spacing:.04em}
.strip svg{width:22px;height:22px;flex:none}
.who{margin-top:0}.who small,.kv small{display:block;font-size:9.5px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:#53636f}
.who b{display:block;font-size:24px;line-height:1.2;color:#0b3d2e;margin-top:2px}
.kv{display:grid;grid-template-columns:1fr 1fr 1fr;gap:0 24px}.kv>div{padding:6px 0 7px;border-bottom:1px dotted #b9c4cc}.kv b{display:block;font-weight:600;font-size:13.5px;margin-top:1px}
.kv .w{grid-column:span 3}
table{width:100%;border-collapse:collapse}th{background:#0b3d2e;color:#fff;font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:.12em;text-align:left;padding:7px 10px}
td{padding:4.6px 10px;border-bottom:1px solid #e1e8e5}tr:nth-child(even) td{background:#f5f9f7}td.c,th.c{text-align:center}
td.code{color:#53636f;width:62px;white-space:nowrap}.conv{font-size:11px;color:#53636f;text-align:right;margin-top:6px}.conv b{color:#1d2a33}
.f4{font-size:8.5px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#006a4e;border:1px solid #006a4e;border-radius:3px;padding:0 4px;margin-left:6px}td.gr{font-weight:600;width:84px}td.pt{width:110px}
.roomy td{padding:10.5px 10px;font-size:14.5px}.roomy th{padding:9px 10px}.roomy .kv>div{padding:9px 0 10px}.roomy .body{gap:20px}.roomy .strip>div{padding:15px 18px 16px}.roomy .strip>div:first-child{padding-left:2px}
.roomy .scale{margin-top:2px}
@media print{html,body{width:210mm;height:297mm;overflow:hidden}.page{height:1122px;break-after:avoid;break-inside:avoid}}
.dense td{padding:3px 10px;font-size:12.5px}.dense .kv>div{padding:4px 0 5px}
.sub td{background:#e6f0eb!important;font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:.12em;color:#0b3d2e;padding:4px 10px}
.scale{font-size:10px;color:#53636f;display:flex;justify-content:space-between}
.foot{margin:auto 46px 0;padding:11px 0 28px;border-top:2px solid #006a4e;display:flex;justify-content:space-between;gap:24px;font-size:10.5px;color:#53636f;position:relative}
.foot b{color:#1d2a33;font-weight:600}
.credit{position:absolute;left:0;right:0;bottom:6px;text-align:center;font-size:11px;font-weight:600;letter-spacing:.12em;color:#53636f}"""


def gpa_letter(g):
    return next((l for lo, l in GRADE_OF_GPA if g >= lo), "F")


def parse_entry(part):
    """One `display_details` entry -> (code, marks, grade). The site writes `101:A+`, or with marks `101:171=A+`
    (two papers of a subject share a code like `101-102`), or `101:60+40+30=130=A+` (parts, then the total)."""
    code, _, rest = part.partition(":")
    *marks, grade = (x.strip() for x in rest.split("="))
    total = marks[-1] if marks else ""
    return code.strip(), (total.lstrip("0") or "0") if total.isdigit() else total, grade


def render(rec, exam, year, style=None):
    style = style or CardStyle()
    r, d = rec["result"]["res"], rec["result"]
    names = {s["SUB_CODE"]: s["SUB_NAME"] for s in d.get("sub_details", [])}

    has_marks = any("=" in p for p in (r.get("display_details") or "").split(","))

    def subject(code):  # `101-102` is two papers of one subject: show its name once
        seen = []
        for c in code.split("-"):
            if names.get(c) and names[c] not in seen:
                seen.append(names[c])
        return e(" / ".join(seen)) + (" <span class=f4>4th subject</span>" if code == r.get("sub4th") else "")

    def rows(text):
        out = []
        for part in (text or "").split(","):
            if ":" in part:
                code, marks, grade = parse_entry(part)
                out.append(f'<tr><td class=code>{e(code)}</td><td>{subject(code)}</td>'
                           f'{f"<td class=c>{e(marks)}</td>" if has_marks else ""}'
                           f'<td class="c gr">{e(grade)}</td><td class="c pt">{POINTS.get(grade.upper(), 0):.2f}</td></tr>')
        return "".join(out)

    n_rows = (r.get("display_details") or "").count(":") + (r.get("display_details_ca") or "").count(":")
    gpa = (r.get("res_detail") or "").replace("GPA=", "").strip()
    try:
        g = float(gpa)
    except ValueError:
        g = 0.0
    failed = g <= 0
    ca = rows(r.get("display_details_ca"))
    took = f' · fetched in {rec["ms"] / 1000:.1f}s' if rec.get("ms") and style.show_fetch_time else ""  # shown beside the site
    host = re.sub(r"^https?://", "", rec.get("site", ""))
    ref = f'{r.get("board_name", "")[:3]}-{exam}{str(year)[-2:]}-{r.get("roll_no", "")}'.upper()
    fields = [("Father", "fname"), ("Mother", "mname"), ("Roll No", "roll_no"), ("Registration", "regno"), ("Session", "session"),
              ("Group", "stud_group"), ("Student type", "stud_type"), ("Date of birth", "dob")]
    kv = "".join(f'<div><small>{k}</small><b>{e(str(r.get(key) or "-"))}</b></div>' for k, key in fields)
    kv += f'<div><small>Thana / District</small><b>{e(r.get("t_name") or "-")} / {e(r.get("z_name") or "-")}</b></div>'
    kv += f'<div class=w><small>Institution</small><b>{e(r.get("inst_name") or "-")}</b></div>'
    conv_note = f"<div class=conv>Converted marks (out of 1000): <b>{e(str(r['conv_1000']))}</b></div>" if r.get("conv_1000") else ""
    tick = '<svg viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=3 stroke-linecap=round stroke-linejoin=round><circle cx=12 cy=12 r=10.5 stroke-width=2 /><path d="M7 12.5l3.2 3.2L17 8.8"/></svg>'
    cross = '<svg viewBox="0 0 24 24" fill=none stroke=currentColor stroke-width=3 stroke-linecap=round><circle cx=12 cy=12 r=10.5 stroke-width=2 /><path d="M8 8l8 8M16 8l-8 8"/></svg>'
    return f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=794"><style>{CSS}</style>
<div class="page{' dense' if n_rows > 12 else ' roomy' if n_rows <= 9 else ''}"><div class=top></div>{f'<img class=wm src="{style.board_logo}" alt="">' if style.board_logo else ''}
<div class=head>{f'<img src="{style.seal}" alt="">' if style.seal else '<span></span>'}<div class=c>
<div class=gov>{e(style.header_line)}</div>
<h1 class=serif>{e(style.board_title)}</h1><h2>{e((r.get("board_name") or "").upper())}</h2></div>
{f'<img src="{style.board_logo}" alt="">' if style.board_logo else '<span></span>'}</div><div class=rule></div>
<div class=title><b class=serif>{e(style.sheet_title)}</b><span>{e(EXAMS.get(exam.lower(), exam.upper()))} Examination, {e(str(year))}</span></div>
<div class=body>
<div class=strip>
<div><small>Grade point average</small><div class="v serif">{'—' if failed else f'{g:.2f}'}<i>/ 5.00</i></div></div>
<div><small>Letter grade</small><div class="v serif">{'F' if failed else gpa_letter(g)}</div></div>
<div><small>Result</small><div class="res serif {'no' if failed else 'ok'}">{cross if failed else tick}{'NOT PASSED' if failed else 'PASSED'}</div></div></div>
<div class=who><small>Name of examinee</small><b class=serif>{e(r.get("name") or "")}</b></div>
<div class=kv>{kv}</div>
<table><tr><th>Code</th><th>Subject</th>{"<th class=c>Marks</th>" if has_marks else ""}<th class=c>Grade</th><th class=c>Grade point</th></tr>{rows(r.get("display_details"))}
{f'<tr class=sub><td colspan={4 + has_marks}>Additional / co-curricular</td></tr>{ca}' if ca else ''}</table>
{conv_note}<div class=scale><span>A+ 5.00</span><span>A 4.00</span><span>A- 3.50</span><span>B 3.00</span><span>C 2.00</span><span>D 1.00</span><span>F 0.00</span></div>
</div>
<div class=foot><span>{e(style.footer_note)}</span>
<span style="text-align:right;white-space:nowrap">{e(host)}{e(took)}<br>Ref. {e(ref)}</span></div>
{f'<div class=credit>{e(style.credit)}</div>' if style.credit else ''}</div>"""
