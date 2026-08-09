"""
Flask REST API + dashboard for the funnel drop-off analyzer.

Endpoints:
    GET /                    -> HTML dashboard (funnel chart, segment table, narrative)
    GET /api/funnel          -> recompute funnel from data/events.csv, persist a snapshot, return JSON
    GET /api/funnel/latest   -> return the most recently persisted snapshot (no recompute)
    GET /api/funnel/history  -> list past snapshots (id, created_at, overall_cvr_pct)
    GET /api/funnel/trend    -> latest vs previous snapshot delta

Run with: python -m src.app
"""
import os

from flask import Flask, jsonify, render_template

from src.funnel import FunnelAnalyzer, load_events
from src.narrative import generate_narrative
from src import storage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "events.csv")
DB_PATH = os.path.join(BASE_DIR, "data", "funnel.db")

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))


def _run_analysis():
    df = load_events(DATA_PATH)
    analyzer = FunnelAnalyzer(df)
    report = analyzer.full_report()
    narrative = generate_narrative(report)
    return report, narrative


@app.route("/api/funnel")
def api_funnel():
    report, narrative = _run_analysis()
    conn = storage.get_connection(DB_PATH)
    cvr = storage.save_snapshot(conn, report, narrative)
    conn.close()
    return jsonify({"overall_cvr_pct": cvr, "report": report, "narrative": narrative})


@app.route("/api/funnel/latest")
def api_funnel_latest():
    conn = storage.get_connection(DB_PATH)
    snap = storage.latest_snapshot(conn)
    conn.close()
    if not snap:
        return jsonify({"error": "no snapshots yet, call /api/funnel first"}), 404
    return jsonify(snap)


@app.route("/api/funnel/history")
def api_funnel_history():
    conn = storage.get_connection(DB_PATH)
    rows = storage.history(conn, limit=20)
    conn.close()
    slim = [{"id": r["id"], "created_at": r["created_at"], "overall_cvr_pct": r["overall_cvr_pct"]} for r in rows]
    return jsonify(slim)


@app.route("/api/funnel/trend")
def api_funnel_trend():
    conn = storage.get_connection(DB_PATH)
    trend = storage.trend_vs_previous(conn)
    conn.close()
    return jsonify(trend or {"message": "not enough snapshots yet"})


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    if not os.path.exists(DATA_PATH):
        from src.data_gen import write_csv
        write_csv(DATA_PATH)
    app.run(debug=True, port=5024)
