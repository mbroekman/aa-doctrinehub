"""App configuration for aa_doctrinehub."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AaDoctrineHubConfig(AppConfig):
    """Django app config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "aa_doctrinehub"
    label = "aa_doctrinehub"
    verbose_name = _("Doctrine Hub")
