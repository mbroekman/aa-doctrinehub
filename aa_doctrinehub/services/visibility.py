"""Which doctrines and fittings a user may see."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Q, QuerySet

from ..models import Doctrine, Fitting


def _category_filter(user: User) -> Q:
    """Visible when no category restricts it, or the user is in a group of one that does."""
    restricted = Q(categories__visible_to_groups__isnull=False)
    allowed = Q(categories__visible_to_groups__in=user.groups.all())
    return ~restricted | allowed


def visible_doctrines(user: User) -> QuerySet[Doctrine]:
    """Doctrines the user may see. Managers also see drafts and archived doctrines."""
    qs = Doctrine.objects.all()
    if user.is_superuser:
        return qs
    if not user.has_perm("aa_doctrinehub.manage_doctrines"):
        qs = qs.filter(status__in=[Doctrine.Status.ACTIVE, Doctrine.Status.PHASING_OUT])
    allowed_ids = Doctrine.objects.filter(_category_filter(user)).values("pk")
    return qs.filter(pk__in=allowed_ids)


def visible_fittings(user: User) -> QuerySet[Fitting]:
    """Fittings the user may see, by their own categories."""
    if user.is_superuser or user.has_perm("aa_doctrinehub.manage_doctrines"):
        return Fitting.objects.all()
    allowed_ids = Fitting.objects.filter(_category_filter(user)).values("pk")
    return Fitting.objects.filter(pk__in=allowed_ids)
