# LKR Bank Exchange Rates

**Live site: https://doodling-rsa.github.io/srilanka-bank-rates/**

A dashboard of daily **USD, GBP, AUD and SGD → LKR** buying and selling rates from Sri Lankan banks,
compared against Central Bank of Sri Lanka (CBSL) rates. It's a static site with a Python scraper, hosted free on GitHub Pages.

Pick a currency from the bar at the top; each tab also shows today's CBSL middle rate. Links keep your selection,
e.g. `…/srilanka-bank-rates/#cur=GBP&bank=hnb`.

## Reading the rates

- **Buying rate**: what the bank **pays you** for 1 unit of foreign currency, e.g. when you convert money you hold or receive a remittance. Higher is better for you.
- **Selling rate**: what **you pay** the bank for 1 unit, e.g. for travel, tuition or imports. Lower is better for you.
- **Spread**: selling − buying, the bank's margin. Smaller is better.
- **TT (Telegraphic Transfer)** rates apply to account transfers and remittances; **cash** rates apply to physical currency notes.
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

All banks quote all four currencies, except **NSB, which doesn't publish SGD**.

- **GitHub Actions** ([update-rates.yml](.github/workflows/update-rates.yml)) scrapes at 10:00 and 15:00 Colombo time. It covers the 8 reachable banks even when the PC is off.
- **A Windows scheduled task** on a PC in Sri Lanka ([local-update.ps1](scripts/local-update.ps1)) runs at the same times and scrapes **all** sources. It then pushes `data/rates.json`, and that push redeploys the site.
- If a source can't be reached, its previous values are kept and the dashboard marks it **stale**. Both jobs merge into the same file, and a failure never overwrites good data.

Not included: **Pan Asia** and **Union Bank** (bot-protection), **Cargills** (PDF only), and HSBC, Standard Chartered, SDB and HDFC (not added yet).

## Project layout

```
scraper/          currencies.py (tracked currencies), banks.py (one function per bank), cbsl.py, run.py
data/rates.json   All history (CBSL backfilled; bank history grows daily from 29 Oct 2026 for USD, 30 Oct 2026 for others)
index.html        Dashboard (vanilla JS + Chart.js, no build step)
assets/           app.js, style.css
scripts/          local-update.ps1 (scrape + push), install-task.ps1 (Windows scheduler)
.github/workflows/update-rates.yml   Scheduled scrape + deploy on every push
```

`data/rates.json` (version 2) stores everything per currency:

```
cbsl:  { "USD": [[date, mid, tt_buy, tt_sell], ...], "GBP": [...], ... }
rates: { "boc": { "USD": [[date, tt_buy, tt_sell, cash_buy, cash_sell], ...], ... }, ... }
```

Older USD-only files are migrated automatically the first time the scraper runs.

## Run locally

```bash
pip install -r requirements.txt
python scraper/run.py                      # today's rates + last 14 days of CBSL
python scraper/run.py --backfill-days 730  # re-pull 2 years of CBSL history
python -m http.server 8765                 # open http://localhost:8765
```

A currency with no CBSL history yet (for example, one you just added) gets about 3 years backfilled automatically.

## Set up the local scheduled task (Windows)

Requirements: Python with the packages above, git, and a git login that can push to this repo.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-task.ps1
```

This registers the task **"USD-LKR rates update"** to run daily at 10:00 and 15:00. It runs while you're signed in, and a missed run (PC asleep or off) runs as soon as the PC is back.
The log is written to `logs/local-update.log`.

- Run once now: `Start-ScheduledTask -TaskName "USD-LKR rates update"`
- Remove: `Unregister-ScheduledTask -TaskName "USD-LKR rates update" -Confirm:$false`

The script only commits `data/rates.json`, so other work in progress in the folder is never included. It only runs while the folder is on `main` (a run on any other branch is skipped and logged).
If GitHub pushed at the same moment, it retries on top of GitHub's commit.

## Deploying your own copy

1. Push this folder to a GitHub repo on `main`.
2. Go to **Settings → Pages → Source: GitHub Actions**.
3. Go to **Actions → Update rates & deploy → Run workflow**. Optionally, set `backfill_days` to 730 for a longer CBSL history (this needs a Sri Lankan IP, so run it locally instead).

## Adding a currency

1. Add it to `scraper/currencies.py`: name, symbol, a regex for how banks label it, and a plausible LKR range.
2. Add its CBSL form values to `MID_FORM` and `TT_FORM` in `scraper/cbsl.py` (copy them from the checkboxes on the CBSL rate pages).

The dashboard picks up new currencies from the data file; no frontend change is needed.

## Adding a bank

Add a function to `scraper/banks.py` and register it in `BANKS`. For an HTML rate table, `_table_bank(url, cols)` does
the work: `cols` maps each rate to its column index after the currency label. API-based banks use `_each_currency`.
Every value is checked against the currency's plausible range, so if a site changes its layout the scraper reports an error instead of storing bad numbers.
