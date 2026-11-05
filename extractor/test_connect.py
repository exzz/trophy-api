"""Test minimal de connexion HFSQL (lecture seule), via hfsql.py (iODBC ANSI).

    source ../env.sh
    export TROPHY_UID=api_lecture TROPHY_PWD=...
    python extractor/test_connect.py

N'affiche aucune donnée patient : seulement l'état de la connexion, le nombre
de tables visibles, et la présence des tables cibles.
"""

from __future__ import annotations

import os
import sys

import hfsql

server = os.environ.get("TROPHY_SERVER", "100.79.174.114")
port = os.environ.get("TROPHY_PORT", "4902")
database = os.environ.get("TROPHY_DB", "Datas")
driver = os.environ["TROPHY_DRIVER"]
uid = os.environ.get("TROPHY_UID")
pwd = os.environ.get("TROPHY_PWD")

if not uid or pwd is None:
    sys.exit("Définir TROPHY_UID et TROPHY_PWD (compte HFSQL en lecture seule).")

print(f"Connexion à {server}:{port}/{database} …")
try:
    conn = hfsql.Connection(server, port, database, uid, pwd, driver)
except hfsql.HfsqlError as exc:
    sys.exit(f"ÉCHEC : {exc}")

tables = conn.tables()
print(f"OK. {len(tables)} table(s) visible(s).")
for name in ("Patients", "Agenda", "Praticiens"):
    print(f"  - {name:<12} {'présente' if name in tables else 'ABSENTE (nom différent ?)'}")
conn.close()
