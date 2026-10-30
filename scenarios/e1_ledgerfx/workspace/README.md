# ledgerfx

Money, rounding and FX conversion helpers used by the finance tooling (invoice exports, the monthly FX report).

```python
from ledgerfx import Money, RateTable, fetch_ecb
table = fetch_ecb()                      # today's ECB reference rates (needs network)
table.convert(Money("100", "EUR"), "USD").rounded()
```

- Amounts are `Decimal`. Ledger amounts are rounded to the currency's minor units with banker's rounding
  (round half to even), as the ledger does; `quantize()` does this.
- `RateTable` holds rates per 1 EUR; cross rates go through EUR.

## Development

```
pip install -e .
python -m pytest
```

Releases are tagged `vX.Y.Z` and the tag must match `ledgerfx.__version__`.
