import json
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.catalog import ProductVariant
from app.db.models.offers import Offer, PriceSnapshot
from app.db.session import build_engine, session_factory
from app.schemas.catalog import CatalogImport
from app.schemas.offers import MatchResult, PriceBreakdown
from app.schemas.search_sessions import CreateSearchSession, EvaluatedOffer
from app.services.catalog import import_catalog
from app.services.search_sessions import create_search_session, save_evaluated_offer


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    database_url = f"sqlite:///{(tmp_path / 'offers.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = build_engine(database_url)
    try:
        with session_factory(engine)() as db:
            yield db
    finally:
        engine.dispose()


@pytest.fixture
def seeded_variant(db_session: Session) -> ProductVariant:
    path = Path(__file__).parents[3] / "fixtures" / "catalog" / "iphone17.json"
    import_catalog(
        db_session,
        CatalogImport.model_validate(json.loads(path.read_text(encoding="utf-8"))),
    )
    return db_session.scalar(select(ProductVariant).where(ProductVariant.storage == "256GB"))


def evaluated_offer(
    platform_sku_id: str | None,
    price: int,
    *,
    region_code: str | None = None,
    region_name: str | None = None,
) -> EvaluatedOffer:
    captured_at = datetime.now(UTC)
    return EvaluatedOffer(
        platform="jd",
        platform_name="京东",
        platform_sku_id=platform_sku_id,
        platform_product_id="product-1",
        platform_shop_id="shop-1",
        shop_name="京东自营",
        shop_type="self_operated",
        title="Apple iPhone 17 256GB 黑色 全新国行",
        product_url="https://example.invalid/jd/product-1",
        brand="Apple",
        model_name="iPhone 17",
        model_code="APPLE_IPHONE_17",
        storage="256GB",
        color="黑色",
        region_version="中国大陆国行",
        condition="全新",
        category="手机",
        sale_price_cents=price,
        subsidy_status="unknown",
        region_code=region_code,
        region_name=region_name,
        match=MatchResult(
            score=100,
            accepted=True,
            review_required=False,
            reasons=["精确匹配"],
        ),
        price=PriceBreakdown(
            ordinary_price_cents=price,
            confirmed_final_price_cents=price,
            comparable_price_cents=price,
            conditions=[],
        ),
        source_type="fixture",
        adapter_version="fixture-v1",
        captured_at=captured_at,
    )


def test_offer_and_snapshot_are_saved_once_per_platform_sku(
    db_session: Session,
    seeded_variant: ProductVariant,
) -> None:
    search = create_search_session(
        db_session,
        CreateSearchSession(
            variant_id=seeded_variant.id,
            region_code="110100",
            include_conditional=False,
        ),
    )
    first = save_evaluated_offer(db_session, search.id, evaluated_offer("sku-1", 519900))
    second = save_evaluated_offer(db_session, search.id, evaluated_offer("sku-1", 509900))

    assert second.id == first.id
    assert db_session.scalar(select(func.count(Offer.id))) == 1
    assert db_session.scalar(select(func.count(PriceSnapshot.id))) == 2


def test_missing_platform_sku_uses_deterministic_fallback(
    db_session: Session,
    seeded_variant: ProductVariant,
) -> None:
    search = create_search_session(
        db_session,
        CreateSearchSession(variant_id=seeded_variant.id),
    )

    first = save_evaluated_offer(db_session, search.id, evaluated_offer(None, 519900))
    second = save_evaluated_offer(db_session, search.id, evaluated_offer(None, 509900))

    assert second.id == first.id
    assert first.platform_sku_id.startswith("fallback:")
    assert db_session.scalar(select(func.count(Offer.id))) == 1


def test_national_session_updates_same_region_and_preserves_other_regions(
    db_session: Session,
    seeded_variant: ProductVariant,
) -> None:
    search = create_search_session(
        db_session,
        CreateSearchSession(variant_id=seeded_variant.id),
    )

    shanghai_first = save_evaluated_offer(
        db_session,
        search.id,
        evaluated_offer("sku-1", 519900, region_code="310100", region_name="上海市"),
    )
    shanghai_second = save_evaluated_offer(
        db_session,
        search.id,
        evaluated_offer("sku-1", 509900, region_code="310100", region_name="上海市"),
    )
    beijing = save_evaluated_offer(
        db_session,
        search.id,
        evaluated_offer("sku-1", 499900, region_code="110100", region_name="北京市"),
    )

    assert shanghai_second.id == shanghai_first.id
    assert beijing.id != shanghai_first.id
    offers = list(db_session.scalars(select(Offer).order_by(Offer.region_key)))
    assert [(item.region_key, item.comparable_price_cents) for item in offers] == [
        ("code:110100", 499900),
        ("code:310100", 509900),
    ]
    snapshot_counts = {
        offer.id: db_session.scalar(
            select(func.count(PriceSnapshot.id)).where(PriceSnapshot.offer_id == offer.id)
        )
        for offer in offers
    }
    assert snapshot_counts[shanghai_first.id] == 2
    assert snapshot_counts[beijing.id] == 1
