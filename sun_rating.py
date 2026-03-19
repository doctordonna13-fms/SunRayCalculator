#!/usr/bin/env python3
"""
sun_rating.py — Urban Sun Visibility Calculator
================================================
Interactively asks for GPS coordinates, uses the current UTC time,
and calculates line-of-sight sun visibility (0-100%) based on surrounding
building data from OpenStreetMap.

No API key required. Only dependency: requests
  pip install requests

Usage:
  python sun_rating.py
"""

import math
import sys
import re
from datetime import datetime, timezone
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: 'requests' is required. Install with: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RADIUS_M      = 1    # Radius of the seating area to sample (1m = realistic table radius)
MIN_INTERSECTION_M   = 0.5  # Min ray distance to register a hit (avoids self-intersection noise)
BUILDING_RADIUS_M = 500  # How far to search for buildings.
                         # A 20m building at 10 degrees sun altitude casts a ~113m shadow,
                         # so 500m safely covers all realistic urban scenarios.

# ---------------------------------------------------------------------------
# Solar Position  (NOAA algorithm - no external dependency)
# ---------------------------------------------------------------------------

def solar_position(lat: float, lon: float, dt: datetime) -> tuple:
    """
    Returns (altitude_deg, azimuth_deg).
    altitude : degrees above horizon (negative = below horizon)
    azimuth  : degrees clockwise from north (N=0, E=90, S=180, W=270)
    Uses pysolar if installed, otherwise the built-in NOAA algorithm.
    """
    try:
        from pysolar.solar import get_altitude, get_azimuth
        return get_altitude(lat, lon, dt), get_azimuth(lat, lon, dt)
    except ImportError:
        return _noaa_solar_position(lat, lon, dt)


def _noaa_solar_position(lat, lon, dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    jd = _julian_date(dt)
    jc = (jd - 2451545.0) / 36525.0

    geom_mean_lon  = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
    geom_mean_anom = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    eccent         = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)

    anom_r = math.radians(geom_mean_anom)
    eq_ctr = (math.sin(anom_r) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
              + math.sin(2 * anom_r) * (0.019993 - 0.000101 * jc)
              + math.sin(3 * anom_r) * 0.000289)

    sun_lon     = geom_mean_lon + eq_ctr
    sun_lon_app = (sun_lon - 0.00569
                   - 0.00478 * math.sin(math.radians(125.04 - 1934.136 * jc)))

    mean_obliq = (23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60)
    obliq_corr = mean_obliq + 0.00256 * math.cos(math.radians(125.04 - 1934.136 * jc))

    sun_decl = math.degrees(math.asin(
        math.sin(math.radians(obliq_corr)) * math.sin(math.radians(sun_lon_app))
    ))

    y   = math.tan(math.radians(obliq_corr / 2)) ** 2
    l0r = math.radians(geom_mean_lon)
    mr  = math.radians(geom_mean_anom)
    eq_time = (y * math.sin(2 * l0r)
               - 2 * eccent * math.sin(mr)
               + 4 * eccent * y * math.sin(mr) * math.cos(2 * l0r)
               - 0.5 * y * y * math.sin(4 * l0r)
               - 1.25 * eccent * eccent * math.sin(2 * mr)) * 4

    utc_offset      = dt.utcoffset().total_seconds() / 3600 if dt.utcoffset() else 0
    time_min        = dt.hour * 60 + dt.minute + dt.second / 60.0
    true_solar_time = (time_min + eq_time + 4 * lon - 60 * utc_offset) % 1440
    hour_angle      = true_solar_time / 4 - 180

    lat_r = math.radians(lat)
    decl_r = math.radians(sun_decl)
    ha_r   = math.radians(hour_angle)

    cos_zenith = max(-1.0, min(1.0,
        math.sin(lat_r) * math.sin(decl_r) + math.cos(lat_r) * math.cos(decl_r) * math.cos(ha_r)
    ))
    zenith   = math.degrees(math.acos(cos_zenith))
    altitude = 90.0 - zenith

    if altitude >= 89.9:
        return altitude, 180.0

    sin_zenith = math.sin(math.radians(zenith))
    cos_az = max(-1.0, min(1.0,
        (math.sin(lat_r) * cos_zenith - math.sin(decl_r)) / (math.cos(lat_r) * sin_zenith)
    ))
    acos_val = math.degrees(math.acos(cos_az))
    # Correct NOAA formula: azimuth clockwise from north
    # afternoon (HA>0): (acos+180) % 360  |  morning (HA<=0): (540-acos) % 360
    if hour_angle > 0:
        azimuth = (acos_val + 180.0) % 360.0
    else:
        azimuth = (540.0 - acos_val) % 360.0

    return altitude, azimuth


