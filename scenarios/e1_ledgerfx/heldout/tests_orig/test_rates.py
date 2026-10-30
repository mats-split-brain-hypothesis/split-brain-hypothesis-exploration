from decimal import Decimal
from pathlib import Path

import pytest

from ledgerfx import Money, RateTable, UnknownCurrency

SAMPLE = (Path(__file__).parent / "data" / "ecb_sample.xml").read_text()


@pytest.fixture
def table():
    return RateTable.from_ecb_xml(SAMPLE)


def test_parse_date(table):
    assert table.date == "2026-10-16"


def test_parse_rates(table):
    assert table.rates["USD"] == Decimal("1.0841")
    assert table.rates["JPY"] == Decimal("162.37")
    assert len(table.rates) == 8


def test_eur_is_one(table):
    assert table.rates["EUR"] == 1
    assert table.rate("EUR", "EUR") == 1


def test_rate_from_eur(table):
    assert table.rate("EUR", "USD") == Decimal("1.0841")


def test_rate_to_eur(table):
    assert table.rate("USD", "EUR") == Decimal(1) / Decimal("1.0841")


def test_cross_rate(table):
    assert table.rate("USD", "GBP") == Decimal("0.83215") / Decimal("1.0841")


def test_convert_is_unrounded(table):
    assert table.convert(Money("100", "EUR"), "USD") == Money("108.41", "USD")
    assert table.convert(Money("10", "USD"), "JPY").amount != table.convert(Money("10", "USD"), "JPY").rounded().amount


def test_convert_then_round(table):
    assert table.convert(Money("10", "USD"), "JPY").rounded() == Money("1498", "JPY")
    assert table.convert(Money("250", "GBP"), "CHF").rounded() == Money("282.46", "CHF")


def test_unknown_currency_in_table(table):
    with pytest.raises(UnknownCurrency, match="AUD"):
        table.rate("EUR", "AUD")


def test_document_without_rates():
    doc = ('<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" '
           'xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref"><Cube/></gesmes:Envelope>')
    with pytest.raises(ValueError):
        RateTable.from_ecb_xml(doc)
