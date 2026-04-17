# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
import datetime

class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'

class Programme(models.Model):
    category = models.CharField(max_length=3, null=False, blank=False)
    name = models.CharField(max_length=70, null=False,unique=True, blank=False)
    programme_begin_year = models.PositiveIntegerField(default=datetime.date.today().year, null=False)

    class Meta:
        managed = False
        db_table = 'programme_curriculum_programme'

    def __str__(self):
        return str(self.category + " - " + self.name)
    
class Discipline(models.Model):
    name = models.CharField(max_length=100, null=False,unique=True, blank=False)
    acronym = models.CharField(max_length=10, null=False, default="", blank=False)
    programmes = models.ManyToManyField(Programme, blank=True)

    class Meta:
        managed = False
        db_table = 'programme_curriculum_discipline'

    def __str__(self):
        return str(self.name) + " " + str(self.acronym)


class Curriculum(models.Model):
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, null=False)
    name = models.CharField(max_length=100, null=False, blank=False)
    version = models.DecimalField(default=1.0,max_digits=5,decimal_places=1)
    working_curriculum = models.BooleanField(default=True, null=False)
    no_of_semester = models.PositiveIntegerField(default=1, null=False)
    min_credit = models.PositiveIntegerField(default=0, null=False)
    latest_version = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'version',)
        managed = False
        db_table = 'programme_curriculum_curriculum'

    def __str__(self):
        return str(self.name + " v" + str(self.version))

class Batch(models.Model):

    name = models.CharField(max_length=50, null=False, blank=False)
    discipline = models.ForeignKey(Discipline, null=False, on_delete=models.CASCADE)
    year = models.PositiveIntegerField(default=datetime.date.today().year, null=False)
    curriculum = models.ForeignKey(Curriculum, null=True, blank=True, on_delete=models.SET_NULL)
    running_batch = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'discipline', 'year',)
        managed = False
        db_table = 'programme_curriculum_batch'

    def __str__(self):
        return str(self.name) + " " + str(self.discipline.acronym) + " " + str(self.year)


class GlobalsDepartmentinfo(models.Model):
    name = models.CharField(unique=True, max_length=100)

    class Meta:
        managed = False
        db_table = 'globals_departmentinfo'


class GlobalsDesignation(models.Model):
    name = models.CharField(unique=True, max_length=50)
    full_name = models.CharField(max_length=100)
    type = models.CharField(max_length=30)
    basic = models.BooleanField(default=False, null=False, blank=False)
    category = models.CharField(max_length=20, null=True, blank=True)
    dept_if_not_basic = models.ForeignKey(GlobalsDepartmentinfo, on_delete=models.CASCADE, blank=True, null=True)    
    class Meta:
        managed = False
        db_table = 'globals_designation'


class GlobalsExtrainfo(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    title = models.CharField(max_length=20)
    sex = models.CharField(max_length=2)
    date_of_birth = models.DateField()
    user_status = models.CharField(max_length=50)
    address = models.TextField()
    phone_no = models.BigIntegerField(blank=True, null=True)
    user_type = models.CharField(max_length=20)
    profile_picture = models.CharField(max_length=100, blank=True, null=True)
    about_me = models.TextField()
    date_modified = models.DateTimeField(blank=True, null=True)
    department = models.ForeignKey(GlobalsDepartmentinfo, on_delete=models.CASCADE, blank=True, null=True)
    user = models.OneToOneField(AuthUser, on_delete=models.CASCADE)

    class Meta:
        managed = False
        db_table = 'globals_extrainfo'

class Staff(models.Model):
    id = models.OneToOneField(GlobalsExtrainfo, on_delete=models.CASCADE, primary_key=True)

    def __str__(self):
        return str(self.id)
    
    class Meta:
        managed = False
        db_table = 'globals_staff'


class GlobalsHoldsdesignation(models.Model):
    held_at = models.DateTimeField(auto_now=True)
    designation = models.ForeignKey(GlobalsDesignation, related_name='designees', on_delete=models.CASCADE)
    user = models.ForeignKey(AuthUser, related_name='holds_designations', on_delete=models.CASCADE)
    working = models.ForeignKey(AuthUser, related_name='current_designation', on_delete=models.CASCADE)

    class Meta:
        managed = False
        db_table = 'globals_holdsdesignation'
        unique_together = (('user', 'designation'), ('working', 'designation'),)


class GlobalsModuleaccess(models.Model):
    designation = models.CharField(max_length=155)
    program_and_curriculum = models.BooleanField()
    course_registration = models.BooleanField()
    course_management = models.BooleanField()
    other_academics = models.BooleanField()
    spacs = models.BooleanField()
    department = models.BooleanField()
    examinations = models.BooleanField()
    hr = models.BooleanField()
    iwd = models.BooleanField()
    complaint_management = models.BooleanField()
    fts = models.BooleanField()
    purchase_and_store = models.BooleanField()
    rspc = models.BooleanField()
    hostel_management = models.BooleanField()
    mess_management = models.BooleanField()
    gymkhana = models.BooleanField()
    placement_cell = models.BooleanField()
    visitor_hostel = models.BooleanField()
    phc = models.BooleanField()
    inventory_management = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'globals_moduleaccess'

class Student(models.Model):

    id = models.OneToOneField(GlobalsExtrainfo, on_delete=models.CASCADE, primary_key=True)
    programme = models.CharField(max_length=10)
    batch = models.IntegerField(default=2016)
    batch_id = models.ForeignKey(Batch, null=True, blank=True, on_delete=models.CASCADE)
    cpi = models.FloatField(default=0)
    category = models.CharField(max_length=10, null=False)
    father_name = models.CharField(max_length=40, default='',null=True)
    mother_name = models.CharField(max_length=40, default='',null=True)
    hall_no = models.IntegerField(default=0)
    room_no = models.CharField(max_length=10, blank=True, null=True)
    specialization = models.CharField(max_length=40, null=True, default='')
    curr_semester_no = models.IntegerField(default=1)

    class Meta:
        managed = False
        db_table = 'academic_information_student'

    def __str__(self):
        username = str(self.id.user.username)
        return username
    
    
class GlobalsFaculty(models.Model):

    id = models.OneToOneField(GlobalsExtrainfo, on_delete=models.CASCADE, primary_key=True)

    def __str__(self):
        return str(self.id)
    
    class Meta:
        managed = False
        db_table = "globals_faculty"


class BackupRecord(models.Model):
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    db_name = models.CharField(
        max_length=200, help_text="Name of the database that was backed up"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="in_progress"
    )
    size_bytes = models.BigIntegerField(
        default=0, help_text="Size of the backup file in bytes"
    )
    duration_ms = models.BigIntegerField(
        default=0, help_text="Duration of the backup in milliseconds"
    )
    file_path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Path to the backup file on disk",
    )
    error_message = models.TextField(
        blank=True, default="", help_text="Error message if backup failed"
    )

    class Meta:
        managed = True
        db_table = "backup_records"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Backup {self.id} - {self.db_name} ({self.status})"


