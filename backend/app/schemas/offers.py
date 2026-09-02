from pydantic import BaseModel, ConfigDict, Field


class RawOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    platform: str = Field(min_length=1, max_length=40)
    listed_price_cents: int | None = Field(default=None, ge=0)
    sale_price_cents: int | None = Field(default=None, ge=0)


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
