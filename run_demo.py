"""
CLI demo: generates synthetic event data (if missing), runs the funnel
analysis, persists a snapshot to SQLite, and prints the narrative +
segment flags to the console. Useful for exercising the whole pipeline
without starting the Flask server.

Usage:
    python run_demo.py
    python run_demo.py --regenerate  # force-regenerate synthetic data
"""
import argparse
import os

from src.data_gen import write_csv
from src.funnel import FunnelAnalyzer, load_events
from src.narrative import generate_narrative
from src import storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "events.csv")
DB_PATH = os.path.join(BASE_DIR, "data", "funnel.db")


def main():
    parser = argparse.ArgumentParser(description="Run the funnel drop-off analyzer demo.")
    parser.add_argument("--regenerate", action="store_true", help="regenerate synthetic event data")
    parser.add_argument("--n-users", type=int, default=6000)
    args = parser.parse_args()

    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    if args.regenerate or not os.path.exists(DATA_PATH):
        n = write_csv(DATA_PATH, n_users=args.n_users)
        print(f"Generated {n} synthetic events -> {DATA_PATH}")

    df = load_events(DATA_PATH)
    analyzer = FunnelAnalyzer(df)
    report = analyzer.full_report()
    narrative = generate_narrative(report)

    conn = storage.get_connection(DB_PATH)
    cvr = storage.save_snapshot(conn, report, narrative)
    trend = storage.trend_vs_previous(conn)
    conn.close()

    print("\n=== Overall funnel ===")
    for row in report["overall_funnel"]:
        print(f"  {row['stage']:<10} users={row['users']:<6} "
              f"pct_of_start={row['pct_of_start']}% pct_of_prev={row['pct_of_prev']}%")

    print(f"\nOverall conversion (first -> last stage): {cvr}%")
    if trend:
        print(f"Trend vs previous snapshot: {trend['delta_pp']:+.2f}pp "
              f"({trend['previous_cvr_pct']}% -> {trend['latest_cvr_pct']}%)")

    print("\n=== Biggest drop-off ===")
    d = report["biggest_dropoff"]
    print(f"  {d['from_stage']} -> {d['to_stage']}: lost {d['users_lost']} users ({d['drop_pct']}%)")

    print("\n=== Narrative ===")
    print(narrative["summary"])
    print("\nRecommendations:")
    for r in narrative["recommendations"]:
        print(f"  - {r}")


if __name__ == "__main__":
    main()
