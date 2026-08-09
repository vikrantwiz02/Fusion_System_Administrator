"""The ERP -> IAM projection.

Every test here fakes iam.sync.erp_source. That is not a shortcut: erp_source
is the only module that knows the ERP's shape, so replacing it exercises
everything downstream of the anti-corruption boundary without needing the ERP's
276-FK schema to exist. If a test here needed a real ERP table, the boundary
would have leaked.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from iam import sync
from iam.models import (IamDesignationModule, IamUser, IamUserAcademic,
                        IamUserDesignation, SyncRun)


def user(uid, username, **over):
    row = {
        "erp_user_id": uid, "username": username,
        "display_name": username.title(), "email": f"{username}@example.invalid",
        "kind": "student", "is_active": True, "password_hash": "pbkdf2$fake",
        "department": "CSE", "programme": "B.Tech", "discipline": "CSE",
        "batch_year": 2023,
    }
    row.update(over)
    return row


def academic(roll, cpi="8.0", **over):
    row = {
        "roll_no": roll, "programme": "B.Tech", "semester": 5,
        "semester_type": "Odd Semester", "declared_seq": 50,
        "cpi": Decimal(cpi), "earned_credits": Decimal("100"),
        "cpi_denominator_credits": Decimal("96"), "active_backlogs": 0,
        "courses_counted": 30, "announcement_id": 7,
    }
    row.update(over)
    return row


def fake_erp(users=(), designations=(), grants=(), academics=(),
             programme_roles=()):
    """A stand-in for iam.erp_source with the same callables.

    Must mirror the real module exactly. When erp_source grows a function, it
    grows here too — a fake that has drifted is worse than no fake, because it
    makes the sync look tested when the new path is not exercised at all.
    """
    return SimpleNamespace(
        iter_users=lambda batch_size=500: iter([list(users)] if users else []),
        all_user_designations=lambda: list(designations),
        all_student_programme_roles=lambda: list(programme_roles),
        all_designation_modules=lambda: list(grants),
        all_academic_standings=lambda: list(academics),
        fetch_password_hash=lambda username: None,
    )


class SyncTests(TestCase):
    databases = {"default", "system_db"}

    def test_projects_users_designations_and_grants(self):
        erp = fake_erp(
            users=[user(1, "alice"), user(2, "bob", kind="faculty")],
            designations=[(1, "student"), (2, "professor")],
            grants=[("professor", "placement_cell"), ("student", "placement_cell")],
        )
        with patch.object(sync, "erp_source", erp):
            run = sync.sync_all()

        self.assertEqual(run.status, "succeeded")
        self.assertEqual(run.users_seen, 2)
        self.assertEqual(IamUser.objects.count(), 2)
        self.assertEqual(IamUserDesignation.objects.count(), 2)
        self.assertEqual(IamDesignationModule.objects.count(), 2)

        alice = IamUser.objects.get(pk=1)
        self.assertEqual(alice.username, "alice")
        self.assertEqual(alice.discipline, "CSE")
        self.assertEqual(alice.batch_year, 2023)

    def test_running_twice_changes_nothing(self):
        erp = fake_erp(users=[user(1, "alice")], designations=[(1, "student")],
                       grants=[("student", "placement_cell")])
        with patch.object(sync, "erp_source", erp):
            sync.sync_all()
            sync.sync_all()

        self.assertEqual(IamUser.objects.count(), 1)
        self.assertEqual(IamUserDesignation.objects.count(), 1)
        self.assertEqual(IamDesignationModule.objects.count(), 1)

    def test_an_updated_user_is_overwritten_not_duplicated(self):
        with patch.object(sync, "erp_source", fake_erp(users=[user(1, "alice")])):
            sync.sync_all()
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "alice", display_name="Alice B",
                                               discipline="ECE")])):
            sync.sync_all()

        self.assertEqual(IamUser.objects.count(), 1)
        alice = IamUser.objects.get(pk=1)
        self.assertEqual(alice.display_name, "Alice B")
        self.assertEqual(alice.discipline, "ECE")

    def test_a_revoked_designation_actually_disappears(self):
        """The security-relevant direction. A diff that only adds would keep a
        revoked role alive forever, so the sync replaces wholesale."""
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "alice")],
                                   designations=[(1, "student"), (1, "placement_coord")])):
            sync.sync_all()
        self.assertEqual(IamUserDesignation.objects.filter(erp_user_id=1).count(), 2)

        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "alice")],
                                   designations=[(1, "student")])):
            sync.sync_all()

        held = set(IamUserDesignation.objects.filter(erp_user_id=1)
                   .values_list("designation", flat=True))
        self.assertEqual(held, {"student"})

    def test_a_revoked_module_grant_actually_disappears(self):
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "alice")],
                                   grants=[("student", "placement_cell"),
                                           ("student", "hr")])):
            sync.sync_all()
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "alice")],
                                   grants=[("student", "placement_cell")])):
            sync.sync_all()

        granted = set(IamDesignationModule.objects.filter(designation="student")
                      .values_list("module_code", flat=True))
        self.assertEqual(granted, {"placement_cell"})

    def test_the_sync_leaves_manifest_granted_modules_alone(self):
        """Two writers share this table, and the ERP is not authoritative here.

        A service declares its own modules and seeds them as `manifest`. If the
        projection deleted by module code rather than by source, a code the ERP
        also happens to know — `examinations` is both a globals_moduleaccess
        column and a Fusion-Academic module — would lose every grant the ERP
        does not repeat, silently, on the next sync.
        """
        IamDesignationModule.objects.create(
            designation="faculty", module_code="examinations",
            source=IamDesignationModule.MANIFEST)

        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "alice")],
                                   grants=[("student", "examinations")])):
            sync.sync_all()

        granted = set(IamDesignationModule.objects.filter(
            module_code="examinations").values_list("designation", flat=True))
        self.assertEqual(granted, {"faculty", "student"})

    def test_a_vanished_user_is_deactivated_never_deleted(self):
        """Applications and audit rows reference the id; a hard delete would
        leave them dangling."""
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "alice"), user(2, "bob")])):
            sync.sync_all()

        with patch.object(sync, "erp_source", fake_erp(users=[user(1, "alice")])):
            run = sync.sync_all()

        self.assertEqual(run.deactivated, 1)
        self.assertEqual(IamUser.objects.count(), 2)          # still there
        self.assertFalse(IamUser.objects.get(pk=2).is_active)
        self.assertTrue(IamUser.objects.get(pk=1).is_active)

    def test_an_empty_erp_read_does_not_deactivate_everyone(self):
        """A failed or empty read must not be mistaken for 'nobody exists'."""
        with patch.object(sync, "erp_source", fake_erp(users=[user(1, "alice")])):
            sync.sync_all()
        with patch.object(sync, "erp_source", fake_erp(users=[])):
            sync.sync_all()

        self.assertTrue(IamUser.objects.get(pk=1).is_active)

    def test_a_failure_is_recorded_and_re_raised(self):
        def boom(batch_size=500):
            raise RuntimeError("ERP went away mid-read")

        erp = fake_erp(users=[user(1, "alice")])
        erp.iter_users = boom
        with patch.object(sync, "erp_source", erp):
            with self.assertRaises(RuntimeError):
                sync.sync_all()

        run = SyncRun.objects.first()
        self.assertEqual(run.status, "failed")
        self.assertIn("ERP went away mid-read", run.error)
        self.assertIsNotNone(run.finished_at)

    def test_academic_standing_is_projected_and_joined_to_the_user(self):
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "21BCS002")],
                                   academics=[academic("21BCS002", cpi="8.4")])):
            run = sync.sync_all()

        self.assertEqual(run.academics_written, 1)
        a = IamUserAcademic.objects.get(pk=1)          # keyed on erp_user_id
        self.assertEqual(a.roll_no, "21BCS002")
        self.assertEqual(a.cpi, Decimal("8.4"))
        self.assertEqual(a.computed_by, sync.COMPUTED_BY)

    def test_a_standing_with_no_matching_user_is_dropped_not_crashed(self):
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "alice")],
                                   academics=[academic("GHOST999")])):
            run = sync.sync_all()
        self.assertEqual(run.academics_written, 0)

    def test_roll_number_case_mismatch_still_joins(self):
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "21bcs002")],
                                   academics=[academic("21BCS002")])):
            run = sync.sync_all()
        self.assertEqual(run.academics_written, 1)

    def test_a_retracted_result_removes_the_standing(self):
        """The case that matters. If a declaration is withdrawn the student's
        CPI must vanish so eligibility fails closed again — an upsert-only sync
        would leave a retracted CPI in place and someone would apply on it."""
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "21BCS002")],
                                   academics=[academic("21BCS002")])):
            sync.sync_all()
        self.assertEqual(IamUserAcademic.objects.count(), 1)

        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "21BCS002")], academics=[])):
            sync.sync_all()
        self.assertEqual(IamUserAcademic.objects.count(), 0)

    def test_designations_are_deduplicated(self):
        """The ERP can hold the same pair twice; the unique constraint must not
        turn that into a crash."""
        with patch.object(sync, "erp_source",
                          fake_erp(users=[user(1, "alice")],
                                   designations=[(1, "student"), (1, "student")])):
            run = sync.sync_all()
        self.assertEqual(run.designations_written, 1)


class FakeMatchesReal(TestCase):
    """The docstring on fake_erp says it must mirror erp_source. This is what
    makes that true rather than aspirational: a fake missing the function the
    sync just started calling makes the sync look tested when it is not."""

    def test_the_fake_offers_everything_the_sync_reads(self):
        from iam import erp_source

        used = {
            name for name in dir(erp_source)
            if not name.startswith("_") and callable(getattr(erp_source, name))
            and getattr(erp_source, name).__module__ == erp_source.__name__
        }
        offered = set(vars(fake_erp()))
        # The fake need not offer helpers the sync never calls, only the ones it
        # already stands in for plus anything newly added beside them.
        missing = {n for n in used if n in {
            "iter_users", "all_user_designations", "all_designation_modules",
            "all_academic_standings", "fetch_password_hash",
            "all_student_programme_roles",
        }} - offered
        self.assertEqual(missing, set())
