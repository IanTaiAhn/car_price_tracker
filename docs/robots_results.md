# robots.txt results

Fetched once per site with the tracker's own User-Agent (`PersonalCarPriceTracker/0.1 (personal, non-commercial; twice-weekly)`). One request each, 2s apart, no retries.

## Summary

| Site | Status | What it means |
|------|--------|---------------|
| kentsoncarcompany.com | 403 | Blocked us. The tracker treats the whole site as off-limits. |
| autolocitymotors.com | 403 | Akamai "Access Denied". Off-limits. |
| buysmartbuy.com | 200 | Allows all (`Disallow:` empty). Only named bots (Yandex, Ahrefs, ...) are banned. |
| gpmotorz.com | 200 | Allows `/inventory/` and `/vehicles/`. Names ClaudeBot with crawl-delay 1. |
| markosianauto.com | 200 | Allows everything except `/wp-admin/`. |
| levelupcarsales.com | 200 | Allows everything except WooCommerce internals and `add-to-cart` URLs. |
| dubs-auto.com | 200 | Allows all. Same template as buysmartbuy. |
| axioauto.com | 403 | Akamai "Access Denied". Off-limits. |
| westautosales.com | 200 | Same template as gpmotorz: allows `/inventory/` and `/vehicles/`, crawl-delay 1 for named bots. |
| autosavvy.com | 403 | Blocked us. Off-limits. |
| automotivesalesandfinance.com | 404 | No robots.txt. Per the standard that means no restrictions, but check the site's terms. |
| webuyanycarusa.com | 200 | Allows all but `/secure/`, `/valuation/`. It is a car-buying service, so probably no inventory. |
| rogersautoutah.com | 403 | Cloudflare "Just a moment..." challenge. Off-limits. |

**Usable so far:** buysmartbuy, gpmotorz, markosianauto, levelupcarsales, dubs-auto, westautosales, and possibly automotivesalesandfinance (404 = no rules).
**Blocked (not retried, no workarounds):** kentson, autolocity, axioauto, autosavvy, rogersautoutah.

robots.txt only says what crawlers may fetch. It is not a check of each site's terms, and it doesn't show whether the inventory pages have JSON-LD. Those checks are still open in `dealers.md`.

---

## https://www.kentsoncarcompany.com/

- Status: **403**

```
(HTML page instead of robots.txt, title: 'Dealer Website')
```

## https://www.autolocitymotors.com/

- Status: **403**

```
(HTML page instead of robots.txt, title: 'Access Denied')
```

## https://www.buysmartbuy.com/

- Status: **200**

```
User-agent: *

Disallow:



User-agent: YandexBot

Disallow: /



User-agent: Baiduspider

Disallow: /



User-agent: Semalt

Disallow: /



User-agent: MJ12bot

Disallow: /



User-agent: turnitinbot

Disallow: /



User-agent: Autobot

Disallow: /



User-agent: AhrefsBot

Disallow: /



Sitemap: https://www.buysmartbuy.com/sitemap.xml
```

## https://www.gpmotorz.com/

- Status: **200**

```
User-agent: *
Disallow: /*highlights[]=
Allow: /
Allow: /llms.txt
Allow: /inventory.md
Allow: /inventory/
Allow: /vehicles/

User-agent: ClaudeBot
Crawl-delay: 1

User-agent: barkrowler
Crawl-delay: 1

Sitemap: https://www.gpmotorz.com/sitemap.xml
```

## https://markosianauto.com/

- Status: **200**

```
User-agent: *

Disallow: /wp-admin/

Allow: /wp-admin/admin-ajax.php



Sitemap: https://markosianauto.com/sitemap.xml

Sitemap: https://markosianauto.com/sitemap.rss
```

## https://levelupcarsales.com/

- Status: **200**

```
User-agent: *
Disallow: /wp-content/uploads/wc-logs/
Disallow: /wp-content/uploads/woocommerce_transient_files/
Disallow: /wp-content/uploads/woocommerce_uploads/
Disallow: /*?add-to-cart=
Disallow: /*?*add-to-cart=
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php

# START YOAST BLOCK
# ---------------------------
User-agent: *
Disallow:

Sitemap: https://levelupcarsales.com/sitemap_index.xml
# ---------------------------
# END YOAST BLOCK
```

## https://www.dubs-auto.com/

- Status: **200**

```
User-agent: *

Disallow:



User-agent: YandexBot

Disallow: /



User-agent: Baiduspider

Disallow: /



User-agent: Semalt

Disallow: /



User-agent: MJ12bot

Disallow: /



User-agent: turnitinbot

Disallow: /



User-agent: Autobot

Disallow: /



User-agent: AhrefsBot

Disallow: /



Sitemap: https://www.dubs-auto.com/sitemap.xml
```

## https://www.axioauto.com/

- Status: **403**

```
(HTML page instead of robots.txt, title: 'Access Denied')
```

## https://westautosales.com/

- Status: **200**

```
User-agent: *
Disallow: /*highlights[]=
Allow: /
Allow: /llms.txt
Allow: /inventory.md
Allow: /inventory/
Allow: /vehicles/

User-agent: ClaudeBot
Crawl-delay: 1

User-agent: barkrowler
Crawl-delay: 1

Sitemap: https://westautosales.com/sitemap.xml
```

## https://www.autosavvy.com/

- Status: **403**

```
(HTML page instead of robots.txt, title: 'Dealer Website')
```

## https://www.automotivesalesandfinance.com/

- Status: **404**

```
(HTML page instead of robots.txt, title: 'Error | AutoMotive Sales &amp; Finance')
```

## https://www.webuyanycarusa.com/

- Status: **200**

```
User-Agent: *
Allow: /
Disallow: /secure/
Disallow: /valuation/
Disallow: /_next/

Sitemap: https://www.webuyanycarusa.com/sitemap.xml
```

## https://www.rogersautoutah.com/

- Status: **403**

```
(HTML page instead of robots.txt, title: 'Just a moment...')
```
