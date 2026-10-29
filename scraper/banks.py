"""Per-bank USD/LKR scrapers.

Each scraper returns a dict with any of: tt_buy, tt_sell, notes_buy, notes_sell.
  tt_*    = Telegraphic Transfer rates (remittances / account transfers)
  notes_* = Currency-note (cash) rates
"Buy" is what the bank pays you for 1 USD; "sell" is what you pay the bank for 1 USD.

To add a bank: write a function and register it in BANKS.
"""
import json
import re

from common import fetch, sane, table_row, to_float


def _rates(tt_buy=None, tt_sell=None, notes_buy=None, notes_sell=None):
    out = {
        "tt_buy": sane(tt_buy),
        "tt_sell": sane(tt_sell),
        "notes_buy": sane(notes_buy),
        "notes_sell": sane(notes_sell),
    }
    if not (out["tt_buy"] and out["tt_sell"]):
        raise ValueError(f"missing TT rates: {out}")
    return out


def _three_pair_table(url, label_re):
    """Common layout: Notes(buy,sell) | Drafts(buy,sell) | TT(buy,sell) [| extra]."""
    v = table_row(fetch(url).text, label_re)
    return _rates(tt_buy=v[4], tt_sell=v[5], notes_buy=v[0], notes_sell=v[1])


def commercial():
    return _three_pair_table("https://www.combank.lk/rates-tariff", r"^US DOLLARS?$")


def boc():
    return _three_pair_table("https://www.boc.lk/rates-tariff", r"^USD$")


def peoples():
    return _three_pair_table("https://www.peoplesbank.lk/exchange-rates/", r"^US Dollars?$")


def ndb():
    return _three_pair_table("https://www.ndbbank.com/rates/exchange-rates", r"^USD$")


def ntb():
    return _three_pair_table("https://www.nationstrust.com/foreign-exchange-rates", r"^\W*USD$")


def seylan():
    return _three_pair_table("https://www.seylan.lk/exchange-rates", r"^USD$")


def nsb():
    # Columns: Buying TT | Buying Currency | Selling TT | Selling Currency
    v = table_row(fetch("https://www.nsb.lk/rates-tarriffs/nsb-exchange-rates/").text,
                  r"United States Dollar")
    return _rates(tt_buy=v[0], notes_buy=v[1], tt_sell=v[2], notes_sell=v[3])


def amana():
    # Columns: Bank Buying | Bank Selling | Currency (notes) Selling
    v = table_row(fetch("https://www.amanabank.lk/business/treasury/exchange-rates.html").text,
                  r"^US Dollar$")
    return _rates(tt_buy=v[0], tt_sell=v[1], notes_sell=v[2])


def sampath():
    data = fetch("https://www.sampath.lk/api/exchange-rates").json()["data"]
    usd = next(d for d in data if d["CurrCode"] == "USD")
    return _rates(tt_buy=to_float(usd["TTBUY"]), tt_sell=to_float(usd["TTSEL"]))


def hnb():
    data = fetch(
        "https://venus.hnb.lk/api/get_exchange_rates_contents_web",
        headers={"Origin": "https://www.hnb.lk", "Referer": "https://www.hnb.lk/"},
    ).json()
    usd = next(d for d in data if d["currencyCode"] == "USD")
    return _rates(tt_buy=usd["buyingRate"], tt_sell=usd["sellingRate"])


def dfcc():
    # Rates are embedded as JSON in the Next.js payload of the homepage.
    html = fetch("https://www.dfcc.lk/").text.replace('\\"', '"')
    m = re.search(r'\{"Currency":"USD"[^{}]*\}', html)
    if not m:
        raise ValueError("DFCC USD rate block not found")
    d = json.loads(m.group(0))
    return _rates(
        tt_buy=to_float(d.get("TT BUY")), tt_sell=to_float(d.get("TT SELL")),
        notes_buy=to_float(d.get("CCY BUY")), notes_sell=to_float(d.get("CCY SELL")),
    )


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
