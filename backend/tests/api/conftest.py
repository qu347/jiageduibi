import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def flow_client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'history-flow.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    client = TestClient(create_app(database_url=database_url))
    fixtures_root = Path(__file__).parents[3] / "fixtures"
    catalog = json.loads((fixtures_root / "catalog" / "iphone17.json").read_text(encoding="utf-8"))
    assert client.post("/api/catalog/import", json=catalog).status_code == 200
    assert client.post(
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
    return client


@pytest.fixture
def variant_id(flow_client: TestClient) -> int:
    return flow_client.get("/api/catalog/search", params={"q": "苹果17"}).json()["items"][0]["variants"][0]["id"]


@pytest.fixture
def completed_search(flow_client: TestClient, variant_id: int) -> int:
    session_id = flow_client.post(
        "/api/search-sessions",
        json={"variant_id": variant_id, "region_code": "110100", "include_conditional": False},
    ).json()["id"]
    fixtures_root = Path(__file__).parents[3] / "fixtures"
    for platform in ("jd", "taobao", "pdd"):
        payload = json.loads((fixtures_root / platform / "search-results.json").read_text(encoding="utf-8"))
        assert flow_client.post(f"/api/search-sessions/{session_id}/offers", json=payload).status_code == 200
    assert flow_client.post(f"/api/search-sessions/{session_id}/finalize").status_code == 200
    return session_id
