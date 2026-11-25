"""Compliance rule evaluation, automatic Auth group grants/revocations, and Discord i18n."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import requests
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.notifications import notify
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from ..discord_i18n import channel_language, discord_language, user_language
from ..models import (
    CharacterAsset,
    CharacterSkillSnapshot,
    ComplianceAuditLog,
    ComplianceRule,
    Doctrine,
    Fitting,
    GroupGrant,
    NotificationConfig,
    PendingApproval,
    RuleEvaluation,
)
from .integrations import count_user_fats
from .skills import STATUS_RANK, evaluate_fitting_for_snapshot

logger = logging.getLogger(__name__)

PASS = RuleEvaluation.Status.PASS
FAIL = RuleEvaluation.Status.FAIL
UNKNOWN = RuleEvaluation.Status.UNKNOWN


def _user_snapshots(user: User) -> list[CharacterSkillSnapshot]:
    snaps: list[CharacterSkillSnapshot] = []
    ownerships = CharacterOwnership.objects.filter(user=user).select_related(
        "character", "character__doctrinehub_skill_snapshot"
    ).prefetch_related(
        "character__doctrinehub_skill_snapshot__skills",
        "character__doctrinehub_skill_snapshot__implants",
    )
    for co in ownerships:
        snap = getattr(co.character, "doctrinehub_skill_snapshot", None)
        if snap is not None and snap.sync_status == CharacterSkillSnapshot.SyncStatus.OK:
            snaps.append(snap)
    return snaps


def _user_has_ship_in_structure(snapshots: list[CharacterSkillSnapshot], ship_type_id: int | None) -> bool:
    """Return True if any synced character of the account has the ship hull docked in a player structure."""
    if not ship_type_id or not snapshots:
        return False
    char_ids = [s.character_id for s in snapshots]
    return CharacterAsset.objects.filter(
        character_id__in=char_ids,
        type_id=ship_type_id,
        is_singleton=True,
        location_id__gte=1000000000000,
    ).exists()


def _skill_name(skill_id: int) -> str:
    try:
        from eveuniverse.models import EveType

        name = EveType.objects.filter(id=skill_id).values_list("name", flat=True).first()
        if name:
            return str(name)
    except ImportError:
        pass
    return f"Skill {skill_id}"


def _format_missing_skills(best: dict[str, Any], level: str) -> str:
    missing = list(best.get("missing_required") or [])
    if level == "recommended":
        missing.extend(best.get("missing_recommended") or [])
    if not missing:
        return "missing required skills"
    parts = [
        f"{m['skill_name']} {m['recommended_level'] if level == 'recommended' else m['required_level']} "
        f"(have {m['current_level']})"
        for m in missing[:6]
    ]
    suffix = f" (+{len(missing) - 6} more)" if len(missing) > 6 else ""
    return "Missing skills: " + ", ".join(parts) + suffix


def _eval_leaf(node: dict[str, Any], user: User, snapshots: list[CharacterSkillSnapshot]) -> tuple[str, str]:
    ctype = str(node.get("type", ""))

    if ctype == "can_fly_fitting":
        fitting_id = int(node.get("fitting_id") or 0)
        level = str(node.get("level", "minimum"))
        require_ship = bool(node.get("require_ship", True))
        fitting = Fitting.objects.filter(pk=fitting_id).prefetch_related("versions__skill_requirements").first()
        if fitting is None or fitting.current_version is None:
            return UNKNOWN, "Fitting not found"
        if not snapshots:
            return UNKNOWN, "No synced skill snapshot"
        reqs = list(fitting.current_version.skill_requirements.all())
        best = max(
            (evaluate_fitting_for_snapshot(reqs, s) for s in snapshots),
            key=lambda e: STATUS_RANK[e["status"]],
        )
        ok_statuses = {"green"} if level == "recommended" else {"green", "yellow"}
        if best["status"] == "unknown":
            return UNKNOWN, "Skill snapshot unknown"
        issues: list[str] = []
        if best["status"] not in ok_statuses:
            issues.append(f"{fitting.ship_type_name} ({fitting.name}): {_format_missing_skills(best, level)}")
        if require_ship and not _user_has_ship_in_structure(snapshots, fitting.ship_type_id):
            issues.append(f"No {fitting.ship_type_name} present in a player structure")
        if issues:
            return FAIL, " | ".join(issues)
        return PASS, f"Can fly {fitting.ship_type_name} ({fitting.name}) & ship in structure"

    if ctype == "doctrine_coverage":
        doctrine_id = int(node.get("doctrine_id") or 0)
        fitting_id = int(node.get("fitting_id") or 0)
        min_pct = float(node.get("min_required_pct", 100))
        level = str(node.get("level", "minimum"))
        require_ship = bool(node.get("require_ship", True))
        doctrine = (
            Doctrine.objects.filter(pk=doctrine_id)
            .prefetch_related("doctrine_fittings__fitting__versions__skill_requirements")
            .first()
        )
        if doctrine is None:
            return UNKNOWN, "Doctrine not found"
        if not snapshots:
            return UNKNOWN, "No synced skill snapshot"
        if fitting_id:
            df = next((item for item in doctrine.doctrine_fittings.all() if item.fitting_id == fitting_id), None)
            if df is None or df.fitting.current_version is None:
                return UNKNOWN, f"Fitting {fitting_id} not found in {doctrine.name}"
            reqs = list(df.fitting.current_version.skill_requirements.all())
            best = max(
                (evaluate_fitting_for_snapshot(reqs, s) for s in snapshots),
                key=lambda e: STATUS_RANK[e["status"]],
            )
            ok_statuses = {"green"} if level == "recommended" else {"green", "yellow"}
            if best["status"] == "unknown":
                return UNKNOWN, "Skill snapshot unknown"
            issues = []
            if best["status"] not in ok_statuses:
                issues.append(
                    f"{doctrine.name} / {df.fitting.ship_type_name} ({df.fitting.name}): "
                    f"{_format_missing_skills(best, level)}"
                )
            if require_ship and not _user_has_ship_in_structure(snapshots, df.fitting.ship_type_id):
                issues.append(f"{doctrine.name}: no {df.fitting.ship_type_name} in a player structure")
            if issues:
                return FAIL, " | ".join(issues)
            return PASS, f"{doctrine.name}: can fly {df.fitting.name} & ship in structure"

        req_dfs = [df for df in doctrine.doctrine_fittings.all() if df.is_required and df.fitting.current_version]
        if not req_dfs:
            return PASS, f"{doctrine.name}: no required fittings"
        flyable = 0
        fail_notes: list[str] = []
        for df in req_dfs:
            ver = df.fitting.current_version
            if ver is None:
                continue
            reqs = list(ver.skill_requirements.all())
            best = max(
                (evaluate_fitting_for_snapshot(reqs, s) for s in snapshots),
                key=lambda e: STATUS_RANK[e["status"]],
            )
            has_skills = best["status"] in {"green", "yellow"}
            has_ship = (not require_ship) or _user_has_ship_in_structure(snapshots, df.fitting.ship_type_id)
            if has_skills and has_ship:
                flyable += 1
            else:
                fit_reasons: list[str] = []
                if not has_skills:
                    fit_reasons.append(_format_missing_skills(best, "minimum"))
                if not has_ship:
                    fit_reasons.append("no ship in structure")
                fail_notes.append(f"{df.fitting.ship_type_name} ({df.fitting.name}): {', '.join(fit_reasons)}")
        pct = (flyable / len(req_dfs)) * 100.0
        if pct >= min_pct:
            return PASS, f"{doctrine.name}: {pct:.0f}% ready (need {min_pct:.0f}%)"
        detail = "; ".join(fail_notes[:4])
        if len(fail_notes) > 4:
            detail += f" (+{len(fail_notes) - 4} more)"
        return FAIL, f"{doctrine.name}: {pct:.0f}% ready (need {min_pct:.0f}%) | {detail}"

    if ctype == "skill":
        skill_id = int(node.get("skill_id") or 0)
        min_level = int(node.get("min_level") or 1)
        if not snapshots:
            return UNKNOWN, "No synced skill snapshot"
        best_lvl = 0
        sname = ""
        for snap in snapshots:
            for sk in snap.skills.all():
                if sk.skill_id == skill_id:
                    if sk.skill_name:
                        sname = sk.skill_name
                    if sk.active_skill_level > best_lvl:
                        best_lvl = sk.active_skill_level
        label = sname or _skill_name(skill_id)
        if best_lvl >= min_level:
            return PASS, f"Skill {label}: {best_lvl}/{min_level}"
        return FAIL, f"Missing skill: {label} {min_level} (have {best_lvl})"

    if ctype == "total_sp":
        min_sp = int(node.get("min_sp") or 0)
        if not snapshots:
            return UNKNOWN, "No synced skill snapshot"
        max_sp = max(s.total_sp for s in snapshots)
        if max_sp >= min_sp:
            return PASS, f"Total SP: {max_sp:,} / {min_sp:,}"
        return FAIL, f"Total SP too low: {max_sp:,} / {min_sp:,}"

    if ctype == "ship_owned":
        ship_type_id = int(node.get("ship_type_id") or 0)
        min_count = int(node.get("min_count") or 1)
        if not snapshots:
            return UNKNOWN, "No synced asset snapshot"
        char_ids = [s.character_id for s in snapshots]
        owned = CharacterAsset.objects.filter(
            character_id__in=char_ids,
            type_id=ship_type_id,
        ).count()
        return (PASS if owned >= min_count else FAIL), f"Owned type {ship_type_id}: {owned}/{min_count}"

    if ctype == "implant":
        target_id = int(node.get("type_id") or 0)
        target_name = str(node.get("type_name") or "").strip().lower()
        if not snapshots:
            return UNKNOWN, "No synced implant snapshot"
        for snap in snapshots:
            for imp in snap.implants.all():
                if (target_id and imp.type_id == target_id) or (
                    target_name and target_name in imp.type_name.lower()
                ):
                    return PASS, f"Implant present: {imp.type_name or imp.type_id}"
        return FAIL, "Required implant not found"

    if ctype == "membership":
        corp_id = node.get("corporation_id")
        alliance_id = node.get("alliance_id")
        chars = [co.character for co in CharacterOwnership.objects.filter(user=user).select_related("character")]
        if not chars:
            return UNKNOWN, "No linked characters"
        for c in chars:
            if corp_id and int(c.corporation_id) == int(corp_id):
                return PASS, f"Member of corp {corp_id}"
            if alliance_id and c.alliance_id and int(c.alliance_id) == int(alliance_id):
                return PASS, f"Member of alliance {alliance_id}"
        return FAIL, "Membership condition not met"

    if ctype == "other_group":
        group_id = node.get("group_id")
        group_name = str(node.get("group_name") or "").strip()
        qs = user.groups.all()
        if group_id:
            matched = qs.filter(pk=int(group_id)).exists()
        elif group_name:
            matched = qs.filter(name=group_name).exists()
        else:
            return UNKNOWN, "No group specified"
        return (PASS if matched else FAIL), f"Group membership: {matched}"

    if ctype == "fleet_participation":
        days = int(node.get("days") or 30)
        min_fats = int(node.get("min_fats") or 1)
        count = count_user_fats(user, days=days)
        if count is None:
            return UNKNOWN, "aa-fatanalysis not installed"
        return (PASS if count >= min_fats else FAIL), f"FATs in {days}d: {count}/{min_fats}"

    return UNKNOWN, f"Unknown condition type: {ctype}"


def evaluate_condition_tree(
    tree: dict[str, Any],
    user: User,
    snapshots: list[CharacterSkillSnapshot] | None = None,
) -> tuple[str, list[str]]:
    """Evaluate a recursive AND/OR/AT_LEAST condition tree for ``user``."""
    snaps = snapshots if snapshots is not None else _user_snapshots(user)
    if not tree:
        return UNKNOWN, ["Empty condition tree"]

    op = str(tree.get("op", "")).upper()
    if not op:
        status, reason = _eval_leaf(tree, user, snaps)
        return status, [reason]

    children = tree.get("children") or []
    if not isinstance(children, list) or not children:
        return UNKNOWN, ["Condition group has no children"]

    results = [evaluate_condition_tree(child, user, snaps) for child in children]
    statuses = [r[0] for r in results]
    reasons = [msg for _st, msgs in results for msg in msgs]

    if op == "AND":
        if FAIL in statuses:
            return FAIL, reasons
        if UNKNOWN in statuses:
            return UNKNOWN, reasons
        return PASS, reasons

    if op == "OR":
        if PASS in statuses:
            return PASS, reasons
        if UNKNOWN in statuses:
            return UNKNOWN, reasons
        return FAIL, reasons

    if op == "AT_LEAST":
        n = max(1, int(tree.get("n") or 1))
        pass_count = statuses.count(PASS)
        unknown_count = statuses.count(UNKNOWN)
        if pass_count >= n:
            return PASS, reasons
        if pass_count + unknown_count >= n:
            return UNKNOWN, reasons
        return FAIL, reasons

    return UNKNOWN, [f"Unsupported operator: {op}"]


def format_warning_dm(user: User, rule: ComplianceRule, grace_until: Any) -> tuple[str, str]:
    """Render the DM warning title and body in the recipient's Alliance Auth language."""
    with discord_language(user_language(user)):
        title = _("Compliance warning: %(rule)s") % {"rule": rule.name}
        body = _(
            "You no longer meet the requirements for group %(group)s (rule: %(rule)s). "
            "Access will be revoked after %(deadline)s unless requirements are met."
        ) % {
            "group": rule.group.name,
            "rule": rule.name,
            "deadline": grace_until.strftime("%Y-%m-%d %H:%M UTC"),
        }
    return str(title), str(body)


