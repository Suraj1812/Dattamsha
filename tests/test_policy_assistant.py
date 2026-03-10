from fastapi.testclient import TestClient


def test_policy_query(client: TestClient) -> None:
    response = client.post(
        "/api/v1/assistant/policy-query",
        json={"question": "How many paid leave days are available?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "policy" in body["answer"].lower() or "paid leave" in body["answer"].lower()
    assert body["citation"]
