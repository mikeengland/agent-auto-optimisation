"""Database helpers used by the agent's tools."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

MAX_ROWS = 50
_READ_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def _connect(db_path: Path) -> sqlite3.Connection:
    # mode=ro makes the connection itself read-only, so a write can't succeed even if the check below is bypassed.
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def describe_schema(db_path: Path) -> str:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT sql FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name").fetchall()
    return "\n\n".join(r[0].strip() + ";" for r in rows if r[0])


def run_sql(db_path: Path, query: str) -> str:
    if not _READ_ONLY.match(query):
        return "ERROR: only read-only SELECT (or WITH ... SELECT) queries are allowed."
    try:
        with _connect(db_path) as conn:
            cur = conn.execute(query)
            columns = [d[0] for d in cur.description or []]
            rows = cur.fetchmany(MAX_ROWS + 1)
    except sqlite3.Error as e:
        return f"ERROR: {e}"
    if not rows:
        return "(no rows)"
    lines = [" | ".join(columns)]
    lines += [" | ".join("NULL" if v is None else str(v) for v in row) for row in rows[:MAX_ROWS]]
    if len(rows) > MAX_ROWS:
        lines.append(f"... (truncated to {MAX_ROWS} rows; aggregate or add LIMIT)")
    return "\n".join(lines)
