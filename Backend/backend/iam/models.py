"""IAM tables. These live in system_db, NOT in the ERP.

Why a token table of our own instead of reusing rest_framework.authtoken:
that model has a ForeignKey to AUTH_USER_MODEL, which the router sends to
system_db — the *operator* pool. The people signing in here are the ~3,277 ERP
users in a different database entirely, so their sessions cannot FK to anything.
`erp_user_id` is therefore a plain integer, matching how Fusion-Integrated
references people.
"""
import binascii
import hashlib
import os
import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone


def _make_key() -> str:
    """Unused: kept only because migration 0001 names it as a field default."""
    return binascii.hexlify(os.urandom(24)).decode()


class IamToken(models.Model):
    """A session for an ERP user. `key` is the SHA-256 of the bearer token,
    so a dump of system_db yields no usable session."""

    key = models.CharField(max_length=64, primary_key=True)
    erp_user_id = models.IntegerField(db_index=True)
    username = models.CharField(max_length=150, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    #: Set in memory by `issue()`, never persisted.
    raw_key: str = ""

    class Meta:
        db_table = "iam_token"
        indexes = [
            models.Index(fields=["erp_user_id", "-created_at"],
                         name="iamtoken_user_recent_idx"),
        ]

    @staticmethod
    def hash_raw(raw: str) -> str:
        # A plain digest: CSPRNG input, so nothing for a slow KDF to protect.
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(cls, *, erp_user_id: int, username: str, ttl_hours: int = 12):
        """Mint a session. The raw token is on `.raw_key`, once."""
        raw = secrets.token_urlsafe(32)
        token = cls.objects.create(
            key=cls.hash_raw(raw), erp_user_id=erp_user_id, username=username,
            expires_at=timezone.now() + timedelta(hours=ttl_hours),
        )
        token.raw_key = raw
        return token

    @classmethod
    def resolve(cls, raw: str) -> "IamToken | None":
        if not raw:
            return None
        return cls.objects.filter(key=cls.hash_raw(raw)).first()

    @property
    def is_live(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()

    def touch(self) -> None:
        """Record use, at most once a minute — an unconditional save here is a
        DB write per request, which is what slowed the legacy app."""
        now = timezone.now()
        if self.last_used_at and (now - self.last_used_at) < timedelta(minutes=1):
            return
        type(self).objects.filter(pk=self.pk).update(last_used_at=now)

    def revoke(self) -> None:
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])


class IamServiceToken(models.Model):
    """A credential for another *service*, not a person.

    Fusion-Integrated reads the directory server-to-server: a report listing
    300 applicants by name has no user session behind it.

    Stored as a SHA-256 digest — the raw value is shown once at creation, so a
    dump of system_db yields no working credential. Narrow by design: it
    authenticates on the directory endpoints only and cannot reach /me,
    because there is no person for it to be.
    """

    PREFIX = "fsvc_"          # makes the value greppable in a leak or a log

    name = models.CharField(max_length=64, unique=True)
    token_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "iam_service_token"
        ordering = ["name"]

    @staticmethod
    def hash_raw(raw: str) -> str:
        # A plain digest, not a password hash: the input is 32 bytes of CSPRNG
        # output, so there is nothing for a slow KDF to protect against.
        return hashlib.sha256(raw.encode()).hexdigest()

    @classmethod
    def issue(cls, name: str) -> tuple["IamServiceToken", str]:
        """Returns (row, raw). The raw value is never persisted."""
        raw = cls.PREFIX + secrets.token_urlsafe(32)
        return cls.objects.create(name=name, token_hash=cls.hash_raw(raw)), raw

    def rotate(self) -> str:
        """New secret under the same name; the old value stops working at once.

        Names are unique, so rotation — not a second row — is how a token is
        replaced without renaming every caller's configuration.
        """
        raw = type(self).PREFIX + secrets.token_urlsafe(32)
        self.token_hash = type(self).hash_raw(raw)
        self.is_active = True
        self.last_used_at = None
        self.save(update_fields=["token_hash", "is_active", "last_used_at"])
        return raw

    @classmethod
    def resolve(cls, raw: str) -> "IamServiceToken | None":
        if not raw or not raw.startswith(cls.PREFIX):
            return None
        return cls.objects.filter(token_hash=cls.hash_raw(raw),
                                  is_active=True).first()

    def touch(self) -> None:
        """Record use, but at most once a minute.

        A write per request is exactly the pattern that made the legacy app slow
        (SESSION_SAVE_EVERY_REQUEST); minute granularity answers "is this token
        still in use?" just as well.
        """
        now = timezone.now()
        if self.last_used_at and (now - self.last_used_at) < timedelta(minutes=1):
            return
        type(self).objects.filter(pk=self.pk).update(last_used_at=now)

    def __str__(self) -> str:
        return f"{self.name}{'' if self.is_active else ' (revoked)'}"


