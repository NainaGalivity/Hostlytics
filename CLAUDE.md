# Hostlitics

## Product
Pricing tools miss local demand spikes, so hosts fix prices by hand. We learn from those fixes automatically. We give short-term rental hosts personalized pricing recommendations with almost no setup.

## Demo goal (for a YC application)
Show one San Francisco host's December 2026 calendar, the upcoming month, "synced from Airbnb" (sample data, clearly labeled). Detect that in December 2025 the host manually raised prices for a conference the pricing tool missed, notice the conference is back in December 2026 with prices still at base, and recommend a fix the host can apply in one click. When the host edits a price by hand, log it as something we learn from.

The conference is the American Geophysical Union (AGU) annual meeting. Its December 7-11, 2026 San Francisco dates are real. Its December 8-12, 2025 San Francisco dates are invented for the demo: the real 2025 meeting was in New Orleans, so never present the 2025 SF dates as fact.

## Rules
- I'm a beginner learning as I go. Explain what you do and why.
- Keep data in `data/`, logic in `demand.py`, and the screen in `app.py`.
- Use mock data only.
- Don't copy Airbnb's logo or branding.