def _julian_date(dt):
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    a = (14 - dt.month) // 12
    y = dt.year + 4800 - a
    m = dt.month + 12 * a - 3
    jdn = (dt.day + (153 * m + 2) // 5 + 365 * y
           + y // 4 - y // 100 + y // 400 - 32045)
    return jdn + (dt.hour - 12) / 24 + dt.minute / 1440 + dt.second / 86400


# ---------------------------------------------------------------------------
# Coordinate Utilities
# ---------------------------------------------------------------------------

def latlon_to_local_m(lat, lon, ref_lat, ref_lon):
    R = 6371000.0
    x = math.radians(lon - ref_lon) * R * math.cos(math.radians(ref_lat))
    y = math.radians(lat - ref_lat) * R
    return x, y


def bbox_from_radius(lat, lon, radius_m):
    delta_lat = math.degrees(radius_m / 6371000.0)
    delta_lon = math.degrees(radius_m / (6371000.0 * math.cos(math.radians(lat))))
    return lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon


# ---------------------------------------------------------------------------
# OpenStreetMap Building Fetcher
# ---------------------------------------------------------------------------

def fetch_buildings_osm(lat, lon, radius_m):
    """
    Fetch building footprints from OpenStreetMap Overpass API.
    Raises exception on failure -- no silent fallback.
    """
    min_lat, min_lon, max_lat, max_lon = bbox_from_radius(lat, lon, radius_m)
    query = f"""
[out:json][timeout:30];
(way["building"]({min_lat},{min_lon},{max_lat},{max_lon}););
out body;>;out skel qt;
"""
    resp = requests.post("https://overpass-api.de/api/interpreter",
                         data={"data": query}, timeout=35)
    resp.raise_for_status()
    data = resp.json()

    nodes = {
        el["id"]: (el["lat"], el["lon"])
        for el in data.get("elements", []) if el["type"] == "node"
    }

    buildings = []
    for el in data.get("elements", []):
        if el["type"] != "way" or "building" not in el.get("tags", {}):
            continue

        height  = _estimate_height(el.get("tags", {}))
        polygon = [
            latlon_to_local_m(nodes[nid][0], nodes[nid][1], lat, lon)
            for nid in el.get("nodes", []) if nid in nodes
        ]

        if len(polygon) < 4:
            continue
        if _point_in_polygon(0.0, 0.0, polygon):
            continue  # We are inside this building

        buildings.append({"polygon": polygon, "height": height})

    return buildings


def _estimate_height(tags):
    if "height" in tags:
        try:
            return float(str(tags["height"]).replace("m", "").strip())
        except ValueError:
            pass
    if "building:levels" in tags:
        try:
            return max(3.0, float(tags["building:levels"]) * 3.2)
        except (ValueError, TypeError):
            pass
    defaults = {
        "house": 7.0, "detached": 7.0, "semidetached_house": 7.0,
        "terrace": 9.0, "apartments": 18.0, "residential": 12.0,
        "commercial": 15.0, "retail": 6.0, "industrial": 10.0,
        "warehouse": 10.0, "office": 20.0, "hotel": 25.0,
        "church": 15.0, "cathedral": 30.0, "school": 10.0,
        "university": 15.0, "hospital": 20.0,
    }
    return defaults.get(tags.get("building", "yes").lower(), 12.0)


def _point_in_polygon(px, py, polygon):
    inside, j = False, len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Shadow Ray Casting
# ---------------------------------------------------------------------------

def _ray_segment_dist(ox, oy, dx, dy, ax, ay, bx, by):
    """Distance along ray to segment. Returns None if no forward intersection."""
    ex, ey = bx - ax, by - ay
    denom = dx * ey - dy * ex
    if abs(denom) < 1e-12:
        return None
    u = ((ax - ox) * dy - (ay - oy) * dx) / denom
    if not (0.0 <= u <= 1.0):
        return None
    t = ((ax - ox) * ey - (ay - oy) * ex) / denom
    return t if t >= MIN_INTERSECTION_M else None


def _point_is_lit(ox, oy, ray_dx, ray_dy, tan_alt, buildings):
    """Return True if point (ox, oy) has line-of-sight to the sun."""
    for b in buildings:
        h    = b["height"]
        poly = b["polygon"]
        for i in range(len(poly) - 1):
            ax, ay = poly[i]
            bx, by = poly[i + 1]
            dist = _ray_segment_dist(ox, oy, ray_dx, ray_dy, ax, ay, bx, by)
            if dist is not None and h >= dist * tan_alt:
                return False
    return True


def compute_sun_rating(lat, lon, buildings, sun_az, sun_alt, sample_radius_m=10):
    """
    Sample a 5x5 grid within a circle of radius sample_radius_m.
    Returns fraction (0.0-1.0) of points with direct line-of-sight to the sun.
    """
    az_r    = math.radians(sun_az)
    ray_dx  = math.sin(az_r)
    ray_dy  = math.cos(az_r)
    tan_alt = math.tan(math.radians(sun_alt))

    grid_n = 5
    step   = 2 * sample_radius_m / (grid_n - 1)
    r2     = sample_radius_m ** 2
    samples = [
        (-sample_radius_m + i * step, -sample_radius_m + j * step)
        for i in range(grid_n) for j in range(grid_n)
        if (-sample_radius_m + i * step) ** 2 + (-sample_radius_m + j * step) ** 2 <= r2
    ]
    if not samples:
        samples = [(0.0, 0.0)]

    lit = sum(1 for ox, oy in samples
              if _point_is_lit(ox, oy, ray_dx, ray_dy, tan_alt, buildings))
    return lit / len(samples)


# ---------------------------------------------------------------------------
# Main Calculation
# ---------------------------------------------------------------------------

def calculate(lat: float, lon: float, dt) -> dict:
    """
    Calculate line-of-sight sun visibility for a location and time.

    Parameters
    ----------
    lat : float   Latitude in decimal degrees.
    lon : float   Longitude in decimal degrees.
    dt  : datetime | str
        When to evaluate. Accepts:
          - A timezone-aware datetime (any timezone)
          - A naive datetime (assumed CET/CEST, i.e. Europe/Copenhagen)
          - An ISO 8601 string: "2024-06-15T14:00:00" (naive -> CET/CEST)
            or "2024-06-15T14:00:00+02:00" (timezone-aware)

    Returns
    -------
    dict:
        rating        int    0-100, percent of seating area with direct sun
        status        str    human-readable label
        sun_altitude  float  degrees above horizon
        sun_azimuth   float  degrees clockwise from north
        buildings     int    number of buildings considered

    Raises
    ------
    ConnectionError  if the OSM Overpass API cannot be reached.

    Example
    -------
        from sun_rating import calculate
        from datetime import datetime

        # Naive datetime -> treated as CET/CEST
        result = calculate(55.6759, 12.5453, datetime(2026, 3, 18, 13, 30))
        print(result["rating"], result["status"])

        # String input
        result = calculate(55.6759, 12.5453, "2026-06-21T15:00:00")
        print(result["rating"])
    """
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td

    def _cet_offset(naive_dt):
        """Return UTC+1 (CET) or UTC+2 (CEST) depending on DST. No tzdata needed."""
        # CEST runs from last Sunday in March 02:00 to last Sunday in October 03:00
        def last_sunday(year, month):
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            d = _dt(year, month, last_day)
            return d - _td(days=d.weekday() + 1) if d.weekday() != 6 else d

        spring = last_sunday(naive_dt.year, 3).replace(hour=2)
        autumn = last_sunday(naive_dt.year, 10).replace(hour=3)
        if spring <= naive_dt < autumn:
            return _tz(_td(hours=2))  # CEST
        return _tz(_td(hours=1))      # CET

    # Normalise dt: string -> datetime, naive -> CET/CEST
    if isinstance(dt, str):
        dt = _dt.fromisoformat(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_cet_offset(dt))

    altitude, azimuth = solar_position(lat, lon, dt)

    if altitude <= 0:
        return {
            "rating": 0,
            "status": "Night -- sun below horizon",
            "sun_altitude": round(altitude, 1),
            "sun_azimuth":  round(azimuth, 1),
            "buildings": 0,
        }

    low_sun = " (very low sun -- long shadows)" if altitude < 5 else ""

    try:
        buildings = fetch_buildings_osm(lat, lon, radius_m=BUILDING_RADIUS_M)
    except Exception as e:
        raise ConnectionError(f"Could not fetch building data: {e}") from e

    raw_rating = compute_sun_rating(lat, lon, buildings, azimuth, altitude,
                                    sample_radius_m=SAMPLE_RADIUS_M)
    rating = round(raw_rating * 100)

    if rating >= 90:
        status = "Full sun" + low_sun
    elif rating >= 60:
        status = "Mostly sunny" + low_sun
    elif rating >= 30:
        status = "Partial sun / edge of shadow" + low_sun
    elif rating > 0:
        status = "Mostly in shadow" + low_sun
    else:
        status = "Full shadow -- building blocking sun" + low_sun

    return {
        "rating":        rating,
        "status":        status,
        "sun_altitude":  round(altitude, 1),
        "sun_azimuth":   round(azimuth, 1),
        "buildings":     len(buildings),
    }



# ---------------------------------------------------------------------------
# Day Schedule
# ---------------------------------------------------------------------------

def sun_schedule(lat: float, lon: float, date, interval_minutes: int = 10) -> list:
    """
    Return a full-day sun schedule as a list of time ranges with labels.

    Samples the sun rating every `interval_minutes` across the given date (00:00–24:00 CET)
    and merges consecutive samples of the same tier into contiguous blocks.

    Parameters
    ----------
    lat               float   Latitude in decimal degrees.
    lon               float   Longitude in decimal degrees.
    date              date | datetime | str
                              The day to evaluate. Accepts:
                                - datetime.date or datetime.datetime (date portion used)
                                - ISO string "2026-03-18" or "2026-03-18T13:00:00"
    interval_minutes  int     Sampling resolution in minutes (default 10).

    Returns
    -------
    List of dicts, each with:
        from_time   str   "HH:MM"
        to_time     str   "HH:MM"
        rating_min  int   Lowest rating% in this block
        rating_max  int   Highest rating% in this block
        tier        str   "none" | "partial" | "full"
        label       str   Fun human-readable label
        emoji       str   Emoji for the tier

    Example
    -------
        from sun_rating import sun_schedule
        import datetime

        for block in sun_schedule(55.6759, 12.5453, datetime.date(2026, 3, 18)):
            print(f"{block['from_time']} - {block['to_time']}  {block['emoji']} {block['label']}")
    """
    from datetime import date as _date, datetime as _dt, timedelta as _td, timezone as _tz
    import calendar

    # --- Normalise date input ---
    if isinstance(date, str):
        date = _dt.fromisoformat(date).date()
    elif isinstance(date, _dt):
        date = date.date()

    # --- Build sample timestamps (CET-aware) ---
    def cet_offset(naive_dt):
        last_day_march  = calendar.monthrange(naive_dt.year, 3)[1]
        last_day_oct    = calendar.monthrange(naive_dt.year, 10)[1]
        def last_sun(year, month, last_day):
            d = _dt(year, month, last_day)
            return d - _td(days=(d.weekday() + 1) % 7)
        spring = last_sun(naive_dt.year, 3, last_day_march).replace(hour=2)
        autumn = last_sun(naive_dt.year, 10, last_day_oct).replace(hour=3)
        return _tz(_td(hours=2)) if spring <= naive_dt < autumn else _tz(_td(hours=1))

    total_minutes = 24 * 60
    steps = range(0, total_minutes, interval_minutes)
    timestamps = []
    for m in steps:
        naive = _dt(date.year, date.month, date.day) + _td(minutes=m)
        timestamps.append(naive.replace(tzinfo=cet_offset(naive)))
    # Add 24:00 = next day 00:00 as sentinel for the final block end
    end_naive = _dt(date.year, date.month, date.day) + _td(days=1)
    end_dt = end_naive.replace(tzinfo=cet_offset(end_naive))

    # --- Fetch buildings once (shared across all timestamps) ---
    try:
        buildings = fetch_buildings_osm(lat, lon, radius_m=BUILDING_RADIUS_M)
    except Exception as e:
        raise ConnectionError(f"Could not fetch building data: {e}") from e

    # --- Sample every interval ---
    samples = []  # (time_str, rating, tier)
    for dt in timestamps:
        altitude, azimuth = solar_position(lat, lon, dt)
        if altitude <= 0:
            rating = 0
        else:
            rating = round(compute_sun_rating(lat, lon, buildings, azimuth, altitude,
                                              sample_radius_m=SAMPLE_RADIUS_M) * 100)
        tier = _tier(rating, altitude)
        samples.append((dt, rating, tier))

    # --- Merge consecutive same-tier samples into blocks ---
    LABELS = {
        "none":    ("No sunnies 😔",    "🌑"),
        "partial": ("Getting there 🫣", "🌤️"),
        "full":    ("Blazing! ☀️",       "☀️"),
    }

    blocks = []
    i = 0
    while i < len(samples):
        dt, rating, tier = samples[i]
        j = i + 1
        rating_min = rating_max = rating
        while j < len(samples) and samples[j][2] == tier:
            rating_min = min(rating_min, samples[j][1])
            rating_max = max(rating_max, samples[j][1])
            j += 1

        to_dt = samples[j][0] if j < len(samples) else end_dt
        label, emoji = LABELS[tier]

        blocks.append({
            "from_time":  dt.strftime("%H:%M"),
            "to_time":    to_dt.strftime("%H:%M"),
            "rating_min": rating_min,
            "rating_max": rating_max,
            "tier":       tier,
            "label":      label,
            "emoji":      emoji,
        })
        i = j

    return blocks


def _tier(rating: int, altitude: float) -> str:
    """Classify a rating into none / partial / full."""
    if altitude <= 0 or rating == 0:
        return "none"
    if rating >= 90:
        return "full"
    return "partial"


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

def prompt_coordinates():
    print()
    print("  +--------------------------------------+")
    print("  |    Sun  Urban Sun Visibility Checker |")
    print("  +--------------------------------------+")
    print()
    print("  Enter coordinates in any of these formats:")
    print("    55.6761, 12.5683")
    print("    55.6761 12.5683")
    print('    55deg40\'33.96"N 12deg34\'5.88"E')
    print()

    while True:
        raw = input("  Coordinates: ").strip()
        if not raw:
            continue
        result = _parse_coordinates(raw)
        if result is None:
            print("  Could not parse. Try: 55.6761, 12.5683")
            continue
        lat, lon = result
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            print("  Out of range. Lat must be -90..90, lon -180..180.")
            continue
        return lat, lon


def _parse_coordinates(raw):
    raw = raw.strip()

    # DMS: 55deg40'33.96"N 12deg34'5.88"E
    m = re.match(
        r"(\d+)[deg\xb0]\s*(\d+)['\u2032]\s*([\d.]+)[\"''\u2033]?\s*([NSns])"
        r"[\s,]+"
        r"(\d+)[deg\xb0]\s*(\d+)['\u2032]\s*([\d.]+)[\"''\u2033]?\s*([EWew])",
        raw,
    )
    if m:
        lat = _dms(float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4).upper())
        lon = _dms(float(m.group(5)), float(m.group(6)), float(m.group(7)), m.group(8).upper())
        return lat, lon

    parts = [p for p in re.split(r"[,\s]+", raw) if p]
    if len(parts) == 2:
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            pass

    return None


