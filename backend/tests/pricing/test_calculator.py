import pytest

from app.pricing.calculator import calculate_price
from app.schemas.offers import OfferPriceInput


def test_confirmed_discounts_and_subsidy_enter_comparable_price() -> None:
    result = calculate_price(
        OfferPriceInput(
            sale_price_cents=600000,
            merchant_discount_cents=20000,
            platform_coupon_cents=10000,
            subsidy_amount_cents=50000,
            subsidy_status="confirmed",
            shipping_fee_cents=0,
            installation_fee_cents=0,
        )
    )

    assert result.ordinary_price_cents == 570000
    assert result.confirmed_final_price_cents == 520000
    assert result.comparable_price_cents == 520000


def test_estimated_subsidy_never_changes_default_comparable_price() -> None:
    result = calculate_price(
        OfferPriceInput(
            sale_price_cents=600000,
            subsidy_amount_cents=50000,
            subsidy_status="estimated",
        )
    )

    assert result.comparable_price_cents == 600000
    assert result.estimated_final_price_cents == 550000


def test_rejects_negative_total() -> None:
    with pytest.raises(ValueError, match="价格计算结果不能为负数"):
        calculate_price(
            OfferPriceInput(
                sale_price_cents=10000,
                merchant_discount_cents=20000,
            )
        )
