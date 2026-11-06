"""Tests du chargement de settings.json (sans base ni réseau)."""
import json

import pytest

from api import config


def _ecrire(tmp_path, data, monkeypatch):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("TROPHY_SETTINGS", str(p))
    config.settings.cache_clear()
    return p


VALIDE = {
    "hfsql": {"server": "s", "database": "Datas", "username": "u", "password": "p"},
    "api_key": "k",
}


def test_settings_valide(tmp_path, monkeypatch):
    _ecrire(tmp_path, VALIDE, monkeypatch)
    s = config.settings()
    assert s["api_key"] == "k"
    assert s["hfsql"]["port"] == 4902  # défaut appliqué


def test_hfsql_incomplet(tmp_path, monkeypatch):
    bad = {"hfsql": {"server": "s", "database": "Datas", "username": "u"}, "api_key": "k"}
    _ecrire(tmp_path, bad, monkeypatch)
    with pytest.raises(config.ConfigError):
        config.settings()


def test_api_key_manquante(tmp_path, monkeypatch):
    bad = {"hfsql": VALIDE["hfsql"]}
    _ecrire(tmp_path, bad, monkeypatch)
    with pytest.raises(config.ConfigError):
        config.settings()


def test_fichier_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("TROPHY_SETTINGS", str(tmp_path / "absent.json"))
    config.settings.cache_clear()
    with pytest.raises(config.ConfigError):
        config.settings()
