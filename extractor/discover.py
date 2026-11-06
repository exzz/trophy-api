"""Découverte, en LECTURE SEULE, du schéma HFSQL de CS Trophy Gestion.

Via hfsql.py (iODBC en ANSI) — pyodbc est incompatible avec le pilote PC SOFT
sous iODBC. Liste tables, colonnes et nombre de lignes, et écrit schema.json.
Aucune donnée patient n'est affichée : seulement noms et totaux.

    # Config dans settings.json (voir api/config.py).
    uv run python extractor/discover.py [--no-counts] [--like RDV] [--out schema.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hfsql  # noqa: E402
from api import config, trophy  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Découverte du schéma HFSQL Trophy (lecture seule).")
    ap.add_argument("--no-counts", action="store_true", help="ne pas compter les lignes")
    ap.add_argument("--like", help="ne garder que les tables dont le nom contient ce texte")
    ap.add_argument("--out", default="schema.json", help="fichier de sortie JSON")
    args = ap.parse_args()

    h = config.settings()["hfsql"]
    conn = trophy.make_connection()
    server, database = h["server"], h["database"]

    tables = conn.tables()
    if args.like:
        needle = args.like.lower()
        tables = [t for t in tables if needle in t.lower()]
    tables.sort()

    print(f"{len(tables)} table(s).\n")
    schema = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "server": server, "database": database, "tables": {},
    }
    for table in tables:
        entry = {"columns": conn.columns(table)}
        if not args.no_counts:
            try:
                entry["rows"] = conn.count(table)
            except hfsql.HfsqlError as exc:
                entry["rows"] = f"erreur: {str(exc)[:80]}"
        schema["tables"][table] = entry
        cols = ", ".join(c["name"] for c in entry["columns"][:8])
        more = " …" if len(entry["columns"]) > 8 else ""
        print(f"- {table:<32} {str(entry.get('rows','?')):>10} | {cols}{more}")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    print(f"\nSchéma écrit dans {args.out}")
    conn.close()


if __name__ == "__main__":
    main()
