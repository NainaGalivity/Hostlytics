"""Create the sample CSV files in data/ for the Hostlitics demo.

Everything here is made up. Run it with: python make_mock_data.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
BASE_PRICE = 185
GUESTS = ["Maya", "Liam", "Sofia", "Noah", "Priya", "Ethan", "Chloe", "Mateo"]

# The 2026 AGU dates are real. The 2025 dates are invented for the demo,
# because the real 2025 meeting was in New Orleans, not San Francisco.
AGU_2025 = (date(2025, 12, 8), date(2025, 12, 12))
AGU_2026 = (date(2026, 12, 7), date(2026, 12, 11))
CHRISTMAS_2025 = (date(2025, 12, 24), date(2025, 12, 26))
CHRISTMAS_2026 = (date(2026, 12, 24), date(2026, 12, 26))

# The nights the host raised by hand, plus one small change that is just noise.
OVERRIDE_NIGHTS_2025 = [date(2025, 12, 9), date(2025, 12, 10), date(2025, 12, 11)]
NOISE_NIGHT_2025 = date(2025, 12, 18)
NOISE_AMOUNT = 10

# On this night in 2026, a guest already booked the conference at base price.
BOOKED_CONFERENCE_NIGHT_2026 = date(2026, 12, 7)


def december_nights(year):
    """Return every night of December in the given year."""
    return [date(year, 12, day) for day in range(1, 32)]


def is_between(night, date_range):
    """Return True if night falls inside (start, end), including both ends."""
    start, end = date_range
    return start <= night <= end


def tool_price(night, conference, holiday, rng):
    """Return what the pricing tool suggests for one night.

    The tool knows about weekends and holidays but not the conference,
    which is the gap this demo is built around.
    """
    if is_between(night, conference):
        return BASE_PRICE + rng.randint(-3, 3)
    if is_between(night, holiday):
        return BASE_PRICE + 35 + rng.randint(-3, 3)
    if night.weekday() in (4, 5):  # Friday and Saturday
        return BASE_PRICE + 20 + rng.randint(-5, 5)
    return BASE_PRICE + rng.randint(-5, 5)


def write_csv(filename, fieldnames, rows):
    """Write a list of dictionaries to a CSV file in data/."""
    with open(DATA_DIR / filename, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def make_listing():
    return [
        {
            "name": "Bright SoMa Loft",
            "neighborhood": "SoMa",
            "base_price": BASE_PRICE,
        }
    ]


def make_history(rng):
    rows = []
    for night in december_nights(2025):
        tool = tool_price(night, AGU_2025, CHRISTMAS_2025, rng)
        final = tool
        booked = rng.random() < 0.65

        if night in OVERRIDE_NIGHTS_2025:
            final = round(tool * 1.4)
            booked = True  # Guests still paid the higher price.
        elif night == NOISE_NIGHT_2025:
            final = tool + NOISE_AMOUNT

        rows.append(
            {
                "date": night,
                "tool_price": tool,
                "final_price": final,
                "booked": "yes" if booked else "no",
            }
        )
    return rows


def make_events():
    return [
        {
            "event_name": "American Geophysical Union Annual Meeting",
            "short_name": "AGU",
            "start_2025": AGU_2025[0],
            "end_2025": AGU_2025[1],
            "start_2026": AGU_2026[0],
            "end_2026": AGU_2026[1],
        },
        {
            "event_name": "Christmas",
            "short_name": "Christmas",
            "start_2025": CHRISTMAS_2025[0],
            "end_2025": CHRISTMAS_2025[1],
            "start_2026": CHRISTMAS_2026[0],
            "end_2026": CHRISTMAS_2026[1],
        },
    ]


def make_calendar(rng):
    rows = []
    for night in december_nights(2026):
        tool = tool_price(night, AGU_2026, CHRISTMAS_2026, rng)

        if is_between(night, AGU_2026):
            # Leave most conference nights open so there is something to fix.
            booked = night == BOOKED_CONFERENCE_NIGHT_2026
        else:
            booked = rng.random() < 0.4

        rows.append(
            {
                "date": night,
                "tool_price": tool,
                "booked": "yes" if booked else "no",
                "guest_first_name": rng.choice(GUESTS) if booked else "",
            }
        )
    return rows


def main():
    DATA_DIR.mkdir(exist_ok=True)
    rng = random.Random(42)  # A fixed seed gives the same data on every run.

    write_csv("listing.csv", ["name", "neighborhood", "base_price"], make_listing())
    write_csv(
        "history_2025.csv",
        ["date", "tool_price", "final_price", "booked"],
        make_history(rng),
    )
    write_csv(
        "events.csv",
        ["event_name", "short_name", "start_2025", "end_2025", "start_2026", "end_2026"],
        make_events(),
    )
    write_csv(
        "calendar_2026.csv",
        ["date", "tool_price", "booked", "guest_first_name"],
        make_calendar(rng),
    )
    print(f"Wrote 4 CSV files to {DATA_DIR}")


if __name__ == "__main__":
    main()
