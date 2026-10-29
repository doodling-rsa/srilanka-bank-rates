# USD/LKR Bank Rates

A dashboard of daily USD → LKR buying and selling rates from Sri Lankan banks, compared against
Central Bank of Sri Lanka (CBSL) rates. It's a static site with a Python scraper, and runs free on
GitHub Actions + GitHub Pages.

```
scraper/        Python scrapers (one function per bank + CBSL) → data/rates.json
data/rates.json All history (CBSL backfilled; bank history grows daily)
index.html      Dashboard (vanilla JS + Chart.js, no build step)
assets/         app.js, style.css
.github/workflows/update-rates.yml   Scrape 2×/day, commit data, deploy to Pages
```

## What's collected

| Source | Rates | How |
|---|---|---|
| CBSL | Middle (indicative) rate, weighted-avg TT buy/sell | Form POST; history back to 2006 |
| BOC, People's, Commercial, Seylan, NDB, NTB, NSB, Amana | TT + cash notes | HTML table |
| Sampath, HNB | TT | JSON API |
| DFCC | TT + cash notes | JSON embedded in homepage |

Not included: **Pan Asia** and **Union Bank** sit behind bot-protection (Sucuri / Incapsula), and
**Cargills** only publishes a PDF (its rates API is down).
Also not included yet: HSBC, Standard Chartered, SDB, HDFC.

## Run locally

```bash
pip install -r requirements.txt
python scraper/run.py                      # today's rates + last 14 days of CBSL
python scraper/run.py --backfill-days 730  # pull 2 years of CBSL history
python -m http.server 8765                 # open http://localhost:8765
```

## Deploy (GitHub Pages)

1. Create a GitHub repo and push this folder to `main`.
2. Repo **Settings → Pages → Source: GitHub Actions**.
3. **Actions → Update rates & deploy → Run workflow** once. After that it runs every day at 10:00 and 15:00 Colombo time.

## Adding a bank

Add a function in `scraper/banks.py` that returns `_rates(tt_buy=..., tt_sell=..., notes_buy=..., notes_sell=...)`
and register it in `BANKS`. `table_row(html, label_regex)` handles most HTML rate tables.
Every value goes through a sanity check (150–1000 LKR), so if a site changes its layout the run fails loudly
and doesn't store bad numbers. If one bank fails, the others still update, and the dashboard marks that bank as *stale*.
