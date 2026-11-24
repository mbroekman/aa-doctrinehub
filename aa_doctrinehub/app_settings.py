"""Technical settings for aa_doctrinehub, read from Django settings."""

from django.conf import settings

DOCTRINEHUB_APP_NAME: str = getattr(settings, "DOCTRINEHUB_APP_NAME", "Doctrines")
