import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import storage

FAKE_REPORT = {
    "overall_funnel": [
        {"stage": "visit", "users": 100, "pct_of_start": 100.0, "pct_of_prev": 100.0},
        {"stage": "signup", "users": 50, "pct_of_start": 50.0, "pct_of_prev": 50.0},
    ],
    "biggest_dropoff": {"from_stage": "visit", "to_stage": "signup", "users_lost": 50, "drop_pct": 50.0},
    "time_to_convert": [],
    "segments": {"channel": [], "device": []},
}
FAKE_NARRATIVE = {"summary": "test summary", "recommendations": ["do the thing"]}


def _tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    return path


def test_save_and_fetch_latest():
    db_path = _tmp_db()
    conn = storage.get_connection(db_path)
    cvr = storage.save_snapshot(conn, FAKE_REPORT, FAKE_NARRATIVE)
    assert cvr == 50.0

    latest = storage.latest_snapshot(conn)
    assert latest["overall_cvr_pct"] == 50.0
    assert latest["narrative"]["summary"] == "test summary"
    conn.close()
    os.remove(db_path)


def test_trend_vs_previous_needs_two_snapshots():
    db_path = _tmp_db()
    conn = storage.get_connection(db_path)
    assert storage.trend_vs_previous(conn) is None

    storage.save_snapshot(conn, FAKE_REPORT, FAKE_NARRATIVE)
    assert storage.trend_vs_previous(conn) is None  # still only 1

    report2 = dict(FAKE_REPORT)
    report2["overall_funnel"] = [
        {"stage": "visit", "users": 100, "pct_of_start": 100.0, "pct_of_prev": 100.0},
        {"stage": "signup", "users": 60, "pct_of_start": 60.0, "pct_of_prev": 60.0},
    ]
    storage.save_snapshot(conn, report2, FAKE_NARRATIVE)
    trend = storage.trend_vs_previous(conn)
    assert trend["delta_pp"] == 10.0
    conn.close()
    os.remove(db_path)


def test_history_ordering():
    db_path = _tmp_db()
    conn = storage.get_connection(db_path)
    storage.save_snapshot(conn, FAKE_REPORT, FAKE_NARRATIVE)
    storage.save_snapshot(conn, FAKE_REPORT, FAKE_NARRATIVE)
    rows = storage.history(conn, limit=10)
    assert len(rows) == 2
    assert rows[0]["id"] > rows[1]["id"]  # most recent first
    conn.close()
    os.remove(db_path)
