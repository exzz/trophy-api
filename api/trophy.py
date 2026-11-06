"""Couche d'accès aux données Trophy (HFSQL), LECTURE SEULE.

S'appuie sur extractor/hfsql.py (iODBC ANSI). Nettoie les valeurs CHAR
(espaces de remplissage), convertit dates (AAAAMMJJ) et heures, et expose
trois lectures : praticiens, patients, planning par praticien.

Aucune écriture. Les entrées externes sont validées (entiers, dates) ou
échappées (recherche par nom) pour fermer toute injection SQL, le client
ctypes n'ayant pas de requêtes paramétrées.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "extractor"))
import hfsql  # noqa: E402

from . import config  # noqa: E402

_DATE8 = re.compile(r"^\d{8}$")


def make_connection():
    """Ouvre UNE connexion HFSQL depuis settings.json. Le pilote PC SOFT ne
    supporte pas d'ouvrir une 2e connexion dans le même process (segfault) :
    l'API en garde une seule, ouverte au démarrage et réutilisée (sérialisée)."""
    h = config.settings()["hfsql"]
    # Le chemin du pilote est de l'infra (figé au conteneur) : env + défaut repo.
    driver = os.environ.get("TROPHY_DRIVER", str(config.BASE_DIR / "driver" / "wd250hfo64.so"))
    return hfsql.Connection(
        h["server"], str(h["port"]), h["database"], h["username"], h["password"], driver,
    )


# --- nettoyage / conversions ---
def s(v):
    return v.strip() if isinstance(v, str) else v


def _date(v):
    """AAAAMMJJ -> 'AAAA-MM-JJ' ; 0 / vide -> None."""
    v = s(v)
    if not v or not _DATE8.match(v) or v == "00000000":
        return None
    return f"{v[0:4]}-{v[4:6]}-{v[6:8]}"


def _time(v):
    """'HH:MM:SS.mmm' -> 'HH:MM' ; vide -> None."""
    v = s(v)
    if not v:
        return None
    return v[:5]


def _duree_min(v):
    """'HH:MM:SS.mmm' -> durée en minutes ; vide/invalide -> None."""
    v = s(v)
    if not v or ":" not in v:
        return None
    try:
        h, m = v.split(":")[:2]
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def _dt(d, t):
    d = _date(d)
    if not d:
        return None
    t = _time(t) or "00:00"
    return f"{d}T{t}"


def _bool(v):
    return s(v) in ("1", "-1", "O", "o", "T", "true", "True")


# Correspondance index de colonne horaire (OUVERT*_n, n=1..7) -> jour ISO
# (1=lundi .. 7=dimanche). VÉRIFIÉ sur données réelles (2026-11-04) : pour les
# praticiens 1 et 2, les jours ouverts n=1,2,4,5 correspondent aux jours à fort
# volume de RDV (lun/mar/jeu/ven) et n=3,6,7 aux jours fermés (mer/sam/dim).
# Donc n = jour ISO : mapping identité.
_COL_TO_ISO = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}


def _creneau(ouvert, debut, fin):
    o = _bool(ouvert)
    # Jour fermé : les heures stockées restent celles du modèle -> on ne les
    # expose pas, pour qu'un consommateur ne réserve pas sur un créneau fermé.
    return {"ouvert": o, "debut": _time(debut) if o else None,
            "fin": _time(fin) if o else None}


def _schedule(d):
    """Construit les horaires hebdo d'un praticien depuis les colonnes
    OUVERT*_n / HH*_n (n=1..7). Renvoie 7 jours triés par jour ISO."""
    days = []
    for n in range(1, 8):
        days.append({
            "jour_semaine": _COL_TO_ISO[n],
            "matin": _creneau(d.get(f"OUVERTMATIN_{n}"),
                              d.get(f"HHDEBMATIN_{n}"), d.get(f"HHFINMATIN_{n}")),
            "apres_midi": _creneau(d.get(f"OUVERTAM_{n}"),
                                   d.get(f"HHDEBAM_{n}"), d.get(f"HHFINAM_{n}")),
        })
    return sorted(days, key=lambda x: x["jour_semaine"])


