"""Make the ERP's tables exist while tests run.

This service reads a database it does not own, so every ERP model is
`managed = False` and the test database gets none of their tables. That has
meant the whole ERP-facing half of the app -- the projection, the kind
inference, the four erp_* commands -- could not be tested at all: the suite
failed during database setup, before a single test ran.

It cannot be fixed from a test case, because `api.models.batches` has managed
models carrying real foreign keys to `auth_user`. Migrating creates those
constraints, so the referenced table has to exist *before* the first migration,
not by the time the first test runs.

`pre_migrate` is the one hook early enough. It is connected only while the test
command is running, so production migrations are untouched.
"""
from __future__ import annotations

import sys

from django.db import connections
from django.db.models.signals import pre_migrate

_built: set[str] = set()


def _models():
    """Every unmanaged model in the ERP shadow module.

    Derived rather than listed. A hand-written list needs extending each time
    the sync reads one more table, and the failure is a missing relation deep
    in a test rather than anything that names the cause -- which is how this
    was found: three rounds of adding one more table.
    """
    from django.apps import apps

    from api.models import erp

    return [
        model
        # Not include_auto_created: create_model builds a model's own
        # many-to-many tables, so listing them separately creates them twice.
        for model in apps.get_app_config("api").get_models()
        if not model._meta.managed and model.__module__ == erp.__name__
    ]


def create_erp_tables(using: str = "default") -> None:
    """Idempotent, and quiet if the tables are already there."""
    if using in _built:
        return
    connection = connections[using]
    existing = set(connection.introspection.table_names())
    with connection.schema_editor() as editor:
        for model in _models():
            if model._meta.db_table not in existing:
                editor.create_model(model)
    _built.add(using)


def _on_pre_migrate(sender, **kwargs):
    using = kwargs.get("using", "default")
    if using != "default":
        return                      # the ERP is only ever the default alias
    create_erp_tables(using)


def install_for_tests() -> None:
    """Connect the hook, but only for a test run."""
    if "test" not in sys.argv[1:2]:
        return
    pre_migrate.connect(_on_pre_migrate, dispatch_uid="iam.create_erp_tables")
