"""Test minimal de connexion HFSQL (lecture seule), via hfsql.py (iODBC ANSI).

    # Config dans settings.json (voir api/config.py).
    uv run python extractor/test_connect.py

N'affiche aucune donnée patient : seulement l'état de la connexion, le nombre
de tables visibles, et la présence des tables cibles.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hfsql  # noqa: E402
from api import config, trophy  # noqa: E402

h = config.settings()["hfsql"]
print(f"Connexion à {h['server']}:{h['port']}/{h['database']} …")
try:
    conn = trophy.make_connection()
except hfsql.HfsqlError as exc:
    sys.exit(f"ÉCHEC : {exc}")

tables = conn.tables()
print(f"OK. {len(tables)} table(s) visible(s).")
for name in ("Patients", "Agenda", "Praticiens"):
    print(f"  - {name:<12} {'présente' if name in tables else 'ABSENTE (nom différent ?)'}")
conn.close()
