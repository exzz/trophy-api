"""Tests des fonctions pures de la couche données (aucune base, aucun réseau).

Garde notamment l'invariant anti-injection de la recherche `q` : le terme doit
toujours produire un nombre pair de quotes dans le SQL (fix : tronquer avant
d'échapper).
"""
import pytest

from api import trophy


def test_date():
    assert trophy._date("20260112") == "2026-01-12"
    assert trophy._date("00000000") is None
    assert trophy._date("") is None
    assert trophy._date("2026") is None


def test_time_et_duree():
    assert trophy._time("08:30:00.000") == "08:30"
    assert trophy._time("") is None
    assert trophy._duree_min("00:45:00.000") == 45
    assert trophy._duree_min("01:00:00.000") == 60
    assert trophy._duree_min("00:00:00.000") == 0
    assert trophy._duree_min("") is None
    assert trophy._duree_min(None) is None


def test_bool():
    assert trophy._bool("1") and trophy._bool("-1") and trophy._bool("O")
    assert not trophy._bool("0")
    assert not trophy._bool("")


def test_iso_to_8():
    assert trophy.iso_to_8("2026-01-05", "from") == "20260105"
    with pytest.raises(ValueError):
        trophy.iso_to_8("2026-13-99", "from")


def test_esc():
    assert trophy.esc("a'b") == "a''b"


def test_as_int():
    assert trophy.as_int("  7 ", "x") == 7
    with pytest.raises(ValueError):
        trophy.as_int("abc", "x")


def test_schedule():
    row = {}
    for n in range(1, 8):
        for p in ("OUVERTMATIN", "HHDEBMATIN", "HHFINMATIN",
                  "OUVERTAM", "HHDEBAM", "HHFINAM"):
            row[f"{p}_{n}"] = ""
    row["OUVERTMATIN_1"] = "1"
    row["HHDEBMATIN_1"] = "08:00:00.000"
    row["HHFINMATIN_1"] = "12:00:00.000"
    sch = trophy._schedule(row)
    assert [j["jour_semaine"] for j in sch] == [1, 2, 3, 4, 5, 6, 7]  # trié, n=1=lundi
    assert sch[0]["matin"] == {"ouvert": True, "debut": "08:00", "fin": "12:00"}
    # jour fermé : heures masquées
    assert sch[0]["apres_midi"] == {"ouvert": False, "debut": None, "fin": None}
    assert sch[1]["matin"] == {"ouvert": False, "debut": None, "fin": None}


class _FakeConn:
    """Capture le dernier SQL exécuté, renvoie un résultat vide."""
    def __init__(self):
        self.sql = None

    def query(self, sql):
        self.sql = sql
        return [], []


def test_recherche_q_quotes_equilibrees():
    # une quote placée pile à la limite de troncature ne doit pas rester seule
    c = _FakeConn()
    trophy.patients(c, q="A" * 39 + "'")
    assert c.sql.count("'") % 2 == 0
