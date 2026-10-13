# Car price tracker

Tracks RAV4 Hybrid, Forester and CX-5 Carbon listings from KSL Cars (via your alert emails) and
local dealer sites, and rebuilds `output/car_tracker.xlsx` every run.

## Setup (once)

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then fill it in
```

1. **Yahoo app password.** Yahoo Account Security → Generate app password. Put it in `.env` as
   `YAHOO_APP_PASSWORD`. Your normal password won't work. Revoke it any time from the same page.
2. **Yahoo filter.** Move mail from KSL into a folder named `KSL Alerts` (or change `email.folder`).
3. **KSL saved searches**, one per vehicle, 50 mi radius, email alerts on. To get price-drop and
   expiring alerts, favorite the listings you care about.
4. **Dealers.** Add each checked dealer under `dealers:` in `config.yaml` and set `enabled: true`.

## Run

```bash
python -m cartracker              # Yahoo + dealers, then rebuild the spreadsheet
python -m cartracker -v           # also print why each skipped listing was skipped
python -m cartracker --eml a.eml  # test the parser on saved alert emails (no Yahoo login)
python -m cartracker --skip-email | --skip-dealers | --export-only
```

Close the spreadsheet in Excel before running.

## How it decides things

| | |
|---|---|
| Mileage cap | `12,000 × (this year − model year + 1)`, recalculated every run. Flip `count_model_year_as_year_one` to drop the +1. |
| KSL status | Alerts never say "sold". A KSL car becomes `likely_gone` 3 days after an *expiring* alert, or after 30 days with no alert at all. |
| Dealer status | Confirmed. A car missing from a complete, successful scrape is `gone`. A blocked or failed scrape, or one that parses 0 cars, changes nothing. |
| Duplicates | Same VIN = merged (shown once, with "Also On"). No VIN but same vehicle/year and within 500 mi and $1,000 = flagged in "Possible Dup" for you to judge. |
| Notes | Yellow column, kept across rebuilds. Everything else is regenerated. |

Data lives in `data/tracker.db` (SQLite). Delete it to start over.

## Scraping rules

The dealer scraper honors robots.txt and crawl-delay, identifies itself honestly, and stops at the
first block, CAPTCHA or challenge page. It never retries or works around one. Only add sites whose
terms allow automated access.

## Tests

```bash
python tests/test_pipeline.py
```
