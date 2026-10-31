"""Detection logic for DemandLens.

Learns from the host's past price changes, then finds the same missed event
this year. The steps match the order of the functions below:

1. Find the nights the host changed the tool's price.
2. Keep the big raises that happened during a known event.
3. Check if that event is back this year with prices still at base.
4. Recommend new prices, using the raise the host chose last time.

Run it with: python demand.py
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

MIN_RAISE_PCT = 0.15  # Smaller changes are treated as noise.
MIN_RAISED_NIGHTS = 2  # One raised night could be a coincidence.
AT_BASE_TOLERANCE = 0.05  # Within 5% above base still counts as "at base".


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


def find_overrides(history):
    """Return the nights where the host charged something other than the tool price."""
    overrides = history[history["final_price"] != history["tool_price"]].copy()
    overrides["change_pct"] = overrides["final_price"] / overrides["tool_price"] - 1
    return overrides


def find_learned_events(history, events):
    """Return the events the host raised prices for by hand last year."""
    overrides = find_overrides(history)
    raises = overrides[overrides["change_pct"] >= MIN_RAISE_PCT]

    learned = []
    for event in events.itertuples():
        during_event = raises[raises["date"].between(event.start_2025, event.end_2025)]
        if len(during_event) < MIN_RAISED_NIGHTS:
            continue

        learned.append(
            {
                "event_name": event.event_name,
                "start_2026": event.start_2026,
                "end_2026": event.end_2026,
                "raise_pct": during_event["change_pct"].mean(),
                "raised_nights": len(during_event),
            }
        )
    return learned


def find_recommendations(calendar, learned_events, base_price):
    """Return one recommendation per learned event still priced near base."""
    at_base_limit = base_price * (1 + AT_BASE_TOLERANCE)

    recommendations = []
    for event in learned_events:
        in_event = calendar["date"].between(event["start_2026"], event["end_2026"])
        at_base = calendar["tool_price"] <= at_base_limit
        missed_nights = calendar[in_event & at_base]

        # Booked nights can't be repriced, so only open nights get a new price.
        open_nights = missed_nights[missed_nights["booked"] == "no"].copy()
        booked_nights = missed_nights[missed_nights["booked"] == "yes"]
        if open_nights.empty:
            continue

        open_nights["new_price"] = (
            (open_nights["tool_price"] * (1 + event["raise_pct"])).round().astype(int)
        )
        recommendations.append(
            {
                "event_name": event["event_name"],
                "raise_pct": event["raise_pct"],
                "raised_nights": event["raised_nights"],
                "nights": open_nights[["date", "tool_price", "new_price"]],
                "extra_revenue": int(
                    (open_nights["new_price"] - open_nights["tool_price"]).sum()
                ),
                "booked_at_base": len(booked_nights),
            }
        )
    return recommendations


def pending_recommendations(recommendations, price_changes):
    """Return the recommendations without nights the host already changed."""
    pending = []
    for recommendation in recommendations:
        nights = recommendation["nights"]
        nights = nights[~nights["date"].isin(list(price_changes))]
        if nights.empty:
            continue

        extra_revenue = int((nights["new_price"] - nights["tool_price"]).sum())
        pending.append(
            {**recommendation, "nights": nights, "extra_revenue": extra_revenue}
        )
    return pending


def fix_prices(recommendation):
    """Return the price changes that apply a recommendation in one click."""
    return {
        night.date: {"price": int(night.new_price), "source": "fix"}
        for night in recommendation["nights"].itertuples()
    }


def describe_edit(change_pct, event):
    """Return what a hand edit might teach us."""
    if abs(change_pct) < MIN_RAISE_PCT:
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


def build_calendar_view(calendar, events, recommendations, price_changes):
    """Return the calendar with each night's event and current price.

    A new_price of 0 means there is no recommendation for that night.
    """
    view = calendar.copy()

    view["event"] = ""
    for event in events.itertuples():
        in_event = view["date"].between(event.start_2026, event.end_2026)
        view.loc[in_event, "event"] = event.short_name

    new_prices = {}
    for recommendation in recommendations:
        for night in recommendation["nights"].itertuples():
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
    base_price, history, events, calendar = load_data()
    learned_events = find_learned_events(history, events)
    recommendations = find_recommendations(calendar, learned_events, base_price)

    print(f"Host changed {len(find_overrides(history))} nights last year.")
    print(f"Found {len(recommendations)} recommendation(s).")
    for recommendation in recommendations:
        print(f"\n{recommendation['event_name']}")
        print(
            f"Host raised {recommendation['raised_nights']} nights "
            f"by {recommendation['raise_pct']:.0%} last year."
        )
        print(recommendation["nights"].to_string(index=False))
        print(f"Possible extra revenue: ${recommendation['extra_revenue']}")
        print(f"Already booked at base: {recommendation['booked_at_base']} night(s)")


if __name__ == "__main__":
    main()
