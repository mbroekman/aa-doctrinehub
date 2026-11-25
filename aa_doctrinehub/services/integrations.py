"""Phase 4 integrations: Hangar check, aa-fatanalysis, aa-industry, and SRP killmail comparison."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta
from typing import Any

from allianceauth.authentication.models import CharacterOwnership
from django.apps import apps
from django.contrib.auth.models import User
from django.utils import timezone

from ..models import CharacterAsset, Doctrine, Fitting, FittingVersion

logger = logging.getLogger(__name__)

FITTED_FLAG_PREFIXES = ("HiSlot", "MedSlot", "LoSlot", "RigSlot", "SubSystemSlot")

# EVE inventory flag integers for killmail fitted slots
KILLMAIL_FITTED_FLAGS = (
    set(range(11, 19))    # Low slots
    | set(range(19, 27))  # Med slots
    | set(range(27, 35))  # High slots
    | set(range(92, 100)) # Rig slots
    | set(range(125, 133))  # Subsystem slots
)


def _is_fitted_asset_flag(flag: str) -> bool:
    return any(flag.startswith(prefix) for prefix in FITTED_FLAG_PREFIXES)


def hangar_check_for_user(user: User, doctrine_id: int | None = None) -> list[dict[str, Any]]:
    """Check which fitted doctrine ships ``user`` owns per character and location."""
    fittings_qs = Fitting.objects.exclude(ship_type_id__isnull=True).prefetch_related("versions__items")
    if doctrine_id:
        fittings_qs = fittings_qs.filter(doctrines__id=doctrine_id).distinct()
    fittings_by_ship: dict[int, list[Fitting]] = {}
    for fitting in fittings_qs:
        if fitting.ship_type_id:
            fittings_by_ship.setdefault(fitting.ship_type_id, []).append(fitting)

    ownerships = CharacterOwnership.objects.filter(user=user).select_related("character")
    results: list[dict[str, Any]] = []

    for co in ownerships:
        char = co.character
        assets = list(CharacterAsset.objects.filter(character=char))
        if not assets:
            continue

        children_by_ship: dict[int, list[CharacterAsset]] = {}
        for asset in assets:
            if _is_fitted_asset_flag(asset.location_flag):
                children_by_ship.setdefault(asset.location_id, []).append(asset)

        for asset in assets:
            if not asset.is_singleton or asset.type_id not in fittings_by_ship:
                continue
            fitted_modules = Counter(
                mod.type_name.lower() for mod in children_by_ship.get(asset.item_id, []) if mod.type_name
            )
            best_match: dict[str, Any] | None = None
            for fitting in fittings_by_ship[asset.type_id]:
                version = fitting.current_version
                if version is None:
                    continue
                expected: Counter[str] = Counter()
                for item in version.items.all():
                    if _is_fitted_asset_flag(item.flag):
                        expected[item.type_name.lower()] += item.quantity
                total_expected = sum(expected.values())
                matched_count = sum(min(fitted_modules[k], cnt) for k, cnt in expected.items())
                pct = round((matched_count / total_expected) * 100) if total_expected else 100
                status = "full" if pct == 100 else ("partial" if matched_count > 0 else "hull_only")
                candidate = {
                    "character_id": char.character_id,
                    "character_name": char.character_name,
                    "item_id": asset.item_id,
                    "location_id": asset.location_id,
                    "ship_type_id": asset.type_id,
                    "ship_type_name": fitting.ship_type_name,
                    "fitting_id": fitting.pk,
                    "fitting_name": fitting.name,
                    "match_status": status,
                    "match_pct": pct,
                }
                if best_match is None or candidate["match_pct"] > best_match["match_pct"]:
                    best_match = candidate
            if best_match:
                results.append(best_match)
    return results


def count_user_fats(user: User, days: int = 30) -> int | None:
    """Return recent FAT count from aa-fatanalysis for ``user``'s characters, or None if not installed."""
    if not apps.is_installed("aa_fatanalysis"):
        return None
    try:
        from aa_fatanalysis.models import Fat
    except ImportError:
        return None

    char_ids = list(CharacterOwnership.objects.filter(user=user).values_list("character_id", flat=True))
    if not char_ids:
        return 0
    since = timezone.now() - timedelta(days=max(days, 1))
    return Fat.objects.filter(character_id__in=char_ids, fleet__start_time__gte=since).count()


