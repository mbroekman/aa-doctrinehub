"""Models for aa_doctrinehub."""

from __future__ import annotations

from allianceauth.eveonline.models import EveCharacter
from django.contrib.auth.models import Group, User
from django.db import models
from django.utils.translation import gettext_lazy as _


class General(models.Model):
    """Meta model for app permissions."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", "Can access Doctrine Hub"),
            ("manage_doctrines", "Can manage doctrines and fittings"),
            ("view_compliance", "Can view doctrine coverage and member compliance"),
            ("manage_rules", "Can manage compliance rules and group assignments"),
        )


class Source(models.TextChoices):
    """Where a record comes from.

    Records synced from another source are read-only in Doctrine Hub and are
    shown with a source label next to our own doctrines and fittings.
    """

    LOCAL = "local", _("Doctrine Hub")
    FITTINGS = "fittings", _("Fittings")
    REMOTE_AUTH = "remote_auth", _("External Auth")


class SourcedQuerySet(models.QuerySet):
    """Queryset helpers shared by sourced models."""

    def local(self):
        """Records created in Doctrine Hub."""
        return self.filter(source=Source.LOCAL)

    def from_source(self, source: str):
        """Records synced from the given source."""
        return self.filter(source=source)


class SourcedModel(models.Model):
    """Abstract base for records that can be synced from an external source."""

    source = models.CharField(max_length=16, choices=Source, default=Source.LOCAL, db_index=True)
    external_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text=_("Primary key of this record in its source, if synced."),
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = SourcedQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_editable(self) -> bool:
        """Only records created in Doctrine Hub can be edited here."""
        return self.source == Source.LOCAL


class Category(SourcedModel):
    """A group of doctrines and fittings, optionally limited to Auth groups."""

    name = models.CharField(max_length=255)
    color = models.CharField(max_length=20, default="#6c757d")
    visible_to_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="+",
        help_text=_("Leave empty to show this category to everyone with basic access."),
    )

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["name"]
        constraints = [
            # No condition: MariaDB can't enforce a conditional unique
            # constraint at all (Django W036) and silently skips creating
            # it. A plain constraint gives the same result on every
            # backend anyway - SQL treats each NULL external_id as
            # distinct, so local (non-synced) rows are unaffected - and
            # it is the one that actually gets enforced on MariaDB.
            models.UniqueConstraint(
                fields=["source", "external_id"],
                name="doctrinehub_category_unique_external",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Fitting(SourcedModel):
    """A ship fitting. Its contents live in versions; the newest version is current."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    ship_type_id = models.PositiveIntegerField(null=True, blank=True)
    ship_type_name = models.CharField(max_length=255)
    categories = models.ManyToManyField(Category, blank=True, related_name="fittings")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Fitting")
        verbose_name_plural = _("Fittings")
        ordering = ["ship_type_name", "name"]
        constraints = [
            # See Category.Meta.constraints for why this has no condition.
            models.UniqueConstraint(
                fields=["source", "external_id"],
                name="doctrinehub_fitting_unique_external",
            )
        ]

    def __str__(self) -> str:
        return f"{self.ship_type_name} ({self.name})"

    @property
    def current_version(self) -> FittingVersion | None:
        """The newest version of this fitting."""
        return self.versions.order_by("-number").first()


