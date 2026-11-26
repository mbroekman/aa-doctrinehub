"""Create and update fittings and their versions."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction

from ..models import Fitting, FittingItem, FittingVersion, Source
from .eft import ExportItem, ParsedFitting, parse_eft, to_eft, to_multibuy
from .skills import extract_dogma_skills_for_version
from .types import resolve_type_ids


class ReadOnlyFittingError(PermissionError):
    """The fitting comes from another source and cannot be edited here."""


def _export_items(version: FittingVersion) -> list[ExportItem]:
    return [
        ExportItem(
            flag=item.flag,
            type_name=item.type_name,
            quantity=item.quantity,
            charge_name=item.charge_name,
            is_offline=item.is_offline,
        )
        for item in version.items.all()
    ]


def version_eft(version: FittingVersion) -> str:
    """EFT text of a version, rebuilt from its items when the stored text is empty."""
    if version.eft:
        return version.eft
    return to_eft(version.fitting.ship_type_name, version.fitting.name, _export_items(version))


def version_multibuy(version: FittingVersion, amount: int = 1) -> str:
    """Multibuy text for ``amount`` copies of a version, including charges."""
    items = _export_items(version)
    charges = [ExportItem(flag="Cargo", type_name=i.charge_name) for i in items if i.charge_name]
    return to_multibuy(version.fitting.ship_type_name, items + charges, amount)


@transaction.atomic
def add_version(
    fitting: Fitting,
    parsed: ParsedFitting,
    eft: str,
    user: User | None = None,
    change_note: str = "",
) -> FittingVersion:
    """Store ``parsed`` as the next version of ``fitting``."""
    last = fitting.versions.order_by("-number").values_list("number", flat=True).first() or 0
    version = FittingVersion.objects.create(
        fitting=fitting, number=last + 1, eft=eft, created_by=user, change_note=change_note
    )
    FittingItem.objects.bulk_create(
        FittingItem(
            version=version,
            flag=item.flag,
            type_name=item.type_name,
            quantity=item.quantity,
            charge_name=item.charge_name,
            is_offline=item.is_offline,
        )
        for item in parsed.items
    )
    return version


def resolve_fitting_types(fitting: Fitting, version: FittingVersion | None = None) -> None:
    """Fill in missing type IDs of the hull and of the items of ``version``."""
    version = version or fitting.current_version
    items = [i for i in version.items.all() if not i.type_id] if version else []
    names = {i.type_name for i in items}
    if not fitting.ship_type_id:
        names.add(fitting.ship_type_name)
    ids = resolve_type_ids(names)
    if not fitting.ship_type_id and ids.get(fitting.ship_type_name):
        fitting.ship_type_id = ids[fitting.ship_type_name]
        fitting.save(update_fields=["ship_type_id", "updated_at"])
    for item in items:
        if ids.get(item.type_name):
            item.type_id = ids[item.type_name]
            item.save(update_fields=["type_id"])


def refresh_requirements(fitting: Fitting, version: FittingVersion | None = None) -> None:
    """Resolve type IDs and recompute the dogma skill requirements of a version."""
    version = version or fitting.current_version
    if version is None:
        return
    resolve_fitting_types(fitting, version)
    fitting.refresh_from_db(fields=["ship_type_id"])
    version.fitting = fitting
    extract_dogma_skills_for_version(version)


def refresh_incomplete_fittings() -> int:
    """Recompute requirements of fittings without a hull type ID or skill requirements."""
    count = 0
    for fitting in Fitting.objects.all():
        version = fitting.current_version
        if version is None:
            continue
        if fitting.ship_type_id and version.skill_requirements.exists():
            continue
        refresh_requirements(fitting, version)
        count += 1
    return count


@transaction.atomic
def import_eft(eft: str, user: User | None = None, description: str = "") -> Fitting:
    """Create a new local fitting from EFT text."""
    parsed = parse_eft(eft)
    fitting = Fitting.objects.create(
        name=parsed.name,
        ship_type_name=parsed.ship_type_name,
        description=description,
        source=Source.LOCAL,
    )
    version = add_version(fitting, parsed, eft.strip(), user=user, change_note="Imported from EFT")
    refresh_requirements(fitting, version)
    return fitting


def update_from_eft(fitting: Fitting, eft: str, user: User | None = None, change_note: str = "") -> FittingVersion:
    """Store a new version of a local fitting from EFT text."""
    if not fitting.is_editable:
        raise ReadOnlyFittingError(f"Fitting {fitting.pk} is synced from {fitting.source}")
    parsed = parse_eft(eft)
    if fitting.ship_type_name != parsed.ship_type_name:
        fitting.ship_type_id = None
    fitting.name = parsed.name
    fitting.ship_type_name = parsed.ship_type_name
    fitting.save(update_fields=["name", "ship_type_name", "ship_type_id", "updated_at"])
    version = add_version(fitting, parsed, eft.strip(), user=user, change_note=change_note)
    refresh_requirements(fitting, version)
    return version
