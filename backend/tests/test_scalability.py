from fastapi.testclient import TestClient


def test_snapshot_refresh_and_paginated_risks(client: TestClient) -> None:
    ingest = client.post("/api/v1/ingest/sample")
    assert ingest.status_code == 200

    refresh = client.post("/api/v1/insights/refresh-risk-snapshots?batch_size=5")
    assert refresh.status_code == 200
    assert refresh.json()["processed_employees"] >= 1

    page_1 = client.get("/api/v1/insights/risks?limit=3&offset=0")
    page_2 = client.get("/api/v1/insights/risks?limit=3&offset=3")

    assert page_1.status_code == 200
    assert page_2.status_code == 200
    assert len(page_1.json()) <= 3
    assert len(page_2.json()) <= 3

    if page_1.json() and page_2.json():
        assert page_1.json()[0]["employee_id"] != page_2.json()[0]["employee_id"]


def test_nudge_listing_is_paginated(client: TestClient) -> None:
    ingest = client.post("/api/v1/ingest/sample")
    assert ingest.status_code == 200

    generated = client.post("/api/v1/nudges/generate")
    assert generated.status_code == 200

    page = client.get("/api/v1/nudges?status=open&limit=1&offset=0")
    assert page.status_code == 200
    assert len(page.json()) <= 1
