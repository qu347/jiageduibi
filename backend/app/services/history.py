from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.offers import Offer, Platform, PriceSnapshot, SearchSession
from app.schemas.history import HistoryPoint


def get_price_history(
    db: Session,
    variant_id: int,
    platform: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[HistoryPoint]:
    query = (
        select(PriceSnapshot, Offer, Platform)
        .join(Offer, PriceSnapshot.offer_id == Offer.id)
        .join(SearchSession, Offer.search_session_id == SearchSession.id)
        .join(Platform, Offer.platform_id == Platform.id)
        .where(
            SearchSession.variant_id == variant_id,
            Offer.excluded_reason.is_(None),
            Offer.deleted_at.is_(None),
        )
        .order_by(PriceSnapshot.captured_at, PriceSnapshot.id)
    )
    if platform:
        query = query.where(Platform.code == platform)
    if from_date:
        query = query.where(PriceSnapshot.captured_at >= datetime.combine(from_date, time.min, tzinfo=UTC))
    if to_date:
        exclusive_end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=UTC)
        query = query.where(PriceSnapshot.captured_at < exclusive_end)

    return [
        HistoryPoint(
            offer_id=offer.id,
            platform=platform_row.code,
            comparable_price_cents=snapshot.comparable_price_cents,
            subsidy_status=snapshot.subsidy_status,
            captured_at=snapshot.captured_at,
            source_type=snapshot.source_type,
        )
        for snapshot, offer, platform_row in db.execute(query).all()
    ]
