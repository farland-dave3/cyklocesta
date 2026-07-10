"""Namespace-tolerant GPX trackpoint parsing.

Reads any <trkpt lat lon><ele/><time/></trkpt> regardless of how deeply
nested under <trk>/<trkseg> it is, and regardless of a default namespace
declaration or single-line formatting (both true of real Bosch Flow
exports). This module only *reads* — it never edits input XML in place;
publishing goes through gpx_write's whitelist re-serializer instead.
"""

import xml.etree.ElementTree as ET

from .xmlutil import localname


class GpxParseError(Exception):
    pass


def parse_points(path):
    """Parse a GPX file into a list of point dicts.

    Each point dict has keys: lat (float), lon (float), ele (float or
    None), time (str or None, raw <time> text, still UTC/untouched).
    """
    try:
        tree = ET.parse(str(path))
    except ET.ParseError as exc:
        raise GpxParseError(f"{path}: not valid XML ({exc})") from exc

    root = tree.getroot()
    points = []
    for elem in root.iter():
        if localname(elem.tag) != "trkpt":
            continue
        try:
            lat = float(elem.attrib["lat"])
            lon = float(elem.attrib["lon"])
        except (KeyError, ValueError) as exc:
            raise GpxParseError(f"{path}: trkpt missing/invalid lat or lon ({exc})") from exc

        ele = None
        time = None
        for child in elem:
            tag = localname(child.tag)
            if tag == "ele" and child.text is not None:
                try:
                    ele = float(child.text)
                except ValueError:
                    ele = None
            elif tag == "time" and child.text is not None:
                time = child.text.strip()

        points.append({"lat": lat, "lon": lon, "ele": ele, "time": time})

    if not points:
        raise GpxParseError(f"{path}: no <trkpt> elements found")

    return points
