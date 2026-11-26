"""Fill in hull types and skill requirements of fittings that miss them."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from aa_doctrinehub.models import Fitting
from aa_doctrinehub.services.fittings import refresh_incomplete_fittings, refresh_requirements


class Command(BaseCommand):
    help = "Resolve ship and item type IDs and recompute dogma skill requirements of fittings."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--all", action="store_true", help="Refresh every fitting, not only incomplete ones.")

    def handle(self, *args: Any, **options: Any) -> None:
        if options["all"]:
            count = 0
            for fitting in Fitting.objects.all():
                refresh_requirements(fitting)
                count += 1
        else:
            count = refresh_incomplete_fittings()
        for fitting in Fitting.objects.all():
            version = fitting.current_version
            if not fitting.ship_type_id or version is None or not version.skill_requirements.exists():
                self.stdout.write(self.style.WARNING(f"Still incomplete: {fitting} (id {fitting.pk})"))
        self.stdout.write(self.style.SUCCESS(f"Refreshed {count} fitting(s)."))
