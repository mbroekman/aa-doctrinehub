"""Tests for Phase 4: Hangar check, shortages, and SRP killmail comparison."""

import pytest
from allianceauth.tests.auth_utils import AuthUtils
from django.urls import reverse

from aa_doctrinehub.models import CharacterAsset, Doctrine, DoctrineFitting, FittingItem
from aa_doctrinehub.services.fittings import import_eft
from aa_doctrinehub.services.integrations import (
    compare_killmail_to_fitting,
    compute_doctrine_shortages,
    hangar_check_for_user,
)

pytestmark = pytest.mark.django_db

EFT = "[Rifter, Tackle]\n\nDamage Control II"


def test_hangar_check_and_shortages_and_srp(client):
    user = AuthUtils.create_user("hangarpilot")
    AuthUtils.add_main_character(user, "Hangar Char", character_id=95001)
    user.profile.refresh_from_db()
    char = user.profile.main_character
    assert char is not None
    AuthUtils.add_permission_to_user_by_name("aa_doctrinehub.basic_access", user)

    fitting = import_eft(EFT)
    fitting.ship_type_id = 587
    fitting.save(update_fields=["ship_type_id"])
    version = fitting.current_version
    assert version is not None
    FittingItem.objects.filter(version=version, type_name="Damage Control II").update(type_id=2048)

    doctrine = Doctrine.objects.create(name="Frigate Wing", status=Doctrine.Status.ACTIVE)
    DoctrineFitting.objects.create(doctrine=doctrine, fitting=fitting, role="tackle", target_count=5)

    # Ship + fitted Damage Control II in Hangar
    CharacterAsset.objects.create(
        character=char,
        item_id=7001,
        type_id=587,
        type_name="Rifter",
        location_id=60003760,
        location_flag="Hangar",
        location_type="station",
        quantity=1,
        is_singleton=True,
    )
    CharacterAsset.objects.create(
        character=char,
        item_id=7002,
        type_id=2048,
        type_name="Damage Control II",
        location_id=7001,
        location_flag="LoSlot0",
        location_type="item",
        quantity=1,
        is_singleton=False,
    )

    matches = hangar_check_for_user(user)
    assert len(matches) == 1
    assert matches[0]["match_status"] == "full"
    assert matches[0]["match_pct"] == 100

    shortages = compute_doctrine_shortages(doctrine)
    assert shortages[0]["target_count"] == 5
    assert shortages[0]["owned_count"] == 1
    assert shortages[0]["shortage"] == 4

    # SRP comparison
    killmail = {
        "victim": {
            "ship_type_id": 587,
            "items": [{"flag": 11, "item_type_id": 2048, "quantity_destroyed": 1, "quantity_dropped": 0}],
        }
    }
    srp = compare_killmail_to_fitting(killmail, version)
    assert srp["hull_match"] is True
    assert srp["compliance_pct"] == 100

    client.force_login(user)
    resp = client.post(
        reverse("aa_doctrinehub:api_srp_compare"),
        data={"fitting_id": fitting.pk, "killmail": killmail},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["compliance_pct"] == 100
