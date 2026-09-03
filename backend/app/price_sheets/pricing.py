from dataclasses import dataclass

from app.automation.contracts import VerifiedOffer


@dataclass(frozen=True, slots=True)
class PriceSheetCalculatedPrice:
    trusted_price_cents: int
    applied_coupon_cents: int
    applied_subsidy_cents: int
    shipping_fee_cents: int


def calculate_price_sheet_offer(offer: VerifiedOffer) -> PriceSheetCalculatedPrice:
    coupon = 0
    if not offer.sale_price_includes_coupon:
        coupon = offer.merchant_discount_cents + offer.platform_coupon_cents
    subsidy = 0
    if offer.subsidy_status == "confirmed" and not offer.sale_price_includes_subsidy:
        subsidy = offer.subsidy_amount_cents
    trusted = offer.sale_price_cents - coupon - subsidy + offer.shipping_fee_cents
    if trusted <= 0:
        raise ValueError("可信到手价必须大于零")
    return PriceSheetCalculatedPrice(
        trusted_price_cents=trusted,
        applied_coupon_cents=coupon,
        applied_subsidy_cents=subsidy,
        shipping_fee_cents=offer.shipping_fee_cents,
    )
