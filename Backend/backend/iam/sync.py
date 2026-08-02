"""The ERP -> IAM projection. One-way, idempotent, batched.

Phase 1 of ADR-0014: the ERP stays the source of truth, and IAM keeps a copy so
that serving a request never requires the ERP to be reachable.

Idempotent by construction — every write is an upsert keyed on a natural key,
so running it twice changes nothing and a half-finished run is safe to repeat.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from iam import erp_source
from iam.models import (IamDesignationModule, IamUser, IamUserAcademic,
                        IamUserDesignation, SyncRun)

log = logging.getLogger("fusion.iam.sync")

USER_FIELDS = ["username", "display_name", "email", "kind", "is_active",
               "password_hash", "department", "programme", "discipline",
               "batch_year", "synced_at"]

# Stamped onto every academic row. Bump the version when iam/grades.py changes
# so a stale CPI is identifiable after the fact rather than indistinguishable.
COMPUTED_BY = "iam-replica/v1"


def sync_all(*, batch_size: int = 500, deactivate_missing: bool = True) -> SyncRun:
    """Project every ERP user, designation and module grant into IAM."""
    run = SyncRun.objects.create()
    try:
        seen: set[int] = set()
        written = 0

        for batch in erp_source.iter_users(batch_size=batch_size):
            rows = [IamUser(**r) for r in batch]
            IamUser.objects.bulk_create(
                rows, update_conflicts=True,
                unique_fields=["erp_user_id"], update_fields=USER_FIELDS,
            )
            seen.update(r["erp_user_id"] for r in batch)
            written += len(rows)

        run.users_seen = len(seen)
        run.users_written = written

        with transaction.atomic(using="system_db"):
            run.designations_written = _replace_designations(
                erp_source.all_user_designations())
            run.module_grants_written = _replace_module_grants(
                erp_source.all_designation_modules())
            run.academics_written = _replace_academics(
                erp_source.all_academic_standings())

        if deactivate_missing and seen:
            # A user who vanished from the ERP is deactivated, never deleted:
            # placement applications and audit rows reference the id, and a
            # hard delete would leave them dangling.
            run.deactivated = (IamUser.objects
                               .exclude(erp_user_id__in=seen)
                               .filter(is_active=True)
                               .update(is_active=False))

        run.status = "succeeded"
    except Exception as exc:                                   # noqa: BLE001
        run.status = "failed"
        run.error = f"{exc.__class__.__name__}: {exc}"
        log.exception("iam.sync.failed")
        raise
    finally:
        run.finished_at = timezone.now()
        run.save()
    return run


def _replace_designations(pairs: list[tuple[int, str]]) -> int:
    """Replace wholesale rather than diff.

    A designation being *removed* is the security-relevant change, and a diff
    that only adds would silently keep revoked roles alive. Wholesale replace
    inside a transaction cannot get that wrong.
    """
    IamUserDesignation.objects.all().delete()
    rows = [IamUserDesignation(erp_user_id=uid, designation=name)
            for uid, name in set(pairs)]
    IamUserDesignation.objects.bulk_create(rows, batch_size=1000)
    return len(rows)


def _replace_module_grants(pairs: list[tuple[str, str]]) -> int:
    """Same reasoning: a revoked module grant must actually disappear."""
    IamDesignationModule.objects.all().delete()
    rows = [IamDesignationModule(designation=d, module_code=m)
            for d, m in set(pairs)]
    IamDesignationModule.objects.bulk_create(rows, batch_size=1000)
    return len(rows)


def _replace_academics(standings: list[dict]) -> int:
    """Wholesale replace, for the same reason as designations.

    A result being RETRACTED is the case that matters: the student's row must
    disappear so eligibility fails closed again. A diff that only upserts would
    leave a retracted CPI in place, and someone would apply on it.

    Rows are keyed by roll_no in the ERP but by erp_user_id here, so the join
    back to identity happens once, in bulk.
    """
    user_by_roll = dict(IamUser.objects.values_list("username", "erp_user_id"))
    # Roll number and username are the same string for students, but compare
    # case-insensitively — the ERP is inconsistent about case in places.
    lower = {k.lower(): v for k, v in user_by_roll.items()}

    rows = []
    for s in standings:
        uid = user_by_roll.get(s["roll_no"]) or lower.get(s["roll_no"].lower())
        if uid is None:
            continue                      # a grade row with no matching user
        rows.append(IamUserAcademic(
            erp_user_id=uid, roll_no=s["roll_no"],
            cpi=s["cpi"], earned_credits=s["earned_credits"],
            cpi_denominator_credits=s["cpi_denominator_credits"],
            active_backlogs=s["active_backlogs"],
            courses_counted=s["courses_counted"],
            semester=s["semester"], semester_type=s["semester_type"],
            declared_seq=s["declared_seq"],
            erp_announcement_id=s["announcement_id"],
            programme=s["programme"], computed_by=COMPUTED_BY,
        ))

    IamUserAcademic.objects.all().delete()
    IamUserAcademic.objects.bulk_create(rows, batch_size=1000)
    return len(rows)


def refresh_password_hash(username: str) -> str | None:
    """Re-pull one user's hash after a live-ERP fallback succeeded.

    Keeps the copy correct without waiting for the next full sync.
    """
    fresh = erp_source.fetch_password_hash(username)
    if fresh:
        IamUser.objects.filter(username__iexact=username).update(
            password_hash=fresh, synced_at=timezone.now())
    return fresh
