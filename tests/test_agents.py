import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.memory.store import MemoryStore
from app.soul import build_system_prompt, list_agents, load_personality

FAMILY = ["shaka", "bhaka", "sarotti", "maria", "sophia"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolierte Speicher pro Test: Default-Store + Agenten-Stores unter tmp_path
    monkeypatch.setattr(main, "store", MemoryStore(tmp_path / "shaka.db"))
    monkeypatch.setattr(main, "_stores", {})
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "app_api_key", None)
    return TestClient(main.app)


def test_family_registered():
    agents = list_agents()
    for name in FAMILY:
        assert name in agents, f"{name} fehlt in list_agents()"


def test_new_agents_inherit_grundgesetz():
    build_system_prompt.cache_clear()
    for name in ["bhaka", "sarotti", "maria", "sophia"]:
        prompt = build_system_prompt(name)
        assert "Grundgesetz" in prompt, f"{name}: Grundgesetz fehlt"
        assert "keine Anweisungen" in prompt, f"{name}: Injektionsschutz fehlt"
        assert load_personality(name)["name"].lower() == name


def test_shaka_keeps_own_security_block():
    build_system_prompt.cache_clear()
    prompt = build_system_prompt("shaka")
    assert "Sicherheitsregeln" in prompt
    # Kein doppelter Block: Shakas soul.md bringt eigene Regeln mit
    assert "Grundgesetz (gilt für jeden Agenten" not in prompt


def test_agents_endpoint_lists_family(client):
    res = client.get("/api/agents")
    assert res.status_code == 200
    names = [a["name"] for a in res.json()["agents"]]
    for name in FAMILY:
        assert name in names


def test_memory_is_isolated_per_agent(client, monkeypatch):
    captured = {}

    def spy(messages, system_prompt):
        captured["content"] = messages[-1]["content"]
        captured["system"] = system_prompt
        yield "ok"

    monkeypatch.setattr(main, "stream_chat", spy)

    # Wissen NUR in Marias Gedächtnis ablegen
    main.get_store("maria").add_chunk("test", "Fristenliste", "Die IKK-Frist endet am 15. August.")

    # Maria sieht ihren Kontext …
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Wann endet die IKK-Frist?"}], "agent": "maria"},
    )
    assert res.status_code == 200
    assert "<kontext>" in captured["content"]
    assert "Maria" in captured["system"]

    # … Shaka bei derselben Frage nicht (getrennte Speicher)
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Wann endet die IKK-Frist?"}], "agent": "shaka"},
    )
    assert res.status_code == 200
    assert "<kontext>" not in captured["content"]


def test_chat_unknown_agent_rejected(client):
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hi"}], "agent": "unbekannt"},
    )
    assert res.status_code == 404


def test_chat_invalid_agent_name_rejected(client):
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hi"}], "agent": "../evil"},
    )
    assert res.status_code == 422  # Pydantic-Pattern blockt Pfad-Tricks


def test_ingest_into_agent_store(client, tmp_path):
    doc = tmp_path / "notiz.md"
    doc.write_text("Sarotti-Kampagne: Der Claim lautet Momentum statt Meetings.", encoding="utf-8")

    res = client.post("/api/ingest", json={"path": "notiz.md", "agent": "sarotti"})
    assert res.status_code == 200
    body = res.json()
    assert body["agent"] == "sarotti"
    assert body["new_chunks"] == 1

    assert main.get_store("sarotti").count() == 1
    assert main.store.count() == 0  # Default-Speicher unberührt
