# SHAKA — Dein persönlicher Claude-Agent mit Seele

[![CI](https://github.com/maximilianvbassenheim-gif/shaka-zerotrust-rag-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/maximilianvbassenheim-gif/shaka-zerotrust-rag-agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-streaming-009688)
![RAG](https://img.shields.io/badge/RAG-SQLite%20FTS5%20%2B%20BM25-orange)
![Security](https://img.shields.io/badge/security-zero--trust-red)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)

Shaka ist ein lokal laufender KI-Agent auf Basis der **Claude API** (Anthropic):
ein Chat-System mit eigener Persönlichkeit ("Seele"), einem **lokalen
Wissensspeicher** für deine Claude-Chats & Dokumente (RAG) und einer
**Zero-Trust-Sicherheitsarchitektur**. Alles außer dem eigentlichen Claude-API-Call
bleibt auf deinem Rechner — Zero-Cloud-Prinzip.

```
┌──────────────┐   Streaming    ┌───────────────┐   HTTPS (einziger    ┌─────────────┐
│  Web-UI      │ ─────────────▶ │ FastAPI       │   externer Call)     │ Claude API  │
│  (Browser)   │ ◀───────────── │ + Seele + RAG │ ───────────────────▶ │ Opus 4.8    │
└──────────────┘                └──────┬────────┘                      └─────────────┘
                                       │ lokal (SQLite FTS5)
                                ┌──────▼─────────┐
                                │ Wissensspeicher │ ◀── Konnektoren: Claude-Export,
                                │ data/memory.db  │     Dateien (.md/.txt/.pdf), …
                                └────────────────┘
```

## Features

- **Seele & Persönlichkeit** — `soul/soul.md` definiert Charakter, Werte und
  Sicherheitsregeln; `soul/personality.yaml` erlaubt individuelle Feinjustierung
  (Name, Sprache, Tonfall, eigene Regeln) ohne Code-Änderung.
- **Gedächtnis (RAG)** — Claude-Chat-Exporte und eigene Dokumente werden lokal in
  SQLite/FTS5 indexiert (BM25) und automatisch als Kontext in Antworten eingebunden.
- **Streaming-Chat** — Antworten erscheinen live Token für Token
  (Claude Opus 4.8, adaptives Thinking, Prompt-Caching für den System-Prompt).
- **Konnektor-Ökosystem** — Datenquellen sind Plugins (`app/connectors/`):
  `claude_export` (offizieller Anthropic-Export) und `files` sind eingebaut;
  weitere (Gmail, Drive, GitHub, …) lassen sich mit ~30 Zeilen ergänzen.
- **Zero-Trust-Security** — Details unten.

## Quickstart

Voraussetzung: Python 3.11+

**Ein-Befehl-Setup** (venv, Abhängigkeiten, .env mit Key-Abfrage, Ingestion, Start):

```bash
# Linux/macOS
./setup.sh

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Oder manuell:

```bash
# 1. Abhängigkeiten
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Konfiguration
cp .env.example .env
#    → ANTHROPIC_API_KEY in .env eintragen (https://platform.claude.com)

# 3. (Optional) Deine Claude-Chats einlesen
#    claude.ai → Einstellungen → Datenschutz → "Daten exportieren"
#    conversations.json aus der ZIP nach data/ legen, dann:
python scripts/ingest.py data/conversations.json

#    Eigene Notizen/Dokumente gehen genauso:
python scripts/ingest.py data/notizen/

# 4. Starten
uvicorn app.main:app --host 127.0.0.1 --port 8100
```

Dann im Browser: **http://127.0.0.1:8100**

## Die Agenten-Familie

SHAKA ist nicht allein: Im Header des UI wählst du zwischen mehreren Agenten —
jede/r mit eigener Seele, eigenem Tonfall und **eigenem, isoliertem Gedächtnis**:

| Agent | Rolle | Gedächtnis |
|---|---|---|
| **Shaka** | Der Copilot — loyal, direkt, M&A & Forensik | `data/memory.db` |
| **Bhaka** | Der Motivator — Training, Gewohnheiten, Momentum | `data/memory-bhaka.db` |
| **Sarotti** | Der Kreativkopf — Marketing, Texte, Storytelling | `data/memory-sarotti.db` |
| **Maria** | Die Organisatorin — Fristen, Finanzen, Papierkram | `data/memory-maria.db` |
| **Sophia** | Die Strategin — Langfrist-Entscheidungen, Sparring | `data/memory-sophia.db` |

Alle Profile liegen unter `souls/<name>/` (`soul.md` + `personality.yaml`).
`souls/_grundgesetz.md` enthält die gemeinsamen, nicht verhandelbaren
Sicherheitsregeln — sie gelten automatisch für jeden Agenten.

**Eigenen Agenten hinzufügen:** Ordner `souls/<name>/` mit einer `soul.md`
anlegen — fertig, er taucht nach Neustart im UI auf. Wissen gezielt füttern:

```bash
python scripts/ingest.py data/rezepte/ --agent maria
curl -X POST localhost:8100/api/ingest -H "Content-Type: application/json" \
     -d '{"path": "notizen/", "agent": "sophia"}'
```

## Die Seele individuell anpassen

Öffne `soul/personality.yaml` und ändere Name, Sprache, Anrede, Tonfall oder füge
unter `eigene_regeln` beliebige Zusatzanweisungen hinzu — z. B.:

```yaml
name: Jarvis
anrede: du
tonfall: ruhig, präzise, britisch-trocken
eigene_regeln:
  - "Sprich mich mit Max an."
  - "Fasse lange Antworten am Ende in 3 Bullet-Points zusammen."
```

Für tiefere Eingriffe (Charakter, Werte, Sicherheitsregeln) editiere
`soul/soul.md`. Änderungen greifen nach einem Neustart des Servers.

## Zero-Trust-Sicherheitsarchitektur

| Maßnahme | Umsetzung |
|---|---|
| Secrets nie im Code | Alles über `.env` (git-ignoriert); `.env.example` als Vorlage |
| Auth pro Request | Optionaler `APP_API_KEY` → Header `X-API-Key`, Vergleich in konstanter Zeit |
| Standardmäßig nur localhost | `HOST=127.0.0.1`; exponierter Host ohne Key wird vom Audit geblockt |
| Rate-Limiting | Sliding-Window pro Client-IP (Default 30/min) |
| Security-Header | Strikte CSP, `nosniff`, `frame-ancestors 'none'`, `no-referrer`, `no-store` |
| Request-Limits | Max. Body-Größe, Längen-/Rollenvalidierung aller Nachrichten |
| Prompt-Injection-Schutz | RAG-Kontext ist als `<kontext>`-**Daten** markiert; die Seele ignoriert Anweisungen daraus |
| Secret-Redaktion | API-Keys/Token/JWTs werden **vor** dem Speichern im Wissensspeicher redigiert |
| Pfad-Härtung | Ingestion nur innerhalb von `data/`, kein Path-Traversal |
| Keine offene API-Doku | `/docs`, `/redoc`, `openapi.json` deaktiviert |
| Audit-Gate | `python scripts/shaka_audit.py` — Secret-Scan & Konfig-Checks, läuft in CI |

**Shaka-Audit manuell ausführen:**

```bash
python scripts/shaka_audit.py
```

## API

| Endpoint | Methode | Beschreibung |
|---|---|---|
| `/api/health` | GET | Status, Modell, Chunk-Anzahl |
| `/api/chat` | POST | `{messages: [{role, content}], use_memory}` → Text-Stream |
| `/api/ingest` | POST | `{path, connector?}` — Pfad relativ zu `data/` |
| `/api/soul` | GET | Aktuelle Persönlichkeits-Konfiguration |

Bei gesetztem `APP_API_KEY` verlangen alle Endpoints außer `/api/health` den
Header `X-API-Key`.

## Eigene Konnektoren schreiben

```python
# app/connectors/mein_dienst.py
from collections.abc import Iterable
from pathlib import Path
from .base import Document, register

@register("mein_dienst")
def load(path: Path) -> Iterable[Document]:
    yield Document(source="mein_dienst", title="…", content="…")
```

Dann in `app/connectors/__init__.py` importieren — fertig. Ingestion:
`python scripts/ingest.py data/export.xyz --connector mein_dienst`

## Tests & CI

```bash
pip install -r requirements-dev.txt
pytest -q
```

GitHub Actions führt bei jedem Push Tests **und** das Shaka-Audit aus
(`.github/workflows/ci.yml`) — ein geleaktes Secret bricht den Build.

## RUFLO-Cockpit — Agenten-Schwärme ohne Kommandozeile

[ruflo](https://github.com/ruvnet/ruflo) (ehem. *Claude Flow*, 40k+ ⭐) ist ein
Agent-Meta-Harness für Multi-Agent-Schwärme auf Claude-Code-Basis. Das
**RUFLO-Cockpit** in diesem Repo macht es per Browser bedienbar: Buttons statt
CLI, Live-Konsole, deutsche Oberfläche.

```bash
# Linux/macOS                          # Windows (PowerShell)
./ruflo-cockpit.sh                     powershell -ExecutionPolicy Bypass -File .\ruflo-cockpit.ps1
```

→ **http://127.0.0.1:8200** — Status, Init, Agent-Typen, Hive-Mind,
Schwarm-Aufträge und Gedächtnis-Suche per Klick.

Zero-Trust auch hier: nur eine feste Befehls-Whitelist (kein freies Shell),
Argumente ohne Shell-Interpretation, Eingabe-Validierung, ein Befehl gleichzeitig,
15-min-Timeout, optionaler `COCKPIT_API_KEY`. Voraussetzungen: Node.js ≥ 20;
für echte Schwarm-Läufe zusätzlich Claude Code CLI + `ANTHROPIC_API_KEY`.

## Roadmap / Ökosystem-Ideen

- Weitere Konnektoren: Gmail/IMAP, Google Drive, GitHub-Repos, Obsidian-Vault
- Sprach-Interface (STT/TTS) für den "Jarvis-Modus"
- Embedding-basierte Suche als Ergänzung zu BM25
- Automatisierungen über n8n/MCP-Anbindung

## Sicherheitshinweis

Dieses Projekt sendet **ausschließlich** deine Chat-Nachrichten samt relevanter
Kontext-Auszüge an die Anthropic-API (`api.anthropic.com`). Der Wissensspeicher,
deine Exporte und deine Konfiguration verlassen deinen Rechner nicht.
