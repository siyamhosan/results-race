"""Read the list of students to look up: .json, .csv or plain text (roll and reg per line)."""
import csv
import io
import json
import re
from pathlib import Path


def load_students(path):
    """-> [(roll, reg), ...] in file order, duplicates dropped. An empty path means no list: start empty."""
    if not path:
        return []
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        raise ValueError(f"cannot read students file {path}: {e.strerror or e}") from None
    suffix = path.suffix.lower()
    if suffix == ".json":
        pairs = _json(text, path)
    elif suffix == ".csv":
        pairs = _csv(text)
    else:
        pairs = _lines(text)
    seen, out = set(), []
    for roll, reg in pairs:
        if roll not in seen:
            seen.add(roll)
            out.append((roll, reg))
    return out


def _json(text, path):
    try:
        rows = json.loads(text)
        return [(str(r["roll"]).strip(), str(r["reg"]).strip()) for r in rows]
    except (ValueError, KeyError, TypeError):
        raise ValueError(f'{path}: expected a list like [{{"roll": 100001, "reg": "2100000001"}}]') from None


def _csv(text):
    rows = [r for r in csv.reader(io.StringIO(text)) if r and any(c.strip() for c in r)]
    swap = False
    if rows and not rows[0][0].strip().isdigit():  # a header row
        head = [c.strip().lower() for c in rows[0]]
        swap = head[:2] == ["reg", "roll"]
        rows = rows[1:]
    out = []
    for n, r in enumerate(rows, 1):
        if len(r) < 2 or not r[0].strip() or not r[1].strip():
            raise ValueError(f"csv row {n}: need roll and reg")
        a, b = r[0].strip(), r[1].strip()
        out.append((b, a) if swap else (a, b))
    return out


def _lines(text):
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [p for p in re.split(r"[,\s]+", line) if p]
        if len(parts) < 2:
            raise ValueError(f"line {n}: expected 'roll reg', got {line!r}")
        out.append((parts[0], parts[1]))
    return out
