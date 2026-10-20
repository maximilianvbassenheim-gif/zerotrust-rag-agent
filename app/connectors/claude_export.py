"""Konnektor für den offiziellen Anthropic-Datenexport (conversations.json).

Export anfordern: claude.ai → Einstellungen → Datenschutz → 'Daten exportieren'.
Die ZIP enthält u. a. conversations.json — diese Datei nach data/ legen und ingestieren.

Unterstützt beide bekannten Formate:
- alt: chat_messages[*].text
- neu: chat_messages[*].content = [{type: 'text', text: ...}, ...]
"""

import json
from collections.abc import Iterable
from pathlib import Path

from .base import Document, register

_ROLE_LABELS = {"human": "Mensch", "assistant": "Assistent"}


def _message_text(message: dict) -> str:
    text = message.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    content = message.get("content")
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p).strip()
    return ""


@register("claude_export")
def load(path: Path) -> Iterable[Document]:
    conversations = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(conversations, list):
        raise ValueError("conversations.json: erwartet eine Liste von Konversationen.")

    for conv in conversations:
        if not isinstance(conv, dict):
            continue
        title = conv.get("name") or conv.get("title") or "Unbenannte Konversation"
        created_at = conv.get("created_at") or ""
        lines: list[str] = []
        for message in conv.get("chat_messages") or []:
            if not isinstance(message, dict):
                continue
            body = _message_text(message)
            if not body:
                continue
            role = _ROLE_LABELS.get(message.get("sender", ""), message.get("sender", "?"))
            lines.append(f"{role}: {body}")
        if lines:
            yield Document(
                source=f"claude:{path.name}",
                title=str(title),
                content="\n".join(lines),
                created_at=str(created_at),
            )