def _dms(d, m, s, direction):
    dd = d + m / 60 + s / 3600
    return -dd if direction in ("S", "W") else dd


def main():
    lat, lon = prompt_coordinates()
    from datetime import timezone as _tz, timedelta as _td
    import calendar as _cal
    def _last_sunday(year, month):
        last_day = _cal.monthrange(year, month)[1]
        d = datetime(year, month, last_day)
        return d - _td(days=d.weekday() + 1) if d.weekday() != 6 else d
    now_naive = datetime.now()
    spring = _last_sunday(now_naive.year, 3).replace(hour=2)
    autumn = _last_sunday(now_naive.year, 10).replace(hour=3)
    offset = _tz(_td(hours=2)) if spring <= now_naive < autumn else _tz(_td(hours=1))
    dt = datetime.now(offset)

    print()
    print(f"  Location  : {lat:.6f}, {lon:.6f}")
    print(f"  Time (CET): {dt.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  Fetching buildings within {BUILDING_RADIUS_M}m, sampling +-{SAMPLE_RADIUS_M}m area (min wall dist {MIN_INTERSECTION_M}m)...")

    try:
        result = calculate(lat, lon, dt)
    except Exception as e:
        print()
        print(f"  ERROR fetching building data: {e}")
        print("  Check your internet connection and try again.")
        print()
        sys.exit(1)

    rating = result["rating"]
    print()
    print("  +--------------------------------------+")
    print(f"  |  Sun Rating : {rating:>3}%                    |")
    print(f"  |  {result['status']:<36}|")
    print("  +--------------------------------------+")
    print(f"  Sun altitude  : {result['sun_altitude']} degrees above horizon")
    print(f"  Sun direction : {result['sun_azimuth']} degrees (N=0, E=90, S=180, W=270)")
    print(f"  Buildings     : {result['buildings']} found within {BUILDING_RADIUS_M}m")
    print()


if __name__ == "__main__":
    main()