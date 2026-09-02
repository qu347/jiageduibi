import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'flow.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    value = TestClient(create_app(database_url=database_url))
    catalog_path = Path(__file__).parents[3] / "fixtures" / "catalog" / "iphone17.json"
    assert value.post("/api/catalog/import", json=json.loads(catalog_path.read_text(encoding="utf-8"))).status_code == 200
    assert value.post(
        "/api/subsidy-rules",
        json={
            "region_code": "110100",
            "category": "手机",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
            "max_unit_price_cents": 600000,
            "subsidy_rate_basis_points": 1000,
            "subsidy_cap_cents": 30000,
            "participating_platforms": ["pdd"],
            "participating_shop_types": ["authorized"],
            "notes": "测试规则，不代表真实政策",
            "source_url": "https://example.invalid/rules/beijing-pdd",
            "verified_at": None,
            "active": True,
        },
    ).status_code == 201
    return value


def test_fixed_offers_produce_three_sorted_comparable_results(client: TestClient) -> None:
    variant_id = client.get("/api/catalog/search", params={"q": "苹果17"}).json()["items"][0]["variants"][0]["id"]
    session_response = client.post(
        "/api/search-sessions",
        json={"variant_id": variant_id, "region_code": "110100", "include_conditional": False},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["id"]

    fixtures_root = Path(__file__).parents[3] / "fixtures"
    for fixture in ("jd", "taobao", "pdd"):
        payload = json.loads((fixtures_root / fixture / "search-results.json").read_text(encoding="utf-8"))
        response = client.post(f"/api/search-sessions/{session_id}/offers", json=payload)
        assert response.status_code == 200

    result = client.post(f"/api/search-sessions/{session_id}/finalize").json()

    assert [offer["platform"] for offer in result["offers"]] == ["jd", "taobao", "pdd"]
    assert [offer["comparable_price_cents"] for offer in result["offers"]] == [499900, 504900, 509900]
    assert result["offers"][2]["estimated_final_price_cents"] == 479900
    assert result["excluded_count"] == 6


def test_invalid_search_payload_uses_structured_error(client: TestClient) -> None:
    response = client.post(
        "/api/search-sessions",
        json={"variant_id": 0, "region_code": "invalid", "include_conditional": False},
    )

    assert response.status_code == 422
    assert set(response.json()["detail"]) == {
        "what_happened",
        "possible_cause",
        "partial_saved",
        "next_action",
    }
