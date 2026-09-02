from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'subsidy.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return TestClient(create_app(database_url=database_url))


def rule_payload() -> dict[str, object]:
    return {
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
    }


def test_create_list_and_update_subsidy_rule(client: TestClient) -> None:
    created = client.post("/api/subsidy-rules", json=rule_payload())
    assert created.status_code == 201
    rule_id = created.json()["id"]

    listed = client.get("/api/subsidy-rules")
    assert [item["id"] for item in listed.json()["items"]] == [rule_id]

    payload = rule_payload()
    payload["active"] = False
    updated = client.put(f"/api/subsidy-rules/{rule_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["active"] is False


def test_rejects_reversed_validity_window(client: TestClient) -> None:
    payload = rule_payload()
    payload["valid_from"] = "2026-12-31"
    payload["valid_to"] = "2026-01-01"

    response = client.post("/api/subsidy-rules", json=payload)

    assert response.status_code == 422
