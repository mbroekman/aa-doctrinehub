"""Which doctrines and fittings a user may see."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import QuerySet

from ..models import Category, Doctrine, Fitting


def _blocked_category_ids(user: User) -> QuerySet[Category]:
    """Categories that restrict visibility to groups the user is not in.

    A single exclude() across the visible_to_groups M2M is required here:
    chaining filter()/exclude() (or combining them in one Q with | across the
    same join) matches per related row, so an object with both a public
    category and a group-restricted one would satisfy the public category's
    row and leak the restricted one. exclude() on its own uses a NOT EXISTS
    subquery instead, so it correctly tests "no allowed group at all".
    """
    return Category.objects.filter(visible_to_groups__isnull=False).exclude(visible_to_groups__in=user.groups.all())


def visible_doctrines(user: User) -> QuerySet[Doctrine]:
    """Doctrines the user may see. Managers also see drafts and archived doctrines."""
    qs = Doctrine.objects.all()
    if user.is_superuser:
        return qs
    if not user.has_perm("aa_doctrinehub.manage_doctrines"):
        qs = qs.filter(status__in=[Doctrine.Status.ACTIVE, Doctrine.Status.PHASING_OUT])
    return qs.exclude(categories__in=_blocked_category_ids(user))


def visible_fittings(user: User) -> QuerySet[Fitting]:
    """Fittings the user may see, by their own categories."""
    if user.is_superuser or user.has_perm("aa_doctrinehub.manage_doctrines"):
        return Fitting.objects.all()
    return Fitting.objects.exclude(categories__in=_blocked_category_ids(user))
