"""Reads the ERP. Used ONLY by the sync — never on a request path.

The anti-corruption boundary: everything that knows the ERP's shape lives
here. Identity spread across auth_user + globals_extrainfo + student/faculty,
module access as one boolean column per module keyed by a designation name,
and the `working` vs `user` rule on `globals_holdsdesignation` applied once
instead of the ERP's three inconsistent ways.

An import of this file from a view undoes Phase 1 — the point is that serving
a request no longer requires the ERP to be up.
"""
from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

from api.models.erp import (AuthUser, CourseReplacement, GlobalsDesignation,
                            GlobalsExtrainfo, GlobalsHoldsdesignation,
                            GlobalsModuleaccess, PublishedResultStudent,
                            ResultAnnouncement, Student, StudentGrade)
from iam import grades

# globals_moduleaccess column -> platform module code. Anything not listed is
# not exposed by the platform, even if the column exists.
MODULE_COLUMNS = {
    "placement_cell": "placement_cell",
    "hr": "hr",
    "mess_management": "mess_management",
    "hostel_management": "hostel_management",
    "complaint_management": "complaint_management",
    "phc": "phc",
    "visitor_hostel": "visitor_hostel",
    "gymkhana": "gymkhana",
    "iwd": "iwd",
    "rspc": "rspc",
    "purchase_and_store": "purchase_and_store",
}


def iter_users(batch_size: int = 500) -> Iterator[list[dict]]:
    """Every ERP user, in batches, with their identity fields flattened.

    Batched because this reads the whole user table (~3,300 rows today) and
    should not hold it all in memory or run one query per person.
    """
    extras = {
        e.user_id: e
        for e in GlobalsExtrainfo.objects.select_related("department").all()
    }
    # Student rows key on extrainfo.id, not user_id.
    students = {
        s.id_id: s
        for s in Student.objects.select_related("batch_id",
                                                "batch_id__discipline").all()
    }

    batch: list[dict] = []
    for u in AuthUser.objects.all().iterator(chunk_size=batch_size):
        e = extras.get(u.id)
        s = students.get(e.id) if e else None
        b = getattr(s, "batch_id", None)
        batch.append({
            "erp_user_id": u.id,
            "username": u.username,
            "display_name": f"{u.first_name} {u.last_name}".strip() or u.username,
            "email": u.email or "",
            "kind": (e.user_type or "staff").lower() if e else "staff",
            "is_active": bool(u.is_active),
            "password_hash": u.password or "",
            "department": getattr(getattr(e, "department", None), "name", "") or "",
            "programme": (s.programme if s else "") or "",
            "discipline": getattr(getattr(b, "discipline", None), "acronym", "") or "",
            "batch_year": getattr(b, "year", None) or (s.batch if s else None),
        })
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def all_user_designations() -> list[tuple[int, str]]:
    """(erp_user_id, designation_name) for every currently-held designation.

    Filtered on `working`, per the ERP's own guidance.
    """
    names = dict(GlobalsDesignation.objects.values_list("id", "name"))
    return [
        (working_id, names[designation_id])
        for working_id, designation_id in GlobalsHoldsdesignation.objects
        .values_list("working_id", "designation_id")
        if designation_id in names
    ]


#: Programme category -> the role a student in it holds, on top of `student`.
#: Derived, never assigned: what someone is studying is not a role anybody grants.
PROGRAMME_ROLES = {"UG": "ug_student", "PG": "pg_student", "PHD": "phd_student"}


def all_student_programme_roles() -> list[tuple[int, str]]:
    """(erp_user_id, role) for every student, from what they are enrolled on.

    A UG student is not a research scholar and a PhD scholar does not register
    for a B.Tech elective, but `globals_holdsdesignation` says only "student"
    for all 3,027 of them — so a permission meant for one reaches all.

    The category comes from the curriculum the batch belongs to, not from
    `academic_information_student.programme`: that column holds "M.Tech", which
    is a programme NAME, and the names in programme_curriculum_programme are
    finer ("M.Tech CSE AI & ML"), so matching on it would resolve nothing. The
    batch -> curriculum -> programme join resolves all 3,027.
    """
    rows = (Student.objects
            .exclude(batch_id__isnull=True)
            .values_list("id__user_id", "batch_id__curriculum__programme__category"))
    return [
        (user_id, PROGRAMME_ROLES[category])
        for user_id, category in rows
        if user_id and category in PROGRAMME_ROLES
    ]


def all_designation_modules() -> list[tuple[str, str]]:
    """(designation, module_code) for every true boolean in globals_moduleaccess."""
    out: list[tuple[str, str]] = []
    for row in GlobalsModuleaccess.objects.all():
        for code, column in MODULE_COLUMNS.items():
            if getattr(row, column, False):
                out.append((row.designation, code))
    return out


def fetch_password_hash(username: str) -> str | None:
    """Live read, used only as a fallback when the synced hash fails — so a
    password changed in the ERP works before the next sync lands."""
    return (AuthUser.objects.filter(username__iexact=username)
            .values_list("password", flat=True).first())


