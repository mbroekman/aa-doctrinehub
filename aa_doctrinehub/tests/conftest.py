"""Shared fixtures: no test may reach public ESI."""

import pytest


@pytest.fixture(autouse=True)
def _no_public_esi(monkeypatch):
    monkeypatch.setattr("aa_doctrinehub.services.types._esi_ids", lambda names: {})
    monkeypatch.setattr("aa_doctrinehub.services.types._esi_required_skills", lambda type_id: None)
    monkeypatch.setattr("aa_doctrinehub.services.types._resolve_type_names", lambda ids: {})
