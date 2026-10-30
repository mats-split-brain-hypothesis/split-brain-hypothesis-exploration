from decimal import Decimal

import pytest


@pytest.fixture
def sample_invoice():
    return [
        {"quantity": 6, "unit_price": Decimal("24.264")},
        {"quantity": 2, "unit_price": Decimal("2.463")},
        {"quantity": 1, "unit_price": Decimal("19.99"), "vat": "reduced"},
    ]
