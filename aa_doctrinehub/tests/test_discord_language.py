"""Tests for fixed-language Discord notifications (AGENTS §14)."""

from unittest.mock import patch

import pytest
from allianceauth.tests.auth_utils import AuthUtils
from django.utils import timezone, translation

from aa_doctrinehub.discord_i18n import channel_language, discord_language, user_language
from aa_doctrinehub.services.rules import ensure_default_capitals_rule, format_channel_notice, format_warning_dm

pytestmark = pytest.mark.django_db


def test_channel_notice_ignores_active_request_language():
    user = AuthUtils.create_user("nl_trigger")
    rule = ensure_default_capitals_rule()

    with translation.override("nl"):
        with patch("aa_doctrinehub.services.rules._", side_effect=lambda s: f"[EN] {s}"):
            msg = format_channel_notice(rule, user, "granted", lang="en")
    assert msg.startswith("[EN] ")
    assert channel_language("en") == "en"


def test_dm_warning_follows_recipient_language():
    user = AuthUtils.create_user("de_pilot")
    user.profile.language = "de"
    rule = ensure_default_capitals_rule()
    assert user_language(user) == "de"

    seen_langs: list[str] = []
    with translation.override("nl"):
        with discord_language(user_language(user)):
            seen_langs.append(translation.get_language())
        title, body = format_warning_dm(user, rule, timezone.now())
    assert seen_langs == ["de"]
    assert rule.name in title
    assert rule.group.name in body
