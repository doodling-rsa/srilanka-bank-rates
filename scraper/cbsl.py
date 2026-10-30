"""Central Bank of Sri Lanka benchmarks against LKR.

- Indicative (middle) rate:   cbsl_custom/exrates
- Weighted average TT buy/sell of licensed banks: cbsl_custom/exratestt
Both forms accept an arbitrary date range, so history can be backfilled.
"""
import re

from common import fetch, sane, soup

BASE = "https://www.cbsl.gov.lk/cbsl_custom"

# The two CBSL forms name currencies differently; values are the checkbox values.
MID_FORM = {
    "USD": "USD~US Dollar",
    "GBP": "GBP~Sterling Pound",
    "AUD": "AUD~Australian Dollar",
    "SGD": "SGD~Singapore Dollar",
}
TT_FORM = {
    "USD": "USD~United States Dollar",
    "GBP": "GBP~British Pound",
    "AUD": "AUD~Australian Dollar",
    "SGD": "SGD~Singapore Dollar",
}


def _post(path, form_value, start, end):
    form = {
        "lookupPage": "lookup_daily_exchange_rates.php",
        "startRange": "2006-11-11",
        "rangeType": "dates",
        "txtStart": start,
        "txtEnd": end,
        "chk_cur[]": form_value,
        "submit_button": "Submit",
    }
    html = fetch(f"{BASE}/{path}", method="POST", data=form, timeout=90).text
    rows = []
    for tr in soup(html).select("table tbody tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if cells and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[0]):
            rows.append(cells)
    return rows


def middle_rates(cur, start, end):
    """{date: mid}"""
    return {c[0]: sane(float(c[1]), cur) for c in _post("exrates/exrates_results.php", MID_FORM[cur], start, end)}


def tt_rates(cur, start, end):
    """{date: (buy, sell)}"""
    return {
        c[0]: (sane(float(c[1]), cur), sane(float(c[2]), cur))
        for c in _post("exratestt/exrates_resultstt.php", TT_FORM[cur], start, end)
    }


def history(cur, start, end):
    """List of {date, mid, tt_buy, tt_sell} sorted by date."""
    mids, tts = middle_rates(cur, start, end), tt_rates(cur, start, end)
    out = []
    for d in sorted(set(mids) | set(tts)):
        b, s = tts.get(d, (None, None))
        out.append({"date": d, "mid": mids.get(d), "tt_buy": b, "tt_sell": s})
    return out
