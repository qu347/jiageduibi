from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from typing import Any

import httpx

from app.automation.contracts import (
    AutomationEnvironment,
    BrowserGateway,
    DiscoveredCandidate,
    GatewayFailure,
    VerifiedOffer,
)
from app.automation.regions import RegionTarget


JD_UNION_GATEWAY_URL = "https://api.jd.com/routerjson"
GOODS_QUERY_METHOD = "jd.union.open.goods.query"
GOODS_RANK_QUERY_METHOD = "jd.union.open.goods.rank.query"


class JdUnionPermissionPending(GatewayFailure):
    def __init__(self) -> None:
        super().__init__(
            "api_permission_pending",
            "京东联盟关键词商品接口权限待开通，已切换到浏览器搜索",
        )


@dataclass(frozen=True, slots=True)
class JdUnionRankItem:
    item_id: str
    sku_id: str | None
    title: str
    price_cents: int


def sign_params(params: Mapping[str, str], app_secret: str) -> str:
    signing_text = app_secret + "".join(
        f"{key}{params[key]}" for key in sorted(params)
    ) + app_secret
    return hashlib.md5(signing_text.encode("utf-8")).hexdigest().upper()


class JdUnionClient:
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        *,
        http_client: httpx.Client | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._app_key = app_key.strip()
        self._app_secret = app_secret.strip()
        if not self._app_key or not self._app_secret:
            raise ValueError("京东联盟 AppKey 和 AppSecret 不能为空")
        self._http_client = http_client
        self._now = now or datetime.now

    def search_goods(self, query: str, limit: int) -> list[DiscoveredCandidate]:
        normalized_query = query.strip()
        if not normalized_query or len(normalized_query) > 200:
            raise ValueError("搜索词长度必须在 1 到 200 个字符之间")
        if limit <= 0:
            raise ValueError("候选数量必须大于 0")
        result = self._request(
            GOODS_QUERY_METHOD,
            {
                "goodsReqDTO": {
                    "keyword": normalized_query,
                    "pageIndex": 1,
                    "pageSize": min(limit, 20),
                }
            },
        )
        data = result.get("data")
        if not isinstance(data, list):
            raise GatewayFailure("invalid_output", "京东联盟商品响应格式无效")
        candidates = [candidate for row in data if (candidate := _parse_candidate(row)) is not None]
        return candidates[:limit]

    def query_rank(
        self,
        *,
        rank_id: int = 200000,
        sort_type: int = 3,
        limit: int = 3,
    ) -> list[JdUnionRankItem]:
        if limit <= 0 or limit > 20:
            raise ValueError("热销榜数量必须在 1 到 20 之间")
        result = self._request(
            GOODS_RANK_QUERY_METHOD,
            {
                "RankGoodsReq": {
                    "rankId": rank_id,
                    "sortType": sort_type,
                    "pageIndex": 1,
                    "pageSize": limit,
                }
            },
        )
        data = result.get("data")
        rows = data.get("rankGoodsResp") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise GatewayFailure("invalid_output", "京东联盟热销榜响应格式无效")
        items = [item for row in rows if (item := _parse_rank_item(row)) is not None]
        return items[:limit]

    def _request(self, method: str, request_data: dict[str, object]) -> dict[str, Any]:
        params = {
            "360buy_param_json": json.dumps(
                request_data,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "app_key": self._app_key,
            "format": "json",
            "method": method,
            "sign_method": "md5",
            "timestamp": self._now().strftime("%Y-%m-%d %H:%M:%S"),
            "v": "1.0",
        }
        params["sign"] = sign_params(params, self._app_secret)
        try:
            if self._http_client is None:
                with httpx.Client() as client:
                    response = client.post(JD_UNION_GATEWAY_URL, data=params, timeout=20.0)
            else:
                response = self._http_client.post(JD_UNION_GATEWAY_URL, data=params, timeout=20.0)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            code = "network_error" if isinstance(exc, httpx.HTTPError) else "invalid_output"
            message = "京东联盟接口网络请求失败" if code == "network_error" else "京东联盟接口响应格式无效"
            raise GatewayFailure(code, message) from exc

        response_key = method.replace(".", "_") + "_responce"
        envelope = payload.get(response_key) if isinstance(payload, dict) else None
        if not isinstance(envelope, dict) or str(envelope.get("code")) != "0":
            raise GatewayFailure("api_error", "京东联盟接口调用失败，请检查应用凭据和接口状态")
        raw_result = envelope.get("queryResult")
        try:
            result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        except (TypeError, json.JSONDecodeError) as exc:
            raise GatewayFailure("invalid_output", "京东联盟接口响应格式无效") from exc
        if not isinstance(result, dict):
            raise GatewayFailure("invalid_output", "京东联盟接口响应格式无效")
        business_code = str(result.get("code"))
        if business_code == "403":
            raise JdUnionPermissionPending()
        if business_code != "200":
            raise GatewayFailure("api_error", "京东联盟接口暂时不可用，请检查接口权限和应用状态")
        return result


class OfficialFirstJdGateway:
    adapter_version = "jd-union-v1+browser-verification"

    def __init__(self, official: JdUnionClient, browser: BrowserGateway) -> None:
        self._official = official
        self._browser = browser

    def diagnose(self) -> AutomationEnvironment:
        return self._browser.diagnose()

    def discover(self, query: str, limit: int) -> list[DiscoveredCandidate]:
        try:
            return self._official.search_goods(query, limit)
        except JdUnionPermissionPending:
            return self._browser.discover(query, limit)

    def verify(
        self,
        candidate: DiscoveredCandidate,
        region: RegionTarget,
    ) -> VerifiedOffer:
        return self._browser.verify(candidate, region)

    def verify_region(
        self,
        query: str,
        candidates: list[DiscoveredCandidate],
        region: RegionTarget,
    ) -> list[VerifiedOffer]:
        verify_region = getattr(self._browser, "verify_region", None)
        if verify_region is None:
            return [self._browser.verify(candidate, region) for candidate in candidates]
        return verify_region(query, candidates, region)


def _parse_candidate(value: object) -> DiscoveredCandidate | None:
    if not isinstance(value, dict):
        return None
    sku_id = _identifier(value.get("skuId"))
    title = value.get("skuName")
    price_info = value.get("priceInfo")
    price_cents = _yuan_to_cents(price_info.get("price")) if isinstance(price_info, dict) else None
    if sku_id is None or not isinstance(title, str) or not title.strip() or price_cents is None:
        return None
    material_url = value.get("materialUrl")
    if isinstance(material_url, str) and material_url.strip():
        product_url = material_url.strip()
        if not product_url.startswith(("http://", "https://")):
            product_url = f"https://{product_url.lstrip('/')}"
    else:
        product_url = f"https://item.jd.com/{sku_id}.html"
    shop_info = value.get("shopInfo")
    shop_name = shop_info.get("shopName") if isinstance(shop_info, dict) else None
    shop_id = _identifier(shop_info.get("shopId")) if isinstance(shop_info, dict) else None
    return DiscoveredCandidate(
        platform_sku_id=sku_id,
        title=title.strip(),
        product_url=product_url,
        shop_name=shop_name.strip() if isinstance(shop_name, str) and shop_name.strip() else "京东平台商家",
        platform_shop_id=shop_id,
        shop_type="self_operated" if value.get("owner") == "g" else "third_party",
        initial_price_cents=price_cents,
    )


def _parse_rank_item(value: object) -> JdUnionRankItem | None:
    if not isinstance(value, dict):
        return None
    item_id = _identifier(value.get("itemId"))
    sku_id = _identifier(value.get("skuId"))
    title = value.get("skuName")
    purchase_info = value.get("purchasePriceInfo")
    purchase_price = purchase_info.get("purchasePrice") if isinstance(purchase_info, dict) else None
    price_cents = _yuan_to_cents(purchase_price) or _yuan_to_cents(value.get("wlprice"))
    if item_id is None or not isinstance(title, str) or not title.strip() or price_cents is None:
        return None
    return JdUnionRankItem(
        item_id=item_id,
        sku_id=sku_id,
        title=title.strip(),
        price_cents=price_cents,
    )


def _identifier(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, str)):
        normalized = str(value).strip()
        return normalized or None
    return None


def _yuan_to_cents(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
