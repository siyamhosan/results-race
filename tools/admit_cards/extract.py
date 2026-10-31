"""Usage: extract.py [folder]. Reads the roll and reg numbers off saved admit cards and writes <folder>/students.json (feeds results-race)."""
import json
import re
import sys
from pathlib import Path

here = Path(__file__).parent
src = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "out"
dest = src / "students.json"
rows = []
for f in sorted(src.glob("*.html")):
    text = re.sub(r"<[^>]+>", "|", f.read_text(encoding="utf-8"))
    roll, reg = (re.search(rf"{k}\.?[\s|]*:\s*([\d ]+)", text) for k in ("Roll No", "Reg No"))
    rows.append({"roll": roll and roll[1].replace(" ", ""), "reg": reg and reg[1].replace(" ", "")})
dest.write_text(json.dumps(rows, indent=2))
print(len(rows), "cards ->", dest)
