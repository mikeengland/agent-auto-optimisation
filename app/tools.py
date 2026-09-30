"""Database helpers used by the agent's tools."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

MAX_ROWS = 50
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_READ_ONLY =re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def _connect(db_path: Path) -> sqlite3.Connection:
    # mode=ro makes the connection itself read-only, so a write can't succeed even if the check below is bypassed.
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def describe_schema(db_path: Path) -> str:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT sql FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name").fetchall()
    return "\n\n".join(r[0].strip() + ";" for r in rows if r[0])


def net_revenue(db_path: Path, start: str, end: str) -> str:
    """Revenue for orders placed in [start, end): completed orders only, net of their refunds.

    Everything is attributed to the order date, including refunds issued in a later period.
    """
    if not (_DATE.match(start) and _DATE.match(end)):
        return "ERROR: start and end must be ISO dates (YYYY-MM-DD)."
    with _connect(db_path) as conn:
        gross, refunded = conn.execute(
            """
            SELECT COALESCE(SUM(o.total_pence), 0),
                   COALESCE(SUM((SELECT SUM(r.amount_pence) FROM refunds r WHERE r.order_id = o.id)), 0)
            FROM orders o
            WHERE o.status = 'completed' AND o.created_at >= ? AND o.created_at < ?
            """,
            (start, end),
        ).fetchone()
    return (
        f"Net revenue for orders placed {start} to {end} (end exclusive): £{(gross - refunded) / 100:,.2f} "
        f"(gross £{gross / 100:,.2f} from completed orders, less £{refunded / 100:,.2f} refunds)"
    )


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
