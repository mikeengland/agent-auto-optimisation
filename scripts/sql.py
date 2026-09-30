"""Run ad-hoc SQL against the demo database: uv run python scripts/sql.py "select ..." """

import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "app" / "data" / "shop.db"

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
for statement in sys.argv[1:]:
    cur = conn.execute(statement)
    print(" | ".join(d[0] for d in cur.description))
    for row in cur.fetchall():
        print(" | ".join(str(v) for v in row))
    print()
