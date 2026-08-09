"""
Core funnel analysis engine.

Computes overall stage-to-stage conversion, per-segment breakdowns (by
acquisition channel and device), flags statistically significant
underperforming segments with a two-proportion z-test, measures
time-to-convert between stages, and identifies the single biggest
drop-off point in the funnel.
"""
import math
from collections import defaultdict

import pandas as pd

from src.data_gen import STAGES


def load_events(path):
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["stage"] = pd.Categorical(df["stage"], categories=STAGES, ordered=True)
    return df


def _two_proportion_z_test(x1, n1, x2, n2):
    """Two-proportion z-test. Returns (z, p_value). Uses a normal approximation
    (no scipy dependency required for this specific test, but we use scipy's
    normal CDF for accuracy)."""
    from scipy.stats import norm

    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    p1, p2 = x1 / n1, x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p1 - p2) / se
    p_value = 2 * (1 - norm.cdf(abs(z)))
    return z, p_value


class FunnelAnalyzer:
    def __init__(self, df):
        self.df = df
        # first timestamp a user reaches each stage
        reach = (
            df.sort_values("timestamp")
            .groupby(["user_id", "stage"], observed=True)["timestamp"]
            .first()
            .unstack("stage")
        )
        # unstack can leave columns as dtype=object when some stages have no
        # rows for a given user; force each stage column back to datetime so
        # downstream subtraction/notna() logic behaves consistently.
        for col in reach.columns:
            reach[col] = pd.to_datetime(reach[col], errors="coerce")
        self.reach = reach

    def overall_funnel(self):
        """Stage counts + conversion rate from previous stage + from stage 1."""
        counts = {s: int(self.reach[s].notna().sum()) if s in self.reach else 0 for s in STAGES}
        total = counts[STAGES[0]] or 1
        rows = []
        prev = None
        for s in STAGES:
            c = counts[s]
            rows.append({
                "stage": s,
                "users": c,
                "pct_of_start": round(100 * c / total, 2),
                "pct_of_prev": round(100 * c / prev, 2) if prev else 100.0,
            })
            prev = c or prev
        return rows

    def biggest_dropoff(self):
        """Return the (from_stage, to_stage, users_lost, drop_pct) with the largest
        percentage loss between consecutive stages."""
        funnel = self.overall_funnel()
        worst = None
        for i in range(1, len(funnel)):
            drop_pct = 100 - funnel[i]["pct_of_prev"]
            lost = funnel[i - 1]["users"] - funnel[i]["users"]
            if worst is None or drop_pct > worst["drop_pct"]:
                worst = {
                    "from_stage": funnel[i - 1]["stage"],
                    "to_stage": funnel[i]["stage"],
                    "users_lost": lost,
                    "drop_pct": round(drop_pct, 2),
                }
        return worst

    def segment_breakdown(self, dimension):
        """Per-segment stage counts + significance test vs. the rest of users,
        at the stage transition where the segment most underperforms."""
        assert dimension in ("channel", "device")
        seg_col = self.df[["user_id", dimension]].drop_duplicates().set_index("user_id")[dimension]
        reach = self.reach.copy()
        reach[dimension] = seg_col

        results = []
        for seg_value, group in reach.groupby(dimension, observed=True):
            rest = reach[reach[dimension] != seg_value]
            seg_result = {"segment": seg_value, "dimension": dimension, "transitions": []}
            worst_p = None
            for i in range(1, len(STAGES)):
                prev_stage, stage = STAGES[i - 1], STAGES[i]
                # a stage may be entirely absent from this dataset (e.g. small
                # test fixtures) -- treat it as zero reached rather than KeyError.
                seg_prev_n = int(group[prev_stage].notna().sum()) if prev_stage in group else 0
                seg_n = int(group[stage].notna().sum()) if stage in group else 0
                rest_prev_n = int(rest[prev_stage].notna().sum()) if prev_stage in rest else 0
                rest_n = int(rest[stage].notna().sum()) if stage in rest else 0

                seg_rate = round(100 * seg_n / seg_prev_n, 2) if seg_prev_n else 0.0
                rest_rate = round(100 * rest_n / rest_prev_n, 2) if rest_prev_n else 0.0
                z, p = _two_proportion_z_test(seg_n, seg_prev_n, rest_n, rest_prev_n)
                significant = p < 0.05 and seg_rate < rest_rate

                transition = {
                    "from_stage": prev_stage, "to_stage": stage,
                    "segment_conversion_pct": seg_rate,
                    "rest_conversion_pct": rest_rate,
                    "p_value": round(float(p), 4),
                    "significant_underperformance": bool(significant),
                }
                seg_result["transitions"].append(transition)
                if significant and (worst_p is None or p < worst_p):
                    worst_p = p
                    seg_result["flagged_transition"] = transition
            results.append(seg_result)
        return results

    def time_to_convert(self):
        """Median hours spent between each consecutive stage, across users who
        completed that transition."""
        out = []
        for i in range(1, len(STAGES)):
            prev_stage, stage = STAGES[i - 1], STAGES[i]
            if prev_stage not in self.reach or stage not in self.reach:
                continue
            delta = (self.reach[stage] - self.reach[prev_stage]).dropna()
            hours = delta.dt.total_seconds() / 3600
            if len(hours) == 0:
                continue
            out.append({
                "from_stage": prev_stage,
                "to_stage": stage,
                "median_hours": round(float(hours.median()), 2),
                "mean_hours": round(float(hours.mean()), 2),
                "n": int(len(hours)),
            })
        return out

    def full_report(self):
        return {
            "overall_funnel": self.overall_funnel(),
            "biggest_dropoff": self.biggest_dropoff(),
            "time_to_convert": self.time_to_convert(),
            "segments": {
                "channel": self.segment_breakdown("channel"),
                "device": self.segment_breakdown("device"),
            },
        }
