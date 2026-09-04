from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class PriceSheetItemInput(BaseModel):
    selected: bool = True
    brand: str = Field(min_length=1, max_length=80)
    model_name: str = Field(min_length=1, max_length=160)
    storage: str = Field(min_length=1, max_length=40)
    color: str = Field(min_length=1, max_length=80)
    today_price_cents: int = Field(ge=100_000, le=3_000_000)
    raw_text: str = Field(default="", max_length=2000)
    confidence: float = Field(ge=0, le=1)
    review_required: bool = False

    @field_validator("brand", "model_name", "storage", "color")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class PriceSheetItemsUpdate(BaseModel):
    price_date: date
    items: list[PriceSheetItemInput] = Field(max_length=200)


class PriceSheetBatchView(BaseModel):
    id: int
    file_name: str
    price_date: date
    date_inferred: bool
    status: str
    recognized_count: int
    selected_count: int
    completed_item_count: int
    partial_item_count: int
    failed_item_count: int
    lower_price_count: int
    current_item_id: int | None
    pause_requested: bool
    stop_requested: bool
    last_error_code: str | None
    last_error_summary: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class PriceSheetItemView(PriceSheetItemInput):
    id: int
    batch_id: int
    sequence: int
    status: str
    candidate_count: int
    total_region_count: int
    completed_region_count: int
    failed_region_count: int
    lowest_price_cents: int | None
    last_error_code: str | None
    last_error_summary: str | None
    started_at: datetime | None
    finished_at: datetime | None


class PriceSheetRegionTaskView(BaseModel):
    id: int
    price_sheet_item_id: int
    region_code: str
    province: str
    city: str
    district: str
    street: str
    sequence: int
    status: str
    attempts: int
    verified_candidate_count: int
    lowest_result_cents: int | None
    error_code: str | None
    error_summary: str | None
    started_at: datetime | None
    finished_at: datetime | None


class PriceSheetCheckoutCurrentView(BaseModel):
    platform_sku_id: str
    region_code: str
    address: str
    entry_mode: str | None


class PriceSheetCheckoutProgressView(BaseModel):
    stage: str
    candidate_count: int
    task_total: int
    task_finished: int
    verified_count: int
    conditional_count: int
    address_required_count: int
    unavailable_count: int
    failed_count: int
    skipped_count: int
    cart_attention_required: bool
    current: PriceSheetCheckoutCurrentView | None = None


class PriceSheetBatchDetail(BaseModel):
    batch: PriceSheetBatchView
    items: list[PriceSheetItemView]
    tasks: list[PriceSheetRegionTaskView] = Field(default_factory=list)
    checkout_progress: PriceSheetCheckoutProgressView


class PriceSheetResultView(BaseModel):
    item_id: int
    model_name: str
    storage: str
    color: str
    today_price_cents: int
    status: str
    coverage: str
    region_code: str | None = None
    address: str | None = None
    platform_sku_id: str | None = None
    title: str | None = None
    product_url: str | None = None
    shop_name: str | None = None
    entry_mode: str | None = None
    price_status: str | None = None
    quantity: int | None = None
    target_only: bool | None = None
    line_original_price_cents: int | None = None
    line_sale_price_cents: int | None = None
    merchant_discount_cents: int | None = None
    ordinary_coupon_cents: int | None = None
    subsidy_amount_cents: int | None = None
    shipping_fee_cents: int | None = None
    payable_price_cents: int | None = None
    discount_summary: str | None = None
    conditional_reason: str | None = None
    cart_restored: bool | None = None
    failed_count: int = 0
    captured_at: datetime | None = None


class PriceSheetResultsView(BaseModel):
    lower_results: list[PriceSheetResultView]
    not_lower_items: list[PriceSheetResultView]
    partial_items: list[PriceSheetResultView]
