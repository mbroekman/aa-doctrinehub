"""Tests for the EFT parser and writer."""

import pytest

from aa_doctrinehub.services.eft import EftParseError, ExportItem, parse_eft, to_eft, to_multibuy

MUNINN = """[Muninn, Shield Muninn]

Damage Control II
Gyrostabilizer II
Gyrostabilizer II

Large Shield Extender II
Multispectrum Shield Hardener II
[Empty Med slot]

720mm Howitzer Artillery II, Republic Fleet Phased Plasma M
720mm Howitzer Artillery II, Republic Fleet Phased Plasma M /offline

Medium Core Defense Field Extender II
Medium Core Defense Field Extender II


Hornet EC-300 x2

Nanite Repair Paste x50
"""


def test_parse_header_and_slots():
    fit = parse_eft(MUNINN)
    assert fit.ship_type_name == "Muninn"
    assert fit.name == "Shield Muninn"
    flags = [i.flag for i in fit.items]
    assert flags[:3] == ["LoSlot0", "LoSlot1", "LoSlot2"]
    assert "MedSlot2" not in flags  # empty slot is skipped
    assert {"HiSlot0", "HiSlot1", "RigSlot0", "RigSlot1"} <= set(flags)


def test_parse_charges_offline_and_bays():
    fit = parse_eft(MUNINN)
    guns = [i for i in fit.items if i.flag.startswith("HiSlot")]
    assert guns[0].charge_name == "Republic Fleet Phased Plasma M"
    assert guns[1].is_offline is True
    drones = [i for i in fit.items if i.flag == "DroneBay"]
    cargo = [i for i in fit.items if i.flag == "Cargo"]
    assert drones[0].type_name == "Hornet EC-300" and drones[0].quantity == 2
    assert cargo[0].type_name == "Nanite Repair Paste" and cargo[0].quantity == 50


@pytest.mark.parametrize("text", ["", "Muninn, Shield Muninn", "[Muninn]"])
def test_parse_rejects_bad_header(text):
    with pytest.raises(EftParseError):
        parse_eft(text)


def test_round_trip_keeps_items():
    fit = parse_eft(MUNINN)
    items = [ExportItem(i.flag, i.type_name, i.quantity, i.charge_name, i.is_offline) for i in fit.items]
    again = parse_eft(to_eft(fit.ship_type_name, fit.name, items))
    assert again.items == [i for i in fit.items]


def test_multibuy_counts_items_per_amount():
    text = to_multibuy(
        "Muninn",
        [ExportItem("LoSlot0", "Gyrostabilizer II"), ExportItem("LoSlot1", "Gyrostabilizer II")],
        amount=3,
    )
    assert text.splitlines() == ["Muninn x3", "Gyrostabilizer II x6"]
