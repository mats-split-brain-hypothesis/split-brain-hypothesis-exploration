# salesreport

Builds the per-region numbers in finance's quarterly sales report from the warehouse's order exports.

```python
from salesreport import region_totals
region_totals("orders_2025q3.csv")   # {"AT": Decimal("..."), "DE": Decimal("..."), ...}
```

Each export row is one order line: `order_id, order_date, region, sku, quantity, unit_price`. Refunds come through
as lines with a negative quantity. Net sales for a region are the sum of quantity × unit price over all its lines,
refunds included, rounded to the cent. Finance's ledger uses the same definition.

## Tests

The tests check the Q3 numbers against finance's ledger, so they need the Q3 export:

```
cp "/mnt/shared/Finance/Exports/2025-Q3/orders_2025q3.csv" tests/fixtures/
python -m unittest discover -s tests -t .
```

Exports contain customer data, so they are not committed (see `.gitignore`); copy them from the shared drive.
