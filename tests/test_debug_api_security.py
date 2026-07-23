from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_debug_api_is_hidden_when_disabled(monkeypatch):
    monkeypatch.setenv("FSS_DEBUG_API_ENABLED", "false")

    response = client.get("/debug/status")

    assert response.status_code == 404


def test_debug_api_requires_configured_token(monkeypatch):
    monkeypatch.setenv("FSS_DEBUG_API_ENABLED", "true")
    monkeypatch.setenv("FSS_DEBUG_API_TOKEN", "secret-token")

    denied = client.get("/debug/status")
    allowed = client.get(
        "/debug/status", headers={"X-FSS-Debug-Token": "secret-token"}
    )

    assert denied.status_code == 403
    assert allowed.status_code == 200
