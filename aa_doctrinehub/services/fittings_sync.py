"""Copy doctrines and fittings from the Fittings app (colcrunch) on the same Auth.

This module is a deliberate, approved exception to workspace AGENTS §15 (no
dependencies on other plugins): the owner asked for a periodic sync so existing
Fittings data shows up in Doctrine Hub. To keep that exception contained:

- Fittings is never imported. Its models are looked up through Django's app
  registry, and the sync switches itself off when the app is not installed.
- Only this module reads Fittings. It turns rows into plain dataclasses
  (:class:`SourceSnapshot`); everything after that works on those.
- Synced records get ``source=Source.FITTINGS`` and are read-only in Doctrine Hub.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from django.apps import apps
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from ..models import Category, Doctrine, DoctrineFitting, Fitting, Source, SyncSettings
from .eft import ExportItem, ParsedFitting, ParsedItem, to_eft
from .fittings import add_version

logger = logging.getLogger(__name__)

FITTINGS_APP_LABEL = "fittings"


@dataclass(frozen=True)
class SourceItem:
    """An item of a source fitting."""

    flag: str
    type_id: int
    type_name: str
    quantity: int


@dataclass
class SourceFitting:
    """A fitting as read from the source."""

    external_id: int
    name: str
    description: str
    ship_type_id: int
    ship_type_name: str
    eft: str
    items: list[SourceItem] = field(default_factory=list)


@dataclass
class SourceDoctrine:
    """A doctrine as read from the source."""

    external_id: int
    name: str
    description: str
    icon_url: str
    fitting_ids: list[int] = field(default_factory=list)


@dataclass
class SourceCategory:
    """A category as read from the source."""

    external_id: int
    name: str
    color: str
    group_ids: list[int] = field(default_factory=list)
    fitting_ids: list[int] = field(default_factory=list)
    doctrine_ids: list[int] = field(default_factory=list)


@dataclass
class SourceSnapshot:
    """Everything read from the source in one pass."""

    fittings: list[SourceFitting] = field(default_factory=list)
    doctrines: list[SourceDoctrine] = field(default_factory=list)
    categories: list[SourceCategory] = field(default_factory=list)


@dataclass
class SyncResult:
    """Counts of what a sync changed."""

    fittings_created: int = 0
    fittings_updated: int = 0
    fittings_removed: int = 0
    doctrines_created: int = 0
    doctrines_updated: int = 0
    doctrines_archived: int = 0
    categories_synced: int = 0

    def summary(self) -> str:
        """One-line summary for the settings page."""
        return (
            f"Fittings: {self.fittings_created} new, {self.fittings_updated} updated, "
            f"{self.fittings_removed} removed. Doctrines: {self.doctrines_created} new, "
            f"{self.doctrines_updated} updated, {self.doctrines_archived} archived. "
            f"Categories: {self.categories_synced}."
        )


def fittings_app_installed() -> bool:
    """Whether the Fittings app is installed on this Auth."""
    return apps.is_installed(FITTINGS_APP_LABEL)


def _type_name(item_type: Any, fallback: str) -> str:
    for attr in ("name_en", "name"):
        value = getattr(item_type, attr, None)
        if value:
            return str(value)
    return fallback


def read_fittings_app() -> SourceSnapshot:
    """Read all fittings, doctrines and categories from the Fittings app."""
    fitting_model = apps.get_model(FITTINGS_APP_LABEL, "Fitting")
    doctrine_model = apps.get_model(FITTINGS_APP_LABEL, "Doctrine")
    category_model = apps.get_model(FITTINGS_APP_LABEL, "Category")

    snapshot = SourceSnapshot()
    for fit in fitting_model.objects.select_related("ship_type").prefetch_related("items__type_fk"):
        ship_name = _type_name(getattr(fit, "ship_type", None), f"Type {fit.ship_type_type_id}")
        items = [
            SourceItem(
                flag=item.flag,
                type_id=item.type_id,
                type_name=_type_name(getattr(item, "type_fk", None), f"Type {item.type_id}"),
                quantity=item.quantity,
            )
            for item in fit.items.all()
        ]
        try:
            eft = str(fit.eft)
        except Exception:  # noqa: BLE001 - the source's own EFT writer may fail on missing SDE rows
            logger.warning("Fittings: could not build EFT for fitting %s, rebuilding from items", fit.pk)
            eft = ""
        snapshot.fittings.append(
            SourceFitting(
                external_id=fit.pk,
                name=fit.name,
                description=fit.description or "",
                ship_type_id=fit.ship_type_type_id,
                ship_type_name=ship_name,
                eft=eft,
                items=items,
            )
        )
    for doctrine in doctrine_model.objects.prefetch_related("fittings"):
        snapshot.doctrines.append(
            SourceDoctrine(
                external_id=doctrine.pk,
                name=doctrine.name,
                description=doctrine.description or "",
                icon_url=doctrine.icon_url or "",
                fitting_ids=[f.pk for f in doctrine.fittings.all()],
            )
        )
    for category in category_model.objects.prefetch_related("groups", "fittings", "doctrines"):
        snapshot.categories.append(
            SourceCategory(
                external_id=category.pk,
                name=category.name,
                color=category.color or "#6c757d",
                group_ids=[g.pk for g in category.groups.all()],
                fitting_ids=[f.pk for f in category.fittings.all()],
                doctrine_ids=[d.pk for d in category.doctrines.all()],
            )
        )
    return snapshot


def _items_signature(items: list[tuple[str, str, int]]) -> list[tuple[str, str, int]]:
    return sorted(items)


def _sync_fitting(
    source_item: SourceFitting,
    now: Any,
    result: SyncResult,
    *,
    source: str = Source.FITTINGS,
    change_note: str = "Synced from Fittings",
) -> Fitting:
    fitting, created = Fitting.objects.get_or_create(
        source=source,
        external_id=source_item.external_id,
        defaults={"name": source_item.name, "ship_type_name": source_item.ship_type_name},
    )
    fitting.name = source_item.name
    fitting.description = source_item.description
    fitting.ship_type_id = source_item.ship_type_id
    fitting.ship_type_name = source_item.ship_type_name
    fitting.last_synced_at = now
    fitting.save()

    current = fitting.current_version
    new_signature = _items_signature([(i.flag, i.type_name, i.quantity) for i in source_item.items])
    old_signature = (
        _items_signature([(i.flag, i.type_name, i.quantity) for i in current.items.all()]) if current else None
    )
    if new_signature != old_signature:
        parsed = ParsedFitting(
            ship_type_name=source_item.ship_type_name,
            name=source_item.name,
            items=[ParsedItem(flag=i.flag, type_name=i.type_name, quantity=i.quantity) for i in source_item.items],
        )
        eft = source_item.eft.strip() or to_eft(
            source_item.ship_type_name,
            source_item.name,
            [ExportItem(flag=i.flag, type_name=i.type_name, quantity=i.quantity) for i in source_item.items],
        )
        version = add_version(fitting, parsed, eft, change_note=change_note)
        type_ids = {(i.flag, i.type_name): i.type_id for i in source_item.items}
        for item in version.items.all():
            item.type_id = type_ids.get((item.flag, item.type_name))
            item.save(update_fields=["type_id"])
        if created:
            result.fittings_created += 1
        else:
            result.fittings_updated += 1
    return fitting


def _sync_doctrine(
    source_item: SourceDoctrine,
    fittings: dict[int, Fitting],
    now: Any,
    result: SyncResult,
    *,
    source: str = Source.FITTINGS,
    prune_missing: bool = True,
) -> Doctrine:
    doctrine, created = Doctrine.objects.get_or_create(
        source=source,
        external_id=source_item.external_id,
        defaults={"name": source_item.name},
    )
    if not created and doctrine.status == Doctrine.Status.ARCHIVED:
        doctrine.status = Doctrine.Status.ACTIVE
    doctrine.name = source_item.name
    doctrine.description = source_item.description
    doctrine.icon_url = source_item.icon_url
    doctrine.last_synced_at = now
    doctrine.save()

    wanted_map = dict(fittings)
    if not prune_missing and source_item.fitting_ids:
        missing_ids = [pk for pk in source_item.fitting_ids if pk not in wanted_map]
        if missing_ids:
            for existing_fit in Fitting.objects.filter(source=source, external_id__in=missing_ids):
                if existing_fit.external_id is not None:
                    wanted_map[existing_fit.external_id] = existing_fit

    wanted = [wanted_map[pk] for pk in source_item.fitting_ids if pk in wanted_map]
    if prune_missing:
        doctrine.doctrine_fittings.exclude(fitting__in=wanted).delete()
    existing = {df.fitting_id: df for df in doctrine.doctrine_fittings.all()}
    for order, fitting in enumerate(wanted):
        link = existing.get(fitting.pk)
        if link is None:
            DoctrineFitting.objects.create(doctrine=doctrine, fitting=fitting, order=order)
        elif link.order != order:
            link.order = order
            link.save(update_fields=["order"])
    if created:
        result.doctrines_created += 1
    else:
        result.doctrines_updated += 1
    return doctrine


def _sync_categories(
    sources: list[SourceCategory],
    fittings: dict[int, Fitting],
    doctrines: dict[int, Doctrine],
    now: Any,
    result: SyncResult,
    *,
    source: str = Source.FITTINGS,
    prune_missing: bool = True,
) -> None:
    kept: list[int] = []
    for source_cat in sources:
        category, _created = Category.objects.update_or_create(
            source=source,
            external_id=source_cat.external_id,
            defaults={"name": source_cat.name, "color": source_cat.color, "last_synced_at": now},
        )
        if source == Source.FITTINGS:
            category.visible_to_groups.set(Group.objects.filter(pk__in=source_cat.group_ids))
        matched_fittings = [fittings[pk] for pk in source_cat.fitting_ids if pk in fittings]
        matched_doctrines = [doctrines[pk] for pk in source_cat.doctrine_ids if pk in doctrines]
        if prune_missing:
            category.fittings.set(matched_fittings)
            category.doctrines.set(matched_doctrines)
        else:
            if matched_fittings:
                category.fittings.add(*matched_fittings)
            if matched_doctrines:
                category.doctrines.add(*matched_doctrines)
        kept.append(source_cat.external_id)
        result.categories_synced += 1
    if prune_missing:
        Category.objects.from_source(source).exclude(external_id__in=kept).delete()


@transaction.atomic
def apply_snapshot(
    snapshot: SourceSnapshot,
    *,
    source: str = Source.FITTINGS,
    change_note: str = "Synced from Fittings",
    prune_missing: bool = True,
) -> SyncResult:
    """Make the sourced records in Doctrine Hub match ``snapshot``.

    When ``prune_missing`` is True (full sync), doctrines that disappeared from
    the source are archived and unused fittings/categories are removed. For
    partial batch imports, pass ``prune_missing=False`` to keep earlier batches.
    """
    now = timezone.now()
    result = SyncResult()

    fittings = {
        s.external_id: _sync_fitting(s, now, result, source=source, change_note=change_note) for s in snapshot.fittings
    }
    doctrines = {
        s.external_id: _sync_doctrine(s, fittings, now, result, source=source, prune_missing=prune_missing)
        for s in snapshot.doctrines
    }
    _sync_categories(
        snapshot.categories,
        fittings,
        doctrines,
        now,
        result,
        source=source,
        prune_missing=prune_missing,
    )

    if prune_missing:
        gone_doctrines = (
            Doctrine.objects.from_source(source)
            .exclude(external_id__in=list(doctrines))
            .exclude(status=Doctrine.Status.ARCHIVED)
        )
        result.doctrines_archived = gone_doctrines.update(status=Doctrine.Status.ARCHIVED)

        gone_fittings = (
            Fitting.objects.from_source(source)
            .exclude(external_id__in=list(fittings))
            .exclude(doctrine_fittings__doctrine__source=Source.LOCAL)
        )
        _total, deleted = gone_fittings.delete()
        result.fittings_removed = deleted.get(Fitting._meta.label, 0)
    return result


def sync_from_fittings_app() -> SyncResult | None:
    """Read the Fittings app and apply it. Returns ``None`` when Fittings is not installed."""
    if not fittings_app_installed():
        logger.info("Fittings sync skipped: the fittings app is not installed")
        return None
    result = apply_snapshot(read_fittings_app())
    settings = SyncSettings.get_solo()
    settings.fittings_last_sync_at = timezone.now()
    settings.fittings_last_sync_summary = result.summary()
    settings.save(update_fields=["fittings_last_sync_at", "fittings_last_sync_summary"])
    logger.info("Fittings sync done: %s", result.summary())
    return result