def format_channel_notice(rule: ComplianceRule, user: User, action: str, lang: str | None = None) -> str:
    """Render a channel Discord webhook notice in the configured fixed language."""
    with discord_language(channel_language(lang)):
        return str(
            _("Doctrine Hub [%(rule)s]: %(action)s group %(group)s for %(user)s.")
            % {
                "rule": rule.name,
                "action": action,
                "group": rule.group.name,
                "user": user.username,
            }
        )


def _send_webhook(message: str, config: NotificationConfig) -> None:
    if not config.discord_webhook_url:
        return
    try:
        requests.post(config.discord_webhook_url, json={"content": message}, timeout=10)
    except requests.RequestException as exc:
        logger.warning("Failed to send Discord webhook notice: %s", exc)


@transaction.atomic
def apply_rule_for_user(rule: ComplianceRule, user: User) -> RuleEvaluation:
    """Evaluate ``rule`` for ``user`` and apply group grants/revocations/approvals."""
    status, reasons = evaluate_condition_tree(rule.condition_tree, user)
    evaluation, _ = RuleEvaluation.objects.get_or_create(rule=rule, user=user)
    evaluation.status = status
    evaluation.details = {"reasons": reasons}

    now = timezone.now()
    active_grant = GroupGrant.objects.filter(rule=rule, user=user, group=rule.group, revoked_at__isnull=True).first()
    config = NotificationConfig.get_solo()

    if status == UNKNOWN:
        # Never revoke on ESI errors / unknown status.
        evaluation.save()
        return evaluation

    if rule.mode == ComplianceRule.Mode.REPORT_ONLY:
        evaluation.save()
        return evaluation

    if rule.mode == ComplianceRule.Mode.AUTOMATIC:
        if status == PASS:
            evaluation.grace_until = None
            evaluation.warned_at = None
            if active_grant is None:
                user.groups.add(rule.group)
                GroupGrant.objects.create(rule=rule, user=user, group=rule.group)
                ComplianceAuditLog.objects.create(
                    rule=rule,
                    user=user,
                    group=rule.group,
                    action=ComplianceAuditLog.Action.GRANTED,
                    reason="; ".join(reasons),
                )
                _send_webhook(
                    format_channel_notice(rule, user, "granted", config.discord_language),
                    config,
                )
        elif status == FAIL and active_grant is not None:
            if evaluation.grace_until is None:
                evaluation.grace_until = now + timedelta(hours=max(rule.grace_period_hours, 1))
                evaluation.warned_at = now
                if config.dm_warnings_enabled:
                    title, body = format_warning_dm(user, rule, evaluation.grace_until)
                    notify.danger(user=user, title=title, message=body)
                ComplianceAuditLog.objects.create(
                    rule=rule,
                    user=user,
                    group=rule.group,
                    action=ComplianceAuditLog.Action.WARNED,
                    reason="; ".join(reasons),
                )
            elif now >= evaluation.grace_until:
                user.groups.remove(rule.group)
                active_grant.revoked_at = now
                active_grant.save(update_fields=["revoked_at"])
                evaluation.grace_until = None
                ComplianceAuditLog.objects.create(
                    rule=rule,
                    user=user,
                    group=rule.group,
                    action=ComplianceAuditLog.Action.REVOKED,
                    reason="; ".join(reasons),
                )
                _send_webhook(
                    format_channel_notice(rule, user, "revoked", config.discord_language),
                    config,
                )

    elif rule.mode == ComplianceRule.Mode.REVIEWER_APPROVAL:
        if status == PASS and active_grant is None:
            PendingApproval.objects.get_or_create(
                rule=rule,
                user=user,
                action=PendingApproval.Action.GRANT,
                status=PendingApproval.Status.PENDING,
                defaults={"reason": "; ".join(reasons)},
            )
        elif status == FAIL and active_grant is not None:
            PendingApproval.objects.get_or_create(
                rule=rule,
                user=user,
                action=PendingApproval.Action.REVOKE,
                status=PendingApproval.Status.PENDING,
                defaults={"reason": "; ".join(reasons)},
            )

    evaluation.save()
    return evaluation


