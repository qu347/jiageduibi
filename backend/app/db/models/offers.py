from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Shop(Base):
    __tablename__ = "shops"
    __table_args__ = (UniqueConstraint("platform_id", "platform_shop_id", name="uq_shops_platform_shop"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), index=True)
    platform_shop_id: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(200))
    shop_type: Mapped[str] = mapped_column(String(40))


class PlatformProduct(Base):
    __tablename__ = "platform_products"
    __table_args__ = (
        UniqueConstraint("platform_id", "platform_product_id", name="uq_platform_products_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), index=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("shops.id"))
    platform_product_id: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    product_url: Mapped[str] = mapped_column(Text)
    adapter_version: Mapped[str] = mapped_column(String(80))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"), index=True)
    region_code: Mapped[str | None] = mapped_column(String(12))
    comparison_scope: Mapped[str] = mapped_column(String(16))
    include_conditional: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="collecting")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint(
            "search_session_id",
            "platform_id",
            "platform_sku_id",
            "region_key",
            name="uq_offers_session_platform_sku_region",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_session_id: Mapped[int] = mapped_column(ForeignKey("search_sessions.id"), index=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), index=True)
    platform_product_id: Mapped[int | None] = mapped_column(ForeignKey("platform_products.id"))
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("shops.id"))
    platform_sku_id: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    product_url: Mapped[str] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(80))
    model_name: Mapped[str | None] = mapped_column(String(160))
    model_code: Mapped[str | None] = mapped_column(String(120))
    storage: Mapped[str | None] = mapped_column(String(32))
    memory: Mapped[str | None] = mapped_column(String(32))
    color: Mapped[str | None] = mapped_column(String(80))
    region_version: Mapped[str | None] = mapped_column(String(80))
    condition: Mapped[str | None] = mapped_column(String(32))
    category: Mapped[str | None] = mapped_column(String(40))
    listed_price_cents: Mapped[int | None] = mapped_column(Integer)
    sale_price_cents: Mapped[int | None] = mapped_column(Integer)
    merchant_discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    platform_coupon_cents: Mapped[int] = mapped_column(Integer, default=0)
    member_discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    payment_discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    subsidy_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    installation_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    final_price_cents: Mapped[int | None] = mapped_column(Integer)
    estimated_final_price_cents: Mapped[int | None] = mapped_column(Integer)
    comparable_price_cents: Mapped[int | None] = mapped_column(Integer)
    conditional_price_cents: Mapped[int | None] = mapped_column(Integer)
    price_type: Mapped[str] = mapped_column(String(32), default="total")
    price_conditions_json: Mapped[str] = mapped_column(Text, default="[]")
    stock_status: Mapped[str] = mapped_column(String(32), default="unknown")
    excluded_reason: Mapped[str | None] = mapped_column(String(80))
    subsidy_status: Mapped[str] = mapped_column(String(24), default="unknown")
    region_code: Mapped[str | None] = mapped_column(String(12))
    region_name: Mapped[str | None] = mapped_column(String(120))
    region_key: Mapped[str] = mapped_column(String(180), server_default="unknown")
    match_confidence: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(32))
    adapter_version: Mapped[str] = mapped_column(String(80))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PriceComponent(Base):
    __tablename__ = "price_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    component_type: Mapped[str] = mapped_column(String(40))
    amount_cents: Mapped[int] = mapped_column(Integer)
    confirmed: Mapped[bool] = mapped_column(Boolean)
    condition_code: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    comparable_price_cents: Mapped[int | None] = mapped_column(Integer)
    estimated_final_price_cents: Mapped[int | None] = mapped_column(Integer)
    subsidy_status: Mapped[str] = mapped_column(String(24))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String(32))


class OfferMatch(Base):
    __tablename__ = "offer_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    accepted: Mapped[bool] = mapped_column(Boolean)
    review_required: Mapped[bool] = mapped_column(Boolean)
    reasons_json: Mapped[str] = mapped_column(Text)
    excluded_reason: Mapped[str | None] = mapped_column(String(80))
    rule_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ManualCorrection(Base):
    __tablename__ = "manual_corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(80))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AdapterRun(Base):
    __tablename__ = "adapter_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), index=True)
    adapter_version: Mapped[str] = mapped_column(String(80))
    source_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int] = mapped_column(Integer)
    success_count: Mapped[int] = mapped_column(Integer)
    excluded_count: Mapped[int] = mapped_column(Integer)
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
