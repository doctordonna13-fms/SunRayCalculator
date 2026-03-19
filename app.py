"""
Copenhagen Sun Café Finder
==========================
Pick a date, see which cafes are bathed in sunlight.
Run with:  streamlit run app.py
Requires:  sun_rating.py in the same folder
           pip install streamlit requests
"""

import streamlit as st
import datetime
import sys
import os
import time
from typing import Optional
import requests as _requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Café data  (real coords from Google Places)
# ---------------------------------------------------------------------------

CAFES = [
    {
        "name": "Juno the Bakery",
        "address": "Århusgade 48, Nordhavn",
        "lat": 55.7061815, "lon": 12.5818152,
        "rating": 4.7, "type": "Bakery",
        "description": "Legendary cardamom buns with a permanent queue outside.",
        "place_id": "ChIJF5yoNfBSUkYRFjOQZdocHAE",
    },
    {
        "name": "Conditori La Glace",
        "address": "Skoubogade 3, Indre By",
        "lat": 55.6785921, "lon": 12.5735765,
        "rating": 4.4, "type": "Konditori",
        "description": "Denmark's oldest pastry shop since 1870. Royal-worthy cakes.",
        "place_id": "ChIJWTHxrRFTUkYRUWrFJLIQ3XE",
    },
    {
        "name": "Skt. Peders Bageri",
        "address": "Sankt Peders Stræde 29, Indre By",
        "lat": 55.6791425, "lon": 12.5692086,
        "rating": 4.7, "type": "Bakery",
        "description": "Best cinnamon rolls in the city. Worth every minute of the queue.",
        "place_id": "ChIJYZCmMw5TUkYRDQkDQk42d-Q",
    },
    {
        "name": "Andersen Bakery",
        "address": "Thorshavnsgade 26, Amager Vest",
        "lat": 55.6672402, "lon": 12.5785336,
        "rating": 4.6, "type": "Bakery",
        "description": "Rosemary focaccia and miso caramel knots that stop time.",
        "place_id": "ChIJZ7Yecw1TUkYREYMSW_uwIQQ",
    },
    {
        "name": "Cakery Copenhagen",
        "address": "Borgergade 17F, Indre By",
        "lat": 55.6847788, "lon": 12.5857796,
        "rating": 4.8, "type": "Cake Shop",
        "description": "Mini éclairs in every flavour. Pistachio is life-changing.",
        "place_id": "ChIJS7a3NmpTUkYR2FfHGxzPtIM",
    },
    {
        "name": "Rug Bakery",
        "address": "Tietgensgade 39, Vesterbro",
        "lat": 55.6712708, "lon": 12.5672720,
        "rating": 4.5, "type": "Bakery",
        "description": "Spacious and cosy — the anti-queue bakery. Great lemon olive oil cake.",
        "place_id": "ChIJwzY0RllTUkYRPqjsIApACpw",
    },
    {
        "name": "norange coffee roasters",
        "address": "Blegdamsvej 4D, Nørrebro",
        "lat": 55.6909650, "lon": 12.5616589,
        "rating": 4.9, "type": "Coffee",
        "description": "Minimalist, spacious, no rush. Seriously exceptional espresso.",
        "place_id": "ChIJS-iN-RVTUkYRVisruoMqMio",
    },
    {
        "name": "The Artisan Copenhagen",
        "address": "Sortedam Dossering 45A, Nørrebro",
        "lat": 55.6919995, "lon": 12.5688717,
        "rating": 4.8, "type": "Coffee",
        "description": "Lakeside specialty coffee. Their cardamom buns are absurdly good.",
        "place_id": "ChIJGZml5xVTUkYRxZoGXkjydpE",
    },
    {
        "name": "ROAST Coffee",
        "address": "Vestmannagade 4, Amager",
        "lat": 55.6683323, "lon": 12.5795253,
        "rating": 4.9, "type": "Coffee",
        "description": "V60 pour-over specialists. Three pastries, done perfectly.",
        "place_id": "ChIJjScl7mpTUkYRSVg6gu40e8s",
    },
    {
        "name": "Impact Roasters",
        "address": "Griffenfeldsgade 4, Nørrebro",
        "lat": 55.6895574, "lon": 12.5554382,
        "rating": 4.8, "type": "Coffee",
        "description": "Soulful atmosphere, V60 pour-over, and genuinely friendly baristas.",
        "place_id": "ChIJpVwa0ApTUkYREl_U2fY1VmU",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TYPE_COLORS = {
    "Bakery":    ("#FFF0DC", "#E8913A", "🥐"),
    "Konditori": ("#FFF0DC", "#E8913A", "🎂"),
    "Cake Shop": ("#FCE8F8", "#C86DB5", "🍰"),
    "Coffee":    ("#E8F4FD", "#3A7DC8", "☕"),
}

TIER_CSS = {
    "none":    "#1E2340",   # near-black night
    "partial": "#F5C842",   # golden yellow
    "full":    "#FF8C00",   # blazing orange
}

TIER_LABELS = {
    "none":    "No sunnies 😔",
    "partial": "Getting there 🫣",
    "full":    "Blazing! ☀️",
}


def stars(rating: float) -> str:
    full  = int(rating)
    half  = 1 if (rating - full) >= 0.5 else 0
    empty = 5 - full - half
    return "★" * full + "½" * half + "☆" * empty


def time_to_minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def minutes_to_time(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def best_sun_window(blocks) -> str:
    """Return the longest continuous 'full' block as a human string."""
    best = max(
        (b for b in blocks if b["tier"] == "full"),
        key=lambda b: time_to_minutes(b["to_time"]) - time_to_minutes(b["from_time"]),
        default=None,
    )
    if best:
        return f"{best['from_time']} → {best['to_time']}"
    partial = [b for b in blocks if b["tier"] == "partial"]
    if partial:
        return "Some windows of sun"
    return "No direct sun today"


def total_sun_minutes(blocks) -> int:
    return sum(
        time_to_minutes(b["to_time"]) - time_to_minutes(b["from_time"])
        for b in blocks if b["tier"] == "full"
    )


def sun_score_label(minutes: int) -> tuple[str, str]:
    """(emoji, label) based on total full-sun minutes."""
    if minutes == 0:
        return "🌑", "None"
    if minutes < 60:
        return "🌤️", f"{minutes}m"
    h = minutes // 60
    m = minutes % 60
    if m:
        return "☀️", f"{h}h {m}m"
    return "☀️", f"{h}h"


def render_schedule_bar(blocks: list, height: int = 28) -> str:
    """Return an HTML sun schedule timeline bar for the full 24h day."""
    segments = []
    for b in blocks:
        start = time_to_minutes(b["from_time"])
        end   = time_to_minutes(b["to_time"])
        if end <= start:
            end = 1440
        pct   = (end - start) / 1440 * 100
        color = TIER_CSS[b["tier"]]
        title = f"{b['from_time']}–{b['to_time']}: {TIER_LABELS[b['tier']]}"
        segments.append(
            f'<div style="width:{pct:.3f}%;background:{color};height:{height}px;'
            f'display:inline-block;vertical-align:top" title="{title}"></div>'
        )

    tick_labels = "".join(
        f'<span style="position:absolute;left:{h/24*100:.1f}%;transform:translateX(-50%);'
        f'font-size:9px;color:#888;top:0">{h:02d}</span>'
        for h in [0, 6, 12, 18, 24]
    )

    return f"""
<div style="margin-bottom:2px;position:relative;height:14px">{tick_labels}</div>
<div style="border-radius:6px;overflow:hidden;height:{height}px;
            background:#1E2340;white-space:nowrap;font-size:0;
            border:1px solid rgba(0,0,0,0.1)">
  {"".join(segments)}
</div>
<div style="display:flex;gap:12px;margin-top:5px;font-size:10px;color:#666">
  <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#1E2340;margin-right:3px;vertical-align:middle"></span>Night / Shadow</span>
  <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#F5C842;margin-right:3px;vertical-align:middle"></span>Getting there</span>
  <span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#FF8C00;margin-right:3px;vertical-align:middle"></span>Blazing!</span>
</div>
"""


def get_photo_url(place_id: str, api_key: str, width: int = 480) -> Optional[str]:
    """Fetch a real Place photo URL via Google Places API."""
    try:
        details = _requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id, "fields": "photos", "key": api_key},
            timeout=5,
        ).json()
        ref = details["result"]["photos"][0]["photo_reference"]
        return (
            f"https://maps.googleapis.com/maps/api/place/photo"
            f"?maxwidth={width}&photo_reference={ref}&key={api_key}"
        )
    except Exception:
        return None


def get_osm_url(lat: float, lon: float) -> str:
    """Fallback OSM static map thumbnail."""
    return (
        f"https://staticmap.openstreetmap.de/staticmap.php"
        f"?center={lat},{lon}&zoom=17&size=480x220"
        f"&markers={lat},{lon},lightblue1"
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_schedule(lat: float, lon: float, date_str: str) -> list | str:
    """Cached wrapper around sun_schedule. Returns list or error string."""
    try:
        from sun_rating import sun_schedule
        return sun_schedule(lat, lon, date_str)
    except ConnectionError as e:
        return f"error:{e}"
    except Exception as e:
        return f"error:{e}"


@st.cache_data(ttl=86400, show_spinner=False)
def load_photo(place_id: str, api_key: str) -> Optional[str]:
    if not api_key:
        return None
    return get_photo_url(place_id, api_key)


# ---------------------------------------------------------------------------
# Page config & CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CPH Sun Cafés ☀️",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

.stApp { background: #FAF6EF; }

.page-title {
    font-family: 'Playfair Display', serif;
    font-size: 2.8rem;
    font-weight: 700;
    color: #1A1208;
    letter-spacing: -0.5px;
    line-height: 1.1;
}
.page-sub {
    font-size: 1rem;
    color: #7A6A52;
    margin-top: 4px;
    margin-bottom: 0;
}
.cafe-card {
    background: #FFFFFF;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    height: 100%;
}
.cafe-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
.cafe-img {
    width: 100%;
    height: 160px;
    object-fit: cover;
    display: block;
}
.cafe-body { padding: 14px 16px 16px; }
.cafe-name {
    font-family: 'Playfair Display', serif;
    font-size: 1.05rem;
    font-weight: 600;
    color: #1A1208;
    margin: 0 0 2px;
}
.cafe-addr { font-size: 0.78rem; color: #9A8A72; margin: 0 0 6px; }
.cafe-desc { font-size: 0.82rem; color: #5A4A32; margin: 0 0 10px; line-height: 1.45; }
.cafe-rating { font-size: 0.82rem; color: #C8860A; }
.type-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 500;
    margin-bottom: 6px;
}
.sun-score {
    font-size: 0.88rem;
    font-weight: 500;
    color: #1A1208;
    margin-bottom: 6px;
}
.best-window {
    font-size: 0.78rem;
    color: #7A6A52;
    margin-bottom: 8px;
}
.section-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    color: #3A2A12;
    margin-bottom: 4px;
    font-weight: 600;
}
div[data-testid="stSidebar"] { background: #FFF8EE; border-right: 1px solid #EDE0CC; }
.stButton > button {
    background: #E8913A !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### ☀️ Sun Café Finder")
    st.markdown("---")

    selected_date = st.date_input(
        "Pick a date",
        value=datetime.date.today(),
        min_value=datetime.date(2020, 1, 1),
        max_value=datetime.date(2030, 12, 31),
    )

    st.markdown("---")
    st.markdown("**Google Maps API key** *(optional)*")
    st.markdown(
        "<div style='font-size:0.78rem;color:#7A6A52;margin-bottom:6px'>"
        "Add a key to show real place photos instead of map thumbnails.</div>",
        unsafe_allow_html=True,
    )
    gmaps_key = st.text_input("API Key", type="password", placeholder="AIza...")

    st.markdown("---")
    sort_by = st.selectbox(
        "Sort by",
        ["Most sun today", "Rating", "Name"],
    )

    st.markdown("---")
    interval = st.slider("Schedule resolution (min)", 5, 30, 10, step=5)

    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.75rem;color:#9A8A72'>"
        "Sun data from OpenStreetMap + NOAA solar algorithm.<br>"
        "Calculations based on building heights and line-of-sight to sun.</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

col_title, col_meta = st.columns([3, 1])
with col_title:
    st.markdown(
        f'<div class="page-title">Copenhagen Sun Cafés</div>'
        f'<div class="page-sub">Where to sit outside on '
        f'{selected_date.strftime("%A, %d %B %Y")}</div>',
        unsafe_allow_html=True,
    )
with col_meta:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄  Reload schedules"):
        st.cache_data.clear()

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load all schedules
# ---------------------------------------------------------------------------

date_str = selected_date.isoformat()

results = {}
_progress_text = st.empty()
_progress_bar  = st.progress(0)
for _i, cafe in enumerate(CAFES):
    _progress_text.markdown(
        f"<div style='font-size:0.85rem;color:#7A6A52'>☀️ Checking <b>{cafe['name']}</b>…</div>",
        unsafe_allow_html=True,
    )
    _progress_bar.progress((_i + 1) / len(CAFES))
    results[cafe["name"]] = load_schedule(cafe["lat"], cafe["lon"], date_str)
_progress_text.empty()
_progress_bar.empty()

# Build enriched cafe list with sun stats
cafes_with_stats = []
for cafe in CAFES:
    data = results[cafe["name"]]
    if isinstance(data, str) and data.startswith("error:"):
        sun_mins = -1
        blocks = []
        error = data[6:]
    else:
        blocks = data
        sun_mins = total_sun_minutes(blocks)
        error = None

    cafes_with_stats.append({**cafe, "blocks": blocks, "sun_mins": sun_mins, "error": error})

# Sort
if sort_by == "Most sun today":
    cafes_with_stats.sort(key=lambda c: c["sun_mins"], reverse=True)
elif sort_by == "Rating":
    cafes_with_stats.sort(key=lambda c: c["rating"], reverse=True)
elif sort_by == "Name":
    cafes_with_stats.sort(key=lambda c: c["name"])

# ---------------------------------------------------------------------------
# Summary strip
# ---------------------------------------------------------------------------

n_sun = sum(1 for c in cafes_with_stats if c["sun_mins"] > 0)
n_blazing = sum(1 for c in cafes_with_stats if c["sun_mins"] >= 120)
top_cafe = max(cafes_with_stats, key=lambda c: c["sun_mins"], default=None)

m1, m2, m3 = st.columns(3)
m1.metric("Cafés with any sun", f"{n_sun} / {len(CAFES)}")
m2.metric("Cafés with 2h+ blazing sun", str(n_blazing))
if top_cafe and top_cafe["sun_mins"] > 0:
    emoji, label = sun_score_label(top_cafe["sun_mins"])
    m3.metric("Best spot today", top_cafe["name"], label)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Cafe grid
# ---------------------------------------------------------------------------

COLS = 3
rows = [cafes_with_stats[i:i+COLS] for i in range(0, len(cafes_with_stats), COLS)]

for row in rows:
    cols = st.columns(COLS, gap="medium")
    for col, cafe in zip(cols, row):
        with col:
            bg, accent, icon = TYPE_COLORS.get(cafe["type"], ("#F5F5F5", "#888", "🏠"))
            emoji_score, label_score = sun_score_label(cafe["sun_mins"])

            # Image
            photo_url = load_photo(cafe["place_id"], gmaps_key) if gmaps_key else None
            img_url = photo_url or get_osm_url(cafe["lat"], cafe["lon"])

            # Sun schedule bar HTML
            if cafe["blocks"]:
                bar_html = render_schedule_bar(cafe["blocks"])
                window   = best_sun_window(cafe["blocks"])
            else:
                bar_html = '<div style="height:28px;background:#eee;border-radius:6px"></div>'
                window   = "—"

            card_html = f"""
<div class="cafe-card">
  <img class="cafe-img" src="{img_url}" alt="{cafe['name']}"
       onerror="this.style.height='80px';this.style.background='#F0E8D8'"/>
  <div class="cafe-body">
    <div>
      <span class="type-badge" style="background:{bg};color:{accent}">{icon} {cafe['type']}</span>
    </div>
    <div class="cafe-name">{cafe['name']}</div>
    <div class="cafe-addr">📍 {cafe['address']}</div>
    <div class="cafe-rating">{'★' * int(cafe['rating'])}{'½' if (cafe['rating'] % 1) >= 0.5 else ''} {cafe['rating']}</div>
    <div class="cafe-desc">{cafe['description']}</div>
    <div class="sun-score">{emoji_score} Full sun today: {label_score}</div>
    <div class="best-window">Best window: {window}</div>
    <div class="section-title" style="font-size:0.82rem;margin-bottom:4px">Sun schedule</div>
    {bar_html}
  </div>
</div>
"""
            st.markdown(card_html, unsafe_allow_html=True)

            if cafe.get("error"):
                st.error(f"⚠ Could not fetch building data", icon="⚠️")

    st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#9A8A72;font-size:0.8rem;padding:8px 0'>"
    "Sun visibility is line-of-sight only (building shadows, not weather) · "
    "Building data © OpenStreetMap contributors · "
    "Solar position via NOAA algorithm"
    "</div>",
    unsafe_allow_html=True,
)