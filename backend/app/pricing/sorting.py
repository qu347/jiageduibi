from collections.abc import Sequence

from app.schemas.offers import ComparableOffer


SHOP_RANK = {"self_operated": 0, "official_flagship": 1, "authorized": 2, "third_party": 3}


def offer_sort_key(offer: ComparableOffer) -> tuple[int, int, int, int, int]:
    missing = 1 if offer.comparable_price_cents is None else 0
    price = offer.comparable_price_cents if offer.comparable_price_cents is not None else 2**63 - 1
    captured_desc = -int(offer.captured_at.timestamp())
    return (missing, price, SHOP_RANK[offer.shop_type], captured_desc, offer.id)


def sort_offers(offers: Sequence[ComparableOffer]) -> list[ComparableOffer]:
    return sorted(offers, key=offer_sort_key)
