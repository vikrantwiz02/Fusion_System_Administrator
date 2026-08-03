"""Seeding from the platform's manifest: authoritative for the modules it names, and nothing else."""
import json
from io import StringIO
from tempfile import TemporaryDirectory
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from iam.models import RolePermission


def manifest(grants, module="placement_cell", version=1):
    return {"version": version,
            "modules": {module: {"permissions": [], "system_permissions": [],
                                 "grants": grants}}}


class SeedPermissionsTests(TestCase):
    databases = {"default", "system_db"}

    def seed(self, payload, **kwargs):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "permissions.json"
            path.write_text(json.dumps(payload))
            out = StringIO()
            call_command("seed_iam_permissions", manifest=path, stdout=out,
                         **kwargs)
            return out.getvalue()

    def test_grants_in_the_manifest_are_created(self):
        self.seed(manifest({"student": ["placement_cell.registration.self"]}))
        self.assertTrue(RolePermission.objects.filter(
            designation="student",
            permission="placement_cell.registration.self").exists())

    def test_running_twice_changes_nothing(self):
        payload = manifest({"student": ["placement_cell.job_posting.view"]})
        self.seed(payload)
        self.assertIn("0 added, 0 revoked", self.seed(payload))
        self.assertEqual(RolePermission.objects.count(), 1)

    def test_a_grant_dropped_upstream_is_revoked(self):
        self.seed(manifest({"student": ["placement_cell.job_posting.view",
                                        "placement_cell.offer.issue"]}))
        self.seed(manifest({"student": ["placement_cell.job_posting.view"]}))
        self.assertEqual(
            [r.permission for r in RolePermission.objects.all()],
            ["placement_cell.job_posting.view"])

    def test_another_module_is_left_alone(self):
        """Scoped by permission prefix: seeding placement must not disarm hr."""
        RolePermission.objects.create(designation="hr_officer",
                                      permission="hr.employment.manage")
        self.seed(manifest({"student": ["placement_cell.job_posting.view"]}))
        self.assertTrue(RolePermission.objects.filter(
            permission="hr.employment.manage").exists())

    def test_dry_run_writes_nothing(self):
        out = self.seed(manifest({"student": ["placement_cell.offer.respond"]}),
                        dry_run=True)
        self.assertIn("1 to add", out)
        self.assertEqual(RolePermission.objects.count(), 0)

    def test_an_unknown_version_is_refused(self):
        with self.assertRaisesMessage(CommandError, "understands 1"):
            self.seed(manifest({"student": []}, version=99))

    def test_an_empty_manifest_is_not_taken_as_revoke_everything(self):
        RolePermission.objects.create(designation="student",
                                      permission="placement_cell.offer.respond")
        with self.assertRaisesMessage(CommandError, "lists no modules"):
            self.seed({"version": 1, "modules": {}})
        self.assertEqual(RolePermission.objects.count(), 1)

    def test_a_missing_manifest_says_how_to_make_one(self):
        with self.assertRaisesMessage(CommandError, "make permissions"):
            call_command("seed_iam_permissions",
                         manifest=Path("/nonexistent/permissions.json"),
                         stdout=StringIO())
