"""Shared HTTP + parsing helpers for the scrapers."""
import re
import time

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def fetch(url, method="GET", retries=3, timeout=40, **kw):
    """Fetch a URL with simple retry/backoff. Returns the Response."""
    last = None
    for attempt in range(retries):
        try:
            r = _session.request(method, url, timeout=timeout, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def to_float(s):
    """'1,100.52' -> 1100.52 ; '-', '', 0 -> None."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s) or None
    s = s.replace(",", "").replace("\xa0", " ").strip()
    m = re.fullmatch(r"-?\d+(\.\d+)?", s)
    if not m:
        return None
    v = float(s)
    return v or None


def soup(html):
    # Drop HTML comments first: some banks leave stale rates commented out in the table.
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    return BeautifulSoup(html, "html.parser")


def table_row(html, label_re):
    """Find the first <tr> whose label cells match label_re.

    Returns the list of rate cells after the label as floats (None for '-' / blanks),
    preserving column positions.
    """
    pat = re.compile(label_re, re.I)
    for tr in soup(html).find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if not cells:
            continue
        label_idx = [i for i, c in enumerate(cells) if re.search(r"[A-Za-z]", c)]
        if not any(pat.search(cells[i]) for i in label_idx):
            continue
        # Rates are the cells after the last label cell (skips leading flag/icon cells).
        vals = [to_float(c) for c in cells[label_idx[-1] + 1:]]
        if any(vals):
            return vals
    raise ValueError(f"row matching {label_re!r} not found")


def sane(v, lo=150, hi=1000):
    """Guard against parsing the wrong column: USD/LKR must be in a plausible band."""
    if v is None:
        return None
    if not lo <= v <= hi:
        raise ValueError(f"implausible USD/LKR rate {v}")
    return round(v, 4)
