from datetime import UTC, datetime

import pytest

from app.automation.contracts import VerifiedOffer
from app.price_sheets.pricing import calculate_price_sheet_offer


def offer(**changes: object) -> VerifiedOffer:
    values = {
        'platform_sku_id': '1',
        'title': 'Apple iPhone 17 256GB 黑色 全新国行',
        'product_url': 'https://item.jd.com/1.html',
        'shop_name': '京东自营',
        'platform_shop_id': 'self',
        'shop_type': 'self_operated',
        'listed_price_cents': 600_000,
        'sale_price_cents': 590_000,
        'merchant_discount_cents': 10_000,
        'platform_coupon_cents': 30_000,
        'member_discount_cents': 50_000,
        'payment_discount_cents': 20_000,
        'subsidy_amount_cents': 50_000,
        'subsidy_status': 'confirmed',
        'shipping_fee_cents': 1_000,
        'installation_fee_cents': 0,
        'conditional_price_cents': 400_000,
        'stock_status': 'in_stock',
        'captured_at': datetime(2026, 9, 3, tzinfo=UTC),
        'sale_price_includes_coupon': False,
        'sale_price_includes_subsidy': False,
    }
    values.update(changes)
    return VerifiedOffer(**values)


def test_calculates_only_ordinary_coupon_confirmed_subsidy_and_shipping() -> None:
    result = calculate_price_sheet_offer(offer())

    assert result.trusted_price_cents == 501_000
    assert result.applied_coupon_cents == 40_000
    assert result.applied_subsidy_cents == 50_000


def test_does_not_double_subtract_included_coupon_or_subsidy() -> None:
    result = calculate_price_sheet_offer(offer(
        sale_price_cents=510_000,
        sale_price_includes_coupon=True,
        sale_price_includes_subsidy=True,
    ))

    assert result.trusted_price_cents == 511_000
    assert result.applied_coupon_cents == 0
    assert result.applied_subsidy_cents == 0


def test_does_not_subtract_estimated_subsidy_or_conditional_discounts() -> None:
    result = calculate_price_sheet_offer(offer(subsidy_status='estimated'))

    assert result.trusted_price_cents == 551_000


def test_rejects_non_positive_result() -> None:
    with pytest.raises(ValueError, match='可信到手价'):
        calculate_price_sheet_offer(offer(
            sale_price_cents=10_000,
            merchant_discount_cents=20_000,
            platform_coupon_cents=0,
            subsidy_amount_cents=0,
        ))
