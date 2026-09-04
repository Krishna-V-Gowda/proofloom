from datetime import datetime, timezone
import pytest

from proofloom.domain import Payment, money_inr, sum_paise


def test_money_formatter_and_integer_contract():
    assert money_inr(137) == "₹1.37"
    assert money_inr(9_898_464) == "₹98,984.64"
    assert sum_paise([100, 37]) == 137
    with pytest.raises(TypeError):
        sum_paise([1.5])


def test_payment_rejects_financially_invalid_fields():
    with pytest.raises(ValueError):
        Payment("pay", "set", 100, 90, 20, datetime.now(timezone.utc))
    with pytest.raises(ValueError):
        Payment("pay", "set", 100, 0, 0, datetime.now())
