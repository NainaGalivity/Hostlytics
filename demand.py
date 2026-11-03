"""Detection logic for Hostlytics.

Learns from the host's manual fixes last December, then finds the same missed
event this December. See find_missed_spikes for the steps.

Run it with: python demand.py
Test it with: python -m unittest
"""

import math
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

MIN_MARKUP = 0.20  # Smaller changes are treated as noise.
MIN_RUN_NIGHTS = 2  # A single raised night could be a coincidence.
NEAR_BASE_TOLERANCE = 0.10  # Within 10% of base counts as "still at base".
MARKUP_STEP = 5  # Suggested markups go down in steps of 5%.


def load_data():
    """Read the CSV files and return the base price and three tables."""
    listing = pd.read_csv(DATA_DIR / "listing.csv")
    history = pd.read_csv(DATA_DIR / "history_2025.csv", parse_dates=["date"])
    calendar = pd.read_csv(DATA_DIR / "calendar_2026.csv", parse_dates=["date"])
    events = pd.read_csv(
        DATA_DIR / "events.csv",
        parse_dates=["start_2025", "end_2025", "start_2026", "end_2026"],
    )
    base_price = int(listing.loc[0, "base_price"])
    return base_price, history, events, calendar


def load_listing():
    """Return the listing's details as a dictionary."""
    listing = pd.read_csv(DATA_DIR / "listing.csv")
    return listing.loc[0].to_dict()


def find_manual_fixes(history):
    """Return each run of consecutive nights the host marked up by hand."""
    nights = history.assign(
        markup=(history["final_price"] - history["tool_price"]) / history["tool_price"]
    )
    nights = nights[nights["markup"] >= MIN_MARKUP].sort_values("date")

    # A new run starts on any night that doesn't directly follow the one before.
    run_ids = (nights["date"].diff() != pd.Timedelta(days=1)).cumsum()
    return [run for _, run in nights.groupby(run_ids) if len(run) >= MIN_RUN_NIGHTS]


def round_down_markup(markup):
    """Return a markup like 0.3996 as a whole percent rounded down, like 35."""
    # round() stops tiny decimal errors from pushing an exact 40% down to 35%.
    percent = round(markup * 100, 6)
    return math.floor(percent / MARKUP_STEP) * MARKUP_STEP


def find_missed_spikes(data=None):
    """Return an alert for each event the host fixed last year and the tool missed again.

    1. Find the host's manual fixes, ignoring one-off changes.
    2. Match those fixes to an event that overlapped them.
    3. Find that event's nights in December 2026.
    4. Keep the nights still near base that are open to reprice.
    5. Build the alert, suggesting last year's markup rounded down.
    """
    base_price, history, events, calendar = data or load_data()
    fixes = find_manual_fixes(history)

    alerts = []
    for event in events.itertuples():
        matching_fixes = [
            run
            for run in fixes
            if run["date"].min() <= event.end_2025
            and run["date"].max() >= event.start_2025
        ]
        if not matching_fixes:
            continue

        this_year = calendar[calendar["date"].between(event.start_2026, event.end_2026)]
        low = base_price * (1 - NEAR_BASE_TOLERANCE)
        high = base_price * (1 + NEAR_BASE_TOLERANCE)
        missed = this_year[this_year["tool_price"].between(low, high)]

        # Booked nights can't be repriced, so only open nights go in the alert.
        open_nights = missed[missed["booked"] == "no"].copy()
        if open_nights.empty:
            continue

        last_year = pd.concat(matching_fixes)
        last_year_markup = last_year["markup"].mean()
        suggested_markup = round_down_markup(last_year_markup)
        open_nights["new_price"] = (
            (open_nights["tool_price"] * (1 + suggested_markup / 100))
            .round()
            .astype(int)
        )
        alerts.append(
            {
                "event_name": event.event_name,
                "last_year_markup": last_year_markup,
                "fixed_nights": len(last_year),
                "dates": open_nights["date"].tolist(),
                "suggested_markup": suggested_markup,
                "nights": open_nights[["date", "tool_price", "new_price"]],
                "extra_revenue": int(
                    (open_nights["new_price"] - open_nights["tool_price"]).sum()
                ),
            }
        )
    return alerts


def pending_alerts(alerts, price_changes):
    """Return the alerts without nights the host already changed."""
    pending = []
    for alert in alerts:
        nights = alert["nights"]
        nights = nights[~nights["date"].isin(list(price_changes))]
        if nights.empty:
            continue

        extra_revenue = int((nights["new_price"] - nights["tool_price"]).sum())
        pending.append(
            {
                **alert,
                "nights": nights,
                "dates": nights["date"].tolist(),
                "extra_revenue": extra_revenue,
            }
        )
    return pending


def fix_prices(alert):
    """Return the price changes that apply an alert in one click."""
    return {
        night.date: {"price": int(night.new_price), "source": "fix"}
        for night in alert["nights"].itertuples()
    }


def describe_edit(change_pct, event):
    """Return what a hand edit might teach us."""
    if abs(change_pct) < MIN_MARKUP:
        return "Small change, treated as noise"

    direction = "Raised" if change_pct > 0 else "Lowered"
    if event:
        return f"{direction} during {event}: remember for next year"
    return f"{direction} with no known event: possible local demand change"


def make_log_entry(night, new_price):
    """Return one edit log row for a hand edit to a calendar night."""
    change_pct = new_price / night.price - 1
    return {
        "night": f"{night.date:%b %-d, %Y}",
        "old_price": int(night.price),
        "new_price": int(new_price),
        "change_pct": change_pct,
        "what_we_learned": describe_edit(change_pct, night.event),
    }


def build_calendar_view(calendar, events, alerts, price_changes):
    """Return the calendar with each night's event and current price.

    A new_price of 0 means no alert wants to change that night.
    """
    view = calendar.copy()

    view["event"] = ""
    for event in events.itertuples():
        in_event = view["date"].between(event.start_2026, event.end_2026)
        view.loc[in_event, "event"] = event.short_name

    new_prices = {}
    for alert in alerts:
        for night in alert["nights"].itertuples():
            new_prices[night.date] = night.new_price
    view["new_price"] = view["date"].map(new_prices).fillna(0).astype(int)

    view["price"] = view["tool_price"]
    view["change_source"] = ""
    for date, change in price_changes.items():
        night = view["date"] == date
        view.loc[night, "price"] = change["price"]
        view.loc[night, "change_source"] = change["source"]

    return view


def main():
    alerts = find_missed_spikes()

    print(f"Found {len(alerts)} alert(s).")
    for alert in alerts:
        print(f"\n{alert['event_name']}")
        print(
            f"Host marked up {alert['fixed_nights']} nights "
            f"by {alert['last_year_markup']:.0%} on average last year."
        )
        print(f"Suggested markup: +{alert['suggested_markup']}%")
        print(alert["nights"].to_string(index=False))
        print(f"Possible extra revenue: ${alert['extra_revenue']}")


if __name__ == "__main__":
    main()