_SCHED_COLS = ", ".join(
    f"OUVERTMATIN_{n}, HHDEBMATIN_{n}, HHFINMATIN_{n}, "
    f"OUVERTAM_{n}, HHDEBAM_{n}, HHFINAM_{n}"
    for n in range(1, 8)
)


# --- validation des entrées ---
def as_int(v, name):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{name} doit être un entier")


def iso_to_8(d, name):
    """'AAAA-MM-JJ' (ou objet date) -> 'AAAAMMJJ', validé."""
    if isinstance(d, date):
        return d.strftime("%Y%m%d")
    d = str(d).strip()
    try:
        return date.fromisoformat(d).strftime("%Y%m%d")
    except ValueError:
        raise ValueError(f"{name} doit être une date AAAA-MM-JJ")


def esc(v):
    """Échappe une chaîne pour un littéral SQL (quotes doublées)."""
    return str(v).replace("'", "''")


# --- lectures ---
def practitioners(conn):
    cols, rows = conn.query(
        "SELECT NUM_PRATICIEN, NOM_PRENOM, TITRE, E_MAIL, TELEPHONE, PROFIL_INACTIF, "
        f"{_SCHED_COLS} FROM Praticiens ORDER BY NOM_PRENOM"
    )
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        out.append({
            "id": as_int(d["NUM_PRATICIEN"], "NUM_PRATICIEN"),
            "nom": s(d["NOM_PRENOM"]),
            "titre": s(d["TITRE"]),
            "email": s(d["E_MAIL"]),
            "telephone": s(d["TELEPHONE"]),
            "inactif": _bool(d.get("PROFIL_INACTIF")),
            "horaires": _schedule(d),
        })
    return out


_PATIENT_COLS = (
    "NUM_PATIENT, CODE_PATIENT, NOM_PATIENT, PRENOM_PATIENT, NOM_J_FILLE, SEXE, "
    "DATE_NAISSANCE, ADRESSE1, ADRESSE2, CP, VILLE, TEL_PERSONNEL, TEL_PORTABLE, "
    "NUM_PRATICIEN, DATE_CREATION, DERNIER_RDV, ARCHIVE, SMSACTIF"
)


def _patient_row(cols, r):
    d = dict(zip(cols, r))
    return {
        "id": as_int(d["NUM_PATIENT"], "NUM_PATIENT"),
        "code": s(d["CODE_PATIENT"]),
        "nom": s(d["NOM_PATIENT"]),
        "prenom": s(d["PRENOM_PATIENT"]),
        "nom_jeune_fille": s(d.get("NOM_J_FILLE")),
        "sexe": s(d["SEXE"]),
        "naissance": _date(d["DATE_NAISSANCE"]),
        "adresse1": s(d["ADRESSE1"]),
        "adresse2": s(d["ADRESSE2"]),
        "cp": s(d["CP"]),
        "ville": s(d["VILLE"]),
        "tel": s(d["TEL_PERSONNEL"]),
        "mobile": s(d["TEL_PORTABLE"]),
        "praticien_id": as_int(d["NUM_PRATICIEN"] or 0, "NUM_PRATICIEN"),
        "cree_le": _date(d["DATE_CREATION"]),
        "dernier_rdv": _date(d["DERNIER_RDV"]),
        "archive": _bool(d["ARCHIVE"]),
        "sms_actif": _bool(d["SMSACTIF"]),
    }


def patients(conn, q=None, practitioner=None, include_archived=False,
             limit=100, offset=0):
    where = []
    if not include_archived:
        where.append("ARCHIVE = 0")
    if practitioner is not None:
        where.append(f"NUM_PRATICIEN = {as_int(practitioner, 'practitioner')}")
    if q:
        term = esc(q.strip()[:40])  # tronquer AVANT d'échapper (sinon coupe une paire '')
        where.append(f"(NOM_PATIENT LIKE '%{term}%' OR PRENOM_PATIENT LIKE '%{term}%')")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    sql = (f"SELECT {_PATIENT_COLS} FROM Patients{clause} "
           f"ORDER BY DATE_CREATION DESC, NUM_PATIENT DESC LIMIT {limit} OFFSET {offset}")
    cols, rows = conn.query(sql)
    return [_patient_row(cols, r) for r in rows]