class RestoreRecord(models.Model):
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    db_name = models.CharField(max_length=200)
    source_backup = models.ForeignKey(
        BackupRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restores",
        help_text="The backup this restore was created from",
    )
    source_backup_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Snapshot of the source backup timestamp (kept even if backup is deleted)",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="in_progress"
    )
    duration_ms = models.BigIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        managed = True
        db_table = "restore_records"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Restore {self.id} - {self.db_name} ({self.status})"


class BackupSchedule(models.Model):
    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("custom", "Custom (cron)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    db_name = models.CharField(max_length=200, unique=True)
    enabled = models.BooleanField(default=True)
    frequency = models.CharField(
        max_length=20, choices=FREQUENCY_CHOICES, default="daily"
    )
    # time of day fields
    hour = models.IntegerField(default=2, help_text="Hour (0-23) in UTC")
    minute = models.IntegerField(default=0, help_text="Minute (0-59)")
    # weekly
    day_of_week = models.IntegerField(
        null=True,
        blank=True,
        help_text="Day of week for weekly schedule (0=Mon, 6=Sun)",
    )
    # monthly
    day_of_month = models.IntegerField(
        null=True, blank=True, help_text="Day of month for monthly schedule (1-28)"
    )
    # custom cron expression (overrides above when frequency=custom)
    cron_expression = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Full cron expression: minute hour day month weekday",
    )
    # retention
    retain_last_n = models.IntegerField(
        default=7, help_text="Keep only the last N successful backups (0 = keep all)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = True
        db_table = "backup_schedules"

    def __str__(self):
        return f"BackupSchedule({self.db_name}, {self.frequency}, {self.hour:02d}:{self.minute:02d})"


class HealthCheck(models.Model):
    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    db_name = models.CharField(max_length=200)
    checked_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="success")
    response_time_ms = models.IntegerField(
        default=0, help_text="DB ping response time in ms"
    )
    error_message = models.TextField(blank=True, default="")

    class Meta:
        managed = True
        db_table = "health_checks"
        ordering = ["-checked_at"]

    def __str__(self):
        return f"HealthCheck {self.db_name} @ {self.checked_at} ({self.status})"
        db_table = 'globals_faculty'


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('RESET_PASSWORD', 'Reset Password'),
        ('BULK_IMPORT', 'Bulk Import'),
        ('ROLE_CHANGE', 'Role Change'),
        ('MODULE_ACCESS_CHANGE', 'Module Access Change'),
    ]
    actor         = models.CharField(max_length=150)
    action        = models.CharField(max_length=30, choices=ACTION_CHOICES)
    target_user   = models.CharField(max_length=150, blank=True, null=True)
    resource_type = models.CharField(max_length=50)
    details       = models.JSONField(default=dict, blank=True)
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    timestamp     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']
