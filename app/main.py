"""SHAKA — persönlicher Claude-Agent. FastAPI-Backend mit Streaming-Chat und lokalem RAG."""

import logging
from typing import Literal

import anthropic
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import DATA_DIR, WEB_DIR, settings
from .llm import stream_chat
from .memory.ingest import ingest_path
from .memory.store import MemoryStore, format_context
from .security import (
    BodySizeLimitMiddleware,
    SecurityHeadersMiddleware,
    rate_limit,
    require_api_key,
)
from .soul import (
    AGENT_NAME_RE,
    DEFAULT_AGENT,
    build_system_prompt,
    list_agents,
    load_personality,
)

logger = logging.getLogger("shaka")

app = FastAPI(
    title="SHAKA — persönlicher Claude-Agent",
    # Zero-Trust: keine öffentliche API-Doku-Oberfläche
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Reihenfolge: zuletzt hinzugefügt = äußerste Schicht. SecurityHeaders muss außen
# liegen, damit auch Short-Circuit-Antworten (413/411) die Header tragen.
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

if settings.cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

store = MemoryStore(settings.db_path)

# Jeder Agent hat sein eigenes, isoliertes Gedächtnis. Der Default-Agent nutzt
# weiterhin data/memory.db (bestehende Ingestionen bleiben erhalten).
_stores: dict[str, MemoryStore] = {}


def get_store(agent: str = DEFAULT_AGENT) -> MemoryStore:
    if agent == DEFAULT_AGENT:
        return store
    if agent not in _stores:
        _stores[agent] = MemoryStore(DATA_DIR / f"memory-{agent}.db")
    return _stores[agent]


def _require_agent(agent: str) -> None:
    if agent not in list_agents():
        raise HTTPException(status_code=404, detail=f"Unbekannter Agent: {agent}")


PROTECTED = [Depends(require_api_key), Depends(rate_limit)]

# ASCII Record Separator — kollidiert nicht mit normalem Text/Markdown
ERROR_MARKER = "\x1e"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=settings.max_message_chars)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=settings.max_history_messages)
    use_memory: bool = True
    agent: str = Field(default=DEFAULT_AGENT, pattern=AGENT_NAME_RE.pattern)


class IngestRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    connector: str | None = None
    agent: str = Field(default=DEFAULT_AGENT, pattern=AGENT_NAME_RE.pattern)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": settings.model,
        "memory_chunks": store.count(),
        "auth_required": bool(settings.app_api_key),
        "agents": list_agents(),
    }


@app.get("/api/agents")
def agents() -> dict:
    """Namen + Anzeigenamen der Agenten-Familie (fürs UI, keine sensiblen Details)."""
    return {
        "agents": [
            {"name": name, "display": load_personality(name)["name"]}
            for name in list_agents()
        ]
    }


@app.get("/api/soul", dependencies=PROTECTED)
def soul(agent: str = DEFAULT_AGENT) -> dict:
    _require_agent(agent)
    return {"agent": agent, "personality": load_personality(agent)}


@app.post("/api/soul/reload", dependencies=PROTECTED)
def soul_reload(agent: str = DEFAULT_AGENT) -> dict:
    """Lädt soul.md + personality.yaml aller Agenten neu, ohne Server-Neustart."""
    _require_agent(agent)
    build_system_prompt.cache_clear()
    return {"reloaded": True, "agent": agent, "personality": load_personality(agent)}


@app.post("/api/chat", dependencies=PROTECTED)
def chat(req: ChatRequest) -> StreamingResponse:
    _require_agent(req.agent)
    messages = [m.model_dump() for m in req.messages]
    if messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Die letzte Nachricht muss vom Nutzer stammen.")

    if req.use_memory:
        hits = get_store(req.agent).search(messages[-1]["content"], settings.max_context_chunks)
        if hits:
            messages[-1]["content"] = (
                format_context(hits) + "\n\n" + messages[-1]["content"]
            )

    system_prompt = build_system_prompt(req.agent)

    def generate():
        # ERROR_MARKER trennt Fehlermeldungen vom echten Antworttext: das UI zeigt
        # sie an, speichert sie aber nicht als Assistent-Antwort im Verlauf.
        try:
            yield from stream_chat(messages, system_prompt)
        except (anthropic.AuthenticationError, TypeError):
            # TypeError: SDK 0.115+ wirft "Could not resolve authentication method",
            # wenn gar kein Key konfiguriert ist (weder .env noch Umgebung).
            yield ERROR_MARKER + "Auth-Fehler: ANTHROPIC_API_KEY fehlt oder ist ungültig — siehe .env"
        except anthropic.RateLimitError:
            yield ERROR_MARKER + "Claude-API-Rate-Limit erreicht — bitte kurz warten"
        except anthropic.APIStatusError as exc:
            logger.error("Claude-API-Fehler %s: %s", exc.status_code, exc.message)
            yield ERROR_MARKER + f"Claude-API-Fehler {exc.status_code} — Details im Server-Log"
        except anthropic.APIConnectionError:
            yield ERROR_MARKER + "Netzwerkfehler: Claude-API nicht erreichbar"
        except Exception as exc:  # noqa: BLE001 — nie Stacktraces an den Client streamen
            logger.exception("Unerwarteter Fehler im Chat-Stream")
            yield ERROR_MARKER + f"Unerwarteter Fehler ({type(exc).__name__}) — Details im Server-Log"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@app.post("/api/ingest", dependencies=PROTECTED)
def ingest(req: IngestRequest) -> dict:
    # Zero-Trust: Ingestion nur aus dem lokalen data/-Verzeichnis, kein Pfad-Ausbruch
    data_root = DATA_DIR.resolve()
    target = (data_root / req.path).resolve()
    if not target.is_relative_to(data_root):
        raise HTTPException(status_code=400, detail="Pfad muss innerhalb von data/ liegen.")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Nicht gefunden: data/{req.path}")

    _require_agent(req.agent)
    target_store = get_store(req.agent)
    try:
        result = ingest_path(target_store, target, connector=req.connector)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "agent": req.agent,
        "documents": result.documents,
        "new_chunks": result.chunks,
        "duplicates": result.duplicates,
        "memory_chunks_total": target_store.count(),
    }


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
