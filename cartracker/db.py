"""SQLite storage: the source of truth. The spreadsheet is rebuilt from this every run."""
from __future__ import annotations

import sqlite3
import statistics
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id              INTEGER PRIMARY KEY,
    source          TEXT NOT NULL,          -- 'KSL' or the dealer name
    source_id       TEXT NOT NULL,          -- KSL listing id, VIN or dealer stock/URL
    vehicle_key     TEXT NOT NULL,
    year            INTEGER,
    make            TEXT,
    model           TEXT,
    trim            TEXT,
    title           TEXT,
    mileage         INTEGER,
    price           INTEGER,
    first_price     INTEGER,
    min_price       INTEGER,
    max_price       INTEGER,
    url             TEXT,
    vin             TEXT,
    location        TEXT,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,          -- last time any source said this car exists
    expiring_at     TEXT,                   -- KSL "expiring" alert date
    status          TEXT NOT NULL DEFAULT 'active',   -- active | likely_gone | gone
    gone_at         TEXT,
    dup_of          INTEGER,                -- confirmed duplicate (VIN or auto-merged) -> canonical id
    possible_dup_of INTEGER,                -- fuzzy match, for you to judge
    notes           TEXT,
    UNIQUE (source, source_id)
);
CREATE TABLE IF NOT EXISTS price_history (
    listing_id  INTEGER NOT NULL REFERENCES listings(id),
    observed_at TEXT NOT NULL,
    price       INTEGER,
    event       TEXT NOT NULL,     -- new | price_drop | price_rise | expiring | gone | likely_gone | back
    recorded_at TEXT               -- when this run wrote it (observed_at may be an older email's date)
);
CREATE TABLE IF NOT EXISTS processed_emails (
    message_id   TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL,
    subject      TEXT,
    n_listings   INTEGER
);
CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    summary    TEXT
);
CREATE TABLE IF NOT EXISTS run_stats (
    run_id       INTEGER NOT NULL REFERENCES runs(id),
    vehicle_key  TEXT NOT NULL,
    active       INTEGER,
    new_count    INTEGER,
    gone_count   INTEGER,
    median_price INTEGER,
    min_price    INTEGER
);
"""


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def commit(self):
        self.conn.commit()

    # ---- writes -------------------------------------------------------------
    def observe(self, source: str, source_id: str, vehicle_key: str, data: dict,
                event: str = "seen", at: str | None = None) -> tuple[int, str]:
        """Record that a listing exists (with its current details). Returns (id, what_changed)."""
        at = at or now_iso()
        cur = self.conn.execute("SELECT * FROM listings WHERE source=? AND source_id=?", (source, source_id))
        row = cur.fetchone()
        price = data.get("price")

        if row is None:
            self.conn.execute(
                """INSERT INTO listings (source, source_id, vehicle_key, year, make, model, trim, title,
                       mileage, price, first_price, min_price, max_price, url, vin, location,
                       first_seen, last_seen, expiring_at, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'active')""",
                (source, source_id, vehicle_key, data.get("year"), data.get("make"), data.get("model"),
                 data.get("trim"), data.get("title"), data.get("mileage"), price, price, price, price,
                 data.get("url"), data.get("vin"), data.get("location"), at, at,
                 at if event == "expiring" else None))
            lid = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            self._history(lid, at, price, "new")
            if event == "expiring":
                self._history(lid, at, price, "expiring")
            return lid, "new"

        lid = row["id"]
        changed = ""
        # Older email processed after a newer one: don't let stale data overwrite current price.
        stale = at < row["last_seen"]
        updates = {}
        if not stale:
            updates["last_seen"] = at
            for k in ("year", "make", "model", "trim", "title", "mileage", "url", "vin", "location"):
                if data.get(k) and data.get(k) != row[k]:
                    updates[k] = data[k]
            if price and row["price"] and price != row["price"]:
                ev = "price_drop" if price < row["price"] else "price_rise"
                self._history(lid, at, price, ev)
                changed = ev
            if price:
                updates["price"] = price
                updates["min_price"] = min(price, row["min_price"] or price)
                updates["max_price"] = max(price, row["max_price"] or price)
            if row["status"] != "active":
                updates.update(status="active", gone_at=None)
                self._history(lid, at, price or row["price"], "back")
                changed = changed or "back"
        if event == "expiring":
            updates["expiring_at"] = at
            self._history(lid, at, price or row["price"], "expiring")
            changed = changed or "expiring"
        if updates:
            sets = ", ".join(f"{k}=?" for k in updates)
            self.conn.execute(f"UPDATE listings SET {sets} WHERE id=?", (*updates.values(), lid))
        return lid, changed

    def mark_gone(self, lid: int, status: str, at: str):
        row = self.conn.execute("SELECT price FROM listings WHERE id=?", (lid,)).fetchone()
        self.conn.execute("UPDATE listings SET status=?, gone_at=? WHERE id=?", (status, at, lid))
        self._history(lid, at, row["price"], "gone" if status == "gone" else "likely_gone")

    def _history(self, lid, at, price, event):
        self.conn.execute("INSERT INTO price_history VALUES (?,?,?,?,?)", (lid, at, price, event, now_iso()))

    # ---- emails -------------------------------------------------------------
    def email_done(self, message_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM processed_emails WHERE message_id=?", (message_id,)).fetchone() is not None

    def mark_email(self, message_id: str, subject: str, n: int):
        self.conn.execute("INSERT OR REPLACE INTO processed_emails VALUES (?,?,?,?)",
                          (message_id, now_iso(), subject, n))

    # ---- status inference ---------------------------------------------------
    def infer_ksl_status(self, grace_days: int, assume_gone_days: int, today: datetime | None = None) -> int:
        today = today or datetime.now()
        n = 0
        for r in self.conn.execute("SELECT * FROM listings WHERE source='KSL' AND status='active'").fetchall():
            last = datetime.fromisoformat(r["last_seen"])
            if r["expiring_at"]:
                exp = datetime.fromisoformat(r["expiring_at"])
                if today > exp + timedelta(days=grace_days) and last <= exp:
                    self.mark_gone(r["id"], "likely_gone", now_iso()); n += 1
                    continue
            if today > last + timedelta(days=assume_gone_days):
                self.mark_gone(r["id"], "likely_gone", now_iso()); n += 1
        return n

    def close_out_dealer(self, source: str, seen_ids: set[str], at: str) -> int:
        """After a complete, successful scrape: anything not seen is gone (confirmed)."""
        n = 0
        for r in self.conn.execute("SELECT id, source_id FROM listings WHERE source=? AND status!='gone'", (source,)):
            if r["source_id"] not in seen_ids:
                self.mark_gone(r["id"], "gone", at); n += 1
        return n

    # ---- dedup --------------------------------------------------------------
    def dedup(self, mileage_tol: int, price_tol: int, auto_merge: bool) -> tuple[int, int]:
        c = self.conn
        merged = flagged = 0
        rows = c.execute("SELECT * FROM listings ORDER BY first_seen, id").fetchall()
        by_vin: dict[str, int] = {}
        for r in rows:
            if not r["vin"]:
                continue
            canon = by_vin.setdefault(r["vin"], r["id"])
            if canon != r["id"] and r["dup_of"] != canon:
                c.execute("UPDATE listings SET dup_of=?, possible_dup_of=NULL WHERE id=?", (canon, r["id"]))
                merged += 1
        rows = c.execute("SELECT * FROM listings WHERE dup_of IS NULL ORDER BY first_seen, id").fetchall()
        for i, a in enumerate(rows):
            if a["possible_dup_of"] or a["mileage"] is None or a["price"] is None:
                continue
            for b in rows[:i]:
                if (b["source"] == a["source"] or b["vehicle_key"] != a["vehicle_key"] or b["year"] != a["year"]
                        or b["mileage"] is None or b["price"] is None):
                    continue
                if a["vin"] and b["vin"] and a["vin"] != b["vin"]:
                    continue
                if abs(a["mileage"] - b["mileage"]) <= mileage_tol and abs(a["price"] - b["price"]) <= price_tol:
                    col = "dup_of" if auto_merge else "possible_dup_of"
                    c.execute(f"UPDATE listings SET {col}=? WHERE id=?", (b["id"], a["id"]))
                    flagged += 1
                    break
        return merged, flagged

    # ---- notes (round-tripped through the spreadsheet) -----------------------
    def set_notes(self, notes: dict[int, str]):
        for lid, text in notes.items():
            self.conn.execute("UPDATE listings SET notes=? WHERE id=?", (text, lid))

    # ---- run stats ----------------------------------------------------------
    def record_run(self, started_at: str, vehicle_keys: list[str], summary: str) -> int:
        c = self.conn
        c.execute("INSERT INTO runs (started_at, summary) VALUES (?,?)", (started_at, summary))
        run_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        since = started_at  # count only events this run recorded
        for key in vehicle_keys:
            active = [r["price"] for r in c.execute(
                "SELECT price FROM listings WHERE vehicle_key=? AND status='active' AND dup_of IS NULL", (key,))]
            prices = [p for p in active if p]
            new = c.execute("""SELECT COUNT(*) FROM price_history h JOIN listings l ON l.id=h.listing_id
                               WHERE l.vehicle_key=? AND l.dup_of IS NULL AND h.event='new' AND h.recorded_at>=?""",
                            (key, since)).fetchone()[0]
            gone = c.execute("""SELECT COUNT(*) FROM price_history h JOIN listings l ON l.id=h.listing_id
                                WHERE l.vehicle_key=? AND l.dup_of IS NULL AND h.event IN ('gone','likely_gone')
                                AND h.recorded_at>=?""", (key, since)).fetchone()[0]
            c.execute("INSERT INTO run_stats VALUES (?,?,?,?,?,?,?)",
                      (run_id, key, len(active), new, gone,
                       int(statistics.median(prices)) if prices else None, min(prices) if prices else None))
        return run_id
