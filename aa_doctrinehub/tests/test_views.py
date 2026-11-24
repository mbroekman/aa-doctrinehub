"""Tests for the page and JSON API views."""

import json
from unittest.mock import patch

import pytest
from allianceauth.tests.auth_utils import AuthUtils
from django.contrib.auth.models import Group
from django.urls import reverse

from aa_doctrinehub.models import Category, Doctrine, DoctrineFitting, SyncSettings
from aa_doctrinehub.services.fittings import import_eft

pytestmark = pytest.mark.django_db

EFT = "[Rifter, Tackle]\n\nDamage Control II"


def _user(*perms):
    user = AuthUtils.create_user("pilot")
    AuthUtils.add_main_character(user, "Doctrine Pilot", character_id=92001)
    for perm in perms:
        AuthUtils.add_permission_to_user_by_name(f"aa_doctrinehub.{perm}", user)
    return user


def _doctrine(name="Rifters", status=Doctrine.Status.ACTIVE):
    doctrine = Doctrine.objects.create(name=name, status=status)
    DoctrineFitting.objects.create(doctrine=doctrine, fitting=import_eft(EFT), role="tackle")
    return doctrine


def test_index_requires_basic_access(client):
    client.force_login(_user())
    assert client.get(reverse("aa_doctrinehub:index")).status_code == 302


def test_index_renders_spa(client):
    client.force_login(_user("basic_access"))
    response = client.get(reverse("aa_doctrinehub:index"))
    assert response.status_code == 200
    assert b"aa-doctrinehub-spa" in response.content


def test_doctrines_hides_drafts_and_restricted_categories(client):
    _doctrine("Visible")
    _doctrine("Draft", status=Doctrine.Status.DRAFT)
    restricted = _doctrine("Restricted")
    category = Category.objects.create(name="Capitals")
    category.visible_to_groups.add(Group.objects.create(name="SIG: Capitals"))
    restricted.categories.add(category)

    client.force_login(_user("basic_access"))
    data = client.get(reverse("aa_doctrinehub:api_doctrines")).json()
    assert [d["name"] for d in data["doctrines"]] == ["Visible"]
    assert data["doctrines"][0]["fittings"][0]["role"] == "tackle"


def test_doctrines_shows_restricted_category_to_group_member(client):
    restricted = _doctrine("Restricted")
    group = Group.objects.create(name="SIG: Capitals")
    category = Category.objects.create(name="Capitals")
    category.visible_to_groups.add(group)
    restricted.categories.add(category)

    user = _user("basic_access")
    user.groups.add(group)
    client.force_login(user)
    data = client.get(reverse("aa_doctrinehub:api_doctrines")).json()
    assert [d["name"] for d in data["doctrines"]] == ["Restricted"]


def test_doctrine_with_public_and_restricted_category_hidden_from_outsider(client):
    """A doctrine tagged with both a public category and a group-restricted
    one must stay hidden from users outside that group - the public
    category must not leak the restricted one."""
    restricted = _doctrine("Mixed")
    public_category = Category.objects.create(name="General")
    restricted_category = Category.objects.create(name="Capitals")
    restricted_category.visible_to_groups.add(Group.objects.create(name="SIG: Capitals"))
    restricted.categories.add(public_category, restricted_category)

    client.force_login(_user("basic_access"))
    data = client.get(reverse("aa_doctrinehub:api_doctrines")).json()
    assert data["doctrines"] == []


def test_fitting_detail_returns_eft_and_multibuy(client):
    fitting = import_eft(EFT)
    client.force_login(_user("basic_access"))
    data = client.get(reverse("aa_doctrinehub:api_fitting_detail", args=[fitting.pk])).json()
    assert data["version"]["eft"].startswith("[Rifter, Tackle]")
    assert data["version"]["multibuy"].startswith("Rifter x1")


def test_import_requires_manage_permission(client):
    client.force_login(_user("basic_access"))
    url = reverse("aa_doctrinehub:api_import_fitting")
    response = client.post(url, json.dumps({"eft": EFT}), content_type="application/json")
    assert response.status_code == 302


def test_import_creates_fitting_and_rejects_bad_eft(client):
    client.force_login(_user("basic_access", "manage_doctrines"))
    url = reverse("aa_doctrinehub:api_import_fitting")
    ok = client.post(url, json.dumps({"eft": EFT}), content_type="application/json")
    bad = client.post(url, json.dumps({"eft": "nonsense"}), content_type="application/json")
    assert ok.status_code == 201 and ok.json()["ship_type_name"] == "Rifter"
    assert bad.status_code == 400


def test_sync_settings_update_and_validation(client):
    client.force_login(_user("basic_access", "manage_doctrines"))
    url = reverse("aa_doctrinehub:api_sync_settings")
    response = client.post(
        url,
        json.dumps({"fittings_sync_enabled": True, "fittings_sync_interval_days": 7}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert SyncSettings.get_solo().fittings_sync_enabled is True
    bad = client.post(url, json.dumps({"fittings_sync_interval_days": 0}), content_type="application/json")
    assert bad.status_code == 400


def test_run_sync_without_fittings_app_returns_conflict(client):
    client.force_login(_user("basic_access", "manage_doctrines"))
    response = client.post(reverse("aa_doctrinehub:api_run_fittings_sync"))
    assert response.status_code == 409


def test_run_sync_queues_the_celery_task_instead_of_running_inline(client):
    """A large Fittings catalogue can take long enough to risk a request
    timeout, so "Sync now" must dispatch the existing Celery task rather
    than call sync_from_fittings_app() in the request/response cycle."""
    client.force_login(_user("basic_access", "manage_doctrines"))
    with (
        patch("aa_doctrinehub.views_spa_api.fittings_app_installed", return_value=True),
        patch("aa_doctrinehub.tasks.sync_from_fittings.delay") as mock_delay,
    ):
        response = client.post(reverse("aa_doctrinehub:api_run_fittings_sync"))
    assert response.status_code == 200
    assert response.json()["queued"] is True
    mock_delay.assert_called_once_with(force=True)
