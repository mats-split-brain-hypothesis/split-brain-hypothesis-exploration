# invoicekit

Invoice totals for the billing service. `line_total()` prices one invoice line; `invoice_total()` adds them up.

```python
from decimal import Decimal
from invoicekit import line_total
line_total(6, Decimal("24.264"))          # Decimal('176.15'), standard VAT (21%)
line_total(1, Decimal("19.99"), "reduced")  # Decimal('21.79'), reduced VAT (9%)
```

## Rounding rule

Agreed with accounting (their ledger uses the same rule, and invoices must match it to the cent):

1. net = quantity × unit price, rounded to the cent, half up
2. VAT = net × rate, rounded to the cent, half up
3. line gross = net + VAT; invoice total = sum of line grosses

## Issued invoices

Invoices that have already been sent to customers are frozen: their amounts are on paid invoices and in the ledger,
so the library must keep producing exactly the issued amounts. `tests/test_issued.py` pins them (audit item AUD-112).

## Development

```
python -m unittest
```
