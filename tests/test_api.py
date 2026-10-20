import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolierter Wissensspeicher pro Test
    from app.memory.store import MemoryStore

    monkeypatch.setattr(main, "store", MemoryStore(tmp_path / "api.db"))
    monkeypatch.setattr(settings, "app_api_key", None)
    return TestClient(main.app)


def fake_stream(messages, system_prompt):
    yield "Hallo "
    yield "Welt"


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["auth_required"] is False


def test_security_headers_present(client):
    res = client.get("/api/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in res.headers


def test_chat_streams_response(client, monkeypatch):
    monkeypatch.setattr(main, "stream_chat", fake_stream)
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hi"}], "use_memory": False},
    )
    assert res.status_code == 200
    assert res.text == "Hallo Welt"


def test_chat_injects_memory_context(client, monkeypatch):
    captured = {}

    def spy_stream(messages, system_prompt):
        captured["messages"] = messages
        yield "ok"

    monkeypatch.setattr(main, "stream_chat", spy_stream)
    main.store.add_chunk("test", "Projektnotiz", "Das Audit-Projekt startet im April.")

    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Wann startet das Audit-Projekt?"}]},
    )
    assert res.status_code == 200
    assert "<kontext>" in captured["messages"][-1]["content"]
    assert "Projektnotiz" in captured["messages"][-1]["content"]


def test_chat_rejects_assistant_last(client):
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "assistant", "content": "Ich bin zuletzt"}]},
    )
    assert res.status_code == 400


def test_api_key_enforced(client, monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "geheim123")
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert res.status_code == 401

    monkeypatch.setattr(main, "stream_chat", fake_stream)
    res = client.post(
        "/api/chat",
        headers={"X-API-Key": "geheim123"},
        json={"messages": [{"role": "user", "content": "Hi"}], "use_memory": False},
    )
    assert res.status_code == 200


def test_ingest_blocks_path_traversal(client):
    res = client.post("/api/ingest", json={"path": "../../etc/passwd"})
    assert res.status_code == 400


def test_ingest_unknown_path(client):
    res = client.post("/api/ingest", json={"path": "gibt-es-nicht.json"})
    assert res.status_code == 404


def test_chat_errors_are_marked_not_plain_text(client, monkeypatch):
    def broken_stream(messages, system_prompt):
        raise RuntimeError("boom")
        yield  # pragma: no cover — macht die Funktion zum Generator

    monkeypatch.setattr(main, "stream_chat", broken_stream)
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hi"}], "use_memory": False},
    )
    assert res.status_code == 200
    assert res.text.startswith(main.ERROR_MARKER)
    assert "boom" not in res.text  # keine internen Details an den Client


def test_soul_reload(client):
    res = client.post("/api/soul/reload")
    assert res.status_code == 200
    assert res.json()["reloaded"] is True


def test_index_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "SHAKA" in res.text
