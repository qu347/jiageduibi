import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.catalog import ProductVariant
from app.db.models.offers import (
    Offer,
    OfferMatch,
    Platform,
    PlatformProduct,
    PriceSnapshot,
    SearchSession,
    Shop,
)
from app.pricing.sorting import sort_offers
from app.schemas.search_sessions import (
    CreateSearchSession,
    EvaluatedOffer,
    OfferView,
    SearchSessionView,
    SearchResult,
)
from app.services.region_identity import build_region_key


def create_search_session(db: Session, command: CreateSearchSession) -> SearchSessionView:
    if db.get(ProductVariant, command.variant_id) is None:
        raise ValueError("目标 SKU 不存在")
    now = datetime.now(UTC)
    search = SearchSession(
        variant_id=command.variant_id,
        region_code=command.region_code,
        comparison_scope=command.comparison_scope,
        include_conditional=command.include_conditional,
        status="collecting",
        created_at=now,
        finalized_at=None,
    )
    db.add(search)
    db.flush()
    return search_session_view(search)


def get_search_session(db: Session, session_id: int) -> SearchSessionView:
    return search_session_view(require_search_session(db, session_id))


def list_offer_views(db: Session, session_id: int | None = None) -> list[OfferView]:
    query = (
        select(Offer, Platform, Shop)
        .join(Platform, Offer.platform_id == Platform.id)
        .join(Shop, Offer.shop_id == Shop.id)
        .where(Offer.deleted_at.is_(None), Offer.excluded_reason.is_(None))
    )
    if session_id is not None:
        query = query.where(Offer.search_session_id == session_id)
    rows = db.execute(query).all()
    return [offer_view(offer, platform.code, shop) for offer, platform, shop in rows]


def finalize_search_session(db: Session, session_id: int) -> SearchResult:
    search = require_search_session(db, session_id)
    if search.status == "collecting":
        search.status = "completed"
        search.finalized_at = datetime.now(UTC)
        db.commit()
    return build_search_result(db, session_id)


def build_search_result(db: Session, session_id: int) -> SearchResult:
    search = require_search_session(db, session_id)
    offers = list_offer_views(db, session_id)
    ranked = sort_offers(offers)
    excluded_count = db.scalar(
        select(func.count(Offer.id)).where(
            Offer.search_session_id == session_id,
            Offer.excluded_reason.is_not(None),
        )
    )
    return SearchResult(
        id=search.id,
        status=search.status,
        comparison_scope=search.comparison_scope,
        offers=ranked,
        excluded_count=excluded_count or 0,
    )


def require_search_session(db: Session, session_id: int) -> SearchSession:
    search = db.get(SearchSession, session_id)
    if search is None:
        raise ValueError("搜索会话不存在")
    return search


def fallback_platform_sku(value: EvaluatedOffer) -> str:
    identity = "|".join(
        (
            value.product_url.strip().casefold().rstrip("/"),
            (value.platform_shop_id or value.shop_name).strip().casefold(),
            " ".join(value.title.casefold().split()),
        )
    )
    return f"fallback:{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


def save_evaluated_offer(db: Session, session_id: int, value: EvaluatedOffer) -> OfferView:
    search = db.get(SearchSession, session_id)
    if search is None:
        raise ValueError("搜索会话不存在")
    if search.status != "collecting":
        raise ValueError("搜索会话已结束")
    region_code, region_name, region_key = resolve_offer_region(
        search,
        value.region_code,
        value.region_name,
    )

    with db.begin_nested():
        platform = db.scalar(select(Platform).where(Platform.code == value.platform))
        if platform is None:
            platform = Platform(code=value.platform, name=value.platform_name, enabled=True)
            db.add(platform)
            db.flush()
        else:
            platform.name = value.platform_name

        shop_identity = value.platform_shop_id or f"name:{value.shop_name.strip().casefold()}"
        shop = db.scalar(
            select(Shop).where(
                Shop.platform_id == platform.id,
                Shop.platform_shop_id == shop_identity,
            )
        )
        if shop is None:
            shop = Shop(
                platform_id=platform.id,
                platform_shop_id=shop_identity,
                name=value.shop_name,
                shop_type=value.shop_type,
            )
            db.add(shop)
            db.flush()
        else:
            shop.name = value.shop_name
            shop.shop_type = value.shop_type

        external_product_id = value.platform_product_id or fallback_platform_sku(value)
        product = db.scalar(
            select(PlatformProduct).where(
                PlatformProduct.platform_id == platform.id,
                PlatformProduct.platform_product_id == external_product_id,
            )
        )
        if product is None:
            product = PlatformProduct(
                platform_id=platform.id,
                shop_id=shop.id,
                platform_product_id=external_product_id,
                title=value.title,
                product_url=value.product_url,
                adapter_version=value.adapter_version,
                last_seen_at=value.captured_at,
            )
            db.add(product)
            db.flush()
        else:
            product.shop_id = shop.id
            product.title = value.title
            product.product_url = value.product_url
            product.adapter_version = value.adapter_version
            product.last_seen_at = value.captured_at

        sku_id = value.platform_sku_id or fallback_platform_sku(value)
        offer = db.scalar(
            select(Offer).where(
                Offer.search_session_id == session_id,
                Offer.platform_id == platform.id,
                Offer.platform_sku_id == sku_id,
                Offer.region_key == region_key,
            )
        )
        if offer is None:
            offer = Offer(
                search_session_id=session_id,
                platform_id=platform.id,
                platform_sku_id=sku_id,
                title=value.title,
                product_url=value.product_url,
                match_confidence=value.match.score,
                source_type=value.source_type,
                adapter_version=value.adapter_version,
                captured_at=value.captured_at,
                region_key=region_key,
            )
            db.add(offer)

        apply_current_offer_values(offer, product, shop, value, region_code, region_name, region_key)
        db.flush()
        db.add(
            PriceSnapshot(
                offer_id=offer.id,
                comparable_price_cents=value.price.comparable_price_cents,
                estimated_final_price_cents=value.price.estimated_final_price_cents,
                subsidy_status=value.subsidy_status,
                captured_at=value.captured_at,
                source_type=value.source_type,
            )
        )
        db.add(
            OfferMatch(
                offer_id=offer.id,
                score=value.match.score,
                accepted=value.match.accepted,
                review_required=value.match.review_required,
                reasons_json=json.dumps(value.match.reasons, ensure_ascii=False),
                excluded_reason=value.match.excluded_reason,
                rule_version="matcher-v1",
                created_at=datetime.now(UTC),
            )
        )
        db.flush()

    return offer_view(offer, value.platform, shop)


