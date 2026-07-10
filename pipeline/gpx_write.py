"""Emit-by-whitelist GPX writer (CLAUDE.md ⛔: never edit input XML in
place). Re-serializes from scratch: only <trk><trkseg><trkpt lat lon>
<ele></ele></trkpt> ever reach the output, so <metadata>/<wpt>/
<extensions> (present in real Flow files, or added by a future firmware
update) can never survive into a published file. No <time> (stripped
patterns-of-life leak — the ride date survives in the filename
instead), no track <name>.
"""

from xml.sax.saxutils import quoteattr

GPX_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<gpx version="1.1" creator="ebike-route-map" '
    'xmlns="http://www.topografix.com/GPX/1/1">\n'
    "<trk><trkseg>\n"
)
GPX_FOOTER = "</trkseg></trk>\n</gpx>\n"


def render_gpx(points):
    """Build the whitelist GPX document text for a list of point dicts
    (lat/lon/ele keys; any other keys, e.g. time, are ignored/dropped)."""
    lines = [GPX_HEADER]
    for p in points:
        lat = quoteattr(f"{p['lat']:.6f}")
        lon = quoteattr(f"{p['lon']:.6f}")
        ele = p.get("ele")
        ele_text = f"{ele:.1f}" if ele is not None else "0.0"
        lines.append(f"<trkpt lat={lat} lon={lon}><ele>{ele_text}</ele></trkpt>\n")
    lines.append(GPX_FOOTER)
    return "".join(lines)


def write_gpx(path, points):
    """Write the whitelist GPX document for `points` to `path`."""
    text = render_gpx(points)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