def compute_doctrine_shortages(doctrine: Doctrine) -> list[dict[str, Any]]:
    """Compare doctrine fitting target_count against owned fitted ships across members."""
    ships = (
        CharacterAsset.objects.filter(is_singleton=True)
        .values_list("type_id", flat=True)
    )
    owned_by_type = Counter(ships)
    shortages: list[dict[str, Any]] = []
    for df in doctrine.doctrine_fittings.select_related("fitting").all():
        target = df.target_count or 0
        if target <= 0:
            continue
        have = owned_by_type.get(df.fitting.ship_type_id or 0, 0)
        if have < target:
            shortages.append(
                {
                    "fitting_id": df.fitting_id,
                    "fitting_name": df.fitting.name,
                    "ship_type_id": df.fitting.ship_type_id,
                    "ship_type_name": df.fitting.ship_type_name,
                    "target_count": target,
                    "owned_count": have,
                    "shortage": target - have,
                }
            )
    return shortages


def push_shortages_to_industry(doctrine: Doctrine, user: User) -> dict[str, Any]:
    """Push doctrine ship shortages to aa-industry when installed."""
    shortages = compute_doctrine_shortages(doctrine)
    if not shortages:
        return {"pushed": 0, "shortages": [], "message": "No shortages found for this doctrine."}
    if not apps.is_installed("industry_reforged"):
        return {
            "pushed": 0,
            "shortages": shortages,
            "message": "aa-industry is not installed; returning calculated shortages only.",
        }
    try:
        from industry_reforged.models import MemberOrder, OrderItem
    except ImportError:
        return {
            "pushed": 0,
            "shortages": shortages,
            "message": "aa-industry models unavailable.",
        }

    main_char = getattr(getattr(user, "profile", None), "main_character", None)
    if main_char is None:
        return {"pushed": 0, "shortages": shortages, "message": "User has no main character."}

    order = MemberOrder.objects.create(
        character=main_char,
        is_corp_order=True,
        notes=f"Doctrine Hub shortage order for {doctrine.name}",
    )
    pushed = 0
    for s in shortages:
        if s["ship_type_id"]:
            OrderItem.objects.create(
                order=order,
                type_id=s["ship_type_id"],
                type_name=s["ship_type_name"],
                quantity=s["shortage"],
            )
            pushed += 1
    return {
        "pushed": pushed,
        "order_id": order.pk,
        "shortages": shortages,
        "message": f"Created aa-industry order #{order.pk} with {pushed} ship lines.",
    }


def compare_killmail_to_fitting(killmail: dict[str, Any], version: FittingVersion) -> dict[str, Any]:
    """Compare an ESI killmail payload against a doctrine FittingVersion for SRP."""
    victim = killmail.get("victim", killmail)
    km_ship_type_id = int(victim.get("ship_type_id") or 0)
    expected_ship_type_id = version.fitting.ship_type_id
    hull_match = expected_ship_type_id is not None and km_ship_type_id == expected_ship_type_id

    km_items = victim.get("items") or []
    fitted_counts: Counter[int] = Counter()
    for item in km_items:
        flag = int(item.get("flag") or 0)
        if flag in KILLMAIL_FITTED_FLAGS:
            tid = int(item.get("item_type_id") or 0)
            qty = int(item.get("quantity_destroyed") or 0) + int(item.get("quantity_dropped") or 0)
            if tid and qty > 0:
                fitted_counts[tid] += qty

    expected_counts: Counter[int] = Counter()
    names_by_id: dict[int, str] = {}
    for fi in version.items.all():
        if _is_fitted_asset_flag(fi.flag) and fi.type_id:
            expected_counts[fi.type_id] += fi.quantity
            names_by_id[fi.type_id] = fi.type_name

    matched: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    extra: list[dict[str, Any]] = []

    total_expected = sum(expected_counts.values())
    total_matched = 0

    for tid, exp_qty in expected_counts.items():
        got = min(fitted_counts.get(tid, 0), exp_qty)
        total_matched += got
        if got > 0:
            matched.append({"type_id": tid, "type_name": names_by_id.get(tid, str(tid)), "quantity": got})
        if got < exp_qty:
            missing.append(
                {
                    "type_id": tid,
                    "type_name": names_by_id.get(tid, str(tid)),
                    "quantity": exp_qty - got,
                }
            )

    for tid, got_qty in fitted_counts.items():
        diff = got_qty - expected_counts.get(tid, 0)
        if diff > 0:
            extra.append({"type_id": tid, "type_name": names_by_id.get(tid, str(tid)), "quantity": diff})

    compliance_pct = round((total_matched / total_expected) * 100) if total_expected else (100 if hull_match else 0)
    return {
        "hull_match": hull_match,
        "killmail_ship_type_id": km_ship_type_id,
        "expected_ship_type_id": expected_ship_type_id,
        "compliance_pct": compliance_pct,
        "matched": matched,
        "missing": missing,
        "extra": extra,
    }