def apply_current_offer_values(
    offer: Offer,
    product: PlatformProduct,
    shop: Shop,
    value: EvaluatedOffer,
    region_code: str | None,
    region_name: str | None,
    region_key: str,
) -> None:
    offer.platform_product_id = product.id
    offer.shop_id = shop.id
    offer.title = value.title
    offer.product_url = value.product_url
    offer.brand = value.brand
    offer.model_name = value.model_name
    offer.model_code = value.model_code
    offer.storage = value.storage
    offer.memory = value.memory
    offer.color = value.color
    offer.region_version = value.region_version
    offer.condition = value.condition
    offer.category = value.category
    offer.listed_price_cents = value.listed_price_cents
    offer.sale_price_cents = value.sale_price_cents
    offer.merchant_discount_cents = value.merchant_discount_cents
    offer.platform_coupon_cents = value.platform_coupon_cents
    offer.member_discount_cents = value.member_discount_cents
    offer.payment_discount_cents = value.payment_discount_cents
    offer.subsidy_amount_cents = value.subsidy_amount_cents
    offer.shipping_fee_cents = value.shipping_fee_cents
    offer.installation_fee_cents = value.installation_fee_cents
    offer.final_price_cents = value.price.confirmed_final_price_cents
    offer.estimated_final_price_cents = value.price.estimated_final_price_cents
    offer.comparable_price_cents = value.price.comparable_price_cents
    offer.conditional_price_cents = value.conditional_price_cents
    offer.price_type = value.price_type
    offer.price_conditions_json = json.dumps(value.price.conditions, ensure_ascii=False)
    offer.stock_status = value.stock_status
    offer.excluded_reason = value.match.excluded_reason
    offer.subsidy_status = value.subsidy_status
    offer.region_code = region_code
    offer.region_name = region_name
    offer.region_key = region_key
    offer.match_confidence = value.match.score
    offer.source_type = value.source_type
    offer.adapter_version = value.adapter_version
    offer.captured_at = value.captured_at
    offer.deleted_at = None


def resolve_offer_region(
    search: SearchSession,
    region_code: str | None,
    region_name: str | None,
) -> tuple[str | None, str | None, str]:
    resolved_code = region_code
    if search.comparison_scope == "regional" and resolved_code is None:
        resolved_code = search.region_code
    return resolved_code, region_name, build_region_key(resolved_code, region_name)


def search_session_view(value: SearchSession) -> SearchSessionView:
    return SearchSessionView.model_validate(value, from_attributes=True)


def offer_view(value: Offer, platform_code: str, shop: Shop) -> OfferView:
    return OfferView(
        id=value.id,
        search_session_id=value.search_session_id,
        platform=platform_code,
        platform_sku_id=value.platform_sku_id,
        title=value.title,
        product_url=value.product_url,
        shop_name=shop.name,
        shop_type=shop.shop_type,
        comparable_price_cents=value.comparable_price_cents,
        confirmed_final_price_cents=value.final_price_cents,
        estimated_final_price_cents=value.estimated_final_price_cents,
        conditional_price_cents=value.conditional_price_cents,
        subsidy_status=value.subsidy_status,
        region_code=value.region_code,
        region_name=value.region_name,
        match_confidence=value.match_confidence,
        excluded_reason=value.excluded_reason,
        captured_at=value.captured_at,
        source_type=value.source_type,
    )