class RolePermission(models.Model):
    """Designation name -> one permission code.

    The ERP has designations and a module-access table, but no concept of a
    permission. Rather than invent a parallel role system, this maps the
    designations that already exist onto the permission codes the platform
    checks. Seeded by `manage.py seed_iam_permissions`.
    """

    designation = models.CharField(max_length=155, db_index=True)
    permission = models.CharField(max_length=100)

    class Meta:
        db_table = "iam_role_permission"
        constraints = [
            models.UniqueConstraint(fields=["designation", "permission"],
                                    name="iam_role_permission_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.designation}:{self.permission}"


class LoginAttempt(models.Model):
    """Recorded for every attempt, including ones against usernames that do not
    exist — that is precisely the signal for enumeration and stuffing."""

    username = models.CharField(max_length=150, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    outcome = models.CharField(max_length=24)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "iam_login_attempt"
        indexes = [models.Index(fields=["username", "-at"],
                                name="iamattempt_user_recent_idx")]


# ---------------------------------------------------------------------------
# The identity projection (Phase 1 of ADR-0014).
#
# A synced copy of who exists, held in system_db. Today the ERP is the source
# of truth and these tables are downstream of it; in Phase 2 the arrow flips
# and these become authoritative, with the ERP receiving a projection instead.
# The schema does not change when that happens — only the direction of sync.
#
# Which is why these are NOT named *_cache: they are the destination.
# ---------------------------------------------------------------------------
class IamUser(models.Model):
    """A person, projected from the ERP's auth_user + extrainfo + student/faculty."""

    KINDS = [("student", "Student"), ("faculty", "Faculty"),
             ("staff", "Staff"), ("compounder", "Compounder")]

    erp_user_id = models.IntegerField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    display_name = models.CharField(max_length=300, blank=True)
    email = models.CharField(max_length=254, blank=True)
    kind = models.CharField(max_length=20, choices=KINDS, default="staff", db_index=True)
    is_active = models.BooleanField(default=True)

    # Copied so login does not need the ERP. If it goes stale (a reset done in
    # the ERP), authenticate() falls back to a live check and re-syncs — see
    # iam/sync.py.
    password_hash = models.CharField(max_length=128, blank=True)

    department = models.CharField(max_length=100, blank=True)
    programme = models.CharField(max_length=40, blank=True)
    discipline = models.CharField(max_length=40, blank=True, db_index=True)
    batch_year = models.IntegerField(null=True, blank=True)

    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "iam_user"
        indexes = [
            models.Index(fields=["kind", "discipline"], name="iamuser_kind_disc_idx"),
            models.Index(fields=["is_active"], name="iamuser_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.username}({self.erp_user_id})"


class IamUserDesignation(models.Model):
    """Which designations a person currently works as.

    Projected from globals_holdsdesignation filtered on `working` — the field
    the ERP's own model docstring says to use for permissions.
    """

    erp_user_id = models.IntegerField(db_index=True)
    designation = models.CharField(max_length=155, db_index=True)

    class Meta:
        db_table = "iam_user_designation"
        constraints = [
            models.UniqueConstraint(fields=["erp_user_id", "designation"],
                                    name="iam_user_designation_unique"),
        ]


class IamDesignationModule(models.Model):
    """Which modules a designation may enter.

    Projected from globals_moduleaccess, whose one-boolean-column-per-module
    shape stays behind in the ERP. Here a grant is a ROW.
    """

    designation = models.CharField(max_length=155, db_index=True)
    module_code = models.CharField(max_length=48)

    class Meta:
        db_table = "iam_designation_module"
        constraints = [
            models.UniqueConstraint(fields=["designation", "module_code"],
                                    name="iam_designation_module_unique"),
        ]


class IamUserAcademic(models.Model):
    """A student's academic standing at their most recently DECLARED semester.

    Placement eligibility needs a CGPA (PC-BR-004) and the ERP has no readable
    one — `academic_information_student.cpi` is permanently 0.0 and the real
    number is recomputed per request. So it is computed here by a replica of
    the ERP's algorithm (iam/grades.py) and projected alongside identity.

    "Declared" is the whole point: an undeclared student has NO ROW rather
    than a zero, so eligibility fails closed instead of reading them as very
    weak. The sync is the only writer.
    """

    erp_user_id = models.IntegerField(primary_key=True)
    roll_no = models.CharField(max_length=32, db_index=True)

    cpi = models.DecimalField(max_digits=4, decimal_places=1)
    earned_credits = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    cpi_denominator_credits = models.DecimalField(max_digits=7, decimal_places=2,
                                                  default=0)
    active_backlogs = models.IntegerField(default=0)
    courses_counted = models.IntegerField(default=0)

    # Provenance. A CPI without its semester is unusable: the placement UI must
    # render "8.1 · Sem 5 (Odd)" so nobody argues about a stale number.
    semester = models.IntegerField()
    semester_type = models.CharField(max_length=20, blank=True)
    declared_seq = models.IntegerField(db_index=True)
    erp_announcement_id = models.IntegerField(null=True, blank=True)

    programme = models.CharField(max_length=40, blank=True)
    computed_by = models.CharField(max_length=64, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "iam_user_academic"
        indexes = [
            models.Index(fields=["cpi"], name="iamacad_cpi_idx"),
            models.Index(fields=["active_backlogs"], name="iamacad_backlog_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.roll_no} cpi={self.cpi} sem={self.semester}"


class SyncRun(models.Model):
    """One execution of the ERP -> IAM projection. Observability, and the
    answer to "how stale is this?"."""

    STATUS = [("running", "Running"), ("succeeded", "Succeeded"),
              ("failed", "Failed")]

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="running")
    users_seen = models.IntegerField(default=0)
    users_written = models.IntegerField(default=0)
    designations_written = models.IntegerField(default=0)
    module_grants_written = models.IntegerField(default=0)
    academics_written = models.IntegerField(default=0)
    deactivated = models.IntegerField(default=0)
    error = models.TextField(blank=True)

    class Meta:
        db_table = "iam_sync_run"
        ordering = ["-started_at"]

    @property
    def duration_seconds(self) -> float | None:
        if not self.finished_at:
            return None
        return (self.finished_at - self.started_at).total_seconds()
