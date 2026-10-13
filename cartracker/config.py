"""Config loading and the per-vehicle filter rules."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml


@dataclass
class VehicleSpec:
    key: str
    sheet: str
    make: str
    model: str
    min_year: int
    max_year: int | None = None
    trims: list[str] = field(default_factory=list)
    exclude_trim_words: list[str] = field(default_factory=list)
    require_hybrid: bool = False
    exclude_hybrid: bool = False


@dataclass
class Config:
    raw: dict
    root: Path
    vehicles: list[VehicleSpec]

    # ---- convenience accessors -------------------------------------------------
    @property
    def mileage(self) -> dict:
        return self.raw.get("mileage", {})

    @property
    def dedup(self) -> dict:
        return self.raw.get("dedup", {})

    @property
    def status(self) -> dict:
        return self.raw.get("status", {})

    @property
    def email(self) -> dict:
        return self.raw.get("email", {})

    @property
    def dealers(self) -> list[dict]:
        return [d for d in self.raw.get("dealers", []) if d.get("enabled")]

    @property
    def db_path(self) -> Path:
        return self.root / self.raw["output"]["db_path"]

    @property
    def xlsx_path(self) -> Path:
        return self.root / self.raw["output"]["xlsx_path"]

    def mileage_cap(self, model_year: int, today: date | None = None) -> int:
        today = today or date.today()
        per_year = int(self.mileage.get("miles_per_year", 12000))
        years = today.year - model_year
        if self.mileage.get("count_model_year_as_year_one", True):
            years += 1
        return per_year * max(1, years)


def load_config(path: str | Path) -> Config:
    path = Path(path).resolve()
    raw = yaml.safe_load(path.read_text())
    vehicles = [VehicleSpec(**v) for v in raw.get("vehicles", [])]
    return Config(raw=raw, root=path.parent, vehicles=vehicles)


# ---- matching ----------------------------------------------------------------

def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _has_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(_norm(phrase))}\b", text) is not None


def match_vehicle(cfg: Config, listing: dict) -> tuple[VehicleSpec | None, str]:
    """Return (spec, "") if the listing fits a tracked vehicle, else (None, reason).

    `listing` needs make/model/year and ideally trim/title/mileage/fuel.
    """
    text = _norm(" ".join(str(listing.get(k) or "") for k in ("make", "model", "trim", "title", "fuel")))
    year = listing.get("year")
    reasons = []
    for spec in cfg.vehicles:
        if not (_has_phrase(text, spec.make) or _norm(listing.get("make")) == _norm(spec.make)):
            continue
        if not _has_phrase(text, spec.model):
            continue
        if year is None:
            reasons.append(f"{spec.key}: no year")
            continue
        max_year = spec.max_year or date.today().year + 1
        if not (spec.min_year <= year <= max_year):
            reasons.append(f"{spec.key}: year {year} out of range")
            continue
        is_hybrid = _has_phrase(text, "hybrid")
        if spec.require_hybrid and not is_hybrid:
            reasons.append(f"{spec.key}: not hybrid")
            continue
        if spec.exclude_hybrid and is_hybrid:
            reasons.append(f"{spec.key}: hybrid excluded")
            continue
        if spec.trims and not any(_has_phrase(text, t) for t in spec.trims):
            reasons.append(f"{spec.key}: trim not wanted")
            continue
        if any(_has_phrase(text, w) for w in spec.exclude_trim_words):
            reasons.append(f"{spec.key}: excluded trim word")
            continue
        miles = listing.get("mileage")
        if miles is None:
            if not cfg.mileage.get("keep_unknown_mileage", True):
                reasons.append(f"{spec.key}: unknown mileage")
                continue
        elif miles > cfg.mileage_cap(year):
            reasons.append(f"{spec.key}: {miles} mi over cap {cfg.mileage_cap(year)}")
            continue
        return spec, ""
    return None, "; ".join(reasons) or "not a tracked make/model"


def detect_trim(spec: VehicleSpec, listing: dict) -> str | None:
    """Pick the configured trim name that appears in the listing text (longest match wins)."""
    text = _norm(" ".join(str(listing.get(k) or "") for k in ("trim", "title")))
    hits = [t for t in spec.trims if _has_phrase(text, t)]
    return max(hits, key=len) if hits else listing.get("trim")
