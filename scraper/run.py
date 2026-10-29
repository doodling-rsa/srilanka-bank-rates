"""Fetch today's rates from every bank + CBSL and merge them into data/rates.json.

Usage:
  python scraper/run.py                     # normal daily run
  python scraper/run.py --backfill-days 730 # also pull ~2 years of CBSL history
  python scraper/run.py --only hnb,boc      # debug a subset of banks
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

COLOMBO = timezone(timedelta(hours=5, minutes=30))
DATA = Path(__file__).resolve().parent.parent / "data" / "rates.json"
FIELDS = ("tt_buy", "tt_sell", "notes_buy", "notes_sell")


def load():
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    return {"cbsl": [], "rates": {}, "status": {}}


def upsert(rows, date, values):
    """rows: [[date, *values]] sorted by date; replace or insert this date's row."""
    rows[:] = [r for r in rows if r[0] != date] + [[date, *values]]
    rows.sort(key=lambda r: r[0])


def scrape_bank(bank_id):
    fn = BANKS[bank_id][3]
    try:
        return bank_id, fn(), None
    except Exception as e:  # keep going; one broken site must not stop the rest
        traceback.print_exc()
        return bank_id, None, f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill-days", type=int, default=14)
    ap.add_argument("--only", help="comma-separated bank ids")
    args = ap.parse_args()

    now = datetime.now(COLOMBO)
    today = now.strftime("%Y-%m-%d")
    db = load()

    # --- CBSL benchmarks (re-fetch a window so late publications get filled in)
    start = (now - timedelta(days=args.backfill_days)).strftime("%Y-%m-%d")
    try:
        for row in cbsl.history(start, today):
            upsert(db["cbsl"], row["date"], [row["mid"], row["tt_buy"], row["tt_sell"]])
        db["status"]["cbsl"] = {"ok": True, "checked": now.isoformat(timespec="seconds")}
        print(f"cbsl: {len(db['cbsl'])} days, latest {db['cbsl'][-1]}")
    except Exception as e:
        traceback.print_exc()
        db["status"]["cbsl"] = {"ok": False, "error": str(e), "checked": now.isoformat(timespec="seconds")}

    # --- Banks
    ids = args.only.split(",") if args.only else list(BANKS)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(scrape_bank, ids))

    failures = 0
    for bank_id, rates, err in results:
        st = {"checked": now.isoformat(timespec="seconds")}
        if rates:
            upsert(db["rates"].setdefault(bank_id, []), today, [rates[f] for f in FIELDS])
            st.update(ok=True)
            print(f"{bank_id:11s} TT {rates['tt_buy']} / {rates['tt_sell']}   notes {rates['notes_buy']} / {rates['notes_sell']}")
        else:
            failures += 1
            st.update(ok=False, error=err)
            print(f"{bank_id:11s} FAILED: {err}")
        db["status"][bank_id] = st

    db["banks"] = {k: {"name": v[0], "short": v[1], "url": v[2]} for k, v in BANKS.items()}
    db["fields"] = {"cbsl": ["date", "mid", "tt_buy", "tt_sell"], "rates": ["date", *FIELDS]}
    db["updated"] = now.isoformat(timespec="seconds")

    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(db, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {DATA} ({DATA.stat().st_size // 1024} KB); {failures} bank(s) failed")
    # Only fail the job if everything broke (likely a network problem).
    return 1 if failures == len(ids) else 0


if __name__ == "__main__":
    sys.exit(main())
