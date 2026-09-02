from fastapi.testclient import TestClient


def test_history_returns_snapshots_in_time_order(
    flow_client: TestClient,
    completed_search: int,
    variant_id: int,
) -> None:
    response = flow_client.get("/api/price-history", params={"variant_id": variant_id})

    assert response.status_code == 200
    points = response.json()["points"]
    assert len(points) == 4
    assert [point["comparable_price_cents"] for point in points] == [499900, 504900, 509900, 519900]
    assert [point["captured_at"] for point in points] == sorted(point["captured_at"] for point in points)
    assert all(point["offer_id"] for point in points)
