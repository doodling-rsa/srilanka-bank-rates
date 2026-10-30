"""Currencies tracked against LKR.

code -> name, symbol, how banks label it in rate tables, and a plausible LKR range
(guards against parsing the wrong row or column).
To add one: add an entry here plus its CBSL form values in cbsl.py.
"""

CURRENCIES = {
    "USD": {
        "name": "US Dollar", "symbol": "$",
        "label": r"^\W*(USD|US DOLLARS?|U\.?S\.? DOLLARS?|UNITED STATES DOLLARS?( \(USD\))?)$",
        "range": (150, 1000),
    },
    "GBP": {
        "name": "British Pound", "symbol": "£",
        "label": r"^\W*(GBP|STERLING POUNDS?|BRITISH POUNDS?( STERLING)?|GREAT BRITISH POUNDS?( \(GBP\))?)$",
        "range": (200, 1500),
    },
    "AUD": {
        "name": "Australian Dollar", "symbol": "A$",
        "label": r"^\W*(AUD|AUSTRALIAN DOLLARS?( \(AUD\))?)$",
        "range": (100, 700),
    },
    "SGD": {
        "name": "Singapore Dollar", "symbol": "S$",
        "label": r"^\W*(SGD|SINGAPORE DOLLARS?( \(SGD\))?)$",
        "range": (100, 700),
    },
}
