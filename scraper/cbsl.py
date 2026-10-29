"""Central Bank of Sri Lanka USD/LKR benchmarks.

- Indicative (middle) rate:   cbsl_custom/exrates
- Weighted average TT buy/sell of licensed banks: cbsl_custom/exratestt
Both forms accept an arbitrary date range, so history can be backfilled.
"""
import re

from common import fetch, sane, soup

BASE = "https://www.cbsl.gov.lk/cbsl_custom"


def _post(path, cur, start, end):
    form = {
        "lookupPage": "lookup_daily_exchange_rates.php",
        "startRange": "2006-11-11",
        "rangeType": "dates",
        "txtStart": start,
        "txtEnd": end,
        "chk_cur[]": cur,
        "submit_button": "Submit",
    }
    html = fetch(f"{BASE}/{path}", method="POST", data=form, timeout=90).text
    rows = []
    for tr in soup(html).select("table tbody tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if cells and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[0]):
            rows.append(cells)
    return rows


def middle_rates(start, end):
    """{date: mid}"""
    return {c[0]: sane(float(c[1])) for c in _post("exrates/exrates_results.php", "USD~US Dollar", start, end)}


def tt_rates(start, end):
    """{date: (buy, sell)}"""
    return {
        c[0]: (sane(float(c[1])), sane(float(c[2])))
        for c in _post("exratestt/exrates_resultstt.php", "USD~United States Dollar", start, end)
    }


def history(start, end):
    """List of {date, mid, tt_buy, tt_sell} sorted by date."""
    mids, tts = middle_rates(start, end), tt_rates(start, end)
    out = []
    for d in sorted(set(mids) | set(tts)):
        b, s = tts.get(d, (None, None))
        out.append({"date": d, "mid": mids.get(d), "tt_buy": b, "tt_sell": s})
    return out
