"""API REST en LECTURE SEULE sur CS Trophy Gestion (HFSQL).

Expose : praticiens, patients, planning de rendez-vous par praticien.
Données de santé : à garder sur le réseau interne / VPN (Tailscale), jamais
exposée publiquement. Authentification par clé (en-tête X-API-Key).

Contraintes du pilote HFSQL (iODBC) :
- utilisable uniquement depuis le thread principal → endpoints en `async def`
  (exécutés sur la boucle d'événements, thread principal) ;
- une seule connexion par process → connexion unique ouverte au démarrage,
  réutilisée, accès sérialisés par un verrou.
Si la connexion est perdue, relancer le service (ex. systemd Restart=always).

Configuration dans settings.json (voir api/config.py). Lancement :
    uv run uvicorn api.app:app --host 127.0.0.1 --port 8333
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

import api.config as config
import api.trophy as trophy

log = logging.getLogger("trophy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # connexion unique, ouverte sur le thread principal au démarrage
    app.state.conn = trophy.make_connection()
    app.state.lock = asyncio.Lock()
    try:
        yield
    finally:
        try:
            app.state.conn.close()
        except Exception:
            pass


app = FastAPI(
    title="Trophy – API lecture seule",
    version="0.1.0",
    description="Patients et planning par praticien, en lecture seule, depuis HFSQL.",
    lifespan=lifespan,
)


def require_key(x_api_key: str = Header(default="")):
    expected = config.settings()["api_key"]  # validée non vide au démarrage
    if not hmac.compare_digest(x_api_key, expected):  # comparaison à temps constant
        raise HTTPException(401, "Clé API invalide ou absente (en-tête X-API-Key).")


async def run_db(fn):
    """Exécute fn(conn) sous verrou sur la connexion unique.

    Le pilote PC SOFT ne supporte PAS de rouvrir une connexion dans le même
    process (segfault), même après close(). Donc pas de reconnexion en vol :
    si la connexion est perdue (SQLSTATE 08xxx), on quitte le process et
    systemd (Restart=always) en relance un neuf avec une connexion saine.
    Les erreurs SQL (requête) remontent normalement (-> 502)."""
    async with app.state.lock:
        try:
            return fn(app.state.conn)
        except trophy.hfsql.HfsqlError as exc:
            if "[08" in str(exc):  # 08xxx = connexion perdue
                log.error("HFSQL connexion perdue, arrêt pour redémarrage : %s", exc)
                os._exit(1)
            raise


@app.exception_handler(ValueError)
def _bad_input(request, exc):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(trophy.hfsql.HfsqlError)
def _db_error(request, exc):
    log.error("HFSQL: %s", exc)  # détail dans les logs serveur, pas dans la réponse
    return JSONResponse(status_code=502, content={"detail": "Erreur base de données"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/practitioners", dependencies=[Depends(require_key)])
async def get_practitioners(include_inactive: bool = False):
    data = await run_db(trophy.practitioners)
    if not include_inactive:
        data = [p for p in data if not p["inactif"]]
    return data


@app.get("/patients", dependencies=[Depends(require_key)])
async def get_patients(
    q: str | None = Query(default=None, description="recherche nom/prénom"),
    practitioner: int | None = None,
    include_archived: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return await run_db(lambda c: trophy.patients(
        c, q=q, practitioner=practitioner, include_archived=include_archived,
        limit=limit, offset=offset))


@app.get("/patients/{num}", dependencies=[Depends(require_key)])
async def get_patient(num: int):
    p = await run_db(lambda c: trophy.patient(c, num))
    if not p:
        raise HTTPException(404, "Patient introuvable")
    return p


@app.get("/holidays", dependencies=[Depends(require_key)])
async def get_holidays(
    date_from: str = Query(..., alias="from", description="AAAA-MM-JJ"),
    date_to: str = Query(..., alias="to", description="AAAA-MM-JJ"),
):
    return await run_db(lambda c: trophy.holidays(c, date_from, date_to))


@app.get("/appointment-types", dependencies=[Depends(require_key)])
async def get_appointment_types():
    return await run_db(trophy.appointment_types)


@app.get("/appointments", dependencies=[Depends(require_key)])
async def get_appointments(
    practitioner: int = Query(..., description="NUM_PRATICIEN"),
    date_from: str = Query(..., alias="from", description="AAAA-MM-JJ"),
    date_to: str = Query(..., alias="to", description="AAAA-MM-JJ"),
    with_patient: bool = True,
):
    return await run_db(lambda c: trophy.appointments(
        c, practitioner, date_from, date_to, include_patient=with_patient))
