from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.offers import MatchResult, PriceBreakdown, RawOffer


class CreateSearchSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: int = Field(gt=0)
    region_code: str | None = Field(default=None, pattern=r"^\d{6,12}$")
    comparison_scope: Literal["national", "regional"] | None = None
    include_conditional: bool = False

    @model_validator(mode="after")
    def resolve_comparison_scope(self) -> "CreateSearchSession":
        scope = self.comparison_scope or ("regional" if self.region_code else "national")
        if scope == "national" and self.region_code is not None:
            raise ValueError("全国会话不能设置统一地区")
        if scope == "regional" and self.region_code is None:
            raise ValueError("地区会话必须设置地区")
        self.comparison_scope = scope
        return self


class SearchSessionView(BaseModel):
    id: int
    variant_id: int
    region_code: str | None
    include_conditional: bool
    status: str
    created_at: datetime
    finalized_at: datetime | None


class EvaluatedOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str
    platform_name: str
    platform_sku_id: str | None = None
    platform_product_id: str | None = None
    platform_shop_id: str | None = None
    shop_name: str = "未知店铺"
    shop_type: Literal["self_operated", "official_flagship", "authorized", "third_party"] = "third_party"
    title: str
    product_url: str
    brand: str | None = None
    model_name: str | None = None
    model_code: str | None = None
    storage: str | None = None
    memory: str | None = None
    color: str | None = None
    region_version: str | None = None
    condition: str | None = None
    category: str | None = None
    listed_price_cents: int | None = Field(default=None, ge=0)
    sale_price_cents: int | None = Field(default=None, ge=0)
    merchant_discount_cents: int = Field(default=0, ge=0)
    platform_coupon_cents: int = Field(default=0, ge=0)
    member_discount_cents: int = Field(default=0, ge=0)
    payment_discount_cents: int = Field(default=0, ge=0)
    subsidy_amount_cents: int = Field(default=0, ge=0)
    shipping_fee_cents: int = Field(default=0, ge=0)
    installation_fee_cents: int = Field(default=0, ge=0)
    conditional_price_cents: int | None = Field(default=None, ge=0)
    price_type: str = "total"
    stock_status: str = "unknown"
    subsidy_status: Literal["confirmed", "estimated", "unknown", "ineligible"] = "unknown"
    region_code: str | None = None
    region_name: str | None = None
    match: MatchResult
    price: PriceBreakdown
    source_type: str
    adapter_version: str
    captured_at: datetime


class OfferView(BaseModel):
    id: int
    search_session_id: int
    platform: str
    platform_sku_id: str
    title: str
    product_url: str
    shop_name: str
    shop_type: str
    comparable_price_cents: int | None
    confirmed_final_price_cents: int | None
    estimated_final_price_cents: int | None
    conditional_price_cents: int | None
    subsidy_status: str
    region_code: str | None
    region_name: str | None
    match_confidence: int
    excluded_reason: str | None
    captured_at: datetime
    source_type: str


class PlatformOfferBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str
    platform_name: str
    adapter_version: str
    source_type: str
    items: list[RawOffer]


class IngestionSummary(BaseModel):
    platform: str
    accepted_count: int
    excluded_count: int
    exclusions: dict[str, int]


class SearchResult(BaseModel):
    id: int
    status: str
    offers: list[OfferView]
    excluded_count: int
