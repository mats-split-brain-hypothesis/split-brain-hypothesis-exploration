from pathlib import Path

from ledgerfx import Money, RateTable, to_reporting_currency, totals_by_currency

SAMPLE = (Path(__file__).parent / "data" / "ecb_sample.xml").read_text()


def test_totals_by_currency_sums_and_sorts():
    items = [Money("1.10", "USD"), Money("2", "EUR"), Money("3.05", "USD")]
    assert totals_by_currency(items) == [Money("2.00", "EUR"), Money("4.15", "USD")]


def test_totals_round_once():
    assert totals_by_currency([Money("0.005", "EUR")] * 3) == [Money("0.02", "EUR")]


def test_totals_empty():
    assert totals_by_currency([]) == []


def test_reporting_currency_eur():
    table = RateTable.from_ecb_xml(SAMPLE)
    assert to_reporting_currency([Money("10", "USD"), Money("5", "EUR")], table) == Money("14.22", "EUR")


def test_reporting_currency_usd():
    table = RateTable.from_ecb_xml(SAMPLE)
    assert to_reporting_currency([Money("1000", "JPY"), Money("20", "GBP")], table, "USD") == Money("32.73", "USD")
