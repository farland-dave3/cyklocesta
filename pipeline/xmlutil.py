"""Small shared XML helpers.

Bosch Flow GPX declares a default namespace
(xmlns="http://www.topografix.com/GPX/1/1"), so xml.etree tags come back
as "{http://www.topografix.com/GPX/1/1}trkpt". We work by local tag name
everywhere so the parser tolerates namespaced or bare XML alike.
"""


def localname(tag):
    """Return the local (namespace-stripped) part of an ElementTree tag."""
    return tag.split("}", 1)[-1] if "}" in tag else tag
