import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    database = tmp_path / "catalog.db"
    database_url = f"sqlite:///{database.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return TestClient(create_app(database_url=database_url))


def catalog_fixture() -> dict[str, object]:
    path = Path(__file__).parents[3] / "fixtures" / "catalog" / "iphone17.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_search_apple_17_returns_standard_models(client: TestClient) -> None:
    assert client.post("/api/catalog/import", json=catalog_fixture()).status_code == 200

    response = client.get("/api/catalog/search", params={"q": "苹果17"})

    assert response.status_code == 200
    assert [item["model_code"] for item in response.json()["items"]] == [
        "APPLE_IPHONE_17",
        "APPLE_IPHONE_17_PRO",
        "APPLE_IPHONE_17_PRO_MAX",
    ]
    assert response.json()["items"][0]["variants"][0]["sku_code"] == "APPLE_IPHONE_17_256_CN_NEW_ANY"


def test_catalog_import_is_atomic_on_invalid_variant_reference(client: TestClient) -> None:
    payload = catalog_fixture()
    payload["variants"][0]["model_code"] = "MISSING"

    response = client.post("/api/catalog/import", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["partial_saved"] is False
    assert client.get("/api/catalog/export").json() == {
        "brands": [],
        "series": [],
        "models": [],
        "variants": [],
    }


def test_catalog_export_has_deterministic_code_order(client: TestClient) -> None:
    assert client.post("/api/catalog/import", json=catalog_fixture()).status_code == 200

    exported = client.get("/api/catalog/export").json()

    assert [model["code"] for model in exported["models"]] == [
        "APPLE_IPHONE_17",
        "APPLE_IPHONE_17_PRO",
        "APPLE_IPHONE_17_PRO_MAX",
    ]
    assert exported["variants"][0]["sku_code"] == "APPLE_IPHONE_17_256_CN_NEW_ANY"


def test_get_catalog_variant_by_id_for_session_restore(client: TestClient) -> None:
    assert client.post("/api/catalog/import", json=catalog_fixture()).status_code == 200
    variant_id = client.get("/api/catalog/search", params={"q": "苹果17"}).json()["items"][0]["variants"][0]["id"]

    response = client.get(f"/api/catalog/variants/{variant_id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": variant_id,
        "sku_code": "APPLE_IPHONE_17_256_CN_NEW_ANY",
        "storage": "256GB",
        "memory": None,
        "color": "不限",
        "region_version": "中国大陆国行",
        "condition": "全新",
    }


def test_missing_catalog_variant_uses_structured_404(client: TestClient) -> None:
    response = client.get("/api/catalog/variants/999999")

    assert response.status_code == 404
    assert set(response.json()["detail"]) == {
        "what_happened",
        "possible_cause",
        "partial_saved",
        "next_action",
    }