class FittingVersion(models.Model):
    """An immutable snapshot of a fitting's contents."""

    fitting = models.ForeignKey(Fitting, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    eft = models.TextField(help_text=_("The fitting in EFT format."))
    change_note = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Fitting version")
        verbose_name_plural = _("Fitting versions")
        ordering = ["fitting", "-number"]
        constraints = [
            models.UniqueConstraint(fields=["fitting", "number"], name="doctrinehub_fittingversion_unique_number")
        ]

    def __str__(self) -> str:
        return f"{self.fitting} v{self.number}"


class FittingItem(models.Model):
    """One line of a fitting version: a module, drone, fighter or cargo item."""

    version = models.ForeignKey(FittingVersion, on_delete=models.CASCADE, related_name="items")
    flag = models.CharField(max_length=25, help_text=_("EVE inventory flag, e.g. HiSlot0, DroneBay, Cargo."))
    type_id = models.PositiveIntegerField(null=True, blank=True)
    type_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    charge_name = models.CharField(max_length=255, blank=True, default="")
    is_offline = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Fitting item")
        verbose_name_plural = _("Fitting items")
        ordering = ["version", "id"]

    def __str__(self) -> str:
        return f"{self.type_name} x{self.quantity} ({self.flag})"


class Doctrine(SourcedModel):
    """A named set of fittings with roles, flown together."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        ACTIVE = "active", _("Active")
        PHASING_OUT = "phasing_out", _("Phasing out")
        ARCHIVED = "archived", _("Archived")

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    icon_url = models.URLField(blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    categories = models.ManyToManyField(Category, blank=True, related_name="doctrines")
    fittings = models.ManyToManyField(Fitting, through="DoctrineFitting", related_name="doctrines")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Doctrine")
        verbose_name_plural = _("Doctrines")
        ordering = ["name"]
        constraints = [
            # See Category.Meta.constraints for why this has no condition.
            models.UniqueConstraint(
                fields=["source", "external_id"],
                name="doctrinehub_doctrine_unique_external",
            )
        ]

    def __str__(self) -> str:
        return self.name


class DoctrineFitting(models.Model):
    """A fitting's place in a doctrine: its role, how many and whether it is required."""

    class Role(models.TextChoices):
        UNSPECIFIED = "", _("Unspecified")
        DPS = "dps", _("DPS")
        LOGISTICS = "logistics", _("Logistics")
        TACKLE = "tackle", _("Tackle")
        EWAR = "ewar", _("EWAR")
        COMMAND = "command", _("Command")
        SUPPORT = "support", _("Support")
        SCOUT = "scout", _("Scout")

    doctrine = models.ForeignKey(Doctrine, on_delete=models.CASCADE, related_name="doctrine_fittings")
    fitting = models.ForeignKey(Fitting, on_delete=models.CASCADE, related_name="doctrine_fittings")
    role = models.CharField(max_length=16, choices=Role.choices, blank=True, default=Role.UNSPECIFIED)
    is_required = models.BooleanField(default=True)
    target_count = models.PositiveIntegerField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _("Doctrine fitting")
        verbose_name_plural = _("Doctrine fittings")
        ordering = ["doctrine", "order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["doctrine", "fitting"], name="doctrinehub_doctrinefitting_unique")
        ]

    def __str__(self) -> str:
        return f"{self.doctrine}: {self.fitting}"


class SyncSettings(models.Model):
    """Functional settings for syncing from other sources (singleton, edited in the frontend)."""

    fittings_sync_enabled = models.BooleanField(
        default=False,
        help_text=_("Periodically copy doctrines and fittings from the Fittings app on this Auth."),
    )
    fittings_sync_interval_days = models.PositiveIntegerField(default=7)
    fittings_last_sync_at = models.DateTimeField(null=True, blank=True)
    fittings_last_sync_summary = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = _("Sync settings")
        verbose_name_plural = _("Sync settings")

    def __str__(self) -> str:
        return "Doctrine Hub sync settings"

    @classmethod
    def get_solo(cls) -> SyncSettings:
        """Return the single settings row, creating it if needed."""
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class CharacterSkillSnapshot(models.Model):
    """Latest ESI skill & implant snapshot for a character."""

    class SyncStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        OK = "ok", _("OK")
        ERROR = "error", _("Error")

    character = models.OneToOneField(
        EveCharacter,
        on_delete=models.CASCADE,
        related_name="doctrinehub_skill_snapshot",
    )
    total_sp = models.PositiveBigIntegerField(default=0)
    unallocated_sp = models.PositiveIntegerField(default=0)
    sync_status = models.CharField(max_length=16, choices=SyncStatus.choices, default=SyncStatus.PENDING)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = _("Character skill snapshot")
        verbose_name_plural = _("Character skill snapshots")
        ordering = ["character__character_name"]

    def __str__(self) -> str:
        return f"{self.character} ({self.sync_status})"


class CharacterSkill(models.Model):
    """One trained skill in a character's snapshot."""

    snapshot = models.ForeignKey(CharacterSkillSnapshot, on_delete=models.CASCADE, related_name="skills")
    skill_id = models.PositiveIntegerField(db_index=True)
    skill_name = models.CharField(max_length=255, blank=True, default="")
    trained_skill_level = models.PositiveSmallIntegerField(default=0)
    active_skill_level = models.PositiveSmallIntegerField(default=0)
    skillpoints_in_skill = models.PositiveBigIntegerField(default=0)

    class Meta:
        verbose_name = _("Character skill")
        verbose_name_plural = _("Character skills")
        ordering = ["skill_name", "skill_id"]
        constraints = [
            models.UniqueConstraint(fields=["snapshot", "skill_id"], name="doctrinehub_charskill_unique")
        ]

    def __str__(self) -> str:
        return f"{self.skill_name or self.skill_id} {self.active_skill_level}"


class CharacterImplant(models.Model):
    """An implant currently plugged into the character's active clone."""

    snapshot = models.ForeignKey(CharacterSkillSnapshot, on_delete=models.CASCADE, related_name="implants")
    type_id = models.PositiveIntegerField(db_index=True)
    type_name = models.CharField(max_length=255, blank=True, default="")
    slot = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("Character implant")
        verbose_name_plural = _("Character implants")
        ordering = ["slot", "type_id"]

    def __str__(self) -> str:
        return self.type_name or str(self.type_id)


class CharacterAsset(models.Model):
    """Own ESI asset snapshot for a character (ships and fitted modules)."""

    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE, related_name="doctrinehub_assets")
    item_id = models.PositiveBigIntegerField(db_index=True)
    type_id = models.PositiveIntegerField(db_index=True)
    type_name = models.CharField(max_length=255, blank=True, default="")
    location_id = models.PositiveBigIntegerField(db_index=True)
    location_flag = models.CharField(max_length=64, blank=True, default="")
    location_type = models.CharField(max_length=32, blank=True, default="")
    quantity = models.PositiveIntegerField(default=1)
    is_singleton = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Character asset")
        verbose_name_plural = _("Character assets")
        constraints = [
            models.UniqueConstraint(fields=["character", "item_id"], name="doctrinehub_charasset_unique")
        ]

    def __str__(self) -> str:
        return f"{self.type_name or self.type_id} x{self.quantity}"


