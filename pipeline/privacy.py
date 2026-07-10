"""Endpoint-relative privacy trim, zero config, no secrets.

DESIGN (2026-07-06, replaces the earlier zone-based model): routes
originate from many "homes" (house, camp, hotel — not one fixed
address), and the maintainer will not hand-enter real coordinates or
generate a secret anywhere. So there is no privacy-zones.json, no
salt, no zone list. Instead, each ride is trimmed relative to its OWN
raw geometry:

- Anchors: the ride's own FIRST raw trackpoint and LAST raw trackpoint.
- Two independent radii, each jittered into [RADIUS_M, RADIUS_MAX_M),
  derived from SHA-256 of the RAW FILE'S BYTES (not the filename, not a
  secret): u_start from digest bytes 0:8, u_end from digest bytes 8:16.
  Nobody outside the maintainer's machine can predict either radius —
  it depends on the full untrimmed geometry + every per-point
  timestamp — yet re-processing the same raw bytes is fully
  deterministic (idempotent), and renaming the published file later
  never touches this (it isn't filename-keyed at all).
- Remove EVERY point (anywhere in the track, mid-route passes too)
  within radius_start of the start anchor OR within radius_end of the
  end anchor. Pin = first surviving point. Zero survivors -> caller
  skips + warns (never emit a null pin).
"""

import hashlib

try:  # dual-mode: package import (tests) and bare script, just in case
    from .geo import haversine_m
except ImportError:  # pragma: no cover
    from geo import haversine_m

#: Default endpoint trim radius range, in meters. CLI-overridable via
#: `process --radius-m/--radius-max-m`.
RADIUS_M = 300
RADIUS_MAX_M = 600


def compute_endpoint_radii(raw_bytes, radius_m=RADIUS_M, radius_max_m=RADIUS_MAX_M):
    """Two independent jittered radii (radius_start, radius_end), each
    in [radius_m, radius_max_m), derived from SHA-256(raw_bytes).

    u_start comes from digest bytes [0:8], u_end from [8:16] — distinct
    slices of the same hash, so the two radii are independent of each
    other but both fully determined by (and only knowable from) the raw
    file's exact bytes.
    """
    digest = hashlib.sha256(raw_bytes).digest()
    u_start = int.from_bytes(digest[0:8], "big") / 2 ** 64
    u_end = int.from_bytes(digest[8:16], "big") / 2 ** 64
    span = radius_max_m - radius_m
    return radius_m + span * u_start, radius_m + span * u_end


def trim_endpoints(points, raw_bytes, radius_m=RADIUS_M, radius_max_m=RADIUS_MAX_M):
    """Remove every point within radius_start of the ride's own first
    raw point OR within radius_end of its own last raw point (mid-route
    passes included — e.g. a loop that swings back near its own start
    gets that pass trimmed too, not just the literal first/last point).

    `points` must be the untrimmed raw points (anchors are taken from
    points[0]/points[-1] BEFORE any trimming). `raw_bytes` are the raw
    file's exact original bytes (used only to derive the radii).

    Returns the surviving points, in original order (may be empty —
    caller must skip+warn rather than emit, never plant a null pin).
    """
    if not points:
        return []

    radius_start, radius_end = compute_endpoint_radii(raw_bytes, radius_m, radius_max_m)
    start = points[0]
    end = points[-1]

    kept = []
    for p in points:
        d_start = haversine_m(p["lat"], p["lon"], start["lat"], start["lon"])
        d_end = haversine_m(p["lat"], p["lon"], end["lat"], end["lon"])
        if d_start >= radius_start and d_end >= radius_end:
            kept.append(p)
    return kept
