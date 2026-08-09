"""
Synthetic event-log generator for the funnel analyzer.

Simulates a typical SaaS/e-commerce acquisition funnel:
    visit -> signup -> activate -> purchase -> retain

Each simulated user is assigned an acquisition channel (organic, paid,
referral, email) and a device (desktop, mobile). Per-segment conversion
probabilities are deliberately uneven so the analyzer has real drop-off
patterns and statistically significant segment gaps to find.
"""
import csv
import random
from datetime import datetime, timedelta

STAGES = ["visit", "signup", "activate", "purchase", "retain"]

CHANNELS = ["organic", "paid", "referral", "email"]
DEVICES = ["desktop", "mobile"]

# Base probability of advancing to the next stage, per channel.
# (visit->signup, signup->activate, activate->purchase, purchase->retain)
CHANNEL_CONVERSION = {
    "organic": [0.42, 0.68, 0.55, 0.60],
    "paid": [0.30, 0.50, 0.35, 0.38],   # paid traffic converts worse (realistic)
    "referral": [0.55, 0.72, 0.60, 0.65],
    "email": [0.38, 0.60, 0.50, 0.55],
}

# Mobile underperforms desktop at the purchase step specifically
# (a classic real-world checkout-friction pattern).
DEVICE_MULTIPLIER = {
    "desktop": [1.0, 1.0, 1.0, 1.0],
    "mobile": [0.95, 0.90, 0.65, 0.90],
}


def _advance(prob):
    return random.random() < prob


def generate_events(n_users=6000, seed=42, start_date="2026-06-01"):
    """Return a list of dict rows: user_id, channel, device, stage, timestamp."""
    random.seed(seed)
    start = datetime.fromisoformat(start_date)
    rows = []

    for uid in range(1, n_users + 1):
        channel = random.choices(CHANNELS, weights=[0.35, 0.30, 0.15, 0.20])[0]
        device = random.choices(DEVICES, weights=[0.55, 0.45])[0]

        base = CHANNEL_CONVERSION[channel]
        mult = DEVICE_MULTIPLIER[device]

        t = start + timedelta(minutes=random.randint(0, 60 * 24 * 60))
        rows.append({
            "user_id": uid, "channel": channel, "device": device,
            "stage": "visit", "timestamp": t.isoformat(),
        })

        reached = True
        for i, stage in enumerate(STAGES[1:]):
            prob = min(base[i] * mult[i], 0.98)
            if reached and _advance(prob):
                t = t + timedelta(hours=random.uniform(0.1, 72))
                rows.append({
                    "user_id": uid, "channel": channel, "device": device,
                    "stage": stage, "timestamp": t.isoformat(),
                })
            else:
                reached = False
    return rows


def write_csv(path, n_users=6000, seed=42):
    rows = generate_events(n_users=n_users, seed=seed)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "channel", "device", "stage", "timestamp"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "data/events.csv"
    count = write_csv(out)
    print(f"Wrote {count} events to {out}")