class FittingSkillRequirement(models.Model):
    """Minimum and recommended skill levels required to fly a fitting version."""

    class RequirementSource(models.TextChoices):
        DOGMA = "dogma", _("Dogma")
        MANUAL = "manual", _("Manual")

    version = models.ForeignKey(FittingVersion, on_delete=models.CASCADE, related_name="skill_requirements")
    skill_id = models.PositiveIntegerField()
    skill_name = models.CharField(max_length=255)
    required_level = models.PositiveSmallIntegerField(default=1)
    recommended_level = models.PositiveSmallIntegerField(default=1)
    source = models.CharField(
        max_length=16,
        choices=RequirementSource.choices,
        default=RequirementSource.DOGMA,
    )

    class Meta:
        verbose_name = _("Fitting skill requirement")
        verbose_name_plural = _("Fitting skill requirements")
        ordering = ["skill_name", "skill_id"]
        constraints = [
            models.UniqueConstraint(fields=["version", "skill_id"], name="doctrinehub_fitskillreq_unique")
        ]

    def __str__(self) -> str:
        return f"{self.skill_name} {self.required_level} (rec {self.recommended_level})"


class NotificationConfig(models.Model):
    """Discord notification settings (singleton, edited in the frontend)."""

    discord_webhook_url = models.URLField(blank=True, default="")
    discord_language = models.CharField(max_length=10, blank=True, default="")
    dm_warnings_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Notification settings")
        verbose_name_plural = _("Notification settings")

    def __str__(self) -> str:
        return "Doctrine Hub notification settings"

    @classmethod
    def get_solo(cls) -> NotificationConfig:
        """Return the single notification config row, creating it if needed."""
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class ComplianceRule(models.Model):
    """Rule linking a boolean condition tree to an Alliance Auth group."""

    class Mode(models.TextChoices):
        REPORT_ONLY = "report_only", _("Report only")
        AUTOMATIC = "automatic", _("Automatic")
        REVIEWER_APPROVAL = "reviewer_approval", _("Reviewer approval")

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="doctrinehub_rules")
    mode = models.CharField(max_length=24, choices=Mode.choices, default=Mode.REPORT_ONLY)
    is_active = models.BooleanField(default=True)
    grace_period_hours = models.PositiveIntegerField(default=48)
    condition_tree = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Compliance rule")
        verbose_name_plural = _("Compliance rules")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} -> {self.group.name}"


