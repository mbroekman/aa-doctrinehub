"""Skill requirements, eligibility traffic lights, skill plans, and gap analysis."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from allianceauth.authentication.models import CharacterOwnership
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet

from ..models import (
    CharacterSkillSnapshot,
    Doctrine,
    FittingSkillRequirement,
    FittingVersion,
)
from .types import dogma_lookup as default_dogma_lookup

DogmaLookup = Callable[[set[int]], dict[int, list[tuple[int, str, int]]]]


@transaction.atomic
def extract_dogma_skills_for_version(
    version: FittingVersion,
    dogma_lookup: DogmaLookup | None = None,
) -> list[FittingSkillRequirement]:
    """Populate dogma skill requirements for ``version``, keeping manual extras intact."""
    type_ids: set[int] = set()
    if version.fitting.ship_type_id:
        type_ids.add(version.fitting.ship_type_id)
    for tid in version.items.exclude(type_id__isnull=True).values_list("type_id", flat=True):
        if tid:
            type_ids.add(int(tid))

    lookup = dogma_lookup or default_dogma_lookup
    dogma_by_type = lookup(type_ids)
    ship_type_id = version.fitting.ship_type_id
    if ship_type_id and ship_type_id not in dogma_by_type:
        # Every hull needs skills, so the lookup failed (e.g. ESI down). Keep what we had.
        return list(version.skill_requirements.order_by("skill_name", "skill_id"))

    aggregated: dict[int, tuple[str, int]] = {}
    for reqs in dogma_by_type.values():
        for sid, sname, lvl in reqs:
            prev_name, prev_lvl = aggregated.get(sid, (sname, 0))
            aggregated[sid] = (sname or prev_name, max(prev_lvl, lvl))

    manual_ids = set(
        version.skill_requirements.filter(source=FittingSkillRequirement.RequirementSource.MANUAL).values_list(
            "skill_id", flat=True
        )
    )
    version.skill_requirements.filter(source=FittingSkillRequirement.RequirementSource.DOGMA).exclude(
        skill_id__in=aggregated.keys()
    ).delete()

    for sid, (sname, lvl) in aggregated.items():
        if sid in manual_ids:
            continue
        req, created = FittingSkillRequirement.objects.get_or_create(
            version=version,
            skill_id=sid,
            defaults={
                "skill_name": sname,
                "required_level": lvl,
                "recommended_level": lvl,
                "source": FittingSkillRequirement.RequirementSource.DOGMA,
            },
        )
        if not created and (req.required_level != lvl or req.skill_name != sname):
            req.skill_name = sname
            req.required_level = lvl
            if req.recommended_level < lvl:
                req.recommended_level = lvl
            req.save(update_fields=["skill_name", "required_level", "recommended_level"])

    return list(version.skill_requirements.order_by("skill_name", "skill_id"))


def evaluate_fitting_for_snapshot(
    reqs: list[FittingSkillRequirement],
    snapshot: CharacterSkillSnapshot | None,
) -> dict[str, Any]:
    """Evaluate a list of skill requirements against one character snapshot.

    Without any requirements the status is ``unknown``: the hull always needs
    skills, so an empty list means they could not be determined, not that
    everyone can fly it.
    """
    if not reqs or snapshot is None or snapshot.sync_status != CharacterSkillSnapshot.SyncStatus.OK:
        return {
            "status": "unknown",
            "missing_required": [],
            "missing_recommended": [],
            "met_required": 0,
            "total_requirements": len(reqs),
        }

    trained = {s.skill_id: s.active_skill_level for s in snapshot.skills.all()}
    missing_req: list[dict[str, Any]] = []
    missing_rec: list[dict[str, Any]] = []
    met_req = 0

    for req in reqs:
        current = trained.get(req.skill_id, 0)
        if current < req.required_level:
            missing_req.append(
                {
                    "skill_id": req.skill_id,
                    "skill_name": req.skill_name,
                    "current_level": current,
                    "required_level": req.required_level,
                    "recommended_level": req.recommended_level,
                }
            )
        else:
            met_req += 1
            if current < req.recommended_level:
                missing_rec.append(
                    {
                        "skill_id": req.skill_id,
                        "skill_name": req.skill_name,
                        "current_level": current,
                        "required_level": req.required_level,
                        "recommended_level": req.recommended_level,
                    }
                )

    if missing_req:
        status = "red"
    elif missing_rec:
        status = "yellow"
    else:
        status = "green"

    return {
        "status": status,
        "missing_required": missing_req,
        "missing_recommended": missing_rec,
        "met_required": met_req,
        "total_requirements": len(reqs),
    }


STATUS_RANK = {"green": 3, "yellow": 2, "red": 1, "unknown": 0}


def evaluate_fitting_for_user(version: FittingVersion, user: User) -> dict[str, Any]:
    """Evaluate a fitting across all characters owned by ``user``."""
    reqs = list(version.skill_requirements.all())
    ownerships = (
        CharacterOwnership.objects.filter(user=user)
        .select_related("character", "character__doctrinehub_skill_snapshot")
        .prefetch_related("character__doctrinehub_skill_snapshot__skills")
        .order_by("character__character_name")
    )
    characters: list[dict[str, Any]] = []
    best: dict[str, Any] = {
        "status": "unknown",
        "best_character_id": None,
        "best_character_name": None,
        "missing_required": [],
        "missing_recommended": [],
        "met_required": 0,
        "total_requirements": len(reqs),
        "characters": characters,
    }
    best_rank = -1
    for ownership in ownerships:
        char = ownership.character
        snapshot = getattr(char, "doctrinehub_skill_snapshot", None)
        ev = evaluate_fitting_for_snapshot(reqs, snapshot)
        characters.append(
            {
                "character_id": char.character_id,
                "character_name": char.character_name,
                **ev,
            }
        )
        rank = STATUS_RANK[ev["status"]]
        if rank > best_rank:
            best_rank = rank
            best.update(
                {
                    "status": ev["status"],
                    "best_character_id": char.character_id,
                    "best_character_name": char.character_name,
                    "missing_required": ev["missing_required"],
                    "missing_recommended": ev["missing_recommended"],
                    "met_required": ev["met_required"],
                }
            )
    return best


def export_skill_plan(
    version: FittingVersion,
    snapshot: CharacterSkillSnapshot | None = None,
    target: str = "minimum",
) -> str:
    """Return an EVE Online skill plan string for ``version``."""
    reqs = list(version.skill_requirements.order_by("skill_name", "skill_id"))
    trained: dict[int, int] = {}
    if snapshot is not None and snapshot.sync_status == CharacterSkillSnapshot.SyncStatus.OK:
        trained = {s.skill_id: s.active_skill_level for s in snapshot.skills.all()}

    lines: list[str] = []
    for req in reqs:
        goal = req.recommended_level if target == "recommended" else req.required_level
        current = trained.get(req.skill_id, 0)
        if snapshot is None or current < goal:
            lines.append(f"{req.skill_name} {goal}")
    return "\n".join(lines)


def compliance_overview(doctrines_qs: QuerySet[Doctrine]) -> dict[str, Any]:
    """Compute doctrine/role coverage and gap analysis across all users with characters."""
    users = list(User.objects.filter(character_ownerships__isnull=False).distinct())
    user_snapshots: dict[int, list[CharacterSkillSnapshot]] = {u.pk: [] for u in users}
    ownerships = (
        CharacterOwnership.objects.filter(user_id__in=user_snapshots.keys())
        .select_related("character", "character__doctrinehub_skill_snapshot")
        .prefetch_related("character__doctrinehub_skill_snapshot__skills")
    )
    for co in ownerships:
        snap = getattr(co.character, "doctrinehub_skill_snapshot", None)
        if snap is not None and snap.sync_status == CharacterSkillSnapshot.SyncStatus.OK:
            user_snapshots[co.user_id].append(snap)

    doctrines_qs = doctrines_qs.prefetch_related(
        "doctrine_fittings__fitting__versions__skill_requirements",
    )

    doctrine_rows: list[dict[str, Any]] = []
    blocking_users_by_skill: dict[int, tuple[str, set[int]]] = {}

    for doctrine in doctrines_qs:
        role_stats: dict[str, dict[str, Any]] = {}
        doctrine_pass_users = 0

        df_list = list(doctrine.doctrine_fittings.all())
        required_versions: list[tuple[Any, list[FittingSkillRequirement]]] = []
        for df in df_list:
            ver = df.fitting.current_version
            reqs = list(ver.skill_requirements.all()) if ver else []
            if df.is_required:
                required_versions.append((df, reqs))

            green = 0
            yellow = 0
            red = 0
            unknown = 0
            for u in users:
                snaps = user_snapshots[u.pk]
                if not snaps:
                    unknown += 1
                    continue
                best_ev = max(
                    (evaluate_fitting_for_snapshot(reqs, s) for s in snaps),
                    key=lambda e: STATUS_RANK[e["status"]],
                )
                if best_ev["status"] == "green":
                    green += 1
                elif best_ev["status"] == "yellow":
                    yellow += 1
                elif best_ev["status"] == "red":
                    red += 1
                    for miss in best_ev["missing_required"]:
                        sid = int(miss["skill_id"])
                        sname = str(miss["skill_name"])
                        entry = blocking_users_by_skill.get(sid)
                        if entry is None:
                            blocking_users_by_skill[sid] = (sname, {u.pk})
                        else:
                            entry[1].add(u.pk)
                else:
                    unknown += 1

            role_key = df.role or "unspecified"
            bucket = role_stats.setdefault(
                role_key,
                {"role": role_key, "fittings": [], "green": 0, "yellow": 0, "red": 0, "unknown": 0},
            )
            bucket["fittings"].append(
                {
                    "fitting_id": df.fitting_id,
                    "fitting_name": df.fitting.name,
                    "ship_type_name": df.fitting.ship_type_name,
                    "is_required": df.is_required,
                    "target_count": df.target_count,
                    "green": green,
                    "yellow": yellow,
                    "red": red,
                    "unknown": unknown,
                }
            )
            bucket["green"] += green
            bucket["yellow"] += yellow
            bucket["red"] += red
            bucket["unknown"] += unknown

        if required_versions:
            for u in users:
                snaps = user_snapshots[u.pk]
                if not snaps:
                    continue
                can_fly_all = True
                for _df, reqs in required_versions:
                    best_status = max(
                        (evaluate_fitting_for_snapshot(reqs, s)["status"] for s in snaps),
                        key=lambda st: STATUS_RANK[st],
                    )
                    if best_status not in {"green", "yellow"}:
                        can_fly_all = False
                        break
                if can_fly_all:
                    doctrine_pass_users += 1

        doctrine_rows.append(
            {
                "id": doctrine.pk,
                "name": doctrine.name,
                "total_members": len(users),
                "ready_members": doctrine_pass_users,
                "roles": list(role_stats.values()),
            }
        )

    gaps = sorted(
        (
            {
                "skill_id": sid,
                "skill_name": sname,
                "blocked_members": len(blocked_uids),
            }
            for sid, (sname, blocked_uids) in blocking_users_by_skill.items()
        ),
        key=lambda g: (-int(str(g["blocked_members"])), str(g["skill_name"])),
    )

    return {
        "total_members": len(users),
        "doctrines": doctrine_rows,
        "gaps": gaps,
    }
