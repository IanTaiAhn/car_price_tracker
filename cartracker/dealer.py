"""Polite dealer-inventory scraper.

Rules it follows, always:
  * robots.txt is fetched and honored; disallowed URLs are skipped.
  * crawl-delay (or the configured delay, whichever is larger) between every request.
  * Any block or challenge (403/429/503, CAPTCHA, Cloudflare "Just a moment") stops that dealer
    immediately: no retries, no header tricks. The run then treats the scrape as incomplete,
    so nothing is wrongly marked as sold.

Parsing: most dealer sites embed schema.org Vehicle/Car JSON-LD for SEO, which is the cleanest
source (VIN, mileage, price). If a dealer doesn't, we add a site-specific parser after looking at it.
"""
from __future__ import annotations

import json
import time
import urllib.robotparser
from urllib.parse import urlencode, urljoin, urlparse, urlunparse, parse_qsl

import requests
from bs4 import BeautifulSoup

from . import textparse

USER_AGENT = "PersonalCarPriceTracker/0.1 (personal, non-commercial; twice-weekly)"
CHALLENGE_MARKERS = ("cf-chl", "challenge-platform", "just a moment...", "captcha", "are you a robot",
                     "access denied", "px-captcha", "distil_r_captcha")


class Blocked(RuntimeError):
    pass


class DealerScraper:
    def __init__(self, dealer: dict):
        self.d = dealer
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        self.robots = urllib.robotparser.RobotFileParser()
        self.delay = float(dealer.get("crawl_delay", 1))
        self._last = 0.0

    def _wait(self):
        gap = time.monotonic() - self._last
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last = time.monotonic()

    def load_robots(self):
        robots_url = urljoin(self.d["base_url"], "/robots.txt")
        self._wait()
        r = self.session.get(robots_url, timeout=20)
        if r.status_code in (401, 403):
            raise Blocked(f"robots.txt returned {r.status_code}; treating the whole site as off-limits")
        self.robots.parse(r.text.splitlines() if r.ok else [])
        cd = self.robots.crawl_delay(USER_AGENT) or self.robots.crawl_delay("*")
        if cd:
            self.delay = max(self.delay, float(cd))

    def get(self, url: str) -> str:
        if not self.robots.can_fetch(USER_AGENT, url):
            raise Blocked(f"robots.txt disallows {url}")
        self._wait()
        r = self.session.get(url, timeout=30)
        body = r.text
        low = body[:20000].lower()
        if r.status_code in (403, 429, 503) or any(m in low for m in CHALLENGE_MARKERS):
            raise Blocked(f"{url} answered {r.status_code} with a block/challenge page; stopping this dealer")
        r.raise_for_status()
        return body

    def pages(self, url: str):
        param, max_pages = self.d.get("page_param"), int(self.d.get("max_pages", 10))
        for n in range(1, (max_pages if param else 1) + 1):
            if n == 1 or not param:
                yield url
            else:
                p = urlparse(url)
                q = dict(parse_qsl(p.query)); q[param] = str(n)
                yield urlunparse(p._replace(query=urlencode(q)))

    def scrape(self) -> list[dict]:
        """Return every vehicle found. Raises Blocked if the scrape couldn't complete."""
        self.load_robots()
        found: dict[str, dict] = {}
        for start in self.d["inventory_urls"]:
            for url in self.pages(start):
                vehicles = parse_jsonld_vehicles(self.get(url), url)
                new = [v for v in vehicles if v["source_id"] not in found]
                for v in new:
                    found[v["source_id"]] = v
                if not new:  # past the last page
                    break
        return list(found.values())


# ---- parsing ----------------------------------------------------------------

VEHICLE_TYPES = {"car", "vehicle", "motorizedvehicle", "product", "individualproduct"}


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _num(v) -> int | None:
    if isinstance(v, dict):
        v = v.get("value") or v.get("price")
    if v is None:
        return None
    try:
        return int(float(str(v).replace(",", "").replace("$", "")))
    except ValueError:
        return None


def _name(v) -> str | None:
    if isinstance(v, dict):
        return v.get("name")
    if isinstance(v, list) and v:
        return _name(v[0])
    return v


def parse_jsonld_vehicles(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for obj in _walk(data):
            types = obj.get("@type")
            types = {t.lower() for t in (types if isinstance(types, list) else [types]) if isinstance(t, str)}
            if not types & VEHICLE_TYPES:
                continue
            vin = obj.get("vehicleIdentificationNumber") or obj.get("vin")
            name = obj.get("name") or ""
            if not vin and "car" not in types and "vehicle" not in types and not textparse.parse_title(name):
                continue  # a non-vehicle Product
            offers = obj.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            info = textparse.parse_title(name)
            year = _num(obj.get("vehicleModelDate") or obj.get("modelDate") or obj.get("productionDate")) or info.get("year")
            trim = obj.get("vehicleConfiguration") or info.get("trim")
            v = {
                "title": name or info.get("title"),
                "year": year,
                "make": _name(obj.get("brand") or obj.get("manufacturer")) or info.get("make"),
                "model": _name(obj.get("model")) or info.get("model"),
                "trim": trim,
                "fuel": _name(obj.get("fuelType")),
                "mileage": _num(obj.get("mileageFromOdometer")),
                "price": _num(offers.get("price") if isinstance(offers, dict) else None),
                "vin": (vin or "").upper() or None,
                "url": urljoin(page_url, obj.get("url") or (offers.get("url") if isinstance(offers, dict) else "") or ""),
            }
            v["source_id"] = v["vin"] or obj.get("sku") or v["url"]
            if v["source_id"] and v["year"]:
                out.append(v)
    return out
