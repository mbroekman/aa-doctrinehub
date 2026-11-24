"""Models for aa_doctrinehub."""

from __future__ import annotations

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

    source = models.CharField(max_length=16, choices=Source.choices, default=Source.LOCAL, db_index=True)
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
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=models.Q(external_id__isnull=False),
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
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=models.Q(external_id__isnull=False),
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
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=models.Q(external_id__isnull=False),
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
