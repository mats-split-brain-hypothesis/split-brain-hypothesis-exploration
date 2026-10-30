"""Contract checks against the live ECB feed, so a change in its format shows up here before it breaks the
monthly FX report. These need network access."""
import urllib.request

from ledgerfx import RateTable

FEED = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


def _live_table():
    with urllib.request.urlopen(FEED, timeout=10) as r:
        return RateTable.from_ecb_xml(r.read())


def test_live_feed_parses():
    table = _live_table()
    assert table.date
    assert table.rates["USD"] > 0


def test_live_feed_has_report_currencies():
    table = _live_table()
    missing = [c for c in ("USD", "JPY", "GBP", "CHF", "SEK", "HUF", "RON") if c not in table.rates]
    assert not missing, missing
