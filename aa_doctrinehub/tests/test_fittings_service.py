"""Tests for creating fittings and versions."""

import pytest

from aa_doctrinehub.models import Source
from aa_doctrinehub.services.fittings import import_eft, update_from_eft, version_eft, version_multibuy

pytestmark = pytest.mark.django_db

EFT = "[Rifter, Tackle]\n\nDamage Control II\n\nWarp Scrambler II\n\n200mm AutoCannon II, Republic Fleet EMP S"


def test_import_creates_local_fitting_with_first_version():
    fitting = import_eft(EFT)
    assert fitting.source == Source.LOCAL and fitting.is_editable
    assert fitting.ship_type_name == "Rifter"
    version = fitting.current_version
    assert version.number == 1
    assert version.items.count() == 3
    assert version_eft(version).startswith("[Rifter, Tackle]")


def test_update_adds_version():
    fitting = import_eft(EFT)
    update_from_eft(fitting, EFT.replace("Warp Scrambler II", "Warp Disruptor II"), change_note="Point")
    assert fitting.current_version.number == 2
    assert fitting.current_version.change_note == "Point"
    assert fitting.versions.count() == 2


def test_multibuy_includes_charges():
    lines = version_multibuy(import_eft(EFT).current_version).splitlines()
    assert lines[0] == "Rifter x1"
    assert "Republic Fleet EMP S x1" in lines
