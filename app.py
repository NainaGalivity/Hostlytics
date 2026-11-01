import calendar
from datetime import date

import streamlit as st

import demand

YEAR = 2026
MONTH = 12
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def money(amount):
    # The backslash stops Streamlit from reading $ as the start of a math formula.
    return f"\\${amount}"


def apply_fix(alert):
    """Save an alert's new prices when the host clicks Apply."""
    st.session_state.price_changes.update(demand.fix_prices(alert))
    st.session_state.applied_fix = alert


def save_edit(night, new_price):
    """Save a hand edit and add it to the top of the edit log."""
    st.session_state.edit_log.insert(0, demand.make_log_entry(night, new_price))
    st.session_state.price_changes[night.date] = {"price": new_price, "source": "host"}
    st.session_state.form_message = ("success", "Got it. We'll learn from this.")


def submit_edit_form(nights_by_day):
    """Check the form and save it. Runs before the page redraws, so the calendar updates."""
    picked_date = st.session_state.edit_date
    new_price = st.session_state.edit_new_price

    if picked_date is None or new_price is None:
        st.session_state.form_message = ("error", "Pick a date and enter a price.")
        return

    night = nights_by_day[picked_date.day]
    if night.booked == "yes":
        message = f"December {picked_date.day} is booked, so its price can't change."
        st.session_state.form_message = ("error", message)
    elif new_price == night.price:
        message = f"December {picked_date.day} is already {money(new_price)}."
        st.session_state.form_message = ("error", message)
    else:
        save_edit(night, new_price)


def reset_demo():
    """Clear every change so the demo can start over."""
    st.session_state.price_changes = {}
    st.session_state.edit_log = []
    st.session_state.applied_fix = None
    st.session_state.form_message = None
    for key in ["edit_date", "edit_new_price"]:
        st.session_state.pop(key, None)


def show_night(night):
    """Draw one calendar square."""
    with st.container(border=True, height="stretch"):
        # Orange marks the nights an alert wants to change.
        if night.new_price:
            st.markdown(f":orange[**{night.date.day}**]")
        else:
            st.markdown(f"**{night.date.day}**")

        if night.price != night.tool_price:
            st.markdown(f"{money(night.price)} ~~{money(night.tool_price)}~~")
        else:
            st.markdown(money(night.price))

        if night.event:
            st.caption(night.event)

        if night.booked == "yes":
            st.badge(night.guest_first_name, icon=":material/person:", color="gray")
        elif night.change_source == "fix":
            st.badge("Fix applied", icon=":material/check:", color="blue")
        elif night.change_source == "host":
            st.badge("Edited by you", icon=":material/edit:", color="violet")
        elif night.new_price:
            st.badge(
                f"Raise to {money(night.new_price)}",
                icon=":material/trending_up:",
                color="orange",
            )
        else:
            st.badge("Open", color="green")


st.set_page_config(page_title="DemandLens", layout="wide")

# Saved per visitor, so one person's clicks never change the demo for anyone else.
st.session_state.setdefault("price_changes", {})
st.session_state.setdefault("edit_log", [])
st.session_state.setdefault("applied_fix", None)
st.session_state.setdefault("form_message", None)

listing = demand.load_listing()
data = demand.load_data()
_, _, events, calendar_2026 = data
alerts = demand.pending_alerts(
    demand.find_missed_spikes(data), st.session_state.price_changes
)
view = demand.build_calendar_view(
    calendar_2026, events, alerts, st.session_state.price_changes
)

st.title("DemandLens")
st.subheader(f"{listing['name']}, {listing['neighborhood']}, San Francisco")
st.badge("Synced from Airbnb · sample data", icon=":material/sync:", color="blue")

applied_fix = st.session_state.applied_fix
if applied_fix:
    st.success(
        f"{len(applied_fix['nights'])} nights updated. "
        f"Possible extra revenue: {money(applied_fix['extra_revenue'])}.",
        title=f"Fix applied for {applied_fix['event_name']}",
        icon=":material/check_circle:",
    )

for alert in alerts:
    days = ", ".join(f"{date.day}" for date in alert["dates"])
    with st.container(border=True):
        text_column, button_column = st.columns([5, 1], vertical_alignment="center")
        text_column.markdown(
            f":orange[:material/lightbulb:] **{alert['event_name']} is back and "
            f"your pricing tool missed it again**"
        )
        text_column.markdown(
            f"Last December you marked up {alert['fixed_nights']} nights by "
            f"{alert['last_year_markup']:.0%} on average for this event. December "
            f"{days} are open and still near base. Suggested markup: "
            f"+{alert['suggested_markup']}%. "
            f"Possible extra revenue: {money(alert['extra_revenue'])}."
        )
        button_column.button(
            f"Apply +{alert['suggested_markup']}%",
            key=f"apply_{alert['event_name']}",
            icon=":material/bolt:",
            type="primary",
            width="stretch",
            on_click=apply_fix,
            args=(alert,),
        )

st.header("December 2026")

weekday_columns = st.columns(7, gap="xsmall", wrap=False)
for column, weekday in zip(weekday_columns, WEEKDAYS):
    column.markdown(f"**{weekday}**")

nights_by_day = {night.date.day: night for night in view.itertuples()}
weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(YEAR, MONTH)

for week in weeks:
    columns = st.columns(7, gap="xsmall", wrap=False)
    for column, day in zip(columns, week):
        if day == 0:  # A square from the month before or after.
            continue
        with column:
            show_night(nights_by_day[day])

st.header("Edit a price")

first_open_night = view.loc[view["booked"] == "no", "date"].min().date()
with st.container(width=480):
    with st.form("edit_price_form", clear_on_submit=True):
        date_column, price_column = st.columns(2)
        date_column.date_input(
            "Date",
            value=first_open_night,
            min_value=date(YEAR, MONTH, 1),
            max_value=date(YEAR, MONTH, 31),
            key="edit_date",
        )
        price_column.number_input(
            "New price",
            min_value=1,
            max_value=10000,
            value=None,
            step=1,
            placeholder="Example: 250",
            key="edit_new_price",
        )
        st.form_submit_button(
            "Save price", on_click=submit_edit_form, args=(nights_by_day,)
        )

    if st.session_state.form_message:
        kind, message = st.session_state.form_message
        if kind == "success":
            st.success(message, icon=":material/check_circle:")
        else:
            st.error(message, icon=":material/error:")

st.header("Edit log")
st.caption("Each price you change by hand is logged as something we learn from.")

if st.session_state.edit_log:
    st.dataframe(
        st.session_state.edit_log,
        hide_index=True,
        alt="Log of prices the host changed by hand",
        column_config={
            "night": "Night",
            "old_price": st.column_config.NumberColumn("Old price", format="$%d"),
            "new_price": st.column_config.NumberColumn("New price", format="$%d"),
            "change_pct": st.column_config.NumberColumn("Change", format="percent"),
            "what_we_learned": "What we learned",
        },
    )
else:
    st.caption("No hand edits yet.")

st.button("Reset demo", icon=":material/restart_alt:", on_click=reset_demo)
