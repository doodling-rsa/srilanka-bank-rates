"""Per-bank scrapers for every currency in currencies.py.

Each scraper returns ({currency: rates}, {currency: error}) where rates has any of:
  tt_buy, tt_sell, notes_buy, notes_sell
  tt_*    = Telegraphic Transfer rates (remittances / account transfers)
  notes_* = Currency-note (cash) rates
"Buy" is what the bank pays you for 1 unit; "sell" is what you pay the bank for 1 unit.
A bank that doesn't quote a currency simply has it in the error dict.

To add a bank: write a function and register it in BANKS.
"""
import json
import re

from common import fetch, find_row, sane, table_rows, to_float
from currencies import CURRENCIES


def _rates(cur, tt_buy=None, tt_sell=None, notes_buy=None, notes_sell=None):
    out = {
        "tt_buy": sane(tt_buy, cur),
        "tt_sell": sane(tt_sell, cur),
        "notes_buy": sane(notes_buy, cur),
        "notes_sell": sane(notes_sell, cur),
    }
    if not (out["tt_buy"] and out["tt_sell"]):
        raise ValueError(f"missing TT rates: {out}")
    return out


def _each_currency(extract):
    """Run extract(cur) for every currency; one missing currency doesn't fail the bank."""
    out, errors = {}, {}
    for cur in CURRENCIES:
        try:
            out[cur] = extract(cur)
        except Exception as e:
            errors[cur] = f"{type(e).__name__}: {e}"
    if not out:
        raise ValueError(f"no currencies parsed: {errors}")
    return out, errors


def _table_bank(url, cols):
    """HTML rate table. cols maps rate field -> column index after the currency label."""
    rows = table_rows(fetch(url).text)

    def extract(cur):
        v = find_row(rows, CURRENCIES[cur]["label"])
        return _rates(cur, **{f: (v[i] if i < len(v) else None) for f, i in cols.items()})
    return _each_currency(extract)


# Common layout: Notes(buy,sell) | Drafts(buy,sell) | TT(buy,sell) [| extra]
THREE_PAIR = {"notes_buy": 0, "notes_sell": 1, "tt_buy": 4, "tt_sell": 5}


def commercial():
    return _table_bank("https://www.combank.lk/rates-tariff", THREE_PAIR)


def boc():
    return _table_bank("https://www.boc.lk/rates-tariff", THREE_PAIR)


def peoples():
    return _table_bank("https://www.peoplesbank.lk/exchange-rates/", THREE_PAIR)


def ndb():
    return _table_bank("https://www.ndbbank.com/rates/exchange-rates", THREE_PAIR)


def ntb():
    return _table_bank("https://www.nationstrust.com/foreign-exchange-rates", THREE_PAIR)


def seylan():
    return _table_bank("https://www.seylan.lk/exchange-rates", THREE_PAIR)


def nsb():
    # Columns: Buying TT | Buying Currency | Selling TT | Selling Currency
    return _table_bank("https://www.nsb.lk/rates-tarriffs/nsb-exchange-rates/",
                       {"tt_buy": 0, "notes_buy": 1, "tt_sell": 2, "notes_sell": 3})


def amana():
    # Columns: Bank Buying | Bank Selling | Currency (notes) Selling
    return _table_bank("https://www.amanabank.lk/business/treasury/exchange-rates.html",
                       {"tt_buy": 0, "tt_sell": 1, "notes_sell": 2})


def sampath():
    data = {d["CurrCode"]: d for d in fetch("https://www.sampath.lk/api/exchange-rates").json()["data"]}
    return _each_currency(lambda cur: _rates(
        cur, tt_buy=to_float(data[cur]["TTBUY"]), tt_sell=to_float(data[cur]["TTSEL"])))


def hnb():
    data = {d["currencyCode"]: d for d in fetch(
        "https://venus.hnb.lk/api/get_exchange_rates_contents_web",
        headers={"Origin": "https://www.hnb.lk", "Referer": "https://www.hnb.lk/"},
    ).json()}
    return _each_currency(lambda cur: _rates(
        cur, tt_buy=data[cur]["buyingRate"], tt_sell=data[cur]["sellingRate"]))


def dfcc():
    # Rates are embedded as JSON in the Next.js payload of the homepage.
    html = fetch("https://www.dfcc.lk/").text.replace('\\"', '"')

    def extract(cur):
        m = re.search(r'\{"Currency":"%s"[^{}]*\}' % cur, html)
        if not m:
            raise ValueError(f"DFCC {cur} rate block not found")
        d = json.loads(m.group(0))
        return _rates(
            cur,
            tt_buy=to_float(d.get("TT BUY")), tt_sell=to_float(d.get("TT SELL")),
            notes_buy=to_float(d.get("CCY BUY")), notes_sell=to_float(d.get("CCY SELL")),
        )
    return _each_currency(extract)


# id -> (display name, short name, public rates page, scraper)
BANKS = {
    "boc":        ("Bank of Ceylon",            "BOC",      "https://www.boc.lk/rates-tariff#exchange-rates", boc),
    "peoples":    ("People's Bank",             "People's", "https://www.peoplesbank.lk/exchange-rates/", peoples),
    "commercial": ("Commercial Bank",           "ComBank",  "https://www.combank.lk/rates-tariff#exchange-rates", commercial),
    "hnb":        ("Hatton National Bank",      "HNB",      "https://www.hnb.lk/rates", hnb),
    "sampath":    ("Sampath Bank",              "Sampath",  "https://www.sampath.lk/rates-and-charges?activeTab=exchange-rates", sampath),
    "seylan":     ("Seylan Bank",               "Seylan",   "https://www.seylan.lk/exchange-rates", seylan),
    "ndb":        ("National Development Bank", "NDB",      "https://www.ndbbank.com/rates/exchange-rates", ndb),
    "ntb":        ("Nations Trust Bank",        "NTB",      "https://www.nationstrust.com/foreign-exchange-rates", ntb),
    "dfcc":       ("DFCC Bank",                 "DFCC",     "https://www.dfcc.lk/", dfcc),
    "nsb":        ("National Savings Bank",     "NSB",      "https://www.nsb.lk/rates-tarriffs/nsb-exchange-rates/", nsb),
    "amana":      ("Amana Bank",                "Amana",    "https://www.amanabank.lk/business/treasury/exchange-rates.html", amana),
}
