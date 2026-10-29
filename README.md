# USD/LKR Bank Rates

**Live site: https://doodling-rsa.github.io/usd-lkr-rates/**

A dashboard of daily USD → LKR buying and selling rates from Sri Lankan banks, compared against
Central Bank of Sri Lanka (CBSL) rates. It's a static site with a Python scraper, hosted free on GitHub Pages.

## Reading the rates

- **Buying rate**: what the bank **pays you** for 1 USD, e.g. when you convert dollars you hold or receive a remittance. Higher is better for you.
- **Selling rate**: what **you pay** the bank for 1 USD, e.g. for travel, tuition or imports. Lower is better for you.
- **Spread**: selling − buying, the bank's margin. Smaller is better.
- **TT (Telegraphic Transfer)** rates apply to account transfers and remittances; **cash notes** rates apply to physical currency.
- **CBSL average TT buy/sell** is the Central Bank's weighted average of licensed banks' rates; the **middle rate** is its indicative spot rate.
- **Buy vs CBSL / Sell vs CBSL**: how a bank compares with that average. Green means better for you.

## How data is collected

Some sources block requests from foreign data centres, including GitHub's servers, so collection runs in two places:

| Source | Rates | GitHub Actions | Local PC (Sri Lanka) |
|---|---|:-:|:-:|
| CBSL | Middle rate, avg TT buy/sell (history back to 2006) | ✗ blocked | ✓ |
| Bank of Ceylon, Commercial Bank, Nations Trust Bank | TT + cash | ✗ blocked | ✓ |
| People's, Seylan, NDB, NSB, Amana, DFCC | TT + cash | ✓ | ✓ |
| Sampath, HNB | TT | ✓ | ✓ |

- **GitHub Actions** ([update-rates.yml](.github/workflows/update-rates.yml)) scrapes at 10:00 and 15:00 Colombo time. It covers the 8 reachable banks even when the PC is off.
- **A Windows scheduled task** on a PC in Sri Lanka ([local-update.ps1](scripts/local-update.ps1)) runs at the same times and scrapes **all** sources. It then pushes `data/rates.json`, and that push redeploys the site.
- If a source can't be reached, its previous values are kept and the dashboard marks it **stale**. Both jobs merge into the same file, and a failure never overwrites good data.

Not included: **Pan Asia** and **Union Bank** (bot-protection), **Cargills** (PDF only), and HSBC, Standard Chartered, SDB and HDFC (not added yet).

## Project layout

```
scraper/          Python scrapers: banks.py (one function per bank), cbsl.py, run.py
data/rates.json   All history (CBSL backfilled; bank history grows daily from 29 Oct 2026)
index.html        Dashboard (vanilla JS + Chart.js, no build step)
assets/           app.js, style.css
scripts/          local-update.ps1 (scrape + push), install-task.ps1 (Windows scheduler)
.github/workflows/update-rates.yml   Scheduled scrape + deploy on every push
```

## Run locally

```bash
pip install -r requirements.txt
python scraper/run.py                      # today's rates + last 14 days of CBSL
python scraper/run.py --backfill-days 730  # pull 2 years of CBSL history
python -m http.server 8765                 # open http://localhost:8765
```

## Set up the local scheduled task (Windows)

Requirements: Python with the packages above, git, and a git login that can push to this repo.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-task.ps1
```

This registers the task **"USD-LKR rates update"** to run daily at 10:00 and 15:00. It runs while you're signed in, and a missed run (PC asleep or off) runs as soon as the PC is back.
The log is written to `logs/local-update.log`.

- Run once now: `Start-ScheduledTask -TaskName "USD-LKR rates update"`
- Remove: `Unregister-ScheduledTask -TaskName "USD-LKR rates update" -Confirm:$false`

The script only commits `data/rates.json`, so other work in progress in the folder is never included. If GitHub pushed at the same moment, it retries on top of GitHub's commit.

## Deploying your own copy

1. Push this folder to a GitHub repo on `main`.
2. Go to **Settings → Pages → Source: GitHub Actions**.
3. Go to **Actions → Update rates & deploy → Run workflow**. Optionally, set `backfill_days` to 730 for a longer CBSL history (this needs a Sri Lankan IP, so run it locally instead).

## Adding a bank

Add a function to `scraper/banks.py` that returns `_rates(tt_buy=..., tt_sell=..., notes_buy=..., notes_sell=...)`,
then register it in `BANKS`. `table_row(html, label_regex)` handles most HTML rate tables.
Every value is checked against a plausible range (150–1000 LKR), so if a site changes its layout the scraper reports an error instead of storing bad numbers.
