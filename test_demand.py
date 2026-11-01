"""Small tests for find_missed_spikes. Run them with: python -m unittest"""

import unittest

import pandas as pd

import demand

BASE = 100
CONFERENCE_2025 = ("2025-12-08", "2025-12-12")
CONFERENCE_2026 = ("2026-12-07", "2026-12-11")


def make_history(final_prices):
    """Return December 2025 at the tool's $100, with final prices by day of month."""
    days = pd.date_range("2025-12-01", "2025-12-31")
    return pd.DataFrame(
        {
            "date": days,
            "tool_price": 100,
            "final_price": [final_prices.get(day.day, 100) for day in days],
            "booked": "yes",
        }
    )


def make_calendar(tool_prices=None, booked_days=()):
    """Return December 2026, with optional tool prices and booked nights by day."""
    tool_prices = tool_prices or {}
    days = pd.date_range("2026-12-01", "2026-12-31")
    return pd.DataFrame(
        {
            "date": days,
            "tool_price": [tool_prices.get(day.day, 100) for day in days],
            "booked": ["yes" if day.day in booked_days else "no" for day in days],
        }
    )


def make_events(start_2026=CONFERENCE_2026[0], end_2026=CONFERENCE_2026[1]):
    return pd.DataFrame(
        {
            "event_name": ["Conference"],
            "short_name": ["Conf"],
            "start_2025": pd.to_datetime([CONFERENCE_2025[0]]),
            "end_2025": pd.to_datetime([CONFERENCE_2025[1]]),
            "start_2026": pd.to_datetime([start_2026]),
            "end_2026": pd.to_datetime([end_2026]),
        }
    )


def find_alerts(final_prices, calendar=None, events=None):
    if calendar is None:
        calendar = make_calendar()
    if events is None:
        events = make_events()
    data = (BASE, make_history(final_prices), events, calendar)
    return demand.find_missed_spikes(data)


class FindMissedSpikesTests(unittest.TestCase):
    def test_real_data_finds_the_conference(self):
        alerts = demand.find_missed_spikes()
        self.assertEqual(len(alerts), 1)
        alert = alerts[0]
        self.assertEqual(alert["event_name"], "American Geophysical Union Annual Meeting")
        self.assertAlmostEqual(alert["last_year_markup"], 0.3996, places=3)
        self.assertEqual(alert["suggested_markup"], 35)
        self.assertEqual([date.day for date in alert["dates"]], [8, 9, 10, 11])

    def test_run_of_nights_creates_an_alert(self):
        alerts = find_alerts({9: 150, 10: 150})
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["suggested_markup"], 50)

    def test_one_off_change_is_ignored(self):
        self.assertEqual(find_alerts({9: 150}), [])

    def test_gap_between_nights_is_not_a_run(self):
        self.assertEqual(find_alerts({8: 150, 10: 150}), [])

    def test_markup_of_exactly_20_percent_counts(self):
        self.assertEqual(len(find_alerts({9: 120, 10: 120})), 1)

    def test_markup_under_20_percent_is_ignored(self):
        self.assertEqual(find_alerts({9: 119, 10: 119}), [])

    def test_run_with_no_event_is_ignored(self):
        self.assertEqual(find_alerts({20: 150, 21: 150}), [])

    def test_run_touching_the_event_by_one_night_matches(self):
        self.assertEqual(len(find_alerts({12: 150, 13: 150})), 1)

    def test_event_not_back_this_year_is_ignored(self):
        events = make_events(start_2026=None, end_2026=None)
        self.assertEqual(find_alerts({9: 150, 10: 150}, events=events), [])

    def test_tool_already_raised_prices_is_ignored(self):
        calendar = make_calendar(tool_prices={day: 150 for day in range(7, 12)})
        self.assertEqual(find_alerts({9: 150, 10: 150}, calendar=calendar), [])

    def test_price_exactly_10_percent_above_base_counts(self):
        calendar = make_calendar(tool_prices={day: 110 for day in range(7, 12)})
        self.assertEqual(len(find_alerts({9: 150, 10: 150}, calendar=calendar)), 1)

    def test_booked_nights_are_left_out(self):
        calendar = make_calendar(booked_days=[7, 9])
        alerts = find_alerts({9: 150, 10: 150}, calendar=calendar)
        self.assertEqual([date.day for date in alerts[0]["dates"]], [8, 10, 11])

    def test_no_alert_when_every_night_is_booked(self):
        calendar = make_calendar(booked_days=range(7, 12))
        self.assertEqual(find_alerts({9: 150, 10: 150}, calendar=calendar), [])


class RoundDownMarkupTests(unittest.TestCase):
    def test_rounds_down_to_nearest_5(self):
        self.assertEqual(demand.round_down_markup(0.3996), 35)
        self.assertEqual(demand.round_down_markup(0.24), 20)

    def test_exact_multiples_stay_the_same(self):
        for percent in range(5, 150, 5):
            self.assertEqual(demand.round_down_markup(percent / 100), percent)


if __name__ == "__main__":
    unittest.main()
