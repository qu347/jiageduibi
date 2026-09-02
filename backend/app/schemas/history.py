from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HistoryPoint(BaseModel):
    offer_id: int
    platform: str
    comparable_price_cents: int | None
    subsidy_status: str
    captured_at: datetime
    source_type: str


class HistoryResponse(BaseModel):
    points: list[HistoryPoint]


class PlatformStatus(BaseModel):
    platform: str
    fixture_status: Literal["passing", "failing", "not_run"]
    live_status: Literal["not_validated"] = "not_validated"


class PlatformStatusResponse(BaseModel):
    items: list[PlatformStatus]
