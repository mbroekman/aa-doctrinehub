"""Own ESI sync for character skills, implants, and assets (no external plugins)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import requests
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from esi.models import Token

from ..models import (
    CharacterAsset,
    CharacterImplant,
    CharacterSkill,
    CharacterSkillSnapshot,
)

logger = logging.getLogger(__name__)

ESI_BASE_URL = "https://esi.evetech.net/latest"
ESI_TIMEOUT = 20

REQUIRED_SCOPES = [
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-assets.read_assets.v1",
]

EsiFetcher = Callable[[str, str, dict[str, Any] | None], tuple[Any, dict[str, str]]]


def _default_fetcher(url: str, access_token: str, params: dict[str, Any] | None = None) -> tuple[Any, dict[str, str]]:
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        params=params or {},
        timeout=ESI_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json(), dict(resp.headers)


def _resolve_type_names(type_ids: set[int]) -> dict[int, str]:
    """Resolve EVE type IDs to names via django-eveuniverse if installed, else ESI /universe/names/."""
    if not type_ids:
        return {}
    names: dict[int, str] = {}
    try:
        from eveuniverse.models import EveType

        for tid, name in EveType.objects.filter(id__in=type_ids).values_list("id", "name"):
            names[int(tid)] = str(name)
    except ImportError:
        pass

    missing = sorted(tid for tid in type_ids if tid not in names)
    if not missing:
        return names
    for i in range(0, len(missing), 500):
        chunk = missing[i : i + 500]
        try:
            resp = requests.post(
                f"{ESI_BASE_URL}/universe/names/",
                json=chunk,
                timeout=ESI_TIMEOUT,
            )
            if resp.ok:
                for entry in resp.json():
                    if isinstance(entry, dict) and "id" in entry and "name" in entry:
                        names[int(entry["id"])] = str(entry["name"])
        except requests.RequestException:
            logger.debug("Failed to resolve %d type names via ESI", len(chunk))
    return names


def get_valid_token(character_id: int) -> Token | None:
    """Return a valid ESI token for ``character_id`` covering all REQUIRED_SCOPES."""
    return Token.get_token(character_id, REQUIRED_SCOPES)


def character_link_status(user: User) -> list[dict[str, Any]]:
    """Return ESI link & snapshot status for all characters owned by ``user``."""
    ownerships = (
        CharacterOwnership.objects.filter(user=user)
        .select_related("character", "character__doctrinehub_skill_snapshot")
        .order_by("character__character_name")
    )
    result: list[dict[str, Any]] = []
    for ownership in ownerships:
        char = ownership.character
        token = get_valid_token(char.character_id)
        snapshot = getattr(char, "doctrinehub_skill_snapshot", None)
        result.append(
            {
                "character_id": char.character_id,
                "character_name": char.character_name,
                "has_valid_token": token is not None,
                "sync_status": snapshot.sync_status if snapshot else CharacterSkillSnapshot.SyncStatus.PENDING,
                "last_synced_at": snapshot.last_synced_at.isoformat() if snapshot and snapshot.last_synced_at else None,
                "last_error": snapshot.last_error if snapshot else "",
                "total_sp": snapshot.total_sp if snapshot else 0,
            }
        )
    return result


def _fetch_paginated(fetcher: EsiFetcher, url: str, access_token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        data, headers = fetcher(url, access_token, {"page": page})
        if isinstance(data, list):
            items.extend(data)
        total_pages = int(headers.get("X-Pages", headers.get("x-pages", "1")) or "1")
        if page >= total_pages:
            break
        page += 1
    return items


@transaction.atomic
def sync_character_snapshot(
    character: EveCharacter,
    fetcher: EsiFetcher | None = None,
    resolve_names: bool = True,
) -> CharacterSkillSnapshot:
    """Sync skills, implants, and assets for ``character`` from ESI."""
    snapshot, _ = CharacterSkillSnapshot.objects.get_or_create(character=character)
    token = get_valid_token(character.character_id)
    if token is None:
        snapshot.sync_status = CharacterSkillSnapshot.SyncStatus.ERROR
        snapshot.last_error = "Missing ESI token with required scopes."
        snapshot.save(update_fields=["sync_status", "last_error"])
        return snapshot

    call = fetcher or _default_fetcher
    try:
        access_token = token.valid_access_token()
        skills_payload, _ = call(f"{ESI_BASE_URL}/characters/{character.character_id}/skills/", access_token, None)
        implants_payload, _ = call(f"{ESI_BASE_URL}/characters/{character.character_id}/implants/", access_token, None)
        assets_payload = _fetch_paginated(
            call, f"{ESI_BASE_URL}/characters/{character.character_id}/assets/", access_token
        )
    except Exception as exc:  # noqa: BLE001 - ESI / network errors must mark status=error and never raise
        logger.warning(
            "ESI sync failed for character %s (%s): %s",
            character.character_name,
            character.character_id,
            exc,
        )
        snapshot.sync_status = CharacterSkillSnapshot.SyncStatus.ERROR
        snapshot.last_error = str(exc)
        snapshot.save(update_fields=["sync_status", "last_error"])
        return snapshot

    raw_skills = skills_payload.get("skills", []) if isinstance(skills_payload, dict) else []
    raw_implants = implants_payload if isinstance(implants_payload, list) else []

    type_ids: set[int] = set()
    for s in raw_skills:
        if "skill_id" in s:
            type_ids.add(int(s["skill_id"]))
    for imp_id in raw_implants:
        type_ids.add(int(imp_id))
    for asset in assets_payload:
        if "type_id" in asset:
            type_ids.add(int(asset["type_id"]))

    names = _resolve_type_names(type_ids) if resolve_names else {}

    snapshot.total_sp = int(skills_payload.get("total_sp", 0)) if isinstance(skills_payload, dict) else 0
    snapshot.unallocated_sp = int(skills_payload.get("unallocated_sp", 0)) if isinstance(skills_payload, dict) else 0
    snapshot.sync_status = CharacterSkillSnapshot.SyncStatus.OK
    snapshot.last_synced_at = timezone.now()
    snapshot.last_error = ""
    snapshot.save()

    CharacterSkill.objects.filter(snapshot=snapshot).delete()
    CharacterSkill.objects.bulk_create(
        [
            CharacterSkill(
                snapshot=snapshot,
                skill_id=int(s["skill_id"]),
                skill_name=names.get(int(s["skill_id"]), f"Skill {s['skill_id']}"),
                trained_skill_level=int(s.get("trained_skill_level", 0)),
                active_skill_level=int(s.get("active_skill_level", 0)),
                skillpoints_in_skill=int(s.get("skillpoints_in_skill", 0)),
            )
            for s in raw_skills
        ]
    )

    CharacterImplant.objects.filter(snapshot=snapshot).delete()
    CharacterImplant.objects.bulk_create(
        [
            CharacterImplant(
                snapshot=snapshot,
                type_id=int(imp_id),
                type_name=names.get(int(imp_id), f"Implant {imp_id}"),
                slot=idx + 1,
            )
            for idx, imp_id in enumerate(raw_implants)
        ]
    )

    CharacterAsset.objects.filter(character=character).delete()
    CharacterAsset.objects.bulk_create(
        [
            CharacterAsset(
                character=character,
                item_id=int(a["item_id"]),
                type_id=int(a["type_id"]),
                type_name=names.get(int(a["type_id"]), f"Type {a['type_id']}"),
                location_id=int(a["location_id"]),
                location_flag=str(a.get("location_flag", "")),
                location_type=str(a.get("location_type", "")),
                quantity=int(a.get("quantity", 1)),
                is_singleton=bool(a.get("is_singleton", False)),
            )
            for a in assets_payload
            if "item_id" in a and "type_id" in a and "location_id" in a
        ]
    )
    return snapshot


def sync_all_characters() -> dict[str, int]:
    """Sync all characters linked to an Alliance Auth user."""
    characters = (
        EveCharacter.objects.filter(character_ownership__isnull=False)
        .distinct()
        .order_by("character_id")
    )
    ok_count = 0
    error_count = 0
    for character in characters:
        snap = sync_character_snapshot(character)
        if snap.sync_status == CharacterSkillSnapshot.SyncStatus.OK:
            ok_count += 1
        else:
            error_count += 1
    return {"ok": ok_count, "error": error_count}
