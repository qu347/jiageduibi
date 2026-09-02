from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'pairing.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return TestClient(create_app(database_url=database_url))


@pytest.fixture
def pairing_code(client: TestClient) -> str:
    response = client.post("/api/extension/pairing-code")
    assert response.status_code == 200
    return response.json()["code"]


def test_pairing_exchanges_one_time_code_for_token(client: TestClient, pairing_code: str) -> None:
    response = client.post("/api/extension/pair", json={"code": pairing_code})

    assert response.status_code == 200
    assert len(response.json()["token"]) >= 32
    assert client.post("/api/extension/pair", json={"code": pairing_code}).status_code == 409


def test_offer_submission_requires_extension_token(client: TestClient) -> None:
    response = client.post(
        "/api/extension/offers",
        json={"search_session_id": 1, "platform": "jd", "items": []},
    )

    assert response.status_code == 401
