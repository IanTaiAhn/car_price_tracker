# JSON-LD probe results

For the six sites whose robots.txt allows crawling, I fetched the homepage and then one inventory listing page, 2 seconds apart, using the tracker's own scraper rules (honest User-Agent, robots.txt checked, stop on a challenge). I then ran `parse_jsonld_vehicles` on the inventory page.

| Site | Result |
|------|--------|
| gpmotorz.com | `/view-inventory` parsed 7 vehicles from `ItemList` > `Product`. Has year, make, model, trim and price. **No VIN or mileage.** The VIN is in the detail URL (`/inventory/2019-toyota-tacoma-trd-sport-<VIN>`). |
| westautosales.com | `/used-cars-in-utah` parsed 8 vehicles, same shape and same gaps. It shares a platform with gpmotorz. Some detail-link text shows mileage, so it is on the page. |
| markosianauto.com | `/used-cars-inventory/` has only `CollectionPage` and `BreadcrumbList`. 0 vehicles. Needs a custom parser or a detail-page approach. |
| levelupcarsales.com | `/inventory/` has no vehicle data. 0 vehicles. Detail pages are at `/listings/...` and the link text includes price, year and mileage. Needs a custom parser. |
| buysmartbuy.com | The tracker's block heuristic stopped it on the homepage, although the HTTP status was 200. **Not scraped further.** |
| dubs-auto.com | Same as buysmartbuy. Stopped on the homepage and not scraped further. |

## Notes

- The stock parser can't use gpmotorz or westautosales as-is. `source_id` would fall back to the URL or SKU, and mileage would be `None`. The mileage cap isn't applied to listings without mileage (`keep_unknown_mileage: true`), so every car would pass it. Fix: take the VIN from the detail URL and get mileage from the listing text.
- For buysmartbuy and dubs-auto, `CHALLENGE_MARKERS` in `cartracker/dealer.py` does a substring match on the first 20,000 characters, including words like `captcha`. A normal page that merely loads a reCAPTCHA script on a contact form would trip it. I treated it as a block and did not retry or work around it. If you want these two sites, the marker check should apply only to non-200 or very short responses. That change needs your decision.
- I didn't check any site's terms of use.
