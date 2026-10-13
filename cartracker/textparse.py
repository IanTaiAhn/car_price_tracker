"""Pull year / make / model / trim / price / mileage out of free text (titles, email snippets)."""
from __future__ import annotations

import re

KNOWN_MAKES = ["Toyota", "Subaru", "Mazda"]  # extended at runtime from config

_YEAR_MAKE = None


def set_makes(makes: list[str]) -> None:
    global _YEAR_MAKE
    for m in makes:
        if m not in KNOWN_MAKES:
            KNOWN_MAKES.append(m)
    _YEAR_MAKE = None


def _year_make_re() -> re.Pattern:
    global _YEAR_MAKE
    if _YEAR_MAKE is None:
        makes = "|".join(re.escape(m) for m in KNOWN_MAKES)
        _YEAR_MAKE = re.compile(rf"\b((?:19|20)\d{{2}})\s+({makes})\s+([^\n$|•·]+)", re.I)
    return _YEAR_MAKE


PRICE_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d{4,6})(?!\d)")
MILES_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{1,6})\s*(?:mi\b|miles\b|mileage\b)", re.I)
MILES_K_RE = re.compile(r"(\d{1,3}(?:\.\d)?)\s*k\s*(?:mi\b|miles\b)", re.I)
MILES_LABEL_RE = re.compile(r"(?:mileage|odometer|miles)\s*[:\-]?\s*(\d{1,3}(?:,\d{3})+|\d{1,6})", re.I)
VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")


def parse_prices(text: str) -> list[int]:
    out = []
    for m in PRICE_RE.finditer(text or ""):
        v = int(m.group(1).replace(",", ""))
        if 1000 <= v <= 300000:  # ignore fees / monthly payments outside a car-price range
            out.append(v)
    return out


def parse_mileage(text: str) -> int | None:
    text = text or ""
    m = MILES_LABEL_RE.search(text) or MILES_RE.search(text)
    if m:
        return int(m.group(1).replace(",", ""))
    m = MILES_K_RE.search(text)
    if m:
        return int(float(m.group(1)) * 1000)
    return None


def parse_title(text: str) -> dict:
    """'2023 Toyota RAV4 Hybrid XLE Premium AWD' -> year/make/model/trim/title."""
    m = _year_make_re().search(text or "")
    if not m:
        return {}
    rest = re.split(r"\s{2,}|\s[-–]\s", m.group(3).strip())[0].strip()
    parts = rest.split()
    model = parts[0] if parts else None
    trim = " ".join(parts[1:]) or None
    return {
        "year": int(m.group(1)),
        "make": next(k for k in KNOWN_MAKES if k.lower() == m.group(2).lower()),
        "model": model,
        "trim": trim,
        "title": f"{m.group(1)} {m.group(2)} {rest}".strip(),
    }


def parse_vin(text: str) -> str | None:
    for m in VIN_RE.finditer((text or "").upper()):
        v = m.group(1)
        if re.search(r"[A-Z]", v) and re.search(r"\d", v):
            return v
    return None