class RuleEvaluation(models.Model):
    """Latest evaluation of a compliance rule for one user."""

    class Status(models.TextChoices):
        PASS = "pass", _("Pass")
        FAIL = "fail", _("Fail")
        UNKNOWN = "unknown", _("Unknown")

    rule = models.ForeignKey(ComplianceRule, on_delete=models.CASCADE, related_name="evaluations")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="doctrinehub_rule_evaluations")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UNKNOWN)
    details = models.JSONField(default=dict)
    grace_until = models.DateTimeField(null=True, blank=True)
    warned_at = models.DateTimeField(null=True, blank=True)
    evaluated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Rule evaluation")
        verbose_name_plural = _("Rule evaluations")
        constraints = [
            models.UniqueConstraint(fields=["rule", "user"], name="doctrinehub_ruleeval_unique")
        ]

    def __str__(self) -> str:
        return f"{self.rule.name}: {self.user.username} = {self.status}"


class GroupGrant(models.Model):
    """Tracks Auth group memberships granted by Doctrine Hub so only our own grants are revoked."""

    rule = models.ForeignKey(ComplianceRule, on_delete=models.CASCADE, related_name="grants")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="doctrinehub_group_grants")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="doctrinehub_grants")
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Group grant")
        verbose_name_plural = _("Group grants")
        ordering = ["-granted_at"]

    def __str__(self) -> str:
        state = "active" if self.revoked_at is None else "revoked"
        return f"{self.user.username} -> {self.group.name} ({state})"


class PendingApproval(models.Model):
    """Queue item when a rule is in reviewer_approval mode."""

    class Action(models.TextChoices):
        GRANT = "grant", _("Grant")
        REVOKE = "revoke", _("Revoke")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    rule = models.ForeignKey(ComplianceRule, on_delete=models.CASCADE, related_name="approvals")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="doctrinehub_approvals")
    action = models.CharField(max_length=16, choices=Action.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    reason = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Pending approval")
        verbose_name_plural = _("Pending approvals")
        ordering = ["-created_at"]


class ComplianceAuditLog(models.Model):
    """Immutable audit log of every grant, revocation, warning and approval decision."""

    class Action(models.TextChoices):
        GRANTED = "granted", _("Granted")
        REVOKED = "revoked", _("Revoked")
        WARNED = "warned", _("Warned")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    rule = models.ForeignKey(
        ComplianceRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="doctrinehub_audit_logs")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="+")
    action = models.CharField(max_length=16, choices=Action.choices)
    reason = models.TextField(blank=True, default="")
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Compliance audit log")
        verbose_name_plural = _("Compliance audit logs")
        ordering = ["-created_at"]