# -- Declared academic standing (CPI), for placement eligibility -------------
# Set-based on purpose: 104k grade rows across ~3,000 students is six queries,
# where per-student querying would be ~15,000 round trips against a live
# production database.
def _announcements_by_batch() -> dict[int, list[grades.Declaration]]:
    """batch_id -> every announced declaration, with who each one covers.

    Every one, not just the newest, because the newest is frequently not the
    one that applies to a given student: a Summer announcement covering a
    handful sorts above the regular one covering the whole cohort. See
    grades.applicable_declaration.

    Only `announced` rows count — an unannounced row is an admin's placeholder.
    """
    allow_lists = _announcement_allow_lists()
    by_batch: dict[int, list[grades.Declaration]] = {}
    rows = ResultAnnouncement.objects.filter(announced=True).values_list(
        "batch_id", "semester", "semester_type", "id")
    for batch_id, semester, sem_type, ann_id in rows:
        covered = allow_lists.get(ann_id)
        by_batch.setdefault(batch_id, []).append(grades.Declaration(
            announcement_id=ann_id, semester=semester, semester_type=sem_type,
            published_for=frozenset(covered) if covered is not None else None))
    return by_batch


def _announcement_allow_lists() -> dict[int, set[str]]:
    """announcement_id -> the roll numbers it is published for.

    Only announcements using per-student selection appear. An announcement
    absent from this mapping is published for its whole batch.
    """
    per_student = set(
        ResultAnnouncement.objects.filter(announced=True, per_student_selection=True)
        .values_list("id", flat=True))
    if not per_student:
        return {}
    out: dict[int, set[str]] = {aid: set() for aid in per_student}
    for ann_id, roll in (PublishedResultStudent.objects
                         .filter(announcement_id__in=per_student)
                         .values_list("announcement_id", "roll_no")):
        out[ann_id].add((roll or "").strip())
    return out


def _replacement_maps() -> dict[str, dict[str, str]]:
    """roll_no -> {new_course_code: replaced_course_code}.

    The ERP attributes a replacement to a student if EITHER registration is
    theirs, so both sides are indexed.
    """
    out: dict[str, dict[str, str]] = {}
    rows = CourseReplacement.objects.values_list(
        "old_course_registration__student_id_id",
        "old_course_registration__course_id__code",
        "new_course_registration__student_id_id",
        "new_course_registration__course_id__code",
    )
    for old_roll, old_code, new_roll, new_code in rows:
        old_code = (old_code or "").strip()
        new_code = (new_code or "").strip()
        if not old_code or not new_code or old_code == new_code:
            continue
        for roll in {old_roll, new_roll}:
            if roll:
                out.setdefault(roll, {})[new_code] = old_code
    return out


def _grades_by_roll() -> dict[str, list[grades.GradeRow]]:
    out: dict[str, list[grades.GradeRow]] = {}
    rows = StudentGrade.objects.values_list(
        "roll_no", "course_id__code", "course_id__credit",
        "grade", "semester", "semester_type").iterator(chunk_size=5000)
    for roll, code, credit, grade, semester, sem_type in rows:
        roll = (roll or "").strip()
        if not roll:
            continue
        out.setdefault(roll, []).append(grades.GradeRow(
            code=(code or "").strip(),
            credit=Decimal(str(credit)) if credit is not None else Decimal("0"),
            grade=grade or "", semester=semester or 0, semester_type=sem_type,
        ))
    return out


def all_academic_standings() -> list[dict]:
    """Every student's CPI at their most recently DECLARED semester.

    Undeclared students are omitted entirely rather than given a zero — a
    missing standing must fail eligibility closed, and a 0.0 would silently
    read as "very poor student" instead of "no result yet".
    """
    by_batch = _announcements_by_batch()
    if not by_batch:
        return []
    replacements = _replacement_maps()
    grade_rows = _grades_by_roll()

    students = Student.objects.exclude(batch_id__isnull=True).values_list(
        "id_id", "batch_id_id", "programme")

    out: list[dict] = []
    for roll, batch_id, programme in students:
        roll = (roll or "").strip()
        if not roll:
            continue

        # The newest declaration THIS student is actually covered by — see
        # grades.applicable_declaration for why it is not simply the newest.
        declared = grades.applicable_declaration(by_batch.get(batch_id, ()), roll)
        if declared is None:
            continue
        seq = declared.seq
        semester, sem_type = declared.semester, declared.semester_type
        ann_id = declared.announcement_id

        rows = grade_rows.get(roll)
        if not rows:
            continue

        standing = grades.compute_standing(
            rows, upto_semester=semester, semester_type=sem_type,
            replacement_map=replacements.get(roll))
        out.append({
            "roll_no": roll,
            "programme": programme or "",
            "semester": semester,
            "semester_type": sem_type or "",
            "declared_seq": seq,
            "cpi": standing.cpi,
            "earned_credits": standing.earned_credits,
            "cpi_denominator_credits": standing.cpi_denominator_credits,
            "active_backlogs": standing.active_backlogs,
            "courses_counted": standing.courses_counted,
            "announcement_id": ann_id,
        })
    return out
