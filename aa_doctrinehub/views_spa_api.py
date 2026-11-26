"""JSON API for the Doctrine Hub single-page app."""

from __future__ import annotations

import json
from typing import Any, cast

from allianceauth.authentication.models import CharacterOwnership
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Group, User
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .discord_i18n import language_choices
from .models import (
    Category,
    CharacterSkill,
    ComplianceAuditLog,
    ComplianceRule,
    Doctrine,
    DoctrineFitting,
    Fitting,
    FittingSkillRequirement,
    NotificationConfig,
    PendingApproval,
    RuleEvaluation,
    SyncSettings,
)
from .services.eft import EftParseError
from .services.esi_sync import character_link_status, sync_character_snapshot
from .services.fittings import import_eft, version_eft, version_multibuy
from .services.fittings_sync import fittings_app_installed
from .services.integrations import (
    compare_killmail_to_fitting,
    hangar_check_for_user,
    push_shortages_to_industry,
)
from .services.rules import (
    decide_pending_approval,
    ensure_default_capitals_rule,
    evaluate_all_rules,
)
from .services.skills import (
    compliance_overview,
    evaluate_fitting_for_user,
    export_skill_plan,
    extract_dogma_skills_for_version,
)
from .services.visibility import visible_doctrines, visible_fittings


def _user(request: HttpRequest) -> User:
    """The logged-in user; every view here is behind ``login_required``."""
    return cast(User, request.user)


def _json_body(request: HttpRequest) -> dict[str, Any]:
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _category_ref(category: Category) -> dict[str, Any]:
    return {"id": category.pk, "name": category.name, "color": category.color, "source": category.source}


def _fitting_summary(fitting: Fitting) -> dict[str, Any]:
    return {
        "id": fitting.pk,
        "name": fitting.name,
        "ship_type_id": fitting.ship_type_id,
        "ship_type_name": fitting.ship_type_name,
        "source": fitting.source,
        "is_editable": fitting.is_editable,
        "categories": [_category_ref(c) for c in fitting.categories.all()],
    }


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_GET
def doctrines(request: HttpRequest) -> JsonResponse:
    """All doctrines the user may see, with their fittings."""
    fittings_qs = visible_fittings(_user(request))
    qs = (
        visible_doctrines(_user(request))
        .prefetch_related(
            "categories",
            Prefetch(
                "doctrine_fittings",
                queryset=DoctrineFitting.objects.filter(fitting__in=fittings_qs)
                .select_related("fitting")
                .prefetch_related("fitting__categories"),
            ),
        )
        .order_by("name")
    )
    data = [
        {
            "id": d.pk,
            "name": d.name,
            "description": d.description,
            "icon_url": d.icon_url,
            "status": d.status,
            "source": d.source,
            "is_editable": d.is_editable,
            "last_synced_at": d.last_synced_at.isoformat() if d.last_synced_at else None,
            "categories": [_category_ref(c) for c in d.categories.all()],
            "fittings": [
                {
                    **_fitting_summary(df.fitting),
                    "role": df.role,
                    "is_required": df.is_required,
                    "target_count": df.target_count,
                }
                for df in d.doctrine_fittings.all()
            ],
        }
        for d in qs
    ]
    return JsonResponse({"doctrines": data})


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_GET
def fittings(request: HttpRequest) -> JsonResponse:
    """All fittings the user may see."""
    qs = visible_fittings(_user(request)).prefetch_related("categories")
    return JsonResponse({"fittings": [_fitting_summary(f) for f in qs]})


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_GET
def fitting_detail(request: HttpRequest, fitting_id: int) -> JsonResponse:
    """One fitting with its current version, EFT and multibuy text."""
    fitting = get_object_or_404(visible_fittings(_user(request)).prefetch_related("categories"), pk=fitting_id)
    version = fitting.current_version
    payload: dict[str, Any] = {
        **_fitting_summary(fitting),
        "description": fitting.description,
        "version": None,
    }
    if version:
        payload["version"] = {
            "number": version.number,
            "created_at": version.created_at.isoformat(),
            "change_note": version.change_note,
            "eft": version_eft(version),
            "multibuy": version_multibuy(version),
            "items": [
                {
                    "flag": i.flag,
                    "type_id": i.type_id,
                    "type_name": i.type_name,
                    "quantity": i.quantity,
                    "charge_name": i.charge_name,
                    "is_offline": i.is_offline,
                }
                for i in version.items.all()
            ],
        }
    return JsonResponse(payload)


