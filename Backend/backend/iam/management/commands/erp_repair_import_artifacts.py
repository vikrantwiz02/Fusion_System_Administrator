"""Deactivate auth_user rows that are import wreckage, not people.

A failed spreadsheet import can write a whole tab-separated line into a single
auth_user row: the entire line lands in `username`, fragments of the address in
`first_name`/`last_name`, and a mangled address in `email`. The row is nobody.
The real account from the same import usually exists alongside it.

This is the one command here that writes to the ERP, so the signature it
matches is deliberately narrow. A row is only touched when **all** of these
hold:

  * the username contains a tab or newline -- no real username ever does
  * there is no globals_extrainfo row, so the ERP never classified it
  * it holds no designation
  * a different, active account already exists under the first field of that
    line, so the real person is not being locked out

Anything failing one of those is reported and left alone. It deactivates rather
than deletes: other tables reference these ids, and a reversible change is the
right shape for a correction made from a script.

Dry run by default.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models.erp import AuthUser, GlobalsExtrainfo, GlobalsHoldsdesignation


class Command(BaseCommand):
    help = "Find, and optionally deactivate, corrupt auth_user rows from a bad import."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix", action="store_true",
            help="Deactivate the rows. Without this, only reports.")

    def handle(self, *args, **opts) -> None:
        suspects = [
            u for u in AuthUser.objects.all().only("id", "username", "is_active")
            if "\t" in u.username or "\n" in u.username
        ]
        if not suspects:
            self.stdout.write(self.style.SUCCESS("  no malformed usernames"))
            return

        classified = set(GlobalsExtrainfo.objects.values_list("user_id", flat=True))
        employed = set(GlobalsHoldsdesignation.objects.values_list("user_id", flat=True))

        artifacts, keep = [], []
        for u in suspects:
            intended = u.username.split("\t")[0].strip()
            twin = (AuthUser.objects.filter(username=intended, is_active=True)
                    .exclude(pk=u.pk).first())
            reasons = []
            if u.id in classified:
                reasons.append("has a globals_extrainfo row")
            if u.id in employed:
                reasons.append("holds a designation")
            if twin is None:
                reasons.append(f"no other active account under {intended!r}")
            (keep if reasons else artifacts).append((u, intended, twin, reasons))

        for u, intended, twin, _ in artifacts:
            state = "active" if u.is_active else "already inactive"
            self.stdout.write(
                f"  artifact  user {u.id} ({state}): {len(u.username)}-char username, "
                f"duplicate of user {twin.id} ({intended})")
        for u, intended, _, reasons in keep:
            self.stdout.write(self.style.WARNING(
                f"  LEFT ALONE user {u.id}: malformed username but {'; '.join(reasons)} "
                "— needs a person to look at it"))

        live = [a for a in artifacts if a[0].is_active]
        if not opts["fix"]:
            self.stdout.write(self.style.WARNING(
                f"  {len(live)} row(s) would be deactivated — re-run with --fix"))
            return

        with transaction.atomic():
            AuthUser.objects.filter(pk__in=[a[0].pk for a in live]).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(
            f"  deactivated {len(live)} row(s). Run sync_identity to carry it across."))
