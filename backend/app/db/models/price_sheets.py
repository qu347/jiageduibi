from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PriceSheetBatch(Base):
    __tablename__ = "price_sheet_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255))
    price_date: Mapped[date] = mapped_column(Date)
    date_inferred: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), index=True)
    recognized_count: Mapped[int] = mapped_column(Integer, default=0)
    selected_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_item_count: Mapped[int] = mapped_column(Integer, default=0)
    partial_item_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_item_count: Mapped[int] = mapped_column(Integer, default=0)
    lower_price_count: Mapped[int] = mapped_column(Integer, default=0)
    current_item_id: Mapped[int | None] = mapped_column(Integer)
    pause_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    stop_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PriceSheetItem(Base):
    __tablename__ = "price_sheet_items"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "model_name", "storage", "color",
            name="uq_price_sheet_item_variant",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("price_sheet_batches.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    brand: Mapped[str] = mapped_column(String(80))
    model_name: Mapped[str] = mapped_column(String(160))
    storage: Mapped[str] = mapped_column(String(40))
    color: Mapped[str] = mapped_column(String(80))
    today_price_cents: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), index=True)
    candidates_json: Mapped[str | None] = mapped_column(Text)
    candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    total_region_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_region_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_region_count: Mapped[int] = mapped_column(Integer, default=0)
    lowest_price_cents: Mapped[int | None] = mapped_column(Integer)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PriceSheetRegionTask(Base):
    __tablename__ = "price_sheet_region_tasks"
    __table_args__ = (
        UniqueConstraint("price_sheet_item_id", "region_code", name="uq_price_sheet_task_region"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    price_sheet_item_id: Mapped[int] = mapped_column(ForeignKey("price_sheet_items.id"), index=True)
    region_code: Mapped[str] = mapped_column(String(12))
    province: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(80))
    district: Mapped[str] = mapped_column(String(80))
    street: Mapped[str] = mapped_column(String(80))
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified_candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    lowest_result_cents: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PriceSheetRegionResult(Base):
    __tablename__ = "price_sheet_region_results"
    __table_args__ = (
        UniqueConstraint("price_sheet_item_id", "region_code", name="uq_price_sheet_result_region"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    price_sheet_item_id: Mapped[int] = mapped_column(ForeignKey("price_sheet_items.id"), index=True)
    region_code: Mapped[str] = mapped_column(String(12))
    platform_sku_id: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(Text)
    product_url: Mapped[str] = mapped_column(Text)
    shop_name: Mapped[str] = mapped_column(String(200))
    shop_type: Mapped[str] = mapped_column(String(40))
    listed_price_cents: Mapped[int | None] = mapped_column(Integer)
    sale_price_cents: Mapped[int] = mapped_column(Integer)
    merchant_discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    platform_coupon_cents: Mapped[int] = mapped_column(Integer, default=0)
    subsidy_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    trusted_price_cents: Mapped[int] = mapped_column(Integer)
    sale_price_includes_coupon: Mapped[bool] = mapped_column(Boolean, default=False)
    sale_price_includes_subsidy: Mapped[bool] = mapped_column(Boolean, default=False)
    stock_status: Mapped[str] = mapped_column(String(40))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PriceSheetCheckoutTask(Base):
    __tablename__ = "price_sheet_checkout_tasks"
    __table_args__ = (
        UniqueConstraint(
            "price_sheet_item_id", "region_code", "platform_sku_id",
            name="uq_price_sheet_checkout_item_region_sku",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    price_sheet_item_id: Mapped[int] = mapped_column(ForeignKey("price_sheet_items.id"), index=True)
    region_code: Mapped[str] = mapped_column(String(12), index=True)
    platform_sku_id: Mapped[str] = mapped_column(String(160))
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), index=True)
    entry_mode: Mapped[str | None] = mapped_column(String(32))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PriceSheetCheckoutResult(Base):
    __tablename__ = "price_sheet_checkout_results"
    __table_args__ = (
        UniqueConstraint("checkout_task_id", name="uq_price_sheet_checkout_result_task"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    checkout_task_id: Mapped[int] = mapped_column(ForeignKey("price_sheet_checkout_tasks.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    product_url: Mapped[str] = mapped_column(Text)
    shop_name: Mapped[str] = mapped_column(String(200))
    shop_type: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    target_only: Mapped[bool] = mapped_column(Boolean, default=False)
    line_original_price_cents: Mapped[int | None] = mapped_column(Integer)
    line_sale_price_cents: Mapped[int | None] = mapped_column(Integer)
    merchant_discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    ordinary_coupon_cents: Mapped[int] = mapped_column(Integer, default=0)
    subsidy_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    payable_price_cents: Mapped[int | None] = mapped_column(Integer)
    discount_summary: Mapped[str] = mapped_column(Text, default="")
    conditional_reason: Mapped[str | None] = mapped_column(Text)
    unavailable_code: Mapped[str | None] = mapped_column(String(64))
    price_status: Mapped[str] = mapped_column(String(32), index=True)
    region_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    cart_restored: Mapped[bool] = mapped_column(Boolean, default=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
