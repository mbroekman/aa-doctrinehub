"""Tests for model-level constraints."""

import pytest
from django.db import IntegrityError, transaction

from aa_doctrinehub.models import Category, Doctrine, Fitting, Source

pytestmark = pytest.mark.django_db


def _unconditional_unique_names(model):
    """UniqueConstraint names on model with no condition set."""
    return {
        c.name
        for c in model._meta.constraints
        if hasattr(c, "fields") and c.condition is None
    }


@pytest.mark.parametrize(
    "model,constraint_name",
    [
        (Category, "doctrinehub_category_unique_external"),
        (Doctrine, "doctrinehub_doctrine_unique_external"),
        (Fitting, "doctrinehub_fitting_unique_external"),
    ],
)
def test_source_external_id_constraint_has_no_condition(model, constraint_name):
    """MariaDB can't enforce a conditional UniqueConstraint at all (Django
    check W036) and silently skips creating it, so this must stay a plain
    constraint - re-adding a condition would reintroduce an
    unenforced-on-MariaDB uniqueness gap."""
    assert constraint_name in _unconditional_unique_names(model)


def test_multiple_local_records_allowed_with_null_external_id():
    """Local (non-synced) records always have external_id=None and must
    never collide with each other under the constraint."""
    Doctrine.objects.create(name="Alpha")
    Doctrine.objects.create(name="Bravo")
    assert Doctrine.objects.filter(source=Source.LOCAL, external_id=None).count() == 2


def test_duplicate_source_external_id_is_rejected():
    """Two records from the same source with the same external_id must be
    rejected at the database level, matching what the sync service's
    get_or_create(source=..., external_id=...) calls rely on."""
    Doctrine.objects.create(name="Shield HAC", source=Source.FITTINGS, external_id=5)
    with pytest.raises(IntegrityError), transaction.atomic():
        Doctrine.objects.create(name="Shield HAC Dupe", source=Source.FITTINGS, external_id=5)
