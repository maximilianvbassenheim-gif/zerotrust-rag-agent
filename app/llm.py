"""Claude-Anbindung: Streaming-Chat über die Anthropic Messages API.

- Modell: claude-opus-4-8 (adaptives Thinking, kein temperature/top_p — auf 4.8 entfernt)
- System-Prompt wird mit cache_control markiert (Prompt-Caching, stabiler Präfix)
- Streaming vermeidet HTTP-Timeouts bei großen max_tokens
"""

from collections.abc import Iterator

import anthropic

from .config import settings

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        kwargs: dict = {}
        if settings.anthropic_api_key:
            kwargs["api_key"] = settings.anthropic_api_key
        _client = anthropic.Anthropic(**kwargs)
    return _client


def stream_chat(messages: list[dict], system_prompt: str) -> Iterator[str]:
    """Streamt die Antwort-Text-Deltas von Claude."""
    client = get_client()
    with client.messages.stream(
        model=settings.model,
        max_tokens=settings.max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": settings.effort},
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    ) as stream:
        yield from stream.text_stream
