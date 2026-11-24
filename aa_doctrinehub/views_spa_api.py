"""JSON API for the Doctrine Hub single-page app."""

from __future__ import annotations

import json
from typing import Any, cast

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import Category, DoctrineFitting, Fitting, SyncSettings
from .services.eft import EftParseError
from .services.fittings import import_eft, version_eft, version_multibuy
from .services.fittings_sync import fittings_app_installed
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
