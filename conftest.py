"""Legt die Repo-Wurzel in den Importpfad, damit `from app.main import app`
und die uebrigen `app.*`-Importe in den Tests aufloesen."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
