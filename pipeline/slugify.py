"""Slug computation for routes.json (open-questions #10).

Pipeline-side only, on purpose: the slug is stored in routes.json and
never re-derived client-side, so NFC/NFD filename differences between a
macOS dev box, a Windows BFU, and GitHub Pages (Linux) can never bite in
JS. Rule: NFC-normalize -> ASCII-fold diacritics (via NFD, drop
combining marks) -> lowercase -> non-alnum runs -> '-' -> trim '-'.

e.g. "2026-07-06 Okolo Přehrady" -> "2026-07-06-okolo-prehrady"
"""

import re
import unicodedata

_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")


def slugify(stem):
    s = unicodedata.normalize("NFC", stem)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = _NON_ALNUM_RUN.sub("-", s)
    return s.strip("-")
