"""Datei-Konnektor: liest .md/.txt/.pdf aus einer Datei oder rekursiv aus einem Ordner."""

import logging
from collections.abc import Iterable
from pathlib import Path

from .base import Document, register

logger = logging.getLogger(__name__)

TEXT_SUFFIXES = {".md", ".txt"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB pro Datei


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _load_file(path: Path) -> Document | None:
    if path.stat().st_size > MAX_FILE_BYTES:
        logger.warning("Übersprungen (zu groß): %s", path)
        return None
    suffix = path.suffix.lower()
    try:
        if suffix in TEXT_SUFFIXES:
            content = path.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".pdf":
            content = _read_pdf(path)
        else:
            return None
    except Exception:
        logger.exception("Konnte Datei nicht lesen: %s", path)
        return None
    if not content.strip():
        return None
    return Document(source=f"file:{path.name}", title=path.stem, content=content)


@register("files")
def load(path: Path) -> Iterable[Document]:
    if path.is_file():
        doc = _load_file(path)
        if doc:
            yield doc
        return
    root = path.resolve()
    for child in sorted(path.rglob("*")):
        # Dot-Filter nur auf den Pfad RELATIV zur Ingest-Wurzel — sonst blockiert
        # ein verstecktes Eltern-Verzeichnis (~/.local/…) die gesamte Ingestion.
        relative_parts = child.relative_to(path).parts
        if child.is_dir() or any(part.startswith(".") for part in relative_parts):
            continue
        # Symlinks können aus dem Verzeichnis-Jail ausbrechen — überspringen,
        # ebenso Kinder, deren Realpfad außerhalb des Wurzelverzeichnisses liegt.
        if child.is_symlink() or not child.resolve().is_relative_to(root):
            logger.warning("Übersprungen (Symlink/Pfad außerhalb): %s", child)
            continue
        doc = _load_file(child)
        if doc:
            yield doc
