"""Read KSL Cars alert emails from Yahoo over IMAP (read-only) and turn them into listing events.

The parser is deliberately generic: it finds every link that points at a KSL car listing,
then reads the text block around that link for year/make/model/trim, price and mileage.
Once we have real sample alerts, tighten `_listing_blocks` to KSL's actual layout.
"""
from __future__ import annotations

import email
import imaplib
import os
import re
from datetime import datetime, timedelta
from email.message import Message
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from . import textparse

LISTING_ID_RE = re.compile(r"cars\.ksl\.com/(?:listing|vehicle)/(\d{5,})", re.I)


class EmailError(RuntimeError):
    pass


# ---- IMAP -------------------------------------------------------------------

def _credentials() -> tuple[str, str]:
    user = os.environ.get("YAHOO_EMAIL")
    pw = os.environ.get("YAHOO_APP_PASSWORD")
    if not pw and user:
        try:
            import keyring  # optional
            pw = keyring.get_password("car-tracker-yahoo", user)
        except Exception:
            pw = None
    if not user or not pw:
        raise EmailError("Set YAHOO_EMAIL and YAHOO_APP_PASSWORD in .env (or store the password in your OS keyring).")
    return user, pw


def fetch_messages(cfg_email: dict, already_done) -> list[Message]:
    """Read-only fetch of the alert folder. Nothing is marked read, moved or deleted."""
    user, pw = _credentials()
    host, port = cfg_email.get("imap_host", "imap.mail.yahoo.com"), int(cfg_email.get("imap_port", 993))
    folder = cfg_email.get("folder", "KSL Alerts")
    since = (datetime.now() - timedelta(days=int(cfg_email.get("lookback_days", 45)))).strftime("%d-%b-%Y")
    out: list[Message] = []
    with imaplib.IMAP4_SSL(host, port) as imap:
        imap.login(user, pw)
        typ, _ = imap.select(f'"{folder}"', readonly=True)
        if typ != "OK":
            raise EmailError(f'Folder "{folder}" not found in Yahoo. Check the folder name in config.yaml.')
        typ, data = imap.search(None, "SINCE", since)
        if typ != "OK":
            raise EmailError("IMAP search failed")
        for num in data[0].split():
            # Headers first so already-processed mail isn't downloaded again.
            typ, hdr = imap.fetch(num, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
            mid = email.message_from_bytes(hdr[0][1]).get("Message-ID", "").strip() if typ == "OK" else ""
            if mid and already_done(mid):
                continue
            typ, msg_data = imap.fetch(num, "(BODY.PEEK[])")
            if typ == "OK":
                out.append(email.message_from_bytes(msg_data[0][1]))
    return out


def load_eml_files(paths: list[str]) -> list[Message]:
    return [email.message_from_bytes(Path(p).read_bytes()) for p in paths]


# ---- parsing ----------------------------------------------------------------

def classify(subject: str, body_text: str) -> str:
    s = f"{subject} {body_text[:500]}".lower()
    if "expir" in s:
        return "expiring"
    if re.search(r"price\s*(drop|reduc|lower|cut|change)|reduced|dropped", s):
        return "price_drop"
    return "new"


def _body(msg: Message) -> tuple[str | None, str]:
    html, text = None, ""
    for part in msg.walk():
        ctype = part.get_content_type()
        if part.get_content_maintype() == "multipart" or part.get("Content-Disposition", "").startswith("attachment"):
            continue
        try:
            payload = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        if ctype == "text/html" and html is None:
            html = payload
        elif ctype == "text/plain" and not text:
            text = payload
    return html, text


def listing_id_from_url(href: str) -> str | None:
    """Direct KSL links, or tracking redirects that carry the real URL in a query parameter."""
    for candidate in (href, unquote(href)):
        m = LISTING_ID_RE.search(candidate)
        if m:
            return m.group(1)
    for vals in parse_qs(urlparse(href).query).values():
        for v in vals:
            m = LISTING_ID_RE.search(unquote(v))
            if m:
                return m.group(1)
    return None


def _listing_blocks(soup: BeautifulSoup) -> dict[str, str]:
    """listing id -> the text of the smallest enclosing block that contains a price."""
    blocks: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        lid = listing_id_from_url(a["href"])
        if not lid:
            continue
        node, best = a, a.get_text(" ", strip=True)
        for _ in range(8):  # walk up to the card / table row holding this listing
            node = node.parent
            if node is None:
                break
            t = node.get_text(" ", strip=True)
            if len(t) > 1500:
                break
            best = t
            if textparse.parse_prices(t) and textparse.parse_title(t):
                break
        if len(best) > len(blocks.get(lid, "")):
            blocks[lid] = best
    return blocks


def _plaintext_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        lid = listing_id_from_url(line)
        if lid:
            blocks[lid] = " ".join(lines[max(0, i - 6): i + 1])
    return blocks


def parse_message(msg: Message) -> dict:
    """-> {message_id, subject, date, event, listings: [ {source_id, url, year, make, ...} ]}"""
    subject = str(email.header.make_header(email.header.decode_header(msg.get("Subject", ""))))
    try:
        sent = parsedate_to_datetime(msg.get("Date")).astimezone().replace(tzinfo=None, microsecond=0)
    except Exception:
        sent = datetime.now().replace(microsecond=0)
    html, text = _body(msg)
    if html:
        soup = BeautifulSoup(html, "html.parser")
        blocks = _listing_blocks(soup)
        body_text = soup.get_text(" ", strip=True)
    else:
        blocks = _plaintext_blocks(text)
        body_text = text
    event = classify(subject, body_text)

    listings = []
    for lid, block in blocks.items():
        info = textparse.parse_title(block) or textparse.parse_title(subject)
        prices = textparse.parse_prices(block)
        # A price-drop card usually shows old and new price; the current one is the lower.
        price = min(prices) if (prices and event == "price_drop") else (prices[0] if prices else None)
        listings.append({
            **info,
            "source_id": lid,
            "url": f"https://cars.ksl.com/listing/{lid}",
            "price": price,
            "mileage": textparse.parse_mileage(block),
            "vin": textparse.parse_vin(block),
            "raw": block[:300],
        })
    return {
        "message_id": (msg.get("Message-ID") or f"{subject}|{sent}").strip(),
        "subject": subject,
        "date": sent.isoformat(sep=" "),
        "event": event,
        "listings": listings,
    }
