"""
Plain-English narrative generator (NLG) for a funnel report.

Turns the structured output of FunnelAnalyzer.full_report() into a short
paragraph an executive can read without looking at any charts, plus a
bullet list of concrete recommendations. This is template-based NLG
(no external LLM call needed), matching the style of prior days in the
series that use lightweight, explainable text generation.
"""


def generate_narrative(report):
    funnel = report["overall_funnel"]
    drop = report["biggest_dropoff"]
    start_users = funnel[0]["users"]
    end_users = funnel[-1]["users"]
    overall_cvr = round(100 * end_users / start_users, 2) if start_users else 0.0

    lines = []
    lines.append(
        f"Of {start_users:,} users who entered the funnel, {end_users:,} "
        f"({overall_cvr}%) reached the final stage ('{funnel[-1]['stage']}')."
    )
    lines.append(
        f"The steepest drop-off is between '{drop['from_stage']}' and "
        f"'{drop['to_stage']}': {drop['users_lost']:,} users "
        f"({drop['drop_pct']}%) are lost at this step."
    )

    flags = []
    for dim, segments in report["segments"].items():
        for seg in segments:
            ft = seg.get("flagged_transition")
            if ft:
                flags.append(
                    f"{dim}='{seg['segment']}' converts significantly worse than "
                    f"other segments from '{ft['from_stage']}' to '{ft['to_stage']}' "
                    f"({ft['segment_conversion_pct']}% vs {ft['rest_conversion_pct']}%, "
                    f"p={ft['p_value']})."
                )
    if flags:
        lines.append("Statistically significant segment gaps detected: " + " ".join(flags))
    else:
        lines.append("No segment showed a statistically significant conversion gap (p<0.05).")

    recommendations = []
    recommendations.append(
        f"Prioritize fixing the '{drop['from_stage']}' -> '{drop['to_stage']}' step first; "
        f"it accounts for the largest single loss of users in the funnel."
    )
    for dim, segments in report["segments"].items():
        for seg in segments:
            ft = seg.get("flagged_transition")
            if ft:
                recommendations.append(
                    f"Investigate why {dim} segment '{seg['segment']}' underperforms at "
                    f"'{ft['from_stage']}' -> '{ft['to_stage']}' — closing this gap to the "
                    f"rest-of-population rate ({ft['rest_conversion_pct']}%) would recover "
                    f"meaningful volume."
                )
    slowest = max(report["time_to_convert"], key=lambda t: t["median_hours"], default=None)
    if slowest:
        recommendations.append(
            f"Users take the longest to move from '{slowest['from_stage']}' to "
            f"'{slowest['to_stage']}' (median {slowest['median_hours']}h) — consider "
            f"nudges/reminders to shorten this gap."
        )

    return {
        "summary": " ".join(lines),
        "recommendations": recommendations,
    }
