"""
SQLite persistence for funnel analysis snapshots.

Every time the funnel is (re)computed, a snapshot row is stored with the
full JSON report and narrative, so the dashboard/API can show trend vs.
the previous run (e.g. "overall conversion improved 1.3pp since last week").
"""
import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS funnel_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    overall_cvr_pct REAL NOT NULL,
    report_json TEXT NOT NULL,
    narrative_json TEXT NOT NULL
);
"""


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def save_snapshot(conn, report, narrative):
    funnel = report["overall_funnel"]
    start_users, end_users = funnel[0]["users"], funnel[-1]["users"]
    overall_cvr = round(100 * end_users / start_users, 2) if start_users else 0.0
    conn.execute(
        "INSERT INTO funnel_snapshots (created_at, overall_cvr_pct, report_json, narrative_json) "
        "VALUES (?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(),
            overall_cvr,
            json.dumps(report),
            json.dumps(narrative),
        ),
    )
    conn.commit()
    return overall_cvr


def latest_snapshot(conn):
    row = conn.execute(
        "SELECT id, created_at, overall_cvr_pct, report_json, narrative_json "
        "FROM funnel_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def history(conn, limit=20):
    rows = conn.execute(
        "SELECT id, created_at, overall_cvr_pct, report_json, narrative_json "
        "FROM funnel_snapshots ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def trend_vs_previous(conn):
    """Return (latest_cvr, previous_cvr, delta_pp) or None if <2 snapshots."""
    rows = history(conn, limit=2)
    if len(rows) < 2:
        return None
    latest, previous = rows[0], rows[1]
    delta = round(latest["overall_cvr_pct"] - previous["overall_cvr_pct"], 2)
    return {
        "latest_cvr_pct": latest["overall_cvr_pct"],
        "previous_cvr_pct": previous["overall_cvr_pct"],
        "delta_pp": delta,
    }


def _row_to_dict(row):
    id_, created_at, cvr, report_json, narrative_json = row
    return {
        "id": id_,
        "created_at": created_at,
        "overall_cvr_pct": cvr,
        "report": json.loads(report_json),
        "narrative": json.loads(narrative_json),
    }
