"""Map existing ERP designations onto platform permission codes.

The ERP has designations and module access but no permission concept, so this
is the bridge. Idempotent — safe to re-run.

Only placement is covered today, because placement is the only module built.
Add rows here as modules land.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from iam.models import RolePermission

# These codes MUST match modules/placement/registry.py in Fusion-Integrated.
# A grant for a code the platform does not check is dead weight; a code the
# platform checks but nobody can be granted locks the endpoint forever. Both
# are silent, so the list is kept deliberately short and reviewed together with
# the module's PERMISSIONS.
STUDENT = [
    "placement_cell.job_posting.view",
    "placement_cell.application.view_self",
    "placement_cell.application.create",
    "placement_cell.application.delete",
    "placement_cell.offer.respond",
    # Rule 1: without this a student cannot enter the season at all.
    "placement_cell.registration.self",
]

COORDINATOR = [
    "placement_cell.job_posting.view",
    "placement_cell.application.view",
    "placement_cell.application.review",
    "placement_cell.report.view",
    "placement_cell.academic_directory.view",
]

OFFICER = COORDINATOR + [
    "placement_cell.job_posting.manage",
    "placement_cell.interview.schedule",
    "placement_cell.offer.issue",
    "placement_cell.offer.revoke",
    "placement_cell.company.manage",
    "placement_cell.announcement.publish",
    # Rules 18-24: the authority decisions, not a coordinator's review.
    "placement_cell.registration.manage",
    "placement_cell.registration.debar",
    "placement_cell.record.manage",
]

# The chairman oversees rather than operates: reports and announcements, no
# shortlisting and no offers (PC-UC-012, PC-UC-013).
CHAIRMAN = [
    "placement_cell.job_posting.view",
    "placement_cell.application.view",
    "placement_cell.report.view",
    "placement_cell.academic_directory.view",
    "placement_cell.announcement.publish",
]

# Keyed by the designation name as it exists in globals_designation.
GRANTS = {
    "student": STUDENT,
    "placement_coordinator": COORDINATOR,
    "placement_officer": OFFICER,
    "placement_chairman": CHAIRMAN,
    "Dean Academic": CHAIRMAN,
    "acadadmin": COORDINATOR,
}


class Command(BaseCommand):
    help = "Seed designation -> permission mappings for the IAM"

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        for designation, perms in GRANTS.items():
            for perm in perms:
                _, made = RolePermission.objects.get_or_create(
                    designation=designation, permission=perm)
                created += int(made)
            self.stdout.write(f"  {designation}: {len(perms)} permission(s)")
        self.stdout.write(self.style.SUCCESS(
            f"{created} new mapping(s); {RolePermission.objects.count()} total"))
