"""File names for downloaded sheets: who it is, how they did, and their roll, e.g. Md-Rahim-Uddin_GPA-4.22_100001.png"""
import re
import unicodedata
from urllib.parse import quote

NAME_LIMIT = 60


def _words(text):
    """Letters and digits of any script (marks such as Bengali vowel signs stay with their letter); everything else separates."""
    text = unicodedata.normalize("NFKC", str(text or "")).replace("'", "").replace("’", "")
    words, current = [], ""
    for ch in text:
        if ch.isalnum() or unicodedata.category(ch) in ("Mn", "Mc"):
            current += ch
        elif current:
            words.append(current)
            current = ""
    return words + ([current] if current else [])


def _slug(text, limit=NAME_LIMIT):
    return "-".join(w.capitalize() for w in _words(text))[:limit].strip("-")


def _result(res_detail):
    if not (res_detail or "").strip():
        return ""
    m = re.search(r"GPA\s*=?\s*(\d+(?:\.\d+)?)", res_detail, re.I)
    if m:
        gpa = float(m.group(1))
        return f"GPA-{gpa:.2f}" if gpa > 0 else "Not-Passed"
    return _slug(res_detail)


def png_filename(name, res_detail, roll):
    parts = [_slug(name) or "Student", _result(res_detail), "".join(_words(roll))]
    return "_".join(p for p in parts if p) + ".png"


def unique_names(names):
    """Same list, with a counter before the extension on repeats, so a zip never has two entries with one name."""
    seen, out = {}, []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        if seen[n] == 1:
            out.append(n)
        else:
            stem, dot, ext = n.rpartition(".")
            out.append(f"{stem}-{seen[n]}.{ext}" if dot else f"{n}-{seen[n]}")
    return out


def content_disposition(filename):
    """Download header: an ASCII fallback for old clients plus the real name (RFC 5987), so any script survives."""
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r'[\x00-\x1f"\\]', "", ascii_name)
    stem, dot, ext = ascii_name.rpartition(".")
    if not re.search(r"[A-Za-z0-9]", stem or ascii_name):
        ascii_name = "result" + (dot + ext if dot else "")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"
