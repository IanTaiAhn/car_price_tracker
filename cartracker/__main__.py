"""Run the tracker:  python -m cartracker  [--config config.yaml] [--skip-email] [--skip-dealers]
                                         [--eml FILE ...] [--export-only] [--verbose]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import dealer as dealer_mod
from . import export, ksl_email, textparse
from .config import detect_trim, load_config, match_vehicle
from .db import DB, now_iso


def _load_env(root: Path):
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
    except ImportError:
        pass


def ingest_emails(cfg, db, messages, verbose, report):
    for msg in messages:
        parsed = ksl_email.parse_message(msg)
        if db.email_done(parsed["message_id"]):
            continue
        kept = 0
        for item in parsed["listings"]:
            spec, why = match_vehicle(cfg, item)
            if not spec:
                if verbose:
                    print(f"  skip KSL {item['source_id']}: {why}  [{item.get('title') or item['raw'][:60]}]")
                continue
            item["trim"] = detect_trim(spec, item)
            _, change = db.observe("KSL", item["source_id"], spec.key, item, parsed["event"], parsed["date"])
            report[change or "updated"] = report.get(change or "updated", 0) + 1
            kept += 1
        if not parsed["listings"]:
            report["emails_without_listings"] = report.get("emails_without_listings", 0) + 1
            if verbose:
                print(f"  ! no listing links found in: {parsed['subject']!r}")
        db.mark_email(parsed["message_id"], parsed["subject"], kept)
        report["emails"] = report.get("emails", 0) + 1


def run_dealers(cfg, db, verbose, report):
    for d in cfg.dealers:
        name = d["name"]
        at = now_iso()
        try:
            vehicles = dealer_mod.DealerScraper(d).scrape()
        except dealer_mod.Blocked as e:
            print(f"  ✗ {name}: {e}. Nothing marked gone for this dealer.")
            report["dealer_errors"] = report.get("dealer_errors", 0) + 1
            continue
        except Exception as e:  # network error etc.
            print(f"  ✗ {name}: {type(e).__name__}: {e}. Nothing marked gone for this dealer.")
            report["dealer_errors"] = report.get("dealer_errors", 0) + 1
            continue
        if not vehicles:
            had = db.conn.execute("SELECT COUNT(*) FROM listings WHERE source=? AND status!='gone'", (name,)).fetchone()[0]
            print(f"  ! {name}: 0 vehicles parsed. The page layout may have changed; "
                  f"{'not marking its ' + str(had) + ' cars gone.' if had else 'nothing to do.'}")
            continue
        seen, kept = set(), 0
        for v in vehicles:
            spec, why = match_vehicle(cfg, v)
            if not spec:
                continue
            v["trim"] = detect_trim(spec, v)
            _, change = db.observe(name, v["source_id"], spec.key, v, "seen", at)
            seen.add(v["source_id"])
            report[change or "updated"] = report.get(change or "updated", 0) + 1
            kept += 1
        gone = db.close_out_dealer(name, seen, at)
        report["gone"] = report.get("gone", 0) + gone
        print(f"  ✓ {name}: {len(vehicles)} vehicles on site, {kept} match, {gone} newly gone")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cartracker", description="Track used-car listings and prices.")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--skip-email", action="store_true", help="don't read Yahoo")
    ap.add_argument("--skip-dealers", action="store_true", help="don't scrape dealer sites")
    ap.add_argument("--eml", nargs="+", metavar="FILE", help="parse saved .eml alert files instead of Yahoo")
    ap.add_argument("--export-only", action="store_true", help="just rebuild the spreadsheet")
    ap.add_argument("-v", "--verbose", action="store_true", help="show why listings were skipped")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    _load_env(cfg.root)
    textparse.set_makes([v.make for v in cfg.vehicles])
    db = DB(cfg.db_path)
    started = now_iso()
    report: dict[str, int] = {}

    # Preserve your Notes column before anything rebuilds the file.
    try:
        db.set_notes(export.read_notes(cfg.xlsx_path))
    except PermissionError:
        sys.exit(f"Close {cfg.xlsx_path.name} in Excel first, then run again.")

    if not args.export_only:
        if args.eml:
            print(f"Reading {len(args.eml)} saved email(s)…")
            ingest_emails(cfg, db, ksl_email.load_eml_files(args.eml), args.verbose, report)
        elif not args.skip_email:
            print("Reading KSL alerts from Yahoo (read-only)…")
            try:
                msgs = ksl_email.fetch_messages(cfg.email, db.email_done)
                print(f"  {len(msgs)} new email(s)")
                ingest_emails(cfg, db, msgs, args.verbose, report)
            except ksl_email.EmailError as e:
                print(f"  ✗ {e}")
            except Exception as e:
                print(f"  ✗ Yahoo: {type(e).__name__}: {e}")
        if not args.skip_dealers and cfg.dealers:
            print("Checking dealer sites…")
            run_dealers(cfg, db, args.verbose, report)

        st = cfg.status
        report["likely_gone"] = db.infer_ksl_status(int(st.get("ksl_expiring_grace_days", 3)),
                                                    int(st.get("ksl_assume_gone_after_days", 30)))
        dd = cfg.dedup
        merged, flagged = db.dedup(int(dd.get("fuzzy_mileage_tolerance", 500)),
                                   int(dd.get("fuzzy_price_tolerance", 1000)),
                                   bool(dd.get("auto_merge_fuzzy", False)))
        report["vin_merged"], report["possible_dups"] = merged, flagged
        summary = ", ".join(f"{k}={v}" for k, v in report.items() if v)
        db.record_run(started, [v.key for v in cfg.vehicles], summary)
    db.commit()

    try:
        path = export.build(cfg, db)
    except PermissionError:
        sys.exit(f"Data saved, but {cfg.xlsx_path.name} is open in Excel. Close it and run with --export-only.")
    print(f"\nDone. {', '.join(f'{k}: {v}' for k, v in report.items() if v) or 'No changes.'}")
    print(f"Spreadsheet: {path}")


if __name__ == "__main__":
    main()
