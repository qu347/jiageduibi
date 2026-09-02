from app.schemas.offers import OfferPriceInput, PriceBreakdown


def calculate_price(value: OfferPriceInput) -> PriceBreakdown:
    ordinary = value.sale_price_cents - value.merchant_discount_cents - value.platform_coupon_cents
    ordinary += value.shipping_fee_cents + value.installation_fee_cents
    if ordinary < 0:
        raise ValueError("价格计算结果不能为负数")

    confirmed = ordinary
    estimated = None
    if value.subsidy_status == "confirmed":
        confirmed -= value.subsidy_amount_cents
    elif value.subsidy_status == "estimated":
        estimated = ordinary - value.subsidy_amount_cents

    if confirmed < 0 or (estimated is not None and estimated < 0):
        raise ValueError("价格计算结果不能为负数")

    return PriceBreakdown(
        ordinary_price_cents=ordinary,
        confirmed_final_price_cents=confirmed,
        estimated_final_price_cents=estimated,
        comparable_price_cents=confirmed,
        conditions=value.conditions,
    )