def patient(conn, num):
    num = as_int(num, "num")
    cols, rows = conn.query(f"SELECT {_PATIENT_COLS} FROM Patients WHERE NUM_PATIENT = {num}")
    return _patient_row(cols, rows[0]) if rows else None


def appointments(conn, practitioner, date_from, date_to, include_patient=True):
    prat = as_int(practitioner, "practitioner")
    d1 = iso_to_8(date_from, "from")
    d2 = iso_to_8(date_to, "to")
    sql = (
        "SELECT a.NUM_ID, a.NUM_PRATICIEN, a.DATE_DEBUT, a.HEURE_DEBUT, "
        "a.DATE_FIN, a.HEURE_FIN, a.NUM_PATIENT, p.NOM_PATIENT, p.PRENOM_PATIENT, "
        "p.TEL_PORTABLE, p.TEL_PERSONNEL, p.SMSACTIF, "
        "a.NUM_TYPERDV, t.LibelleRDV, a.LIBELLE, a.PASVENU, a.RAPPELSMS, a.DATE_PRISERDV "
        "FROM Agenda a "
        "LEFT JOIN Patients p ON p.NUM_PATIENT = a.NUM_PATIENT "
        "LEFT JOIN TypeRDV t ON t.Num_TypeRDV = a.NUM_TYPERDV "
        f"WHERE a.NUM_PRATICIEN = {prat} "
        f"AND a.DATE_DEBUT >= '{d1}' AND a.DATE_DEBUT <= '{d2}' "
        "ORDER BY a.DATE_DEBUT, a.HEURE_DEBUT"
    )
    cols, rows = conn.query(sql)
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        num_pat = s(d["NUM_PATIENT"])
        item = {
            "id": as_int(d["NUM_ID"], "NUM_ID"),
            "praticien_id": prat,
            "debut": _dt(d["DATE_DEBUT"], d["HEURE_DEBUT"]),
            "fin": _dt(d["DATE_FIN"], d["HEURE_FIN"]),
            "type": s(d["LibelleRDV"]) or s(d["LIBELLE"]),
            "libelle": s(d["LIBELLE"]),
            "absent": _bool(d["PASVENU"]),
            "rappel_sms": _bool(d["RAPPELSMS"]),
            "pris_le": _date(d["DATE_PRISERDV"]),
        }
        nt = s(d["NUM_TYPERDV"])
        item["type_id"] = int(nt) if nt and nt.isdigit() else None
        if include_patient:
            pid = int(num_pat) if num_pat and num_pat.isdigit() else None
            item["patient"] = None if not pid else {
                "id": pid,
                "nom": s(d["NOM_PATIENT"]),
                "prenom": s(d["PRENOM_PATIENT"]),
                "mobile": s(d["TEL_PORTABLE"]),
                "tel": s(d["TEL_PERSONNEL"]),
                "sms_actif": _bool(d["SMSACTIF"]),
            }
        out.append(item)
    return out


def holidays(conn, date_from, date_to):
    d1 = iso_to_8(date_from, "from")
    d2 = iso_to_8(date_to, "to")
    cols, rows = conn.query(
        "SELECT DATE_JF, LIBELLE_JF FROM J_Feries "
        f"WHERE DATE_JF >= '{d1}' AND DATE_JF <= '{d2}' ORDER BY DATE_JF"
    )
    return [{"date": _date(r[0]), "libelle": s(r[1])} for r in rows]


def appointment_types(conn):
    cols, rows = conn.query(
        "SELECT NUM_TYPERDV, LIBELLERDV, RDV_EVENT, DUREE_RDV "
        "FROM TypeRDV ORDER BY LIBELLERDV"
    )
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        out.append({
            "id": as_int(d["NUM_TYPERDV"], "NUM_TYPERDV"),
            "libelle": s(d["LIBELLERDV"]),
            # RDV_EVENT : 1 = rendez-vous patient, 2 = événement / plage bloquée
            "rdv_event": as_int(d["RDV_EVENT"] or 0, "RDV_EVENT"),
            "evenement": s(d["RDV_EVENT"]) == "2",
            "duree_min": _duree_min(d["DUREE_RDV"]),
        })
    return out
