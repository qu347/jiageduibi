import json
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.catalog import Brand, ProductModel, ProductSeries, ProductVariant
from app.db.models.offers import AdapterRun, Platform, SearchSession
from app.db.models.subsidy import SubsidyRule
from app.matching.matcher import match_offer
from app.pricing.calculator import calculate_price
from app.schemas.offers import MatchResult, MatchTarget, OfferPriceInput, PriceBreakdown, RawOffer
from app.schemas.search_sessions import EvaluatedOffer, IngestionSummary, PlatformOfferBatch
from app.schemas.subsidy import SubsidyContext, SubsidyRuleInput
from app.services.search_sessions import resolve_offer_region, save_evaluated_offer
from app.subsidy.engine import evaluate_subsidy


def ingest_candidates(db: Session, search_id: int, payload: PlatformOfferBatch) -> IngestionSummary:
    started_at = datetime.now(UTC)
    search = require_collecting_session(db, search_id)
    target = load_match_target(db, search.variant_id)
    rules = load_rules(db)
    accepted_count = 0
    exclusions: Counter[str] = Counter()

    try:
        for raw in payload.items:
            exclusion = evaluate_and_save_candidate(db, search, target, rules, payload, raw)
            if exclusion is None:
                accepted_count += 1
            else:
                exclusions[exclusion] += 1

        finished_at = datetime.now(UTC)
        platform = db.scalar(select(Platform).where(Platform.code == payload.platform))
        if platform is None:
            platform = Platform(code=payload.platform, name=payload.platform_name, enabled=True)
            db.add(platform)
            db.flush()
        db.add(
            AdapterRun(
                platform_id=platform.id,
                adapter_version=payload.adapter_version,
                source_type=payload.source_type,
                status="passing",
                duration_ms=max(0, int((finished_at - started_at).total_seconds() * 1000)),
                success_count=accepted_count,
                excluded_count=sum(exclusions.values()),
                error_summary=None,
                started_at=started_at,
                finished_at=finished_at,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return IngestionSummary(
        platform=payload.platform,
        accepted_count=accepted_count,
        excluded_count=sum(exclusions.values()),
        exclusions=dict(exclusions),
    )


def ingest_verified_browser_offer(
    db: Session,
    search_id: int,
    raw: RawOffer,
    *,
    adapter_version: str,
) -> IngestionSummary:
    payload = PlatformOfferBatch(
        platform="jd",
        platform_name="京东",
        adapter_version=adapter_version,
        source_type="browser",
        items=[raw],
    )
    search = require_collecting_session(db, search_id)
    target = load_match_target(db, search.variant_id)
    rules = load_rules(db)
    try:
        exclusion = evaluate_and_save_candidate(db, search, target, rules, payload, raw)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return IngestionSummary(
        platform="jd",
        accepted_count=0 if exclusion else 1,
        excluded_count=1 if exclusion else 0,
        exclusions={exclusion: 1} if exclusion else {},
    )


def evaluate_and_save_candidate(
    db: Session,
    search: SearchSession,
    target: MatchTarget,
    rules: list[SubsidyRuleInput],
    payload: PlatformOfferBatch,
    raw: RawOffer,
) -> str | None:
    if raw.platform != payload.platform:
        raise ValueError("批次平台与报价平台不一致")
    region_code, region_name, _region_key = resolve_offer_region(
        search,
        raw.region_code,
        raw.region_name,
    )
    match = match_offer(raw, target)
    if not match.accepted:
        reason = match.excluded_reason or "low_confidence"
        save_excluded(db, search, target, raw, payload, match, region_code, region_name)
        return reason
    if raw.sale_price_cents is None:
        missing = MatchResult(
            score=match.score,
            accepted=False,
            review_required=False,
            reasons=[*match.reasons, "缺少一次性总价"],
            excluded_reason="missing_price",
        )
        save_excluded(db, search, target, raw, payload, missing, region_code, region_name)
        return "missing_price"

    decision = evaluate_subsidy(
        rules,
        SubsidyContext(
            region_code=region_code,
            category="手机",
            platform=raw.platform,
            shop_type=raw.shop_type,
            price_cents=raw.sale_price_cents,
            at_date=raw.captured_at.date(),
            platform_confirmed=raw.subsidy_status == "confirmed",
            platform_sku_matches=raw.platform_sku_id is not None,
            platform_subsidy_amount_cents=(
                raw.subsidy_amount_cents if raw.subsidy_status == "confirmed" else None
            ),
        ),
    )
    price = calculate_price(
        OfferPriceInput(
            sale_price_cents=raw.sale_price_cents,
            merchant_discount_cents=raw.merchant_discount_cents,
            platform_coupon_cents=raw.platform_coupon_cents,
            subsidy_amount_cents=decision.amount_cents,
            subsidy_status=decision.status,
            shipping_fee_cents=raw.shipping_fee_cents,
            installation_fee_cents=raw.installation_fee_cents,
            conditions=[decision.reason] if decision.status == "estimated" else [],
        )
    )
    save_evaluated_offer(
        db,
        search.id,
        evaluated(
            raw,
            payload,
            target,
            match,
            price,
            decision.status,
            decision.amount_cents,
            region_code,
            region_name,
        ),
    )
    return None


def require_collecting_session(db: Session, search_id: int) -> SearchSession:
    search = db.get(SearchSession, search_id)
    if search is None:
        raise ValueError("搜索会话不存在")
    if search.status != "collecting":
        raise ValueError("搜索会话已结束")
    return search


def load_match_target(db: Session, variant_id: int) -> MatchTarget:
    row = db.execute(
        select(ProductVariant, ProductModel, ProductSeries, Brand)
        .join(ProductModel, ProductVariant.model_id == ProductModel.id)
        .join(ProductSeries, ProductModel.series_id == ProductSeries.id)
        .join(Brand, ProductSeries.brand_id == Brand.id)
        .where(ProductVariant.id == variant_id)
    ).one_or_none()
    if row is None:
        raise ValueError("目标 SKU 不存在")
    variant, model, _series, brand = row
    return MatchTarget(
        brand=brand.name,
        model_code=model.model_code,
        model_name=model.model_name,
        storage=variant.storage,
        region_version=variant.region_version,
        condition=variant.condition,
    )


def load_rules(db: Session) -> list[SubsidyRuleInput]:
    rows = list(db.scalars(select(SubsidyRule).where(SubsidyRule.deleted_at.is_(None))))
    return [
        SubsidyRuleInput(
            region_code=row.region_code,
            category=row.category,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            max_unit_price_cents=row.max_unit_price_cents,
            subsidy_rate_basis_points=row.subsidy_rate_basis_points,
            subsidy_cap_cents=row.subsidy_cap_cents,
            participating_platforms=json.loads(row.participating_platforms_json),
            participating_shop_types=json.loads(row.participating_shop_types_json),
            notes=row.notes,
            source_url=row.source_url,
            verified_at=row.verified_at,
            active=row.active,
        )
        for row in rows
    ]


def evaluated(
    raw: RawOffer,
    batch: PlatformOfferBatch,
    target: MatchTarget,
    match: MatchResult,
    price: PriceBreakdown,
    subsidy_status: str,
    subsidy_amount_cents: int,
    region_code: str | None,
    region_name: str | None,
) -> EvaluatedOffer:
    return EvaluatedOffer(
        platform=batch.platform,
        platform_name=batch.platform_name,
        platform_sku_id=raw.platform_sku_id,
        platform_product_id=raw.platform_product_id,
        platform_shop_id=raw.platform_shop_id,
        shop_name=raw.shop_name,
        shop_type=raw.shop_type,
        title=raw.title,
        product_url=raw.product_url,
        brand=target.brand,
        model_name=target.model_name,
        model_code=target.model_code,
        storage=target.storage,
        color=raw.color,
        region_version=target.region_version,
        condition=target.condition,
        category="手机",
        listed_price_cents=raw.listed_price_cents,
        sale_price_cents=raw.sale_price_cents,
        merchant_discount_cents=raw.merchant_discount_cents,
        platform_coupon_cents=raw.platform_coupon_cents,
        member_discount_cents=raw.member_discount_cents,
        payment_discount_cents=raw.payment_discount_cents,
        subsidy_amount_cents=subsidy_amount_cents,
        shipping_fee_cents=raw.shipping_fee_cents,
        installation_fee_cents=raw.installation_fee_cents,
        conditional_price_cents=raw.conditional_price_cents,
        price_type=raw.price_type,
        stock_status=raw.stock_status,
        subsidy_status=subsidy_status,
        region_code=region_code,
        region_name=region_name,
        match=match,
        price=price,
        source_type=batch.source_type,
        adapter_version=batch.adapter_version,
        captured_at=raw.captured_at,
    )


def save_excluded(
    db: Session,
    search: SearchSession,
    target: MatchTarget,
    raw: RawOffer,
    batch: PlatformOfferBatch,
    match: MatchResult,
    region_code: str | None,
    region_name: str | None,
) -> None:
    empty_price = PriceBreakdown(
        ordinary_price_cents=0,
        confirmed_final_price_cents=0,
        estimated_final_price_cents=None,
        comparable_price_cents=0,
        conditions=[],
    )
    save_evaluated_offer(
        db,
        search.id,
        evaluated(
            raw,
            batch,
            target,
            match,
            empty_price,
            "unknown",
            0,
            region_code,
            region_name,
        ),
    )
