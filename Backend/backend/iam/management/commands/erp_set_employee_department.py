"""Set the department an employee belongs to.

Leave routes a request to the head of the applicant's unit, and the unit is
this field. An employee without one has a request that no queue can show and no
head can act on, so it sits until somebody notices -- which makes this a gap
worth filling deliberately rather than leaving blank.

Feed real values with --csv or --set. --placeholder fills the gap meanwhile
with a department named so that nobody mistakes it for a real one, and
--report lists who is still waiting for a real answer.

Writes to the ERP, so: an existing department is never overwritten without
--force, an unknown department name is refused rather than created, and
--dry-run shows the plan.
"""
import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models.erp import (AuthUser, GlobalsDepartmentinfo, GlobalsExtrainfo,
                            GlobalsHoldsdesignation)

PLACEHOLDER = "UNASSIGNED (placeholder)"


class Command(BaseCommand):
    help = "Set, or report, the department of employees who have none."

    def add_arguments(self, parser):
        parser.add_argument("--set", action="append", default=[], metavar="ID=NAME",
                            help="One assignment. Repeatable.")
        parser.add_argument("--csv", help="A file of user_id,department rows.")
        parser.add_argument("--placeholder", action="store_true",
                            help=f"Put everyone still missing one in {PLACEHOLDER!r}.")
        parser.add_argument("--report", action="store_true",
                            help="List employees with no department and exit.")
        parser.add_argument("--force", action="store_true",
                            help="Also change employees who already have one.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        if opts["report"]:
            self._report()
            return

        wanted = self._assignments(opts)
        if not wanted:
            raise CommandError(
                "Nothing to do. Give --set, --csv or --placeholder, or use --report "
                "to see who is missing a department.")

        departments = {d.name: d for d in GlobalsDepartmentinfo.objects.all()}
        if opts["placeholder"]:
            departments.setdefault(PLACEHOLDER, self._make_placeholder(opts["dry_run"]))

        unknown = sorted({n for n in wanted.values() if n not in departments})
        if unknown:
            raise CommandError(
                f"Not a department: {unknown}. Departments are created in the ERP, "
                f"not here. Known: {sorted(departments)}")

        planned, skipped, blocked = [], [], []
        for user_id, name in sorted(wanted.items()):
            user = AuthUser.objects.filter(pk=user_id).first()
            if user is None:
                raise CommandError(f"No such user: {user_id}")
            extra = GlobalsExtrainfo.objects.filter(user_id=user_id).first()
            if extra and extra.department_id and not opts["force"]:
                skipped.append((user_id, user.username))
                continue
            reason = self._blocked(user) if extra is None else ""
            if reason:
                blocked.append((user, reason))
                continue
            planned.append((user, extra, departments[name]))

        for user, extra, dept in planned:
            action = "set" if extra else "create extrainfo +"
            self.stdout.write(f"  {action:<20} user {user.id:<6} {user.username:<20} "
                              f"-> {dept.name}")
        for user_id, username in skipped:
            self.stdout.write(self.style.WARNING(
                f"  already has one     user {user_id:<6} {username:<20} "
                "-- pass --force to change it"))
        for user, reason in blocked:
            self.stdout.write(self.style.ERROR(
                f"  NEEDS A PERSON      user {user.id:<6} {user.username!r}: {reason}"))

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(
                f"  dry run -- {len(planned)} change(s) not written"))
            return

        with transaction.atomic():
            for user, extra, dept in planned:
                if extra:
                    extra.department = dept
                    extra.save(update_fields=["department"])
                else:
                    self._create_extrainfo(user, dept)

        self.stdout.write(self.style.SUCCESS(
            f"  {len(planned)} written. Run sync_identity to carry it across."))

    def _blocked(self, user) -> str:
        """Why this account cannot simply be given a department.

        The extrainfo key is the username, so a collision means two accounts
        differ only by whitespace: one person with a duplicate login. Giving the
        spare one a department entrenches the split instead of fixing it, and
        which account survives is a decision about somebody's role.
        """
        key = user.username.strip()
        clash = GlobalsExtrainfo.objects.filter(pk=key).exclude(user_id=user.id).first()
        if clash:
            return (f"{key!r} already belongs to user {clash.user_id}; the same "
                    "person under two accounts. See erp_repair_import_artifacts.")
        return ""

    def _assignments(self, opts) -> dict[int, str]:
        wanted: dict[int, str] = {}
        for pair in opts["set"]:
            if "=" not in pair:
                raise CommandError(f"--set wants ID=NAME, got {pair!r}")
            uid, name = pair.split("=", 1)
            wanted[int(uid)] = name.strip()
        if opts["csv"]:
            with open(opts["csv"], newline="") as fh:
                for row in csv.DictReader(fh):
                    if "user_id" not in row or "department" not in row:
                        raise CommandError(
                            "The CSV needs a header row with user_id and department.")
                    wanted[int(row["user_id"])] = row["department"].strip()
        if opts["placeholder"]:
            # Explicit assignments win; the placeholder only fills what is left.
            for user_id in self._missing():
                wanted.setdefault(user_id, PLACEHOLDER)
        return wanted

    def _missing(self) -> list[int]:
        """Employees with no department, by the same rule the projection uses."""
        employed = set(
            GlobalsHoldsdesignation.objects.values_list("user_id", flat=True).distinct())
        out = []
        for user in AuthUser.objects.filter(is_active=True).only("id"):
            extra = GlobalsExtrainfo.objects.filter(user_id=user.id).first()
            kind = (extra.user_type or "staff").lower() if extra else (
                "staff" if user.id in employed else "unknown")
            if kind in ("faculty", "staff") and not (extra and extra.department_id):
                out.append(user.id)
        return out

    def _report(self) -> None:
        missing = self._missing()
        if not missing:
            self.stdout.write(self.style.SUCCESS("  every employee has a department"))
            return
        self.stdout.write(f"  {len(missing)} employee(s) with no department:")
        for user in AuthUser.objects.filter(pk__in=missing).order_by("id"):
            extra = GlobalsExtrainfo.objects.filter(user_id=user.id).first()
            note = "" if extra else "  (no globals_extrainfo row at all)"
            self.stdout.write(f"    {user.id:<6} {user.username:<20}{note}")
        self.stdout.write(
            "\n  Feed real values with:  --csv file.csv   (user_id,department)")

    def _make_placeholder(self, dry_run: bool) -> GlobalsDepartmentinfo:
        if dry_run:
            return GlobalsDepartmentinfo(name=PLACEHOLDER)
        dept, created = GlobalsDepartmentinfo.objects.get_or_create(name=PLACEHOLDER)
        if created:
            self.stdout.write(self.style.WARNING(
                f"  created department {PLACEHOLDER!r} -- replace these with real "
                "ones and remove it"))
        return dept

    def _create_extrainfo(self, user, dept) -> None:
        """Only for an employee the ERP never set up at all.

        The identity fields are left empty rather than guessed: this row exists
        to carry a department, and inventing a title or a sex for somebody is
        not this command's business.
        """
        key = user.username.strip()
        GlobalsExtrainfo.objects.create(
            id=key, user=user, department=dept,
            user_type="staff", user_status="PRESENT", title="", sex="",
        )
