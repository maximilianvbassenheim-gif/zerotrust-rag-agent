"""Konnektor-Registry: neue Datenquellen registrieren sich hier selbst."""

from .base import CONNECTORS, Document, register  # noqa: F401
from . import claude_export, files  # noqa: F401  (Registrierung durch Import)
