from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.offers import Offer, Platform, Shop
from app.pricing.sorting import sort_offers
from app.schemas.offers import ComparableOffer
from app.schemas.search_sessions import OfferView
from app.services.region_identity import normalize_region_name


def limit_offers_per_platform_region(
    offers: Sequence[OfferView],
    limit: int = 10,
) -> list[OfferView]:
    if limit < 1:
        raise ValueError("每个平台地区至少保留一条报价")
    counts: Counter[tuple[str, str]] = Counter()
    limited: list[OfferView] = []
    for offer in offers:
        region_identity = (
            offer.region_code
            or (normalize_region_name(offer.region_name) if offer.region_name else "unknown")
        )
        key = (offer.platform, region_identity)
        if counts[key] >= limit:
            continue
        counts[key] += 1
        limited.append(offer)
    return limited


def retain_region_top_offers(
    db: Session,
    search_session_id: int,
    platform: str,
    region_code: str,
    limit: int = 10,
) -> int:
    if limit < 1:
        raise ValueError("每个平台地区至少保留一条报价")
    rows = db.execute(
        select(Offer, Shop)
        .join(Platform, Offer.platform_id == Platform.id)
        .join(Shop, Offer.shop_id == Shop.id)
        .where(
            Offer.search_session_id == search_session_id,
            Platform.code == platform,
            Offer.region_code == region_code,
            Offer.deleted_at.is_(None),
            Offer.excluded_reason.is_(None),
        )
    ).all()
    comparable = [
        ComparableOffer(
            id=offer.id,
            comparable_price_cents=offer.comparable_price_cents,
            conditional_price_cents=offer.conditional_price_cents,
            shop_type=shop.shop_type,
            captured_at=offer.captured_at,
        )
        for offer, shop in rows
    ]
    excess_ids = {item.id for item in sort_offers(comparable)[limit:]}
    if not excess_ids:
        return 0
    removed_at = datetime.now(UTC)
    for offer, _shop in rows:
        if offer.id in excess_ids:
            offer.deleted_at = removed_at
    db.flush()
    return len(excess_ids)
