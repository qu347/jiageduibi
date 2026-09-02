from datetime import UTC, datetime

from sqlalchemy import func, select

from app.db.models.offers import AdapterRun
from app.schemas.offers import RawOffer
from app.services.offer_ingestion import ingest_verified_browser_offer


def test_browser_offer_uses_existing_ingestion_without_adapter_run_per_item(
    flow_client,
    variant_id: int,
) -> None:
    session_id = flow_client.post(
        "/api/search-sessions",
        json={"variant_id": variant_id, "comparison_scope": "national"},
    ).json()["id"]
    raw = RawOffer(
        title="Apple iPhone 17 256GB 全新国行",
        platform="jd",
        platform_product_id="100000000001",
        platform_sku_id="100000000001",
        platform_shop_id="jd-self",
        shop_name="京东自营",
        shop_type="self_operated",
        product_url="https://item.jd.com/100000000001.html",
        sale_price_cents=519900,
        stock_status="in_stock",
        region_code="110100",
        region_name="北京市",
        captured_at=datetime(2026, 9, 2, 10, 0, tzinfo=UTC),
    )

    with flow_client.app.state.session_factory() as db:
        summary = ingest_verified_browser_offer(
            db,
            session_id,
            raw,
            adapter_version="price-compare-jd/0.1.0",
        )
        adapter_runs = db.scalar(select(func.count(AdapterRun.id)))

    assert summary.accepted_count == 1
    assert summary.excluded_count == 0
    assert adapter_runs == 0
    result = flow_client.get(f"/api/search-sessions/{session_id}/result").json()
    assert result["offers"][0]["region_name"] == "北京市"
    assert result["offers"][0]["source_type"] == "browser"
