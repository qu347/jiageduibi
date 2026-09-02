import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from app.automation.contracts import (
    AutomationEnvironment,
    DiscoveredCandidate,
    VerifiedOffer,
)
from app.automation.regions import RegionTarget
from app.core.config import PROJECT_ROOT


class FixtureBrowserGateway:
    adapter_version = "fixture-jd/1.0"

    def __init__(self, fixtures_root: Path | None = None) -> None:
        root = fixtures_root or PROJECT_ROOT / "fixtures" / "automation"
        self._candidates = [
            DiscoveredCandidate(**row)
            for row in json.loads((root / "jd-search.json").read_text(encoding="utf-8"))
        ]
        self._verification = json.loads((root / "jd-verify.json").read_text(encoding="utf-8"))
        delay_ms = float(os.environ.get("PRICE_COMPARE_AUTOMATION_FIXTURE_DELAY_MS", "20"))
        self._delay_seconds = min(max(delay_ms, 0.0), 1000.0) / 1000

    def diagnose(self) -> AutomationEnvironment:
        return AutomationEnvironment(
            agent_reach_available=True,
            opencli_available=True,
            browser_bridge_ready=True,
            plugin_ready=True,
            safe_message="自动采集环境可用",
        )

    def discover(self, query: str, limit: int) -> list[DiscoveredCandidate]:
        if not query.strip():
            raise ValueError("查询内容不能为空")
        return self._candidates[:limit]

    def verify(
        self,
        candidate: DiscoveredCandidate,
        region: RegionTarget,
    ) -> VerifiedOffer:
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        sale_price = (
            candidate.initial_price_cents
            + (region.sequence - 1) * int(self._verification["region_price_step_cents"])
        )
        return VerifiedOffer(
            platform_sku_id=candidate.platform_sku_id,
            title=candidate.title,
            product_url=candidate.product_url,
            shop_name=candidate.shop_name,
            platform_shop_id=candidate.platform_shop_id,
            shop_type=candidate.shop_type,
            listed_price_cents=sale_price + int(self._verification["listed_price_markup_cents"]),
            sale_price_cents=sale_price,
            merchant_discount_cents=0,
            platform_coupon_cents=0,
            member_discount_cents=0,
            payment_discount_cents=0,
            subsidy_amount_cents=0,
            subsidy_status=self._verification["subsidy_status"],
            shipping_fee_cents=0,
            installation_fee_cents=0,
            conditional_price_cents=None,
            stock_status=self._verification["stock_status"],
            captured_at=datetime.now(UTC),
        )
