from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_version_and_pending_database(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'unmigrated.db').as_posix()}"
    response = TestClient(create_app(database_url=database_url)).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "database": "pending",
    }
