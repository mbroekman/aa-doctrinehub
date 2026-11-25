"""Tests for Phase 3: Compliance rules, AND/OR/AT_LEAST, grace period, GroupGrant, and audit log."""

from datetime import timedelta

import pytest
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.tests.auth_utils import AuthUtils
from django.contrib.auth.models import Group
from django.utils import timezone

from aa_doctrinehub.models import (
    CharacterSkill,
    CharacterSkillSnapshot,
    ComplianceAuditLog,
    ComplianceRule,
    GroupGrant,
    PendingApproval,
    RuleEvaluation,
)
from aa_doctrinehub.services.rules import (
    apply_rule_for_user,
    decide_pending_approval,
    ensure_default_capitals_rule,
    evaluate_condition_tree,
)

pytestmark = pytest.mark.django_db


def _user_with_snapshot(username="rulepilot", char_id=94001, total_sp=20000000, cap_level=1):
    user = AuthUtils.create_user(username)
    AuthUtils.add_main_character(user, f"Char {char_id}", character_id=char_id)
    user.profile.refresh_from_db()
    char = user.profile.main_character
    assert char is not None
    CharacterOwnership.objects.get_or_create(user=user, character=char, defaults={"owner_hash": f"hash-{char_id}"})
    snap = CharacterSkillSnapshot.objects.create(
        character=char,
        total_sp=total_sp,
        sync_status=CharacterSkillSnapshot.SyncStatus.OK,
    )
    CharacterSkill.objects.create(
        snapshot=snap,
        skill_id=20533,
        skill_name="Capital Ships",
        active_skill_level=cap_level,
        trained_skill_level=cap_level,
    )
    return user, char, snap


def test_condition_tree_and_or_at_least():
    user, _c, _s = _user_with_snapshot("treeuser", 94002, total_sp=20000000, cap_level=1)
    tree_at_least = {
        "op": "AT_LEAST",
        "n": 2,
        "children": [
            {"type": "skill", "skill_id": 20533, "min_level": 1},
            {"type": "total_sp", "min_sp": 15000000},
            {"type": "total_sp", "min_sp": 999000000},
        ],
    }
    status, _ = evaluate_condition_tree(tree_at_least, user)
    assert status == RuleEvaluation.Status.PASS

    tree_or = {
        "op": "OR",
        "children": [
            {"type": "total_sp", "min_sp": 999000000},
            {"type": "skill", "skill_id": 20533, "min_level": 1},
        ],
    }
    assert evaluate_condition_tree(tree_or, user)[0] == RuleEvaluation.Status.PASS


def test_automatic_grant_grace_period_revocation_and_unknown_safety():
    user, _c, snap = _user_with_snapshot("autouser", 94003, total_sp=20000000, cap_level=1)
    rule = ensure_default_capitals_rule()
    assert rule.mode == ComplianceRule.Mode.REPORT_ONLY

    rule.mode = ComplianceRule.Mode.AUTOMATIC
    rule.grace_period_hours = 24
    rule.save()

    # Pass -> grants group + creates GroupGrant + audit log
    ev = apply_rule_for_user(rule, user)
    assert ev.status == RuleEvaluation.Status.PASS
    assert user.groups.filter(pk=rule.group_id).exists()
    assert GroupGrant.objects.filter(rule=rule, user=user, revoked_at__isnull=True).exists()
    assert ComplianceAuditLog.objects.filter(rule=rule, user=user, action=ComplianceAuditLog.Action.GRANTED).exists()

    # ESI error -> status unknown -> NEVER revokes!
    snap.sync_status = CharacterSkillSnapshot.SyncStatus.ERROR
    snap.save()
    ev = apply_rule_for_user(rule, user)
    assert ev.status == RuleEvaluation.Status.UNKNOWN
    assert user.groups.filter(pk=rule.group_id).exists()

    # Recover snapshot, but fail condition -> first failure sets grace_until + warning, does not revoke yet
    snap.sync_status = CharacterSkillSnapshot.SyncStatus.OK
    snap.total_sp = 1000
    snap.save()
    ev = apply_rule_for_user(rule, user)
    assert ev.status == RuleEvaluation.Status.FAIL
    assert ev.grace_until is not None
    assert user.groups.filter(pk=rule.group_id).exists()
    assert ComplianceAuditLog.objects.filter(rule=rule, user=user, action=ComplianceAuditLog.Action.WARNED).exists()

    # Fast-forward past grace_until -> revokes GroupGrant
    ev.grace_until = timezone.now() - timedelta(minutes=5)
    ev.save()
    ev = apply_rule_for_user(rule, user)
    assert not user.groups.filter(pk=rule.group_id).exists()
    assert GroupGrant.objects.filter(rule=rule, user=user, revoked_at__isnull=False).exists()
    assert ComplianceAuditLog.objects.filter(rule=rule, user=user, action=ComplianceAuditLog.Action.REVOKED).exists()


def test_reviewer_approval_workflow():
    user, _c, _s = _user_with_snapshot("revuser", 94004, total_sp=20000000, cap_level=1)
    reviewer = AuthUtils.create_user("reviewer")
    group = Group.objects.create(name="SIG: Reviewers Test")
    rule = ComplianceRule.objects.create(
        name="Reviewer Rule",
        group=group,
        mode=ComplianceRule.Mode.REVIEWER_APPROVAL,
        condition_tree={"type": "skill", "skill_id": 20533, "min_level": 1},
    )
    apply_rule_for_user(rule, user)
    approval = PendingApproval.objects.get(rule=rule, user=user, status=PendingApproval.Status.PENDING)
    decide_pending_approval(approval, reviewer, approve=True, note="Looks good")
    assert user.groups.filter(pk=group.pk).exists()
    assert ComplianceAuditLog.objects.filter(rule=rule, user=user, action=ComplianceAuditLog.Action.APPROVED).exists()
