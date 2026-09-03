import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.automation.contracts import AutomationEnvironment
from app.db.models import CollectionRegionTask, CollectionRun
from app.main import create_app


class FakeCoordinator:
    def __init__(self) -> None:
        self.submitted: list[int] = []
        self.closed = False

    def submit(self, run_id: int) -> bool:
        self.submitted.append(run_id)
        return True

    def close(self) -> None:
        self.closed = True


class DiagnosticGateway:
    adapter_version = "fake/1.0"

    def diagnose(self) -> AutomationEnvironment:
        return AutomationEnvironment(
            agent_reach_available=True,
            opencli_available=True,
            browser_bridge_ready=False,
            plugin_ready=True,
            safe_message="请连接 OpenCLI 浏览器扩展",
        )


@pytest.fixture
def collection_client(tmp_path: Path) -> tuple[TestClient, FakeCoordinator, int]:
    database_url = f"sqlite:///{(tmp_path / 'collection-api.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    coordinator = FakeCoordinator()
    app = create_app(
        database_url=database_url,
        browser_gateway_factory=DiagnosticGateway,
        collection_coordinator_factory=lambda _executor: coordinator,
    )
    client = TestClient(app)
    fixtures_root = Path(__file__).parents[3] / "fixtures"
    catalog = json.loads((fixtures_root / "catalog" / "iphone17.json").read_text(encoding="utf-8"))
    assert client.post("/api/catalog/import", json=catalog).status_code == 200
    variant_id = client.get("/api/catalog/search", params={"q": "苹果17"}).json()["items"][0]["variants"][0]["id"]
    session_response = client.post(
        "/api/search-sessions",
        json={"variant_id": variant_id, "comparison_scope": "national"},
    )
    assert session_response.status_code == 201
    return client, coordinator, session_response.json()["id"]


def test_post_collection_run_creates_31_tasks_and_submits_once(
    collection_client: tuple[TestClient, FakeCoordinator, int],
) -> None:
    client, coordinator, session_id = collection_client

    response = client.post(
        f"/api/search-sessions/{session_id}/collection-runs",
        json={"platform": "jd"},
    )

    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "queued"
    assert run["total_region_count"] == 31
    assert coordinator.submitted == [run["id"]]
    tasks = client.get(f"/api/collection-runs/{run['id']}/tasks").json()
    assert len(tasks) == 31
    assert tasks[0]["province"] == "北京市"
    assert tasks[-1]["province"] == "新疆维吾尔自治区"
    assert tasks[0]["street"] == "奥运村街道"
    assert tasks[-1]["street"] == "解放南路街道"


def test_run_controls_are_idempotent_and_resume_resubmits(
    collection_client: tuple[TestClient, FakeCoordinator, int],
) -> None:
    client, coordinator, session_id = collection_client
    run_id = client.post(
        f"/api/search-sessions/{session_id}/collection-runs",
        json={"platform": "jd"},
    ).json()["id"]

    assert client.post(f"/api/collection-runs/{run_id}/pause").status_code == 200
    assert client.post(f"/api/collection-runs/{run_id}/pause").status_code == 200
    assert client.post(f"/api/collection-runs/{run_id}/resume").status_code == 200
    assert client.post(f"/api/collection-runs/{run_id}/resume").status_code == 200
    assert client.post(f"/api/collection-runs/{run_id}/stop").status_code == 200
    assert coordinator.submitted == [run_id, run_id, run_id, run_id]


def test_duplicate_and_missing_runs_use_structured_safe_errors(
    collection_client: tuple[TestClient, FakeCoordinator, int],
) -> None:
    client, _coordinator, session_id = collection_client
    assert client.post(
        f"/api/search-sessions/{session_id}/collection-runs",
        json={"platform": "jd"},
    ).status_code == 201

    duplicate = client.post(
        f"/api/search-sessions/{session_id}/collection-runs",
        json={"platform": "jd"},
    )
    missing = client.get("/api/collection-runs/999999")

    assert duplicate.status_code == 422
    assert duplicate.json()["detail"]["what_happened"] == "创建自动采集任务失败"
    assert missing.status_code == 404
    assert missing.json()["detail"]["partial_saved"] is False


def test_environment_endpoint_returns_only_safe_diagnostics(
    collection_client: tuple[TestClient, FakeCoordinator, int],
) -> None:
    client, _coordinator, _session_id = collection_client

    response = client.get("/api/automation/environment")

    assert response.status_code == 200
    assert response.json() == {
        "agent_reach_available": True,
        "opencli_available": True,
        "browser_bridge_ready": False,
        "plugin_ready": True,
        "safe_message": "请连接 OpenCLI 浏览器扩展",
    }


def test_app_restart_requeues_and_resubmits_interrupted_run(
    collection_client: tuple[TestClient, FakeCoordinator, int],
) -> None:
    client, _first_coordinator, session_id = collection_client
    run_id = client.post(
        f"/api/search-sessions/{session_id}/collection-runs",
        json={"platform": "jd"},
    ).json()["id"]
    with client.app.state.session_factory() as db:
        run = db.get(CollectionRun, run_id)
        first_task = db.get(CollectionRegionTask, 1)
        assert run is not None and first_task is not None
        run.status = "running"
        first_task.status = "running"
        db.commit()

    restarted_coordinator = FakeCoordinator()
    restarted = create_app(
        database_url=str(client.app.state.engine.url),
        browser_gateway_factory=DiagnosticGateway,
        collection_coordinator_factory=lambda _executor: restarted_coordinator,
    )

    assert restarted_coordinator.submitted == [run_id]
    with restarted.state.session_factory() as db:
        assert db.get(CollectionRun, run_id).status == "queued"
        assert db.get(CollectionRegionTask, 1).status == "queued"
