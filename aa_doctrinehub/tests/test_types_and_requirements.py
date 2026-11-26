"""Local (EFT) fittings get a hull type ID and dogma skill requirements."""

import pytest
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.tests.auth_utils import AuthUtils
from django.core.management import call_command

from aa_doctrinehub.models import CharacterSkill, CharacterSkillSnapshot, FittingItem
from aa_doctrinehub.services import types
from aa_doctrinehub.services.eft import BAY_FLAGS
from aa_doctrinehub.services.fittings import import_eft, refresh_incomplete_fittings, update_from_eft, version_eft
from aa_doctrinehub.services.types import CATEGORY_DRONE, CATEGORY_FIGHTER
from aa_doctrinehub.services.skills import evaluate_fitting_for_snapshot, evaluate_fitting_for_user

pytestmark = pytest.mark.django_db

HEL = 22852
SUPERCARRIERS = 24311
MINMATAR_CARRIER = 24314
EFT = "[Hel, My Hel]\n\nDamage Control II\n\nTemplar I x10"
IDS = {"Hel": HEL, "Damage Control II": 2048, "Templar I": 23055}
SKILLS = {
    HEL: [(SUPERCARRIERS, 1), (MINMATAR_CARRIER, 5)],
    2048: [(3318, 1)],
    23055: [(23069, 1)],
}


@pytest.fixture
def fake_esi(monkeypatch):
    monkeypatch.setattr(types, "_esi_ids", lambda names: {n: IDS[n] for n in names if n in IDS})
    monkeypatch.setattr(types, "_esi_required_skills", lambda tid: SKILLS.get(tid, []))
    monkeypatch.setattr(types, "_resolve_type_names", lambda ids: {i: f"Skill {i}" for i in ids})


def _user_with_snapshot(skills: dict[int, int]):
    user = AuthUtils.create_user("pilot")
    char = AuthUtils.add_main_character_2(user, "Pilot", 94001, corp_id=2001, corp_name="Corp")
    CharacterOwnership.objects.create(user=user, character=char, owner_hash="hash-94001")
    snap = CharacterSkillSnapshot.objects.create(character=char, sync_status=CharacterSkillSnapshot.SyncStatus.OK)
    for sid, lvl in skills.items():
        CharacterSkill.objects.create(snapshot=snap, skill_id=sid, active_skill_level=lvl, trained_skill_level=lvl)
    return user, snap


def test_import_resolves_hull_and_items_and_skills(fake_esi):
    fitting = import_eft(EFT)
    assert fitting.ship_type_id == HEL
    version = fitting.current_version
    assert set(FittingItem.objects.filter(version=version).values_list("type_id", flat=True)) == {2048, 23055}
    reqs = {r.skill_id: r.required_level for r in version.skill_requirements.all()}
    assert reqs == {SUPERCARRIERS: 1, MINMATAR_CARRIER: 5, 3318: 1, 23069: 1}


def test_pilot_without_capital_skills_is_red(fake_esi):
    fitting = import_eft(EFT)
    user, _snap = _user_with_snapshot({3318: 5, 23069: 5})
    assert evaluate_fitting_for_user(fitting.current_version, user)["status"] == "red"


def test_no_requirements_is_unknown_not_green():
    _user, snap = _user_with_snapshot({3318: 5})
    assert evaluate_fitting_for_snapshot([], snap)["status"] == "unknown"


def test_import_without_esi_leaves_status_unknown():
    fitting = import_eft(EFT)
    assert fitting.ship_type_id is None
    user, _snap = _user_with_snapshot({})
    assert evaluate_fitting_for_user(fitting.current_version, user)["status"] == "unknown"


def test_failed_lookup_keeps_existing_requirements(fake_esi, monkeypatch):
    fitting = import_eft(EFT)
    monkeypatch.setattr(types, "_esi_required_skills", lambda tid: None)
    update_from_eft(fitting, EFT.replace("My Hel", "My Hel v2"))
    # New version starts empty; a failed lookup must not invent "no requirements".
    assert fitting.current_version.skill_requirements.count() == 0
    monkeypatch.setattr(types, "_esi_required_skills", lambda tid: SKILLS.get(tid, []))
    assert refresh_incomplete_fittings() == 1
    assert fitting.current_version.skill_requirements.count() == 4


def test_backfill_command_fixes_existing_fitting(fake_esi, monkeypatch):
    monkeypatch.setattr(types, "_esi_ids", lambda names: {})
    fitting = import_eft(EFT)
    assert fitting.ship_type_id is None
    monkeypatch.setattr(types, "_esi_ids", lambda names: {n: IDS[n] for n in names if n in IDS})
    call_command("doctrinehub_refresh_requirements")
    fitting.refresh_from_db()
    assert fitting.ship_type_id == HEL
    assert fitting.current_version.skill_requirements.filter(skill_id=MINMATAR_CARRIER).exists()


TITAN_EFT = "[Ragnarok, Titan]\n\nDamage Control II\n\nStrontium Clathrates x5000\nHobgoblin II x5"
CATEGORIES = {2048: 7, 16275: 4, 2456: CATEGORY_DRONE, 23055: CATEGORY_FIGHTER}
TITAN_IDS = {"Ragnarok": 23773, "Damage Control II": 2048, "Strontium Clathrates": 16275, "Hobgoblin II": 2456}


@pytest.fixture
def fake_categories(monkeypatch):
    ids = {**IDS, **TITAN_IDS}
    monkeypatch.setattr(types, "_esi_ids", lambda names: {n: ids[n] for n in names if n in ids})
    monkeypatch.setattr(types, "_esi_category", lambda tid: CATEGORIES.get(tid))


def _bays(fitting):
    return {i.type_name: i.flag for i in fitting.current_version.items.all() if i.flag in BAY_FLAGS}


def test_cargo_only_block_is_not_drones(fake_categories):
    fitting = import_eft("[Ragnarok, Titan]\n\nDamage Control II\n\nStrontium Clathrates x5000")
    assert _bays(fitting) == {"Strontium Clathrates": "Cargo"}


def test_mixed_bay_block_is_split_by_type(fake_categories):
    fitting = import_eft(TITAN_EFT)
    assert _bays(fitting) == {"Strontium Clathrates": "Cargo", "Hobgoblin II": "DroneBay"}


def test_fighters_go_to_fighter_bay(fake_categories):
    fitting = import_eft(EFT)
    assert _bays(fitting) == {"Templar I": "FighterBay"}
    assert "Templar I x10" in version_eft(fitting.current_version)


def test_unknown_types_keep_positional_guess():
    fitting = import_eft("[Ragnarok, Titan]\n\nDamage Control II\n\nStrontium Clathrates x5000")
    assert _bays(fitting) == {"Strontium Clathrates": "DroneBay"}


def test_refresh_fixes_bays_of_existing_local_fitting(fake_categories, monkeypatch):
    monkeypatch.setattr(types, "_esi_ids", lambda names: {})
    fitting = import_eft("[Ragnarok, Titan]\n\nDamage Control II\n\nStrontium Clathrates x5000")
    assert _bays(fitting) == {"Strontium Clathrates": "DroneBay"}
    monkeypatch.setattr(types, "_esi_ids", lambda names: {n: TITAN_IDS[n] for n in names if n in TITAN_IDS})
    call_command("doctrinehub_refresh_requirements", "--all")
    assert _bays(fitting) == {"Strontium Clathrates": "Cargo"}
