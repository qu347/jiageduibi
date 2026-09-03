from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from app.automation.regions import RegionTarget


ShopType = Literal["self_operated", "official_flagship", "authorized", "third_party"]
SubsidyStatus = Literal["confirmed", "estimated", "unknown", "ineligible"]


@dataclass(frozen=True, slots=True)
class DiscoveredCandidate:
    platform_sku_id: str
    title: str
    product_url: str
    shop_name: str
    platform_shop_id: str | None
    shop_type: ShopType
    initial_price_cents: int


@dataclass(frozen=True, slots=True)
class VerifiedOffer:
    platform_sku_id: str
    title: str
    product_url: str
    shop_name: str
    platform_shop_id: str | None
    shop_type: ShopType
    listed_price_cents: int | None
    sale_price_cents: int
    merchant_discount_cents: int
    platform_coupon_cents: int
    member_discount_cents: int
    payment_discount_cents: int
    subsidy_amount_cents: int
    subsidy_status: SubsidyStatus
    shipping_fee_cents: int
    installation_fee_cents: int
    conditional_price_cents: int | None
    stock_status: str
    captured_at: datetime


@dataclass(frozen=True, slots=True)
class AutomationEnvironment:
    agent_reach_available: bool
    opencli_available: bool
    browser_bridge_ready: bool
    plugin_ready: bool
    safe_message: str


class GatewayFailure(RuntimeError):
    def __init__(self, code: str, safe_message: str) -> None:
        message = safe_message[:300]
        super().__init__(message)
        self.code = code
        self.safe_message = message


class BrowserGateway(Protocol):
    adapter_version: str

    def diagnose(self) -> AutomationEnvironment: ...

    def discover(self, query: str, limit: int) -> list[DiscoveredCandidate]: ...

    def verify(
        self,
        candidate: DiscoveredCandidate,
        region: RegionTarget,
    ) -> VerifiedOffer: ...


@runtime_checkable
class RegionBatchGateway(Protocol):
    def verify_region(
        self,
        query: str,
        candidates: list[DiscoveredCandidate],
        region: RegionTarget,
    ) -> list[VerifiedOffer]: ...
