import calendar

import streamlit as st

import demand

YEAR = 2026
MONTH = 12
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def money(amount):
    # The backslash stops Streamlit from reading $ as the start of a math formula.
    return f"\\${amount}"


def apply_fix(recommendation):
    """Save a recommendation's new prices when the host clicks Apply."""
    st.session_state.price_changes.update(demand.fix_prices(recommendation))
    st.session_state.applied_fix = recommendation


def save_edit(night, new_price):
    """Save a hand edit and add it to the top of the edit log."""
    st.session_state.edit_log.insert(0, demand.make_log_entry(night, new_price))
    st.session_state.price_changes[night.date] = {"price": new_price, "source": "host"}


@st.dialog("Edit price")
def edit_price(night):
    st.markdown(f"**{night.date:%A, %B %-d}**")
    new_price = st.number_input(
        "New nightly price",
        min_value=1,
        max_value=10000,
        value=int(night.price),
        step=1,
    )
    if st.button("Save price", type="primary"):
        if new_price != night.price:
            save_edit(night, new_price)
        st.rerun()


def show_night(night):
    """Draw one calendar square. Return True if its Edit button was clicked."""
    with st.container(border=True, height="stretch"):
        st.markdown(f"**{night.date.day}**")

        if night.price != night.tool_price:
            st.markdown(f"{money(night.price)} ~~{money(night.tool_price)}~~")
        else:
            st.markdown(money(night.price))

        if night.event:
            st.caption(night.event)

        if night.booked == "yes":
            st.badge(night.guest_first_name, icon=":material/person:", color="gray")
            return False

        if night.change_source == "fix":
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

        return st.button(
            "Edit",
            key=f"edit_{night.date.day}",
            icon=":material/edit:",
            type="tertiary",
        )


st.set_page_config(page_title="DemandLens", layout="wide")

# Saved per visitor, so one person's clicks never change the demo for anyone else.
st.session_state.setdefault("price_changes", {})
st.session_state.setdefault("edit_log", [])
st.session_state.setdefault("applied_fix", None)

listing = demand.load_listing()
base_price, history, events, calendar_2026 = demand.load_data()
learned_events = demand.find_learned_events(history, events)
all_recommendations = demand.find_recommendations(
    calendar_2026, learned_events, base_price
)
recommendations = demand.pending_recommendations(
    all_recommendations, st.session_state.price_changes
)
view = demand.build_calendar_view(
    calendar_2026, events, recommendations, st.session_state.price_changes
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

for recommendation in recommendations:
    st.warning(
        f"Last December you raised {recommendation['raised_nights']} nights by "
        f"{recommendation['raise_pct']:.0%} for this event, and your pricing tool "
        f"missed it. Possible extra revenue: {money(recommendation['extra_revenue'])}.",
        title=f"{recommendation['event_name']} is back and prices are still at base",
        icon=":material/lightbulb:",
    )
    st.button(
        f"Apply fix to {len(recommendation['nights'])} nights",
        key=f"apply_{recommendation['event_name']}",
        icon=":material/bolt:",
        type="primary",
        on_click=apply_fix,
        args=(recommendation,),
    )

st.header("December 2026")

weekday_columns = st.columns(7, gap="xsmall", wrap=False)
for column, weekday in zip(weekday_columns, WEEKDAYS):
    column.markdown(f"**{weekday}**")

nights_by_day = {night.date.day: night for night in view.itertuples()}
weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(YEAR, MONTH)

night_to_edit = None
for week in weeks:
    columns = st.columns(7, gap="xsmall", wrap=False)
    for column, day in zip(columns, week):
        if day == 0:  # A square from the month before or after.
            continue
        with column:
            if show_night(nights_by_day[day]):
                night_to_edit = nights_by_day[day]

if night_to_edit:
    edit_price(night_to_edit)

st.header("Edit log")
st.caption(
    "Each price you change by hand is logged as something we learn from. "
    "Refreshing the page resets the demo."
)

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
