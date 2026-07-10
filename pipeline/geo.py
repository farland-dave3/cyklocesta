"""Geometry helpers: haversine distance, Douglas-Peucker simplification,
route distance, and hysteresis-smoothed elevation gain.

No third-party deps (stdlib `math` only).
"""

import math

EARTH_RADIUS_M = 6_371_000.0

#: Douglas-Peucker simplification tolerance, per CLAUDE.md ("~8 m").
DEFAULT_SIMPLIFY_TOLERANCE_M = 8.0

#: Elevation-gain hysteresis threshold: only count a climb once
#: cumulative rise since the last confirmed reversal exceeds this many
#: meters (open-questions #11b — naive per-point summation over-counts
#: ~1 Hz GPS noise).
DEFAULT_ELEVATION_HYSTERESIS_M = 3.0


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return EARTH_RADIUS_M * c


def total_distance_km(points):
    """Sum of haversine distances between consecutive points, in km,
    rounded to 1 decimal. `points` is a list of dicts with lat/lon keys
    (or (lat, lon, ...) tuples)."""
    if len(points) < 2:
        return 0.0
    total_m = 0.0
    prev = points[0]
    for p in points[1:]:
        lat1, lon1 = _latlon(prev)
        lat2, lon2 = _latlon(p)
        total_m += haversine_m(lat1, lon1, lat2, lon2)
        prev = p
    return round(total_m / 1000.0, 1)


def _latlon(p):
    if isinstance(p, dict):
        return p["lat"], p["lon"]
    return p[0], p[1]


def _project_local_meters(lat, lon, lat0):
    """Flat-earth (equirectangular) projection to local meters, using
    lat0 as the reference latitude for the longitude scale factor. Only
    valid for the small distances a single route spans."""
    x = math.radians(lon) * math.cos(math.radians(lat0)) * EARTH_RADIUS_M
    y = math.radians(lat) * EARTH_RADIUS_M
    return x, y


def _perpendicular_distance_m(point, start, end):
    lat0, lon0 = _latlon(start)
    x, y = _project_local_meters(*_latlon(point), lat0)
    x1, y1 = _project_local_meters(lat0, lon0, lat0)
    x2, y2 = _project_local_meters(*_latlon(end), lat0)
    if x1 == x2 and y1 == y2:
        return math.hypot(x - x1, y - y1)
    num = abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1)
    den = math.hypot(y2 - y1, x2 - x1)
    return num / den


def douglas_peucker(points, tolerance=DEFAULT_SIMPLIFY_TOLERANCE_M):
    """Simplify a polyline, iteratively (no recursion — real tracks can
    run thousands of points deep, which risks recursion-limit blowups on
    a plain recursive DP). Always keeps the first and last point.

    `points` is a list of dicts (lat/lon/ele/...) or tuples; the same
    element objects are returned (not copies), just a filtered subset.
    """
    n = len(points)
    if n < 3:
        return list(points)

    keep = [False] * n
    keep[0] = True
    keep[-1] = True
    stack = [(0, n - 1)]

    while stack:
        start_i, end_i = stack.pop()
        if end_i <= start_i + 1:
            continue
        start, end = points[start_i], points[end_i]
        dmax = 0.0
        index = start_i
        for i in range(start_i + 1, end_i):
            d = _perpendicular_distance_m(points[i], start, end)
            if d > dmax:
                dmax = d
                index = i
        if dmax > tolerance:
            keep[index] = True
            stack.append((start_i, index))
            stack.append((index, end_i))

    return [p for p, k in zip(points, keep) if k]


def elevation_gain_m(elevations, threshold=DEFAULT_ELEVATION_HYSTERESIS_M):
    """Hysteresis-smoothed cumulative ascent, in whole meters.

    Acts like a Schmitt trigger on the elevation trace: only commits a
    climb to the running total once the trace has reversed by at least
    `threshold` meters, so GPS sensor noise (a few tenths of a meter of
    jitter per sample) doesn't get double-counted as endless micro
    climbs. Naive per-point positive-delta summation on ~1 Hz data
    grossly overestimates ascent for exactly this reason.
    """
    elevations = [e for e in elevations if e is not None]
    if len(elevations) < 2:
        return 0

    anchor = elevations[0]
    extreme = elevations[0]
    direction = "up"  # arbitrary; see note below
    gain = 0.0

    # Starting `direction = "up"` with anchor == extreme is safe even if
    # the track actually descends first: the first confirmed reversal
    # adds (extreme - anchor) == 0 before flipping to "down", so no
    # spurious gain is introduced by the arbitrary initial guess.
    for e in elevations[1:]:
        if direction == "up":
            if e > extreme:
                extreme = e
            elif extreme - e >= threshold:
                gain += extreme - anchor
                anchor = extreme
                direction = "down"
                extreme = e
        else:
            if e < extreme:
                extreme = e
            elif e - extreme >= threshold:
                anchor = extreme
                direction = "up"
                extreme = e

    if direction == "up":
        gain += extreme - anchor

    return round(gain)


def bbox(points):
    """[[min_lat, min_lon], [max_lat, max_lon]] over the given points."""
    lats = []
    lons = []
    for p in points:
        lat, lon = _latlon(p)
        lats.append(lat)
        lons.append(lon)
    return [[min(lats), min(lons)], [max(lats), max(lons)]]
