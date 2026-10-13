# Dealer list

Candidate dealer sites for the tracker. Nothing here has been checked yet: no robots.txt, terms or JSON-LD review, and no site has been fetched.

Once a dealer is checked and its inventory URL is known, add it under `dealers:` in `config.yaml` (see README, "Scraping rules").

## Checklist per dealer

1. `robots.txt` allows the inventory path.
2. The site's terms allow automated access.
3. The inventory page has `application/ld+json` with `Car` / `Vehicle` entries (price, mileage, VIN). If not, it needs a custom parser.
4. Find the inventory URL(s) and the `page_param` (the query param for page 2, 3, ...).
5. Add to `config.yaml`, set `enabled: true`, and run `python -m cartracker --skip-email -v`.

## Sites

| # | Dealer | Base URL | robots OK | Terms OK | JSON-LD | Inventory URL / page_param | In config |
|---|--------|----------|-----------|----------|---------|----------------------------|-----------|
| 1 | Kentson Car Company | https://www.kentsoncarcompany.com/ | BLOCKED (403) | ? | ? | | no |
| 2 | Autolocity Motors | https://www.autolocitymotors.com/ | BLOCKED (403) | ? | ? | | no |
| 3 | Buy Smart Buy | https://www.buysmartbuy.com/ | yes | flagged as challenge by tracker heuristic (HTTP 200); not scraped | see docs/jsonld_probe.md | | no |
| 4 | GP Motorz | https://www.gpmotorz.com/ | yes | partial: ItemList/Product (year, make, model, trim, price; no VIN or mileage) | `/view-inventory`, `/inventory`; page_param unknown | | no |
| 5 | Markosian Auto (Ogden) | https://markosianauto.com/ | yes | no: listing page has only CollectionPage/Breadcrumb | `/used-cars-inventory/` | | no |
| 6 | Level Up Car Sales | https://levelupcarsales.com/ | yes | no: listing page has no vehicle data | `/inventory/` (detail pages at `/listings/...`) | | no |
| 7 | Dubs Auto | https://www.dubs-auto.com/ | yes | flagged as challenge by tracker heuristic (HTTP 200); not scraped | see docs/jsonld_probe.md | | no |
| 8 | Axio Auto | https://www.axioauto.com/ | BLOCKED (403) | ? | ? | | no |
| 9 | West Auto Sales | https://westautosales.com/ | yes | partial: ItemList/Product (year, make, model, trim, price; no VIN or mileage) | `/used-cars-in-utah`; page_param unknown | | no |
| 10 | Auto Savvy | https://www.autosavvy.com/ | BLOCKED (403) | ? | ? | | no |
| 11 | Automotive Sales and Finance | https://www.automotivesalesandfinance.com/ | none (404) | ? | ? | | no |
| 12 | We Buy Any Car USA | https://www.webuyanycarusa.com/ | yes | ? | ? | | no |
| 13 | Rogers Auto Utah | https://www.rogersautoutah.com/ | BLOCKED (Cloudflare) | ? | ? | | no |

## Notes

- #5: the original link carried tracking params (`utm_medium`, `utm_source`, `utm_campaign`, `utm_term=ogden`). They are stripped above because they don't change the page. "Ogden" is the location the Google listing pointed to.
- #12: the name suggests a car-buying service rather than a dealer with used inventory to browse. It may have nothing to scrape, so check that first.
