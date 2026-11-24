"""Tests for the Fittings sync."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from aa_doctrinehub.models import Category, Doctrine, DoctrineFitting, Fitting, Source, SyncSettings
from aa_doctrinehub.services.fittings import ReadOnlyFittingError, import_eft, update_from_eft
from aa_doctrinehub.services.fittings_sync import (
    SourceCategory,
    SourceDoctrine,
    SourceFitting,
    SourceItem,
    SourceSnapshot,
    apply_snapshot,
    sync_from_fittings_app,
)
from aa_doctrinehub.tasks import fittings_sync_due, sync_from_fittings

pytestmark = pytest.mark.django_db


def _fitting(external_id=10, gyros=2):
    return SourceFitting(
        external_id=external_id,
        name="Shield Muninn",
        description="Main DPS",
        ship_type_id=12015,
        ship_type_name="Muninn",
        eft="",
        items=[
            SourceItem(flag=f"LoSlot{i}", type_id=519, type_name="Gyrostabilizer II", quantity=1) for i in range(gyros)
        ],
    )


def _snapshot(gyros=2, with_doctrine=True, group_ids=None):
    snap = SourceSnapshot(fittings=[_fitting(gyros=gyros)])
    if with_doctrine:
        snap.doctrines.append(
            SourceDoctrine(external_id=5, name="Shield HAC", description="", icon_url="", fitting_ids=[10])
        )
    snap.categories.append(
        SourceCategory(
            external_id=7,
            name="Alliance",
            color="#ff0000",
            group_ids=group_ids or [],
            fitting_ids=[10],
            doctrine_ids=[5],
        )
    )
    return snap


def test_first_sync_creates_read_only_records():
    result = apply_snapshot(_snapshot())
    fitting = Fitting.objects.get(source=Source.FITTINGS, external_id=10)
    doctrine = Doctrine.objects.get(source=Source.FITTINGS, external_id=5)
    assert result.fittings_created == 1 and result.doctrines_created == 1
    assert fitting.is_editable is False
    assert fitting.current_version.number == 1
    assert fitting.current_version.items.first().type_id == 519
    assert "[Muninn, Shield Muninn]" in fitting.current_version.eft
    assert list(doctrine.fittings.all()) == [fitting]
    assert Category.objects.get(external_id=7).doctrines.get() == doctrine


def test_unchanged_fitting_gets_no_new_version():
    apply_snapshot(_snapshot())
    result = apply_snapshot(_snapshot())
    assert result.fittings_updated == 0
    assert Fitting.objects.get(external_id=10).versions.count() == 1


def test_changed_fitting_gets_new_version():
    apply_snapshot(_snapshot(gyros=2))
    result = apply_snapshot(_snapshot(gyros=3))
    assert result.fittings_updated == 1
    assert Fitting.objects.get(external_id=10).current_version.number == 2


def test_removed_doctrine_is_archived_and_unused_fitting_deleted():
    apply_snapshot(_snapshot())
    result = apply_snapshot(SourceSnapshot())
    assert result.doctrines_archived == 1
    assert Doctrine.objects.get(external_id=5).status == Doctrine.Status.ARCHIVED
    assert result.fittings_removed == 1
    assert not Fitting.objects.filter(source=Source.FITTINGS).exists()
    assert not Category.objects.filter(source=Source.FITTINGS).exists()


def test_removed_fitting_kept_when_a_local_doctrine_uses_it():
    apply_snapshot(_snapshot())
    local = Doctrine.objects.create(name="Our doctrine")
    DoctrineFitting.objects.create(doctrine=local, fitting=Fitting.objects.get(external_id=10))
    apply_snapshot(SourceSnapshot())
    assert Fitting.objects.filter(external_id=10).exists()


def test_category_groups_are_copied():
    group = Group.objects.create(name="Alliance members")
    apply_snapshot(_snapshot(group_ids=[group.pk]))
    assert list(Category.objects.get(external_id=7).visible_to_groups.all()) == [group]


def test_local_records_are_untouched_by_sync():
    local = import_eft("[Rifter, Tackle]\n\nDamage Control II")
    apply_snapshot(SourceSnapshot())
    assert Fitting.objects.filter(pk=local.pk).exists()


def test_synced_fitting_cannot_be_edited():
    apply_snapshot(_snapshot())
    with pytest.raises(ReadOnlyFittingError):
        update_from_eft(Fitting.objects.get(external_id=10), "[Muninn, Other]\n\nDamage Control II")


def test_sync_skipped_when_fittings_not_installed():
    with patch("aa_doctrinehub.services.fittings_sync.fittings_app_installed", return_value=False):
        assert sync_from_fittings_app() is None


def test_sync_records_summary():
    with (
        patch("aa_doctrinehub.services.fittings_sync.fittings_app_installed", return_value=True),
        patch("aa_doctrinehub.services.fittings_sync.read_fittings_app", return_value=_snapshot()),
    ):
        sync_from_fittings_app()
    settings = SyncSettings.get_solo()
    assert settings.fittings_last_sync_at is not None
    assert "1 new" in settings.fittings_last_sync_summary


def test_sync_due_logic():
    settings = SyncSettings.get_solo()
    assert fittings_sync_due(settings) is False  # disabled by default
    settings.fittings_sync_enabled = True
    assert fittings_sync_due(settings) is True  # never synced
    settings.fittings_last_sync_at = timezone.now() - timedelta(days=2)
    settings.fittings_sync_interval_days = 7
    assert fittings_sync_due(settings) is False
    settings.fittings_last_sync_at = timezone.now() - timedelta(days=7)
    assert fittings_sync_due(settings) is True


def test_task_skips_when_disabled():
    assert sync_from_fittings() == "skipped"


class _Rows(list):
    """Stands in for a queryset: chainable and iterable."""

    def select_related(self, *args):
        return self

    def prefetch_related(self, *args):
        return self

    def all(self):
        return self


class _Model:
    def __init__(self, rows):
        self.objects = _Rows(rows)


class _Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_reader_maps_fittings_models_to_snapshot():
    """The reader only uses the Fittings v2.3.3 field names, looked up via the app registry."""
    from aa_doctrinehub.services import fittings_sync

    ship = _Obj(name_en="Muninn")
    item = _Obj(flag="LoSlot0", type_id=519, type_fk=_Obj(name_en="Gyrostabilizer II"), quantity=1)
    fit = _Obj(
        pk=10, name="Shield Muninn", description="", ship_type=ship, ship_type_type_id=12015, items=_Rows([item])
    )
    fit.eft = "[Muninn, Shield Muninn]\n\nGyrostabilizer II"
    doctrine = _Obj(pk=5, name="Shield HAC", description="", icon_url=None, fittings=_Rows([fit]))
    category = _Obj(
        pk=7, name="Alliance", color="#fff", groups=_Rows([]), fittings=_Rows([fit]), doctrines=_Rows([doctrine])
    )
    models = {"Fitting": _Model([fit]), "Doctrine": _Model([doctrine]), "Category": _Model([category])}

    with patch.object(fittings_sync.apps, "get_model", side_effect=lambda app, name: models[name]):
        snapshot = fittings_sync.read_fittings_app()

    assert snapshot.fittings[0].ship_type_name == "Muninn"
    assert snapshot.fittings[0].items[0].type_name == "Gyrostabilizer II"
    assert snapshot.doctrines[0].fitting_ids == [10]
    assert snapshot.categories[0].doctrine_ids == [5]
