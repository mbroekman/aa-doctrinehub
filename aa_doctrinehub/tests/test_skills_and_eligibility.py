"""Tests for Phase 2: ESI skill sync, dogma skill requirements, traffic lights, skill plan, and gap analysis."""

from unittest.mock import patch

import pytest
from allianceauth.tests.auth_utils import AuthUtils
from django.urls import reverse
from esi.models import Scope, Token

from aa_doctrinehub.models import (
    CharacterAsset,
    CharacterImplant,
    CharacterSkill,
    CharacterSkillSnapshot,
    Doctrine,
    DoctrineFitting,
    FittingSkillRequirement,
)
from aa_doctrinehub.services.esi_sync import REQUIRED_SCOPES, sync_character_snapshot
from aa_doctrinehub.services.fittings import import_eft
from aa_doctrinehub.services.skills import (
    compliance_overview,
    evaluate_fitting_for_user,
    export_skill_plan,
    extract_dogma_skills_for_version,
)

pytestmark = pytest.mark.django_db

EFT = "[Rifter, Tackle]\n\nDamage Control II"


def _make_user_with_token(username="pilot1", char_id=93001):
    user = AuthUtils.create_user(username)
    AuthUtils.add_main_character(user, f"Char {char_id}", character_id=char_id)
    user.profile.refresh_from_db()
    char = user.profile.main_character
    assert char is not None
    token = Token.objects.create(
        user=user,
        character_id=char_id,
        character_name=char.character_name,
        character_owner_hash=f"hash-{char_id}",
        access_token="access-123",
        refresh_token="refresh-123",
    )
    for scope_name in REQUIRED_SCOPES:
        scope, _ = Scope.objects.get_or_create(name=scope_name)
        token.scopes.add(scope)
    return user, char


def test_esi_sync_stores_skills_implants_assets_and_handles_errors():
    _user, char = _make_user_with_token("syncer", 93002)

    def fake_fetcher(url, _token, _params):
        if url.endswith("/skills/"):
            return {
                "total_sp": 5000000,
                "unallocated_sp": 1000,
                "skills": [
                    {
                        "skill_id": 3300,
                        "trained_skill_level": 5,
                        "active_skill_level": 5,
                        "skillpoints_in_skill": 256000,
                    }
                ],
            }, {}
        if url.endswith("/implants/"):
            return [9899], {}
        if url.endswith("/assets/"):
            return [
                {
                    "item_id": 1001,
                    "type_id": 587,
                    "location_id": 60003760,
                    "location_flag": "Hangar",
                    "location_type": "station",
                    "quantity": 1,
                    "is_singleton": True,
                }
            ], {"X-Pages": "1"}
        raise AssertionError(url)

    with patch.object(Token, "valid_access_token", return_value="tok"):
        snap = sync_character_snapshot(char, fetcher=fake_fetcher, resolve_names=False)

    assert snap.sync_status == CharacterSkillSnapshot.SyncStatus.OK
    assert snap.total_sp == 5000000
    assert CharacterSkill.objects.filter(snapshot=snap, skill_id=3300, active_skill_level=5).exists()
    assert CharacterImplant.objects.filter(snapshot=snap, type_id=9899).exists()
    assert CharacterAsset.objects.filter(character=char, item_id=1001, type_id=587).exists()

    def failing_fetcher(_url, _token, _params):
        raise RuntimeError("ESI 503")

    with patch.object(Token, "valid_access_token", return_value="tok"):
        snap = sync_character_snapshot(char, fetcher=failing_fetcher, resolve_names=False)
    assert snap.sync_status == CharacterSkillSnapshot.SyncStatus.ERROR
    assert "ESI 503" in snap.last_error


def test_dogma_extraction_preserves_manual_and_evaluates_traffic_lights():
    user, char = _make_user_with_token("flyer", 93003)
    fitting = import_eft(EFT)
    fitting.ship_type_id = 587
    fitting.save(update_fields=["ship_type_id"])
    version = fitting.current_version
    assert version is not None

    # Manual extra requirement
    FittingSkillRequirement.objects.create(
        version=version,
        skill_id=3426,
        skill_name="CPU Management",
        required_level=4,
        recommended_level=5,
        source=FittingSkillRequirement.RequirementSource.MANUAL,
    )

    def fake_dogma(type_ids):
        assert 587 in type_ids
        return {587: [(3328, "Minmatar Frigate", 1)]}

    extract_dogma_skills_for_version(version, dogma_lookup=fake_dogma)
    assert version.skill_requirements.count() == 2

    # Without snapshot -> unknown
    assert evaluate_fitting_for_user(version, user)["status"] == "unknown"

    snap = CharacterSkillSnapshot.objects.create(
        character=char,
        total_sp=100000,
        sync_status=CharacterSkillSnapshot.SyncStatus.OK,
    )
    CharacterSkill.objects.create(
        snapshot=snap,
        skill_id=3328,
        skill_name="Minmatar Frigate",
        active_skill_level=1,
        trained_skill_level=1,
    )
    # Missing CPU Management 4 -> red
    assert evaluate_fitting_for_user(version, user)["status"] == "red"

    # Train CPU Management to 4 (meets minimum, below recommended 5) -> yellow
    CharacterSkill.objects.create(
        snapshot=snap,
        skill_id=3426,
        skill_name="CPU Management",
        active_skill_level=4,
        trained_skill_level=4,
    )
    assert evaluate_fitting_for_user(version, user)["status"] == "yellow"
    assert export_skill_plan(version, snapshot=snap, target="recommended") == "CPU Management 5"

    # Train CPU Management to 5 -> green
    CharacterSkill.objects.filter(snapshot=snap, skill_id=3426).update(active_skill_level=5)
    assert evaluate_fitting_for_user(version, user)["status"] == "green"
    assert export_skill_plan(version, snapshot=snap, target="recommended") == ""


def test_compliance_overview_and_gap_analysis(client):
    user, char = _make_user_with_token("viewer", 93004)
    AuthUtils.add_permission_to_user_by_name("aa_doctrinehub.basic_access", user)
    AuthUtils.add_permission_to_user_by_name("aa_doctrinehub.view_compliance", user)

    fitting = import_eft(EFT)
    version = fitting.current_version
    assert version is not None
    FittingSkillRequirement.objects.create(
        version=version, skill_id=3426, skill_name="CPU Management", required_level=5, recommended_level=5
    )
    doctrine = Doctrine.objects.create(name="Tackle Wing", status=Doctrine.Status.ACTIVE)
    DoctrineFitting.objects.create(doctrine=doctrine, fitting=fitting, role="tackle", is_required=True)

    snap = CharacterSkillSnapshot.objects.create(
        character=char, total_sp=1000, sync_status=CharacterSkillSnapshot.SyncStatus.OK
    )
    CharacterSkill.objects.create(snapshot=snap, skill_id=3426, skill_name="CPU Management", active_skill_level=3)

    overview = compliance_overview(Doctrine.objects.filter(pk=doctrine.pk))
    assert overview["gaps"][0]["skill_name"] == "CPU Management"
    assert overview["gaps"][0]["blocked_members"] == 1

    client.force_login(user)
    resp = client.get(reverse("aa_doctrinehub:api_compliance_overview"))
    assert resp.status_code == 200
    assert resp.json()["doctrines"][0]["ready_members"] == 0
