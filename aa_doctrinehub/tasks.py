"""Celery tasks for aa_doctrinehub."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import SyncSettings
from .services.esi_sync import sync_all_characters
from .services.fittings_sync import sync_from_fittings_app
from .services.rules import evaluate_all_rules

logger = logging.getLogger(__name__)


def fittings_sync_due(settings: SyncSettings) -> bool:
    """Whether the periodic Fittings sync should run now."""
    if not settings.fittings_sync_enabled:
        return False
    if settings.fittings_last_sync_at is None:
        return True
    interval = timedelta(days=max(settings.fittings_sync_interval_days, 1))
    # A little slack, so a daily beat run at a fixed time still fires on the due day.
    return timezone.now() - settings.fittings_last_sync_at >= interval - timedelta(hours=1)


@shared_task(name="aa_doctrinehub.tasks.sync_from_fittings")
def sync_from_fittings(force: bool = False) -> str:
    """Copy doctrines and fittings from the Fittings app when enabled and due.

    Runs daily from beat; the interval in days is set in the frontend settings.
    """
    settings = SyncSettings.get_solo()
    if not force and not fittings_sync_due(settings):
        return "skipped"
    result = sync_from_fittings_app()
    return result.summary() if result else "fittings app not installed"


@shared_task(name="aa_doctrinehub.tasks.sync_character_snapshots")
def sync_character_snapshots() -> str:
    """Sync character skills, implants, and assets from ESI every 4 hours."""
    counts = sync_all_characters()
    return f"ok={counts['ok']} error={counts['error']}"


@shared_task(name="aa_doctrinehub.tasks.evaluate_compliance_rules")
def evaluate_compliance_rules() -> str:
    """Evaluate all active compliance rules and apply automatic group grants/revocations."""
    counts = evaluate_all_rules()
    return f"rules={counts['rules']} evaluations={counts['evaluations']}"
