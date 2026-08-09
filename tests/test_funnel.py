import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.funnel import FunnelAnalyzer, _two_proportion_z_test


def _fixture_df():
    """10 users: all visit, 8 signup, 4 activate. Channel A users convert
    much better than channel B users on purpose, so the significance test
    has something real to flag."""
    rows = []
    ts = "2026-01-01T00:00:00"
    for uid in range(1, 11):
        channel = "A" if uid <= 5 else "B"
        device = "desktop"
        rows.append({"user_id": uid, "channel": channel, "device": device, "stage": "visit", "timestamp": ts})
    # channel A: 5/5 signup, channel B: 3/5 signup
    for uid in [1, 2, 3, 4, 5, 6, 7, 8]:
        channel = "A" if uid <= 5 else "B"
        rows.append({"user_id": uid, "channel": channel, "device": "desktop", "stage": "signup", "timestamp": ts})
    # activate: only users 1,2,3,4 (all channel A) -- the steepest drop (50%)
    for uid in [1, 2, 3, 4]:
        rows.append({"user_id": uid, "channel": "A", "device": "desktop", "stage": "activate", "timestamp": ts})
    # purchase: same 4 users carry through (0% drop from activate)
    for uid in [1, 2, 3, 4]:
        rows.append({"user_id": uid, "channel": "A", "device": "desktop", "stage": "purchase", "timestamp": ts})
    # retain: 3 of the 4 purchasers stick around (25% drop, smaller than activate's 50%)
    for uid in [1, 2, 3]:
        rows.append({"user_id": uid, "channel": "A", "device": "desktop", "stage": "retain", "timestamp": ts})
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    from src.data_gen import STAGES
    df["stage"] = pd.Categorical(df["stage"], categories=STAGES, ordered=True)
    return df


def test_overall_funnel_counts():
    analyzer = FunnelAnalyzer(_fixture_df())
    funnel = {row["stage"]: row for row in analyzer.overall_funnel()}
    assert funnel["visit"]["users"] == 10
    assert funnel["signup"]["users"] == 8
    assert funnel["activate"]["users"] == 4
    assert funnel["purchase"]["users"] == 4
    assert funnel["retain"]["users"] == 3
    assert funnel["signup"]["pct_of_prev"] == 80.0


def test_biggest_dropoff_is_signup_to_activate():
    analyzer = FunnelAnalyzer(_fixture_df())
    drop = analyzer.biggest_dropoff()
    assert drop["from_stage"] == "signup"
    assert drop["to_stage"] == "activate"
    assert drop["users_lost"] == 4


def test_segment_breakdown_flags_channel_b():
    analyzer = FunnelAnalyzer(_fixture_df())
    segments = analyzer.segment_breakdown("channel")
    by_name = {s["segment"]: s for s in segments}
    # Channel B converts 0/3 at activate vs channel A which converts well —
    # channel B should be flagged as significantly underperforming somewhere.
    assert "flagged_transition" in by_name["B"] or any(
        t["significant_underperformance"] for t in by_name["B"]["transitions"]
    )


def test_two_proportion_z_test_identical_rates_not_significant():
    z, p = _two_proportion_z_test(50, 100, 50, 100)
    assert p == pytest.approx(1.0, abs=1e-6)


def test_two_proportion_z_test_large_gap_significant():
    z, p = _two_proportion_z_test(10, 100, 90, 100)
    assert p < 0.001


def test_time_to_convert_shape():
    analyzer = FunnelAnalyzer(_fixture_df())
    ttc = analyzer.time_to_convert()
    assert isinstance(ttc, list)
    for entry in ttc:
        assert entry["median_hours"] >= 0