@transaction.atomic
def decide_pending_approval(
    approval: PendingApproval,
    reviewer: User,
    approve: bool,
    note: str = "",
) -> PendingApproval:
    """Approve or reject a pending grant/revocation request."""
    if approval.status != PendingApproval.Status.PENDING:
        return approval

    now = timezone.now()
    approval.reviewed_by = reviewer
    approval.reviewed_at = now

    if not approve:
        approval.status = PendingApproval.Status.REJECTED
        approval.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        ComplianceAuditLog.objects.create(
            rule=approval.rule,
            user=approval.user,
            group=approval.rule.group,
            action=ComplianceAuditLog.Action.REJECTED,
            reason=note or approval.reason,
            actor=reviewer,
        )
        return approval

    approval.status = PendingApproval.Status.APPROVED
    approval.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    ComplianceAuditLog.objects.create(
        rule=approval.rule,
        user=approval.user,
        group=approval.rule.group,
        action=ComplianceAuditLog.Action.APPROVED,
        reason=note or approval.reason,
        actor=reviewer,
    )

    if approval.action == PendingApproval.Action.GRANT:
        approval.user.groups.add(approval.rule.group)
        if not GroupGrant.objects.filter(
            rule=approval.rule, user=approval.user, group=approval.rule.group, revoked_at__isnull=True
        ).exists():
            GroupGrant.objects.create(rule=approval.rule, user=approval.user, group=approval.rule.group)
        ComplianceAuditLog.objects.create(
            rule=approval.rule,
            user=approval.user,
            group=approval.rule.group,
            action=ComplianceAuditLog.Action.GRANTED,
            reason=note or approval.reason,
            actor=reviewer,
        )
    elif approval.action == PendingApproval.Action.REVOKE:
        active = GroupGrant.objects.filter(
            rule=approval.rule, user=approval.user, group=approval.rule.group, revoked_at__isnull=True
        ).first()
        if active is not None:
            approval.user.groups.remove(approval.rule.group)
            active.revoked_at = now
            active.save(update_fields=["revoked_at"])
            ComplianceAuditLog.objects.create(
                rule=approval.rule,
                user=approval.user,
                group=approval.rule.group,
                action=ComplianceAuditLog.Action.REVOKED,
                reason=note or approval.reason,
                actor=reviewer,
            )
    return approval


def evaluate_all_rules() -> dict[str, int]:
    """Evaluate all active compliance rules across all users with characters."""
    rules = list(ComplianceRule.objects.filter(is_active=True).select_related("group"))
    users = list(User.objects.filter(character_ownerships__isnull=False).distinct())
    count = 0
    for rule in rules:
        for user in users:
            apply_rule_for_user(rule, user)
            count += 1
    return {"rules": len(rules), "evaluations": count}


def ensure_default_capitals_rule() -> ComplianceRule:
    """Create the initial 'SIG: Capitals' rule in report_only mode if it does not exist."""
    group, _ = Group.objects.get_or_create(name="SIG: Capitals")
    rule, _ = ComplianceRule.objects.get_or_create(
        name="SIG: Capitals",
        defaults={
            "description": "Capital ship pilots (report only until reviewed).",
            "group": group,
            "mode": ComplianceRule.Mode.REPORT_ONLY,
            "grace_period_hours": 48,
            "condition_tree": {
                "op": "AND",
                "children": [
                    {"type": "skill", "skill_id": 20533, "min_level": 1},  # Capital Ships
                    {"type": "total_sp", "min_sp": 15000000},
                ],
            },
        },
    )
    return rule
