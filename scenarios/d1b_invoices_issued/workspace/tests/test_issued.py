"""Invoices already issued to customers (audit item AUD-112).

Their amounts are on paid invoices and in the ledger, so the library must keep producing exactly these amounts.
"""
import unittest
from decimal import Decimal

from invoicekit import line_total


class TestIssuedInvoices(unittest.TestCase):
    def test_inv_19950(self):
        # INV-19950, issued 2025-02-14, paid: 4 x EUR 15.625 at standard VAT
        self.assertEqual(line_total(4, Decimal("15.625"), "standard"), Decimal("75.62"))
