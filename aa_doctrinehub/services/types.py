"""Resolve EVE type names to type IDs and read their required skills.

Fittings imported from EFT only carry names. Without type IDs there is no ship
icon and no dogma data, so no skill requirements. This module looks the names
up in django-eveuniverse when it is installed and falls back to public ESI.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import requests
from django.core.cache import cache

from .esi_sync import ESI_BASE_URL, ESI_TIMEOUT, _resolve_type_names

logger = logging.getLogger(__name__)

# EVE dogma pairs: (requiredSkillN attribute_id, requiredSkillNLevel attribute_id)
DOGMA_SKILL_ATTRS: list[tuple[int, int]] = [
    (182, 277),
    (183, 278),
    (184, 279),
    (1285, 1286),
    (1289, 1287),
    (1290, 1288),
]
_SKILL_ATTR_IDS = {aid for pair in DOGMA_SKILL_ATTRS for aid in pair}
_CACHE_TTL = 60 * 60 * 24 * 7
_IDS_CHUNK = 500


def _eveuniverse_ids(names: set[str]) -> dict[str, int]:
    try:
        from eveuniverse.models import EveType
    except ImportError:
        return {}
    found: dict[str, int] = {}
    for tid, name in EveType.objects.filter(name__in=names).values_list("id", "name"):
        found[str(name)] = int(tid)
    return found


def _esi_ids(names: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for i in range(0, len(names), _IDS_CHUNK):
        chunk = names[i : i + _IDS_CHUNK]
        try:
            resp = requests.post(f"{ESI_BASE_URL}/universe/ids/", json=chunk, timeout=ESI_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            logger.warning("Could not resolve %d type names via ESI", len(chunk))
            continue
        for entry in data.get("inventory_types", []) if isinstance(data, dict) else []:
            if isinstance(entry, dict) and "id" in entry and "name" in entry:
                found[str(entry["name"])] = int(entry["id"])
    return found


def resolve_type_ids(names: Iterable[str]) -> dict[str, int]:
    """Map EVE type names to type IDs. Names that cannot be resolved are left out."""
    wanted = {n.strip() for n in names if n and n.strip()}
    if not wanted:
        return {}
    found = _eveuniverse_ids(wanted)
    missing = sorted(n for n in wanted if n not in found)
    if missing:
        esi = _esi_ids(missing)
        found.update(esi)
        # ESI matches names case-insensitively; map them back to what was asked.
        lowered = {k.lower(): v for k, v in esi.items()}
        for name in missing:
            if name not in found and name.lower() in lowered:
                found[name] = lowered[name.lower()]
    return found


def _skills_from_attributes(attrs: dict[int, float]) -> list[tuple[int, int]]:
    reqs: list[tuple[int, int]] = []
    for skill_attr, level_attr in DOGMA_SKILL_ATTRS:
        sid = int(attrs.get(skill_attr) or 0)
        lvl = int(attrs.get(level_attr) or 0)
        if sid and lvl:
            reqs.append((sid, max(1, min(5, lvl))))
    return reqs


def _eveuniverse_required_skills(type_ids: set[int]) -> dict[int, list[tuple[int, int]]]:
    """Required skills per type from eveuniverse, only for types whose dogma is loaded."""
    try:
        from eveuniverse.models import EveTypeDogmaAttribute
    except ImportError:
        return {}
    covered = set(
        EveTypeDogmaAttribute.objects.filter(eve_type_id__in=type_ids).values_list("eve_type_id", flat=True).distinct()
    )
    if not covered:
        return {}
    attrs: dict[int, dict[int, float]] = defaultdict(dict)
    rows = EveTypeDogmaAttribute.objects.filter(
        eve_type_id__in=covered, dogma_attribute_id__in=_SKILL_ATTR_IDS
    ).values_list("eve_type_id", "dogma_attribute_id", "value")
    for tid, aid, val in rows:
        attrs[int(tid)][int(aid)] = float(val)
    return {int(tid): _skills_from_attributes(attrs.get(int(tid), {})) for tid in covered}


def _esi_required_skills(type_id: int) -> list[tuple[int, int]] | None:
    """Required skills of one type from ESI, cached. ``None`` when ESI failed."""
    key = f"aa_doctrinehub:type_skills:{type_id}"
    cached = cache.get(key)
    if cached is not None:
        return [tuple(pair) for pair in cached]  # type: ignore[misc]
    try:
        resp = requests.get(f"{ESI_BASE_URL}/universe/types/{type_id}/", timeout=ESI_TIMEOUT)
        resp.raise_for_status()
        data: Any = resp.json()
    except (requests.RequestException, ValueError):
        logger.warning("Could not load dogma for type %s via ESI", type_id)
        return None
    attrs = {
        int(a["attribute_id"]): float(a["value"])
        for a in (data.get("dogma_attributes") or [])
        if isinstance(a, dict) and "attribute_id" in a and "value" in a
    }
    reqs = _skills_from_attributes(attrs)
    cache.set(key, reqs, _CACHE_TTL)
    return reqs


def dogma_lookup(type_ids: set[int]) -> dict[int, list[tuple[int, str, int]]]:
    """Required skills per type: ``{type_id: [(skill_id, skill_name, level), ...]}``.

    Uses eveuniverse dogma when loaded and public ESI for the rest.
    """
    if not type_ids:
        return {}
    by_type = _eveuniverse_required_skills(type_ids)
    for tid in sorted(type_ids - by_type.keys()):
        reqs = _esi_required_skills(tid)
        if reqs is not None:
            by_type[tid] = reqs
    skill_ids = {sid for reqs in by_type.values() for sid, _lvl in reqs}
    names = _resolve_type_names(skill_ids) if skill_ids else {}
    return {
        tid: [(sid, names.get(sid, f"Skill {sid}"), lvl) for sid, lvl in reqs] for tid, reqs in by_type.items() if reqs
    }
