from datetime import UTC, datetime, timedelta

from app.pricing.sorting import sort_offers
from app.schemas.offers import ComparableOffer


def test_sorts_by_price_then_shop_then_recent_capture() -> None:
    now = datetime.now(UTC)
    offers = [
        ComparableOffer(id=4, comparable_price_cents=None, shop_type="self_operated", captured_at=now),
        ComparableOffer(id=3, comparable_price_cents=500000, shop_type="third_party", captured_at=now),
        ComparableOffer(
            id=2,
            comparable_price_cents=500000,
            shop_type="self_operated",
            captured_at=now - timedelta(minutes=1),
        ),
        ComparableOffer(id=1, comparable_price_cents=500000, shop_type="self_operated", captured_at=now),
        ComparableOffer(id=5, comparable_price_cents=499900, shop_type="third_party", captured_at=now),
    ]

    assert [offer.id for offer in sort_offers(offers)] == [5, 1, 2, 3, 4]


def test_sort_does_not_mutate_input_sequence() -> None:
    now = datetime.now(UTC)
    offers = [
        ComparableOffer(id=2, comparable_price_cents=200, shop_type="authorized", captured_at=now),
        ComparableOffer(id=1, comparable_price_cents=100, shop_type="authorized", captured_at=now),
    ]

    sorted_offers = sort_offers(offers)

    assert [offer.id for offer in offers] == [2, 1]
    assert [offer.id for offer in sorted_offers] == [1, 2]


def test_conditional_price_never_changes_default_order() -> None:
    now = datetime.now(UTC)
    offers = [
        ComparableOffer(
            id=1,
            comparable_price_cents=499900,
            conditional_price_cents=None,
            shop_type="self_operated",
            captured_at=now,
        ),
        ComparableOffer(
            id=2,
            comparable_price_cents=509900,
            conditional_price_cents=399900,
            shop_type="self_operated",
            captured_at=now,
        ),
    ]

    assert [offer.comparable_price_cents for offer in sort_offers(offers)] == [499900, 509900]