@login_required
@permission_required("aa_doctrinehub.manage_doctrines")
@require_POST
def import_fitting(request: HttpRequest) -> JsonResponse:
    """Create a local fitting from EFT text."""
    body = _json_body(request)
    eft = str(body.get("eft", ""))
    try:
        fitting = import_eft(eft, user=_user(request), description=str(body.get("description", "")))
    except EftParseError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(_fitting_summary(fitting), status=201)


def _sync_settings_payload(settings: SyncSettings) -> dict[str, Any]:
    return {
        "fittings_app_installed": fittings_app_installed(),
        "fittings_sync_enabled": settings.fittings_sync_enabled,
        "fittings_sync_interval_days": settings.fittings_sync_interval_days,
        "fittings_last_sync_at": settings.fittings_last_sync_at.isoformat() if settings.fittings_last_sync_at else None,
        "fittings_last_sync_summary": settings.fittings_last_sync_summary,
    }


@login_required
@permission_required("aa_doctrinehub.manage_doctrines")
@require_http_methods(["GET", "POST"])
def sync_settings(request: HttpRequest) -> JsonResponse:
    """Read or change the Fittings sync settings."""
    settings = SyncSettings.get_solo()
    if request.method == "POST":
        body = _json_body(request)
        if "fittings_sync_enabled" in body:
            settings.fittings_sync_enabled = bool(body["fittings_sync_enabled"])
        if "fittings_sync_interval_days" in body:
            try:
                days = int(body["fittings_sync_interval_days"])
            except (TypeError, ValueError):
                return JsonResponse({"error": "fittings_sync_interval_days must be a whole number"}, status=400)
            if not 1 <= days <= 90:
                return JsonResponse({"error": "fittings_sync_interval_days must be between 1 and 90"}, status=400)
            settings.fittings_sync_interval_days = days
        settings.save()
    return JsonResponse(_sync_settings_payload(settings))


@login_required
@permission_required("aa_doctrinehub.manage_doctrines")
@require_POST
def run_fittings_sync(request: HttpRequest) -> JsonResponse:
    """Queue the Fittings sync to run now, in the background.

    Dispatches the same Celery task the daily beat schedule uses, rather
    than running the sync inline: a large Fittings catalogue can take long
    enough to risk a request timeout and ties up a web worker for no
    reason when a task queue already exists for this exact job.
    """
    if not fittings_app_installed():
        return JsonResponse({"error": "The Fittings app is not installed on this Auth"}, status=409)
    from .tasks import sync_from_fittings

    sync_from_fittings.delay(force=True)
    return JsonResponse({"queued": True, **_sync_settings_payload(SyncSettings.get_solo())})


