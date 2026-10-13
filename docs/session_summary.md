# Session summary and next steps

## 1. What we did this session

1. **Read the repo.** Reviewed the README, config, `__main__.py`, `db.py` and `dealer.py`, and skimmed the rest by size. Tests couldn't run at the time because dependencies weren't installed.
2. **Explained how dealer scraping works.** There is no "run with a URL" command. Dealers go in `config.yaml`, and the scraper reads JSON-LD vehicle data from their inventory pages.
3. **Wrote [dealers.md](../dealers.md).** It lists 13 candidate dealer sites with a per-dealer checklist and a status table.
4. **Fetched robots.txt for all 13 sites** (one request each, 2s apart, honest User-Agent). Results are in [robots_results.md](robots_results.md).
   - Allowed: buysmartbuy, dubs-auto, gpmotorz, westautosales, markosianauto, levelupcarsales.
   - No robots.txt (404): automotivesalesandfinance.
   - Allowed, but a car-buying service: webuyanycarusa.
   - Blocked (403 or challenge), not retried: kentsoncarcompany, autolocitymotors, axioauto, autosavvy, rogersautoutah.
5. **Probed the 6 clear sites for JSON-LD** and parsed one inventory page each with the stock parser. Results are in [jsonld_probe.md](jsonld_probe.md).
   - gpmotorz and westautosales: parse, but without VIN or mileage.
   - markosianauto and levelupcarsales: 0 vehicles parsed.
   - buysmartbuy and dubs-auto: stopped by the tracker's block heuristic (HTTP 200).
6. **Set up the environment:** created `.venv` (git-ignored) and installed `requirements.txt`.

No code in `cartracker/` was changed. `config.yaml` still has only the disabled example dealer.

## 2. What the repo has

| Path | Purpose |
|------|---------|
| `cartracker/__main__.py` | CLI entry point. Orchestrates email ingest, dealer scrape, status inference, dedup, export. |
| `cartracker/config.py` | Loads `config.yaml`, matches listings to vehicle specs, detects trims, applies the mileage cap. |
| `cartracker/db.py` | SQLite schema and logic for observing listings, price history, status, dedup and run stats. |
| `cartracker/ksl_email.py` | Reads KSL alert emails from Yahoo over IMAP (read-only), or from saved `.eml` files. |
| `cartracker/dealer.py` | Polite scraper: honors robots.txt and crawl-delay, stops at the first block, parses schema.org JSON-LD. |
| `cartracker/textparse.py` | Parses year, make, model and trim from listing titles. |
| `cartracker/export.py` | Rebuilds `output/car_tracker.xlsx` and round-trips the yellow Notes column. |
| `config.yaml` | Vehicles, mileage rules, dedup, status timing, email settings, dealers, output paths. |
| `tests/test_pipeline.py` | Single test script. |
| `dealers.md`, `docs/` | This session's research on candidate dealers. |

**Tracked vehicles:** RAV4 Hybrid (2022+, non-plug-in), Forester (2020–2026), CX-5 Carbon (2025, non-turbo).
**Mileage cap:** 12,000 × (this year − model year + 1), recomputed every run.
**Status:** KSL status is inferred (`likely_gone`). Dealer status is confirmed (`gone`) only after a complete, successful scrape.

## 3. How to use it

```bash
# once
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # add YAHOO_EMAIL and YAHOO_APP_PASSWORD

# every run
python -m cartracker                   # Yahoo + dealers, then rebuild the spreadsheet
python -m cartracker -v                # also explain why listings were skipped
python -m cartracker --skip-email      # dealers only
python -m cartracker --skip-dealers    # email only
python -m cartracker --eml a.eml       # test the email parser on saved files
python -m cartracker --export-only     # just rebuild the spreadsheet
python tests/test_pipeline.py          # tests
```

**Adding a dealer:** check robots.txt and the terms, confirm the inventory page has vehicle JSON-LD, add an entry under `dealers:` in `config.yaml` (`name`, `base_url`, `inventory_urls`, `page_param`, `max_pages`, `crawl_delay`) with `enabled: true`, then run with `--skip-email -v`.

Close the spreadsheet in Excel before running. Data lives in `data/tracker.db`, and deleting it starts over.

## 4. Next steps

**Do first**
1. Run `python tests/test_pipeline.py` now that dependencies are installed, to confirm the baseline.
2. Set up the Yahoo side: app password in `.env`, a filter into a `KSL Alerts` folder, and KSL saved searches (50 mi, email alerts on).
3. Commit the work. History is still a single "Initial commit", and the new files and `.venv` handling should be reviewed first.

**Dealer work (pick in this order)**
4. **gpmotorz and westautosales:** extend the parser to take the VIN from the detail URL and mileage from the listing text. Find the pagination parameter, add both to `config.yaml`, and test.
5. **markosianauto and levelupcarsales:** write custom parsers (listing text or detail pages), since they have no vehicle JSON-LD.
6. **buysmartbuy and dubs-auto:** decide whether to loosen `CHALLENGE_MARKERS` so it only applies to non-200 or very short responses. Then re-probe.
7. **automotivesalesandfinance:** probe it. It has no robots.txt, which means no stated restrictions.
8. **webuyanycarusa:** probably drop it, as it looks like a buying service with no inventory.
9. **The five blocked sites:** leave alone. If you want them, contact the dealers or use their official feeds.

**Cleanups**
10. Deal with the low-priority issues in `db.py`: stale `possible_dup_of` flags aren't cleared, the fuzzy dedup is O(n²), and the status timestamp uses the run time.
11. Add tests for any new dealer parser, using saved HTML fixtures so tests don't hit live sites.

## 5. Things to think about

- **Terms of use are unchecked for every dealer.** robots.txt is necessary, not sufficient. The README says to add only sites whose terms allow automated access.
- **Missing mileage defeats the cap.** With `keep_unknown_mileage: true`, a dealer without mileage passes everything. Decide whether such listings should be flagged or dropped.
- **Missing VINs weaken dedup.** Cross-source merging relies on VINs, and the fuzzy fallback needs mileage and price.
- **Blocks are final by design.** The scraper never retries or evades. Keep it that way, and treat a 0-vehicle parse as "layout changed", never as "everything sold".
- **Run cadence.** The User-Agent says "twice-weekly". Stay near that, and don't schedule frequent runs.
- **Yahoo app password.** It lives in `.env`, which is git-ignored. Revoke it from Yahoo security if it leaks.
- **Spreadsheet is disposable.** Only the Notes column survives a rebuild, so don't edit other columns by hand.
- **Redesigned model years.** The 2026 RAV4 is a redesign, and its trim names may not match `config.yaml`. Check after the first real run.
- **KSL "likely gone" is a guess.** The 30-day default should match KSL's real listing length.
