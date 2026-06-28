"""Smoke tests so CI is green from day one. Real tests arrive in Phase 1."""

import importlib


def test_modules_import():
    for mod in ("ingestion.comexstat", "ingestion.bcb", "ingestion.cepea"):
        assert importlib.import_module(mod) is not None


def test_api_base_is_https():
    from ingestion import comexstat

    assert comexstat.API_BASE.startswith("https://")