@login_required
@permission_required("aa_doctrinehub.manage_doctrines")
@require_POST
def remote_scrape(request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
    """Preview or import doctrines, fittings, and categories from an external Auth."""
    from .models import Doctrine as DoctrineModel, Source as SourceChoices
    from .services.remote_scrape import (
        RemoteScrapeError,
        import_remote_scrape,
        iter_scrape_remote_fittings_site,
        preview_remote_fittings_site,
    )

    body = _json_body(request)
    base_url = str(body.get("base_url") or "")
    sessionid = str(body.get("sessionid") or "")
    mode = str(body.get("mode") or "preview")
    if mode not in {"preview", "import"}:
        return JsonResponse({"error": "mode must be 'preview' or 'import'"}, status=400)

    include_standalone_fits = bool(body.get("include_standalone_fits", True))
    include_categories = bool(body.get("include_categories", True))
    if "overwrite_existing" in body:
        skip_existing = not bool(body["overwrite_existing"])
    else:
        skip_existing = bool(body.get("skip_existing", False))
    raw_limit = body.get("limit")
    limit: int | None = None
    if raw_limit not in (None, "", 0, "0"):
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return JsonResponse({"error": "limit must be a positive whole number"}, status=400)
        if limit < 1:
            return JsonResponse({"error": "limit must be at least 1"}, status=400)

    raw_offset = body.get("offset", 0)
    try:
        offset = int(raw_offset or 0)
    except (TypeError, ValueError):
        return JsonResponse({"error": "offset must be a non-negative whole number"}, status=400)
    if offset < 0:
        return JsonResponse({"error": "offset must be at least 0"}, status=400)

    def _build_import_payload(snapshot, result) -> dict[str, Any]:
        return {
            "mode": "import",
            "summary": result.summary(),
            "fittings_created": result.fittings_created,
            "fittings_updated": result.fittings_updated,
            "fittings_removed": result.fittings_removed,
            "doctrines_created": result.doctrines_created,
            "doctrines_updated": result.doctrines_updated,
            "doctrines_archived": result.doctrines_archived,
            "categories_synced": result.categories_synced,
            "total_doctrines_stored": DoctrineModel.objects.from_source(SourceChoices.REMOTE_AUTH).count(),
            "total_fittings_stored": Fitting.objects.from_source(SourceChoices.REMOTE_AUTH).count(),
            "total_categories_stored": Category.objects.from_source(SourceChoices.REMOTE_AUTH).count(),
            "doctrines": [
                {
                    "external_id": d.external_id,
                    "name": d.name,
                    "fittings_count": len(d.fitting_ids),
                }
                for d in snapshot.doctrines
            ],
        }

    def _iter_events():
        try:
            if mode == "preview":
                logs: list[str] = []
                data = preview_remote_fittings_site(
                    base_url,
                    sessionid,
                    include_standalone_fits=include_standalone_fits,
                    include_categories=include_categories,
                    limit=limit,
                    offset=offset,
                    skip_existing=skip_existing,
                    on_progress=logs.append,
                )
                for msg in logs:
                    yield json.dumps({"type": "log", "message": msg}) + "\n"
                yield json.dumps({"type": "result", "data": data}) + "\n"
                return

            snapshot = None
            for kind, payload in iter_scrape_remote_fittings_site(
                base_url,
                sessionid,
                include_standalone_fits=include_standalone_fits,
                include_categories=include_categories,
                limit=limit,
                offset=offset,
                skip_existing=skip_existing,
            ):
                if kind == "log":
                    yield json.dumps({"type": "log", "message": str(payload)}) + "\n"
                elif kind == "snapshot":
                    snapshot = payload

            assert snapshot is not None
            yield (
                json.dumps(
                    {
                        "type": "log",
                        "message": (
                            f"Saving {len(snapshot.doctrines)} doctrines, {len(snapshot.fittings)} fittings, "
                            f"and {len(snapshot.categories)} categories..."
                        ),
                    }
                )
                + "\n"
            )
            prune_missing = limit is None and offset == 0 and not skip_existing
            result = import_remote_scrape(snapshot, prune_missing=prune_missing)
            yield json.dumps({"type": "log", "message": f"Done: {result.summary()}"}) + "\n"
            yield json.dumps({"type": "result", "data": _build_import_payload(snapshot, result)}) + "\n"
        except RemoteScrapeError as exc:
            yield json.dumps({"type": "error", "error": str(exc)}) + "\n"

    if bool(body.get("stream")):
        response = StreamingHttpResponse(_iter_events(), content_type="application/x-ndjson")
        response["X-Accel-Buffering"] = "no"
        response["Cache-Control"] = "no-cache"
        return response

    try:
        if mode == "preview":
            return JsonResponse(
                preview_remote_fittings_site(
                    base_url,
                    sessionid,
                    include_standalone_fits=include_standalone_fits,
                    include_categories=include_categories,
                    limit=limit,
                    offset=offset,
                    skip_existing=skip_existing,
                )
            )
        snapshot = None
        for kind, payload in iter_scrape_remote_fittings_site(
            base_url,
            sessionid,
            include_standalone_fits=include_standalone_fits,
            include_categories=include_categories,
            limit=limit,
            offset=offset,
            skip_existing=skip_existing,
        ):
            if kind == "snapshot":
                snapshot = payload
        assert snapshot is not None
        prune_missing = limit is None and offset == 0 and not skip_existing
        result = import_remote_scrape(snapshot, prune_missing=prune_missing)
        return JsonResponse(_build_import_payload(snapshot, result))
    except RemoteScrapeError as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@login_required
@permission_required("aa_doctrinehub.manage_doctrines")
@require_POST
def remote_scrape_purge(request: HttpRequest) -> JsonResponse:
    """Delete all imported External Auth doctrines, fittings, and categories."""
    from .services.remote_scrape import purge_remote_auth_records

    counts = purge_remote_auth_records()
    return JsonResponse({"ok": True, **counts})


# ---------------------------------------------------------------------------
# Phase 2: Eligibility, ESI snapshots, skill plans, and compliance overview
# ---------------------------------------------------------------------------


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_GET
def eligibility_status(request: HttpRequest) -> JsonResponse:
    """Return ESI linking and snapshot sync status for the user's characters."""
    characters = character_link_status(_user(request))
    all_linked = bool(characters) and all(c["has_valid_token"] for c in characters)
    return JsonResponse({"all_linked": all_linked, "characters": characters})


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_POST
def eligibility_sync(request: HttpRequest) -> JsonResponse:
    """Trigger an on-demand ESI snapshot sync for all characters of the current user."""
    ownerships = CharacterOwnership.objects.filter(user=_user(request)).select_related("character")
    for co in ownerships:
        sync_character_snapshot(co.character)
    characters = character_link_status(_user(request))
    return JsonResponse({"ok": True, "characters": characters})


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_GET
def fitting_eligibility(request: HttpRequest, fitting_id: int) -> JsonResponse:
    """Return traffic-light eligibility and skill requirements for one fitting."""
    fitting = get_object_or_404(visible_fittings(_user(request)), pk=fitting_id)
    version = fitting.current_version
    if version is None:
        return JsonResponse({"status": "unknown", "requirements": [], "characters": []})
    reqs = list(version.skill_requirements.all())
    ev = evaluate_fitting_for_user(version, _user(request))
    return JsonResponse(
        {
            **ev,
            "requirements": [
                {
                    "id": r.pk,
                    "skill_id": r.skill_id,
                    "skill_name": r.skill_name,
                    "required_level": r.required_level,
                    "recommended_level": r.recommended_level,
                    "source": r.source,
                }
                for r in reqs
            ],
        }
    )


@login_required
@permission_required("aa_doctrinehub.manage_doctrines")
@require_http_methods(["POST", "DELETE"])
def fitting_skills(request: HttpRequest, fitting_id: int) -> JsonResponse:
    """Add/update a manual skill requirement, refresh dogma skills, or remove one."""
    fitting = get_object_or_404(Fitting, pk=fitting_id)
    version = fitting.current_version
    if version is None:
        return JsonResponse({"error": "Fitting has no version."}, status=400)
    data = _json_body(request)

    if request.method == "DELETE":
        skill_id = int(data.get("skill_id") or request.GET.get("skill_id") or 0)
        deleted, _ = FittingSkillRequirement.objects.filter(version=version, skill_id=skill_id).delete()
        return JsonResponse({"deleted": deleted})

    if data.get("refresh_dogma"):
        reqs = extract_dogma_skills_for_version(version)
        return JsonResponse({"count": len(reqs)})

    skill_id = int(data.get("skill_id") or 0)
    skill_name = str(data.get("skill_name") or "").strip()
    required_level = max(1, min(5, int(data.get("required_level") or 1)))
    recommended_level = max(required_level, min(5, int(data.get("recommended_level") or required_level)))
    if not skill_id or not skill_name:
        return JsonResponse({"error": "skill_id and skill_name are required."}, status=400)

    req, _ = FittingSkillRequirement.objects.update_or_create(
        version=version,
        skill_id=skill_id,
        defaults={
            "skill_name": skill_name,
            "required_level": required_level,
            "recommended_level": recommended_level,
            "source": FittingSkillRequirement.RequirementSource.MANUAL,
        },
    )
    return JsonResponse(
        {
            "id": req.pk,
            "skill_id": req.skill_id,
            "skill_name": req.skill_name,
            "required_level": req.required_level,
            "recommended_level": req.recommended_level,
            "source": req.source,
        },
        status=201,
    )


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_GET
def fitting_skill_plan(request: HttpRequest, fitting_id: int) -> JsonResponse:
    """Return an EVE Online skill plan for ``fitting_id``."""
    fitting = get_object_or_404(visible_fittings(_user(request)), pk=fitting_id)
    version = fitting.current_version
    if version is None:
        return JsonResponse({"skill_plan": ""})
    target = "recommended" if request.GET.get("target") == "recommended" else "minimum"
    char_id = request.GET.get("character_id")
    snapshot = None
    if char_id:
        co = (
            CharacterOwnership.objects.filter(user=_user(request), character__character_id=int(char_id))
            .select_related("character__doctrinehub_skill_snapshot")
            .first()
        )
        if co:
            snapshot = getattr(co.character, "doctrinehub_skill_snapshot", None)
    plan = export_skill_plan(version, snapshot=snapshot, target=target)
    return JsonResponse({"skill_plan": plan, "target": target})


@login_required
@permission_required("aa_doctrinehub.view_compliance")
@require_GET
def compliance_overview_view(request: HttpRequest) -> JsonResponse:
    """Return doctrine/role coverage and skill gap analysis."""
    qs = visible_doctrines(_user(request))
    return JsonResponse(compliance_overview(qs))


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_GET
def skills_search(request: HttpRequest) -> JsonResponse:
    """Search EVE skills by name or ID (via eveuniverse if installed, plus synced skill snapshots)."""
    q = str(request.GET.get("q") or "").strip()
    skill_id_param = request.GET.get("id")
    results: dict[int, str] = {}

    try:
        from eveuniverse.models import EveType

        qs = EveType.objects.filter(eve_group__eve_category_id=16, published=True)
        if skill_id_param and skill_id_param.isdigit():
            qs = qs.filter(id=int(skill_id_param))
        elif q:
            if q.isdigit():
                qs = qs.filter(id=int(q))
            else:
                qs = qs.filter(name__icontains=q)
        for tid, name in qs.order_by("name").values_list("id", "name")[:50]:
            results[int(tid)] = str(name)
    except ImportError:
        pass

    if len(results) < 50:
        cs_qs = CharacterSkill.objects.all()
        fs_qs = FittingSkillRequirement.objects.all()
        if skill_id_param and skill_id_param.isdigit():
            cs_qs = cs_qs.filter(skill_id=int(skill_id_param))
            fs_qs = fs_qs.filter(skill_id=int(skill_id_param))
        elif q:
            if q.isdigit():
                cs_qs = cs_qs.filter(skill_id=int(q))
                fs_qs = fs_qs.filter(skill_id=int(q))
            else:
                cs_qs = cs_qs.filter(skill_name__icontains=q)
                fs_qs = fs_qs.filter(skill_name__icontains=q)
        for sid, sname in cs_qs.values_list("skill_id", "skill_name").distinct()[:50]:
            if int(sid) not in results and sname:
                results[int(sid)] = str(sname)
        for sid, sname in fs_qs.values_list("skill_id", "skill_name").distinct()[:50]:
            if int(sid) not in results and sname:
                results[int(sid)] = str(sname)

    items = sorted(
        ({"id": sid, "name": sname} for sid, sname in results.items()),
        key=lambda x: str(x["name"]),
    )[:50]
    return JsonResponse({"skills": items})


# ---------------------------------------------------------------------------
# Phase 3: Compliance rules, approvals, audit log, and notification settings
# ---------------------------------------------------------------------------


def _serialize_rule(rule: ComplianceRule) -> dict[str, Any]:
    evals = list(rule.evaluations.all())
    return {
        "id": rule.pk,
        "name": rule.name,
        "description": rule.description,
        "group_id": rule.group_id,
        "group_name": rule.group.name,
        "mode": rule.mode,
        "is_active": rule.is_active,
        "grace_period_hours": rule.grace_period_hours,
        "condition_tree": rule.condition_tree,
        "summary": {
            "pass": sum(1 for e in evals if e.status == RuleEvaluation.Status.PASS),
            "fail": sum(1 for e in evals if e.status == RuleEvaluation.Status.FAIL),
            "unknown": sum(1 for e in evals if e.status == RuleEvaluation.Status.UNKNOWN),
        },
        "evaluations": [
            {
                "username": e.user.username,
                "status": e.status,
                "reasons": e.details.get("reasons", []) if isinstance(e.details, dict) else [],
                "items": e.details.get("items", []) if isinstance(e.details, dict) else [],
                "grace_until": e.grace_until.isoformat() if e.grace_until else None,
                "evaluated_at": e.evaluated_at.isoformat() if e.evaluated_at else None,
            }
            for e in sorted(evals, key=lambda x: (x.status != RuleEvaluation.Status.FAIL, x.user.username))
        ],
    }


@login_required
@permission_required("aa_doctrinehub.manage_rules")
@require_http_methods(["GET", "POST"])
def rules_collection(request: HttpRequest) -> JsonResponse:
    """List compliance rules (seeding SIG: Capitals if requested) or create a new rule."""
    if request.method == "GET":
        if request.GET.get("seed_capitals") == "1" or not ComplianceRule.objects.exists():
            ensure_default_capitals_rule()
        rules = ComplianceRule.objects.select_related("group").prefetch_related("evaluations__user").all()
        groups = [{"id": g.pk, "name": g.name} for g in Group.objects.order_by("name")]
        return JsonResponse({"rules": [_serialize_rule(r) for r in rules], "groups": groups})

    data = _json_body(request)
    name = str(data.get("name") or "").strip()
    group_id = data.get("group_id")
    if not name or not group_id:
        return JsonResponse({"error": "name and group_id are required."}, status=400)
    group = get_object_or_404(Group, pk=int(group_id))
    mode = str(data.get("mode") or ComplianceRule.Mode.REPORT_ONLY)
    if mode not in set(ComplianceRule.Mode.values):
        return JsonResponse({"error": "Invalid rule mode."}, status=400)
    rule = ComplianceRule.objects.create(
        name=name,
        description=str(data.get("description") or ""),
        group=group,
        mode=mode,
        is_active=bool(data.get("is_active", True)),
        grace_period_hours=max(1, int(data.get("grace_period_hours") or 48)),
        condition_tree=data.get("condition_tree") or {},
    )
    return JsonResponse(_serialize_rule(rule), status=201)


@login_required
@permission_required("aa_doctrinehub.manage_rules")
@require_http_methods(["PUT", "DELETE"])
def rule_detail(request: HttpRequest, rule_id: int) -> JsonResponse:
    """Update or delete a compliance rule."""
    rule = get_object_or_404(ComplianceRule.objects.select_related("group"), pk=rule_id)
    if request.method == "DELETE":
        rule.delete()
        return JsonResponse({"ok": True})

    data = _json_body(request)
    if "name" in data:
        rule.name = str(data["name"]).strip() or rule.name
    if "description" in data:
        rule.description = str(data["description"])
    if "group_id" in data and data["group_id"]:
        rule.group = get_object_or_404(Group, pk=int(data["group_id"]))
    if "mode" in data and data["mode"] in set(ComplianceRule.Mode.values):
        rule.mode = str(data["mode"])
    if "is_active" in data:
        rule.is_active = bool(data["is_active"])
    if "grace_period_hours" in data:
        rule.grace_period_hours = max(1, int(data["grace_period_hours"]))
    if "condition_tree" in data and isinstance(data["condition_tree"], dict):
        rule.condition_tree = data["condition_tree"]
    rule.save()
    return JsonResponse(_serialize_rule(rule))


@login_required
@permission_required("aa_doctrinehub.manage_rules")
@require_POST
def rules_evaluate(request: HttpRequest) -> JsonResponse:
    """Run compliance rule evaluation immediately."""
    counts = evaluate_all_rules()
    return JsonResponse({"ok": True, **counts})


@login_required
@permission_required("aa_doctrinehub.manage_rules")
@require_GET
def rules_approvals(request: HttpRequest) -> JsonResponse:
    """List pending reviewer approvals."""
    qs = PendingApproval.objects.filter(status=PendingApproval.Status.PENDING).select_related(
        "rule", "rule__group", "user"
    )
    return JsonResponse(
        {
            "approvals": [
                {
                    "id": a.pk,
                    "rule_id": a.rule_id,
                    "rule_name": a.rule.name,
                    "group_name": a.rule.group.name,
                    "user_id": a.user_id,
                    "username": a.user.username,
                    "action": a.action,
                    "reason": a.reason,
                    "created_at": a.created_at.isoformat(),
                }
                for a in qs
            ]
        }
    )


@login_required
@permission_required("aa_doctrinehub.manage_rules")
@require_POST
def rule_approval_decide(request: HttpRequest, approval_id: int) -> JsonResponse:
    """Approve or reject a pending group grant/revocation."""
    approval = get_object_or_404(PendingApproval.objects.select_related("rule", "rule__group", "user"), pk=approval_id)
    data = _json_body(request)
    approve = bool(data.get("approve", True))
    note = str(data.get("note") or "")
    decide_pending_approval(approval, _user(request), approve=approve, note=note)
    return JsonResponse({"ok": True, "status": approval.status})


@login_required
@permission_required("aa_doctrinehub.manage_rules")
@require_GET
def rules_audit(request: HttpRequest) -> JsonResponse:
    """Return the latest 100 compliance audit log entries."""
    logs = ComplianceAuditLog.objects.select_related("rule", "user", "group", "actor")[:100]
    return JsonResponse(
        {
            "logs": [
                {
                    "id": entry.pk,
                    "rule_name": entry.rule.name if entry.rule else "",
                    "username": entry.user.username,
                    "group_name": entry.group.name,
                    "action": entry.action,
                    "reason": entry.reason,
                    "actor": entry.actor.username if entry.actor else "system",
                    "created_at": entry.created_at.isoformat(),
                }
                for entry in logs
            ]
        }
    )


@login_required
@permission_required("aa_doctrinehub.manage_rules")
@require_http_methods(["GET", "PUT"])
def notification_settings(request: HttpRequest) -> JsonResponse:
    """Read or update Discord webhook and fixed-language settings."""
    cfg = NotificationConfig.get_solo()
    if request.method == "PUT":
        data = _json_body(request)
        if "discord_webhook_url" in data:
            cfg.discord_webhook_url = str(data["discord_webhook_url"]).strip()
        if "discord_language" in data:
            cfg.discord_language = str(data["discord_language"]).strip()
        if "dm_warnings_enabled" in data:
            cfg.dm_warnings_enabled = bool(data["dm_warnings_enabled"])
        cfg.save()
    return JsonResponse(
        {
            "discord_webhook_url": cfg.discord_webhook_url,
            "discord_language": cfg.discord_language,
            "dm_warnings_enabled": cfg.dm_warnings_enabled,
            "language_choices": [{"code": code, "label": label} for code, label in language_choices()],
        }
    )


# ---------------------------------------------------------------------------
# Phase 4: Hangar check, aa-industry shortage push, and SRP killmail compare
# ---------------------------------------------------------------------------


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_GET
def hangar_check_view(request: HttpRequest) -> JsonResponse:
    """Check fitted doctrine ships in the current user's hangars."""
    doctrine_id = request.GET.get("doctrine_id")
    ships = hangar_check_for_user(_user(request), doctrine_id=int(doctrine_id) if doctrine_id else None)
    return JsonResponse({"ships": ships})


@login_required
@permission_required("aa_doctrinehub.manage_doctrines")
@require_POST
def industry_order_view(request: HttpRequest) -> JsonResponse:
    """Push doctrine ship shortages to aa-industry as an order."""
    data = _json_body(request)
    doctrine_id = int(data.get("doctrine_id") or 0)
    doctrine = get_object_or_404(Doctrine, pk=doctrine_id)
    return JsonResponse(push_shortages_to_industry(doctrine, _user(request)))


@login_required
@permission_required("aa_doctrinehub.basic_access")
@require_POST
def srp_compare_view(request: HttpRequest) -> JsonResponse:
    """Compare a killmail JSON payload against a doctrine fitting version for SRP."""
    data = _json_body(request)
    fitting_id = int(data.get("fitting_id") or 0)
    killmail = data.get("killmail")
    if not fitting_id or not isinstance(killmail, dict):
        return JsonResponse({"error": "fitting_id and killmail JSON object are required."}, status=400)
    fitting = get_object_or_404(visible_fittings(_user(request)), pk=fitting_id)
    version = fitting.current_version
    if version is None:
        return JsonResponse({"error": "Fitting has no version."}, status=400)
    return JsonResponse(compare_killmail_to_fitting(killmail, version))
