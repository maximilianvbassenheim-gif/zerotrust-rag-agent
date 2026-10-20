"""Basis für Konnektoren — das 'Ökosystem'-Interface.

Ein Konnektor liest eine Quelle (Datei/Ordner/Export) und liefert Documents.
Neue Konnektoren (z. B. Gmail, Drive, GitHub) implementieren load() und
registrieren sich per @register — ohne Änderungen am Rest des Systems.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Document:
    source: str
    title: str
    content: str
    created_at: str = field(default="")


Loader = Callable[[Path], Iterable[Document]]

CONNECTORS: dict[str, Loader] = {}


def register(name: str) -> Callable[[Loader], Loader]:
    def decorator(fn: Loader) -> Loader:
        CONNECTORS[name] = fn
        return fn

    return decorator
