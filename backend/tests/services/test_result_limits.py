from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    Brand,
    Offer,
    Platform,
    PriceSnapshot,
    ProductModel,
    ProductSeries,
    ProductVariant,
    SearchSession,
    Shop,
)
from app.db.session import build_engine, session_factory
from app.pricing.sorting import sort_offers
from app.schemas.search_sessions import OfferView
from app.services.offer_retention import limit_offers_per_platform_region, retain_region_top_offers


def offer_view(
    offer_id: int,
    platform: str,
    region_code: str,
    price: int,
) -> OfferView:
    return OfferView(
        id=offer_id,
        search_session_id=1,
        platform=platform,
        platform_sku_id=f"sku-{offer_id}",
        title=f"商品 {offer_id}",
        product_url=f"https://example.invalid/{offer_id}",
        shop_name="测试店铺",
        shop_type="self_operated",
        comparable_price_cents=price,
        confirmed_final_price_cents=price,
        estimated_final_price_cents=None,
        conditional_price_cents=None,
        subsidy_status="unknown",
        region_code=region_code,
        region_name="北京市" if region_code == "110100" else "上海市",
        match_confidence=100,
        excluded_reason=None,
        captured_at=datetime(2026, 9, 2, tzinfo=UTC),
        source_type="browser",
    )


def test_result_keeps_ten_per_platform_region_without_changing_global_order() -> None:
    rows = [offer_view(index + 1, "jd", "110100", 500000 + index * 100) for index in range(12)]
    rows += [offer_view(100 + index, "jd", "310100", 500050 + index * 100) for index in range(3)]
    rows += [offer_view(200 + index, "taobao", "110100", 500075 + index * 100) for index in range(2)]
    ranked = sort_offers(rows)
    expensive_beijing_ids = {
        item.id
        for item in sorted(rows[:12], key=lambda item: item.comparable_price_cents or 0)[-2:]
    }

    limited = limit_offers_per_platform_region(ranked, limit=10)

    assert sum(item.platform == "jd" and item.region_code == "110100" for item in limited) == 10
    assert sum(item.platform == "jd" and item.region_code == "310100" for item in limited) == 3
    assert [item.id for item in limited] == [
        item.id for item in ranked if item.id not in expensive_beijing_ids
    ]


@pytest.fixture
def db(tmp_path) -> Session:
    engine = build_engine(f"sqlite:///{(tmp_path / 'retention.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def populated_session(db: Session) -> int:
    brand = Brand(name="Apple", deleted_at=None)
    db.add(brand)
    db.flush()
    series = ProductSeries(brand_id=brand.id, name="iPhone", active=True, deleted_at=None)
    db.add(series)
    db.flush()
    model = ProductModel(
        series_id=series.id,
        model_name="iPhone 17",
        model_code="APPLE_IPHONE_17",
        category="手机",
        active=True,
        deleted_at=None,
    )
    db.add(model)
    db.flush()
    variant = ProductVariant(
        model_id=model.id,
        sku_code="APPLE_IPHONE_17_256",
        storage="256GB",
        memory=None,
        color="不限",
        region_version="中国大陆国行",
        condition="全新",
        active=True,
        deleted_at=None,
    )
    db.add(variant)
    db.flush()
    search = SearchSession(
        variant_id=variant.id,
        region_code=None,
        comparison_scope="national",
        include_conditional=False,
        status="collecting",
        created_at=datetime.now(UTC),
        finalized_at=None,
    )
    platform = Platform(code="jd", name="京东", enabled=True)
    db.add_all([search, platform])
    db.flush()
    shop = Shop(
        platform_id=platform.id,
        platform_shop_id="jd-self",
        name="京东自营",
        shop_type="self_operated",
    )
    db.add(shop)
    db.flush()
    captured = datetime.now(UTC)
    for index in range(12):
        price = 500000 + index * 100
        offer = Offer(
            search_session_id=search.id,
            platform_id=platform.id,
            platform_product_id=None,
            shop_id=shop.id,
            platform_sku_id=f"sku-{index}",
            title=f"Apple iPhone 17 256GB {index}",
            product_url=f"https://item.jd.com/{index}.html",
            brand="Apple",
            model_name="iPhone 17",
            model_code="APPLE_IPHONE_17",
            storage="256GB",
            memory=None,
            color="不限",
            region_version="中国大陆国行",
            condition="全新",
            category="手机",
            listed_price_cents=price,
            sale_price_cents=price,
            merchant_discount_cents=0,
            platform_coupon_cents=0,
            member_discount_cents=0,
            payment_discount_cents=0,
            subsidy_amount_cents=0,
            shipping_fee_cents=0,
            installation_fee_cents=0,
            final_price_cents=price,
            estimated_final_price_cents=None,
            comparable_price_cents=price,
            conditional_price_cents=None,
            price_type="total",
            price_conditions_json="[]",
            stock_status="in_stock",
            excluded_reason=None,
            subsidy_status="unknown",
            region_code="110100",
            region_name="北京市",
            region_key="code:110100",
            match_confidence=100,
            source_type="browser",
            adapter_version="test/1.0",
            captured_at=captured + timedelta(seconds=index),
            deleted_at=None,
        )
        db.add(offer)
        db.flush()
        db.add(
            PriceSnapshot(
                offer_id=offer.id,
                comparable_price_cents=price,
                estimated_final_price_cents=None,
                subsidy_status="unknown",
                captured_at=offer.captured_at,
                source_type="browser",
            )
        )
    db.commit()
    return search.id


def test_retention_soft_deletes_excess_offers_but_keeps_price_snapshots(db: Session) -> None:
    search_id = populated_session(db)

    removed = retain_region_top_offers(db, search_id, "jd", "110100", limit=10)
    db.commit()

    visible = db.scalar(
        select(func.count(Offer.id)).where(
            Offer.search_session_id == search_id,
            Offer.region_code == "110100",
            Offer.deleted_at.is_(None),
        )
    )
    snapshots = db.scalar(select(func.count(PriceSnapshot.id)))
    assert removed == 2
    assert visible == 10
    assert snapshots == 12
