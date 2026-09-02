from fastapi.testclient import TestClient


def test_platform_status_distinguishes_fixture_from_live_validation(
    flow_client: TestClient,
    completed_search: int,
) -> None:
    response = flow_client.get("/api/platforms/status")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"platform": "jd", "fixture_status": "passing", "live_status": "not_validated"},
        {"platform": "taobao", "fixture_status": "passing", "live_status": "not_validated"},
        {"platform": "pdd", "fixture_status": "passing", "live_status": "not_validated"},
    ]
