from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RawOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    platform: str = Field(min_length=1, max_length=40)
    listed_price_cents: int | None = Field(default=None, ge=0)
    sale_price_cents: int | None = Field(default=None, ge=0)
    platform_product_id: str | None = None
    platform_sku_id: str | None = None
    platform_shop_id: str | None = None
    shop_name: str = "未知店铺"
    shop_type: Literal["self_operated", "official_flagship", "authorized", "third_party"] = "third_party"
    product_url: str = "https://example.invalid/unknown"
    color: str | None = None
    merchant_discount_cents: int = Field(default=0, ge=0)
    platform_coupon_cents: int = Field(default=0, ge=0)
    member_discount_cents: int = Field(default=0, ge=0)
    payment_discount_cents: int = Field(default=0, ge=0)
    subsidy_amount_cents: int = Field(default=0, ge=0)
    subsidy_status: Literal["confirmed", "estimated", "unknown", "ineligible"] = "unknown"
    shipping_fee_cents: int = Field(default=0, ge=0)
    installation_fee_cents: int = Field(default=0, ge=0)
    conditional_price_cents: int | None = Field(default=None, ge=0)
    price_type: str = "total"
    stock_status: str = "unknown"
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MatchTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand: str
    model_code: str
    model_name: str
    storage: str
    region_version: str
    condition: str


class MatchResult(BaseModel):
    score: int = Field(ge=0, le=100)
    accepted: bool
    review_required: bool
    reasons: list[str]
    excluded_reason: str | None = None


class OfferPriceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sale_price_cents: int = Field(ge=0)
    merchant_discount_cents: int = Field(default=0, ge=0)
    platform_coupon_cents: int = Field(default=0, ge=0)
    subsidy_amount_cents: int = Field(default=0, ge=0)
    subsidy_status: Literal["confirmed", "estimated", "unknown", "ineligible"] = "unknown"
    shipping_fee_cents: int = Field(default=0, ge=0)
    installation_fee_cents: int = Field(default=0, ge=0)
    conditions: list[str] = Field(default_factory=list)


class PriceBreakdown(BaseModel):
    ordinary_price_cents: int = Field(ge=0)
    confirmed_final_price_cents: int = Field(ge=0)
    estimated_final_price_cents: int | None = Field(default=None, ge=0)
    comparable_price_cents: int = Field(ge=0)
    conditions: list[str]


class ComparableOffer(BaseModel):
    id: int
    comparable_price_cents: int | None = Field(default=None, ge=0)
    shop_type: Literal["self_operated", "official_flagship", "authorized", "third_party"]
    captured_at: datetime
