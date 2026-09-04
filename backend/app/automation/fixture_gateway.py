import json
import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.automation.contracts import (
    AutomationEnvironment,
    CheckoutPreview,
    DiscoveredCandidate,
    GatewayFailure,
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
        color = next(
            (value for value in ("黑色", "白色", "紫色", "蓝色", "绿色", "橙色", "金色") if value in query),
            None,
        )
        if color:
            return [replace(
                self._candidates[0],
                platform_sku_id=str(900_000_000_000 + index),
                title=f"{query.strip()} 全新国行",
                product_url=f"https://item.jd.com/{900_000_000_000 + index}.html",
                platform_shop_id=f"fixture-price-sheet-{index:02d}",
                initial_price_cents=519900 + index * 1000,
            ) for index in range(20)][:limit]
        return self._candidates[:limit]

    def checkout_preview(
        self,
        candidate: DiscoveredCandidate,
        region: RegionTarget,
        allow_cart_fallback: bool = True,
    ) -> CheckoutPreview:
        del allow_cart_fallback
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        if "紫色" in candidate.title:
            raise GatewayFailure("cart_isolation_failed", "离线夹具模拟购物车恢复失败")
        if "白色" in candidate.title and region.region_code == "110100":
            return self._checkout_unavailable(candidate, "checkout_address_required")

        candidate_index = max(int(candidate.platform_sku_id) - 900_000_000_000, 0)
        conditional = candidate_index == 1
        payable = (
            400_000 + (region.sequence - 1) * 50
            if conditional
            else candidate.initial_price_cents + (region.sequence - 1) * 50
        )
        return CheckoutPreview(
            platform_sku_id=candidate.platform_sku_id,
            title=candidate.title,
            product_url=candidate.product_url,
            shop_name=candidate.shop_name,
            shop_type=candidate.shop_type,
            entry_mode="buy_now",
            price_status="conditional" if conditional else "verified",
            quantity=1,
            target_only=True,
            line_original_price_cents=payable + 60_000,
            line_sale_price_cents=payable + 50_000,
            merchant_discount_cents=0,
            ordinary_coupon_cents=10_000,
            subsidy_amount_cents=40_000,
            shipping_fee_cents=0,
            payable_price_cents=payable,
            discount_summary="PLUS会员专享" if conditional else "优惠券 100 元；国家补贴 400 元",
            conditional_reason="PLUS会员" if conditional else None,
            unavailable_code=None,
            region_confirmed=True,
            cart_restored=True,
            captured_at=datetime.now(UTC),
        )

    @staticmethod
    def _checkout_unavailable(candidate: DiscoveredCandidate, code: str) -> CheckoutPreview:
        return CheckoutPreview(
            platform_sku_id=candidate.platform_sku_id,
            title=candidate.title,
            product_url=candidate.product_url,
            shop_name=candidate.shop_name,
            shop_type=candidate.shop_type,
            entry_mode="buy_now",
            price_status="unavailable",
            quantity=0,
            target_only=False,
            line_original_price_cents=None,
            line_sale_price_cents=None,
            merchant_discount_cents=0,
            ordinary_coupon_cents=0,
            subsidy_amount_cents=0,
            shipping_fee_cents=0,
            payable_price_cents=None,
            discount_summary="",
            conditional_reason=None,
            unavailable_code=code,
            region_confirmed=False,
            cart_restored=True,
            captured_at=datetime.now(UTC),
        )

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
