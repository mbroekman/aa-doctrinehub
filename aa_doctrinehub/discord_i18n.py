"""Fixed-language helper for Discord messages sent by aa-doctrinehub (AGENTS §14)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _


def default_language() -> str:
    """Return the configured default Discord message language."""
    return getattr(settings, "DISCORD_MESSAGE_LANGUAGE", "") or settings.LANGUAGE_CODE


def channel_language(code: str | None) -> str:
    """Return the channel's configured language, falling back to default_language()."""
    return code or default_language()


def user_language(user: Any) -> str:
    """Return the recipient's Alliance Auth language, falling back to default_language()."""
    profile = getattr(user, "profile", None)
    lang = getattr(profile, "language", "") if profile is not None else ""
    return lang or default_language()


@contextmanager
def discord_language(code: str | None) -> Iterator[None]:
    """Context manager that activates the target Discord language for gettext calls."""
    with translation.override(code or default_language()):
        yield


def language_choices() -> list[tuple[str, str]]:
    """Choices for configuring a webhook language in the frontend."""
    return [("", str(_("Default")))] + [(code, str(label)) for code, label in settings.LANGUAGES]
