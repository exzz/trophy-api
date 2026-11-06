"""Configuration : `settings.json` à la racine du projet (hors git).

Même principe que sterilog/medirappel : un fichier JSON, dont le chemin peut
être surchargé par `TROPHY_SETTINGS` (tests, conteneur). Lu une fois, validé :
un fichier absent ou invalide empêche le démarrage.

Forme attendue (voir settings.example.json) :
    {"hfsql": {"server","port","database","username","password"}, "api_key"}
"""

from __future__ import annotations

import json
import os
from functools import cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class ConfigError(Exception):
    """Configuration absente ou invalide : l'application refuse de démarrer."""


def chemin() -> Path:
    return Path(os.environ.get("TROPHY_SETTINGS", BASE_DIR / "settings.json"))


@cache
def settings() -> dict:
    p = chemin()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Lecture impossible de {p} : {exc}") from exc
    except ValueError as exc:
        raise ConfigError(f"{p} n'est pas un JSON valide.") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{p} doit contenir un objet JSON.")

    h = data.get("hfsql")
    if not isinstance(h, dict) or not all(
        h.get(k) for k in ("server", "database", "username", "password")
    ):
        raise ConfigError(f"{p} : hfsql.{{server,database,username,password}} sont requis.")
    h.setdefault("port", 4902)

    if not data.get("api_key"):
        raise ConfigError(f"{p} : api_key est requis.")
    return data
