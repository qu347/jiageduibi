from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubsidyRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region_code: str = Field(pattern=r"^\d{6,12}$")
    category: str = Field(min_length=1, max_length=40)
    valid_from: date
    valid_to: date
    max_unit_price_cents: int | None = Field(default=None, ge=0)
    subsidy_rate_basis_points: int = Field(ge=0, le=10_000)
    subsidy_cap_cents: int | None = Field(default=None, ge=0)
    participating_platforms: list[str] = Field(default_factory=list)
    participating_shop_types: list[str] = Field(default_factory=list)
    notes: str = ""
    source_url: str = ""
    verified_at: datetime | None = None
    active: bool = True

    @model_validator(mode="after")
    def validate_rule(self) -> "SubsidyRuleInput":
        if self.valid_from > self.valid_to:
            raise ValueError("生效日期不能晚于失效日期")
        if self.active and not self.source_url.strip():
            raise ValueError("启用规则必须填写来源链接")
        if self.source_url and not self.source_url.startswith(("https://", "http://")):
            raise ValueError("来源链接必须使用 http 或 https")
        return self


class SubsidyContext(BaseModel):
    region_code: str | None
    category: str
    platform: str
    shop_type: str
    price_cents: int = Field(ge=0)
    at_date: date
    platform_confirmed: bool = False
    platform_sku_matches: bool = False
    platform_subsidy_amount_cents: int | None = Field(default=None, ge=0)


class SubsidyDecision(BaseModel):
    status: Literal["confirmed", "estimated", "unknown", "ineligible"]
    amount_cents: int = Field(default=0, ge=0)
    rule_level: Literal["city", "province"] | None = None
    reason: str


class SubsidyRuleView(SubsidyRuleInput):
    id: int
    created_at: datetime
    updated_at: datetime


class SubsidyRuleList(BaseModel):
    items: list[SubsidyRuleView]
