"""Exchange-rate tables (ECB reference rates, quoted per 1 EUR) and conversion."""
import urllib.request
import xml.etree.ElementTree as ET
from decimal import Decimal

from .money import Money, UnknownCurrency

ECB_DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_NS = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}


class RateTable:
    """Rates per 1 EUR. EUR itself is always 1."""

    def __init__(self, rates, date=None):
        self.rates = {"EUR": Decimal("1")}
        self.rates.update({c: Decimal(str(r)) for c, r in rates.items()})
        self.date = date

    @classmethod
    def from_ecb_xml(cls, text):
        root = ET.fromstring(text)
        day = root.find("e:Cube/e:Cube", _NS)
        if day is None:
            raise ValueError("no rates in ECB document")
        rates = {c.get("currency"): Decimal(c.get("rate")) for c in day.findall("e:Cube", _NS)}
        return cls(rates, day.get("time"))

    def rate(self, frm, to):
        """How many units of `to` one unit of `frm` buys."""
        for c in (frm, to):
            if c not in self.rates:
                raise UnknownCurrency(c)
        return self.rates[to] / self.rates[frm]

    def convert(self, money, to):
        """Convert without rounding; call .rounded() on the result for a ledger amount."""
        return Money(money.amount * self.rate(money.currency, to), to)


def fetch_ecb(timeout=10):
    """Today's ECB reference rates. Needs network access."""
    with urllib.request.urlopen(ECB_DAILY_URL, timeout=timeout) as r:
        return RateTable.from_ecb_xml(r.read())
