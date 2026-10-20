"""Ingestion: Dokumente aus Konnektoren laden, Secrets redigieren, chunken, speichern."""

from dataclasses import dataclass
from pathlib import Path

from ..connectors import CONNECTORS
from ..security import redact_secrets
from .store import MemoryStore

CHUNK_SIZE = 1400
CHUNK_OVERLAP = 200


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Teilt Text in überlappende Chunks, bevorzugt an Absatz-/Zeilengrenzen."""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # Weiche Grenze: letzter Absatz- oder Zeilenumbruch im Fenster
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind("\n"))
            if cut > size // 2:
                end = start + cut
        chunk = text[start:end].strip()
        # Reine Teilmengen des Vorgänger-Chunks überspringen (entstehen bei
        # Whitespace-Läufen durch die Overlap-Rückstellung) — sie verzerren BM25.
        if chunk and not (chunks and chunk in chunks[-1]):
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


@dataclass
class IngestResult:
    documents: int = 0
    chunks: int = 0
    duplicates: int = 0


def detect_connector(path: Path) -> str:
    if path.is_file() and path.suffix.lower() == ".json":
        return "claude_export"
    return "files"


def ingest_path(store: MemoryStore, path: Path, connector: str | None = None) -> IngestResult:
    name = connector or detect_connector(path)
    loader = CONNECTORS.get(name)
    if loader is None:
        raise ValueError(f"Unbekannter Konnektor: {name}. Verfügbar: {sorted(CONNECTORS)}")

    result = IngestResult()
    for doc in loader(path):
        result.documents += 1
        clean = redact_secrets(doc.content)
        for chunk in chunk_text(clean):
            if store.add_chunk(doc.source, doc.title, chunk, doc.created_at):
                result.chunks += 1
            else:
                result.duplicates += 1
    return result
