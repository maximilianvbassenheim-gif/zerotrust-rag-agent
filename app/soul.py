"""Seelen-Verwaltung für die Agenten-Familie.

Profile:
- "shaka"       → Legacy-Verzeichnis soul/ (bleibt unverändert, inkl. bestehender Daten)
- alle anderen  → souls/<name>/ mit soul.md + personality.yaml

souls/_grundgesetz.md enthält die nicht verhandelbaren Sicherheitsregeln und wird
jedem Profil angehängt, dessen soul.md keinen eigenen Sicherheitsblock mitbringt.

System-Prompts werden pro Agent gecacht (Prompt-Caching-freundlich) —
/api/soul/reload leert den Cache ohne Neustart.
"""

import re
from functools import lru_cache

import yaml

from .config import BASE_DIR, SOUL_DIR

SOULS_DIR = BASE_DIR / "souls"
GRUNDGESETZ_FILE = SOULS_DIR / "_grundgesetz.md"
DEFAULT_AGENT = "shaka"

# Agent-Namen sind Verzeichnis- und DB-Bestandteile → strikt validieren (Zero-Trust)
AGENT_NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")

DEFAULT_PERSONALITY: dict = {
    "name": "Shaka",
    "sprache": "Deutsch",
    "anrede": "du",
    "tonfall": "warm, direkt, humorvoll, fokussiert",
    "emojis": "sparsam",
    "fokus": [],
    "eigene_regeln": [],
}


def _profile_dir(agent: str):
    return SOUL_DIR if agent == DEFAULT_AGENT else SOULS_DIR / agent


def list_agents() -> list[str]:
    """Alle verfügbaren Agenten-Profile (Default zuerst, Rest alphabetisch)."""
    agents = [DEFAULT_AGENT] if (SOUL_DIR / "soul.md").exists() else []
    if SOULS_DIR.exists():
        for entry in sorted(SOULS_DIR.iterdir()):
            if (
                entry.is_dir()
                and not entry.name.startswith("_")
                and AGENT_NAME_RE.match(entry.name)
                and (entry / "soul.md").exists()
            ):
                agents.append(entry.name)
    return agents


def load_personality(agent: str = DEFAULT_AGENT) -> dict:
    merged = dict(DEFAULT_PERSONALITY)
    merged["name"] = agent.capitalize()
    pfile = _profile_dir(agent) / "personality.yaml"
    if pfile.exists():
        raw = yaml.safe_load(pfile.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raw = {}
        merged.update({k: v for k, v in raw.items() if v is not None})
    return merged


def _render_personality(p: dict) -> str:
    lines = [
        "## Individuelle Anpassung (personality.yaml)",
        f"- Dein Name: {p['name']}",
        f"- Sprache: {p['sprache']} (antworte standardmäßig in dieser Sprache)",
        f"- Anrede: {p['anrede']}",
        f"- Tonfall: {p['tonfall']}",
        f"- Emoji-Nutzung: {p['emojis']}",
    ]
    if p.get("fokus"):
        lines.append("- Themenschwerpunkte: " + ", ".join(str(f) for f in p["fokus"]))
    if p.get("eigene_regeln"):
        lines.append("- Zusätzliche Regeln:")
        lines.extend(f"  - {r}" for r in p["eigene_regeln"])
    return "\n".join(lines)


@lru_cache(maxsize=32)
def build_system_prompt(agent: str = DEFAULT_AGENT) -> str:
    soul_file = _profile_dir(agent) / "soul.md"
    soul = soul_file.read_text(encoding="utf-8") if soul_file.exists() else ""

    parts = [soul.strip()]
    # Grundgesetz anhängen, falls das Profil keinen eigenen Sicherheitsblock hat
    if "Sicherheitsregeln" not in soul and GRUNDGESETZ_FILE.exists():
        parts.append(GRUNDGESETZ_FILE.read_text(encoding="utf-8").strip())
    parts.append(_render_personality(load_personality(agent)))
    return "\n\n".join(parts) + "\n"
