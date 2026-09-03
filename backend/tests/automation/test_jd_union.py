import json
from datetime import datetime
from urllib.parse import parse_qs

import httpx
import pytest

from app.automation.contracts import DiscoveredCandidate, GatewayFailure
from app.automation.jd_union import (
    JdUnionClient,
    JdUnionPermissionPending,
    OfficialFirstJdGateway,
    sign_params,
)
from app.automation.regions import get_region_target


FIXED_NOW = datetime(2026, 9, 3, 12, 34, 56)


def _http_client(payload: dict[str, object], captured: dict[str, str] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.update({key: values[0] for key, values in parse_qs(request.content.decode()).items()})
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _response(method: str, result: dict[str, object]) -> dict[str, object]:
    response_key = method.replace(".", "_") + "_responce"
    return {
        response_key: {
            "code": "0",
            "queryResult": json.dumps(result, ensure_ascii=False),
        }
    }


def test_sign_params_matches_jd_md5_contract() -> None:
    params = {
        "360buy_param_json": '{"RankGoodsReq":{"rankId":200000,"sortType":3,"pageIndex":1,"pageSize":3}}',
        "app_key": "test-app",
        "format": "json",
        "method": "jd.union.open.goods.rank.query",
        "sign_method": "md5",
        "timestamp": "2026-09-03 12:34:56",
        "v": "1.0",
    }

    assert sign_params(params, "test-secret") == "AAFB397A9A19EDB5C8B49D67C4C4950E"


def test_goods_query_emits_signed_request_and_maps_candidates() -> None:
    method = "jd.union.open.goods.query"
    captured: dict[str, str] = {}
    payload = _response(method, {
        "code": 200,
        "data": [{
            "skuId": 100000000001,
            "skuName": "Apple iPhone 17 256GB 白色",
            "materialUrl": "https://item.jd.com/100000000001.html",
            "owner": "g",
            "imageInfo": {"imageList": [{"url": "example.invalid/iphone.jpg"}]},
            "priceInfo": {"price": 5199.00},
            "shopInfo": {"shopId": 1000000123, "shopName": "京东自营"},
        }],
        "message": "success",
        "totalCount": 1,
    })
    client = JdUnionClient(
        "test-app",
        "test-secret",
        http_client=_http_client(payload, captured),
        now=lambda: FIXED_NOW,
    )

    candidates = client.search_goods("Apple iPhone 17 256GB", limit=3)

    assert captured["method"] == method
    assert captured["timestamp"] == "2026-09-03 12:34:56"
    assert captured["360buy_param_json"] == (
        '{"goodsReqDTO":{"keyword":"Apple iPhone 17 256GB","pageIndex":1,"pageSize":3}}'
    )
    assert captured["sign"] == "5717688B539F515CD53CA2CD593D1B11"
    assert candidates == [DiscoveredCandidate(
        platform_sku_id="100000000001",
        title="Apple iPhone 17 256GB 白色",
        product_url="https://item.jd.com/100000000001.html",
        shop_name="京东自营",
        platform_shop_id="1000000123",
        shop_type="self_operated",
        initial_price_cents=519900,
    )]


def test_rank_query_accepts_current_nested_response_and_item_id_fallback() -> None:
    method = "jd.union.open.goods.rank.query"
    payload = _response(method, {
        "code": 200,
        "data": {
            "rankGoodsResp": [{
                "itemId": 987654321,
                "skuId": None,
                "skuName": "京东热销商品",
                "imageUrl": "example.invalid/rank.jpg",
                "wlprice": 4299.00,
                "purchasePriceInfo": {"purchasePrice": 4199.00},
            }]
        },
        "message": "success",
        "totalCount": 100,
    })
    client = JdUnionClient(
        "test-app",
        "test-secret",
        http_client=_http_client(payload),
        now=lambda: FIXED_NOW,
    )

    items = client.query_rank(rank_id=200000, sort_type=3, limit=3)

    assert len(items) == 1
    assert items[0].item_id == "987654321"
    assert items[0].sku_id is None
    assert items[0].title == "京东热销商品"
    assert items[0].price_cents == 419900


def test_permission_pending_falls_back_to_browser_discovery() -> None:
    method = "jd.union.open.goods.query"
    payload = _response(method, {
        "code": 403,
        "data": None,
        "message": "无访问权限",
    })
    official = JdUnionClient(
        "test-app",
        "test-secret",
        http_client=_http_client(payload),
        now=lambda: FIXED_NOW,
    )
    fallback = _FallbackGateway()

    candidates = OfficialFirstJdGateway(official, fallback).discover("iPhone 17", 5)

    assert candidates == fallback.candidates
    assert fallback.discover_calls == [("iPhone 17", 5)]


def test_official_first_gateway_delegates_region_batch_to_browser() -> None:
    official = JdUnionClient(
        "test-app",
        "test-secret",
        http_client=_http_client({}),
        now=lambda: FIXED_NOW,
    )
    browser = _FallbackGateway()
    gateway = OfficialFirstJdGateway(official, browser)
    region = get_region_target("110100")

    offers = gateway.verify_region("iPhone 17", browser.candidates, region)

    assert offers == []
    assert browser.verify_region_calls == [
        ("iPhone 17", browser.candidates, region),
    ]


def test_goods_query_reports_permission_pending_without_credentials_or_raw_response() -> None:
    method = "jd.union.open.goods.query"
    payload = _response(method, {
        "code": 403,
        "data": None,
        "message": "无访问权限 secret-must-not-pass",
    })
    client = JdUnionClient(
        "test-app",
        "test-secret",
        http_client=_http_client(payload),
        now=lambda: FIXED_NOW,
    )

    with pytest.raises(JdUnionPermissionPending) as failure:
        client.search_goods("iPhone 17", 5)

    assert failure.value.code == "api_permission_pending"
    assert "test-secret" not in failure.value.safe_message
    assert "secret-must-not-pass" not in failure.value.safe_message


def test_goods_query_rejects_malformed_payload() -> None:
    method = "jd.union.open.goods.query"
    client = JdUnionClient(
        "test-app",
        "test-secret",
        http_client=_http_client({
            method.replace(".", "_") + "_responce": {
                "code": "0",
                "queryResult": "not-json",
            }
        }),
        now=lambda: FIXED_NOW,
    )

    with pytest.raises(GatewayFailure) as failure:
        client.search_goods("iPhone 17", 5)

    assert failure.value.code == "invalid_output"
    assert "not-json" not in failure.value.safe_message


class _FallbackGateway:
    adapter_version = "fallback-test"

    def __init__(self) -> None:
        self.candidates = [DiscoveredCandidate(
            platform_sku_id="fallback-1",
            title="浏览器候选",
            product_url="https://item.jd.com/fallback-1.html",
            shop_name="测试店铺",
            platform_shop_id=None,
            shop_type="third_party",
            initial_price_cents=529900,
        )]
        self.discover_calls: list[tuple[str, int]] = []
        self.verify_region_calls: list[tuple[str, list[DiscoveredCandidate], object]] = []

    def discover(self, query: str, limit: int) -> list[DiscoveredCandidate]:
        self.discover_calls.append((query, limit))
        return self.candidates

    def diagnose(self):
        raise AssertionError("discover fallback must not diagnose")

    def verify(self, candidate, region):
        raise AssertionError("discover fallback must not verify")

    def verify_region(self, query, candidates, region):
        self.verify_region_calls.append((query, candidates, region))
        return []
