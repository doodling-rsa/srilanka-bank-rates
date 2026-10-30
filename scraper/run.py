"""Fetch today's rates from every bank + CBSL and merge them into data/rates.json.

Usage:
  python scraper/run.py                     # normal daily run
  python scraper/run.py --backfill-days 730 # also re-pull ~2 years of CBSL history
  python scraper/run.py --only hnb,boc      # debug a subset of banks

data/rates.json (version 2):
  cbsl:  {currency: [[date, mid, tt_buy, tt_sell], ...]}
  rates: {bank: {currency: [[date, tt_buy, tt_sell, notes_buy, notes_sell], ...]}}
"""
import argparse
import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cbsl
from banks import BANKS
from currencies import CURRENCIES

COLOMBO = timezone(timedelta(hours=5, minutes=30))
DATA = Path(__file__).resolve().parent.parent / "data" / "rates.json"
FIELDS = ("tt_buy", "tt_sell", "notes_buy", "notes_sell")
# A currency with no CBSL history yet (e.g. newly added) gets this much backfilled.
NEW_CURRENCY_BACKFILL_DAYS = 1095


def load():
    if not DATA.exists():
        return {"version": 2, "cbsl": {}, "rates": {}, "status": {}}
    db = json.loads(DATA.read_text(encoding="utf-8"))
    if db.get("version") != 2:
        # v1 was USD-only: cbsl was a list, rates[bank] was a list.
        db["cbsl"] = {"USD": db.get("cbsl", [])}
        db["rates"] = {bank: {"USD": rows} for bank, rows in db.get("rates", {}).items()}
        db["version"] = 2
    return db


def upsert(rows, date, values):
    """rows: [[date, *values]] sorted by date; replace or insert this date's row."""
    rows[:] = [r for r in rows if r[0] != date] + [[date, *values]]
    rows.sort(key=lambda r: r[0])


def scrape_bank(bank_id):
    fn = BANKS[bank_id][3]
    try:
        rates, missing = fn()
        return bank_id, rates, missing, None
    except Exception as e:  # keep going; one broken site must not stop the rest
        traceback.print_exc()
        return bank_id, None, {}, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill-days", type=int, default=14)
    ap.add_argument("--only", help="comma-separated bank ids")
    args = ap.parse_args()

    now = datetime.now(COLOMBO)
    stamp = now.isoformat(timespec="seconds")
    today = now.strftime("%Y-%m-%d")
    db = load()

    # --- CBSL benchmarks (re-fetch a window so late publications get filled in)
    cbsl_errors = {}
    for cur in CURRENCIES:
        rows = db["cbsl"].setdefault(cur, [])
        days = args.backfill_days if len(rows) > 30 else max(args.backfill_days, NEW_CURRENCY_BACKFILL_DAYS)
        start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            for row in cbsl.history(cur, start, today):
                upsert(rows, row["date"], [row["mid"], row["tt_buy"], row["tt_sell"]])
            print(f"cbsl {cur}: {len(rows)} days, latest {rows[-1] if rows else None}")
        except Exception as e:
            traceback.print_exc()
            cbsl_errors[cur] = f"{type(e).__name__}: {e}"
            print(f"cbsl {cur}: FAILED {e}")
    db["status"]["cbsl"] = {"ok": not cbsl_errors, "checked": stamp, **({"errors": cbsl_errors} if cbsl_errors else {})}

    # --- Banks
    ids = args.only.split(",") if args.only else list(BANKS)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(scrape_bank, ids))

    failures = 0
    for bank_id, rates, missing, err in results:
        st = {"checked": stamp}
        if rates:
            bank = db["rates"].setdefault(bank_id, {})
            for cur, r in rates.items():
                upsert(bank.setdefault(cur, []), today, [r[f] for f in FIELDS])
            st.update(ok=True, currencies=sorted(rates), **({"missing": missing} if missing else {}))
            usd = rates.get("USD")
            print(f"{bank_id:11s} TT {' '.join(sorted(rates))}" + (f"  USD {usd['tt_buy']} / {usd['tt_sell']}" if usd else "")
                  + (f"  (no {', '.join(missing)})" if missing else ""))
        else:
            failures += 1
            st.update(ok=False, error=err)
            print(f"{bank_id:11s} FAILED: {err}")
        db["status"][bank_id] = st

    db["banks"] = {k: {"name": v[0], "short": v[1], "url": v[2]} for k, v in BANKS.items()}
    db["currencies"] = {k: {"name": v["name"], "symbol": v["symbol"]} for k, v in CURRENCIES.items()}
    db["fields"] = {"cbsl": ["date", "mid", "tt_buy", "tt_sell"], "rates": ["date", *FIELDS]}
    db["updated"] = stamp

    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(db, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {DATA} ({DATA.stat().st_size // 1024} KB); {failures} bank(s) failed")
    # Only fail the job if everything broke (likely a network problem).
    return 1 if failures == len(ids) else 0


if __name__ == "__main__":
    sys.exit(main())
