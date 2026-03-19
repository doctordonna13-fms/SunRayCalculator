# Copenhagen Sun Café Finder ☀️

Pick a date and see which Copenhagen cafés are bathed in direct sunlight. Sun visibility is calculated using real building footprints from OpenStreetMap and the NOAA solar position algorithm — no API key required.

## Features

- Full-day sun schedule for each café, sampled every 10 minutes
- Visual timeline bar showing shadow/partial/blazing blocks
- Sorts by most sun, rating, or name
- Optional Google Maps API key for real place photos
- Works with Python 3.9+

## Setup

```bash
pip install streamlit requests
```

## Run

```bash
streamlit run app.py
```

## How it works

`sun_rating.py` fetches building footprints within 500m of each café from the OpenStreetMap Overpass API, then ray-casts from the seating area toward the sun. If any building wall blocks the line of sight (accounting for building height vs. solar altitude), the point is in shadow. A 5×5 grid of sample points is averaged to produce a 0–100% sun rating.

`app.py` calls `sun_rating.sun_schedule()` for each café across the selected date, merges consecutive same-tier intervals into blocks, and renders everything as a Streamlit grid.

## Cafés included

10 spots across Copenhagen: Juno the Bakery, Conditori La Glace, Skt. Peders Bageri, Andersen Bakery, Cakery Copenhagen, Rug Bakery, norange coffee roasters, The Artisan Copenhagen, ROAST Coffee, and Impact Roasters.

## Data sources

- Building footprints: © OpenStreetMap contributors (ODbL)
- Solar position: NOAA algorithm (no external dependency)
- Place photos: Google Places API (optional)
