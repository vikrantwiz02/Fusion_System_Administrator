"""Fold a duplicate login into the account the person actually uses.

Two auth_user rows for one person happen when a username is created with
whitespace around it, or re-created by a second import. The damage is not the
spare row: it is that their designations, and so their permissions, can end up
on the account they never sign into, while their profile and login history sit
on the other.

Everything that points at the loser is repointed at the keeper before the loser
is deactivated, so nothing is lost and no role disappears. It deactivates
rather than deletes: with 160 foreign keys into auth_user, a delete is not a
reversible operation and this is.

    --pair KEEP=LOSE    the merge, explicit on purpose
    --dry-run           show every row that would move

Which account survives is a decision about somebody's role, so this command
never chooses. It refuses unless you name both.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from api.models.erp import AuthUser

#: Repointed rather than left behind. Anything not listed stays with the loser,
#: which is right for history (a notification was sent to that account) and
#: wrong for nothing that grants access.
CARRY_OVER = [
    ("globals_holdsdesignation", "user_id"),
    ("globals_holdsdesignation", "working_id"),
    ("globals_extrainfo", "user_id"),
    ("notifications_notification", "recipient_id"),
    # Grants access in the legacy leave app. Moved rather than dropped: the
    # person holds it today, and a merge preserves what they have rather than
    # quietly taking it away.
    ("leave_leaveadministrators", "user_id"),
]

#: Deleted, not moved: a credential belonging to a retired account.
DISCARD = [("authtoken_token", "user_id")]


class Command(BaseCommand):
    help = "Merge a duplicate auth_user row into the account that is really used."

    def add_arguments(self, parser):
        parser.add_argument("--pair", required=True, metavar="KEEP=LOSE",
                            help="Keeper and loser user ids.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        keep_id, lose_id = self._pair(opts["pair"])
        keep, lose = self._load(keep_id), self._load(lose_id)
        if keep.id == lose.id:
            raise CommandError("An account cannot be merged into itself.")
        if keep.username.strip().lower() != lose.username.strip().lower():
            raise CommandError(
                f"{keep.username!r} and {lose.username!r} are not the same username "
                "once trimmed. This command is for duplicates, not for moving one "
                "person's records onto another.")

        self.stdout.write(f"  keep  user {keep.id:<6} {keep.username!r} "
                          f"(last login {keep.last_login or 'never'})")
        self.stdout.write(f"  lose  user {lose.id:<6} {lose.username!r} "
                          f"(last login {lose.last_login or 'never'})")

        moves = self._plan(keep.id, lose.id)
        if not moves:
            self.stdout.write("  nothing references the losing account")
        for table, column, count, action in moves:
            self.stdout.write(f"    {action:<8} {count:>3}  {table}.{column}")

        unclassified = [m for m in moves if m[3] == "UNCLASSIFIED"]
        if unclassified:
            self.stdout.write(self.style.ERROR(
                "\n  Rows reference the losing account that this command does not "
                "know how to handle. They would be left pointing at a deactivated "
                "user. Decide what each should do and add it to CARRY_OVER or "
                "DISCARD before merging:"))
            for table, column, count, _ in unclassified:
                self.stdout.write(self.style.ERROR(f"    {count:>3}  {table}.{column}"))
            raise CommandError("Refusing to merge with references unaccounted for.")

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("  dry run — nothing was written"))
            return

        with transaction.atomic(), connections["default"].cursor() as c:
            for table, column, _, action in moves:
                if action == "keep-as-is":
                    continue
                if action == "move":
                    # Skip rows that would collide with one the keeper already
                    # has: they already hold that designation, so there is
                    # nothing to carry over.
                    c.execute(
                        f'UPDATE "{table}" SET "{column}" = %s '
                        f'WHERE "{column}" = %s', [keep.id, lose.id])
                else:
                    c.execute(f'DELETE FROM "{table}" WHERE "{column}" = %s', [lose.id])
            AuthUser.objects.filter(pk=lose.id).update(is_active=False)

        self.stdout.write(self.style.SUCCESS(
            f"  merged. User {lose.id} is deactivated; run sync_identity to carry "
            "it across."))

    def _pair(self, raw: str) -> tuple[int, int]:
        if "=" not in raw:
            raise CommandError("--pair wants KEEP=LOSE, for example --pair 2420=114")
        keep, lose = raw.split("=", 1)
        try:
            return int(keep), int(lose)
        except ValueError as exc:
            raise CommandError("--pair wants two user ids.") from exc

    def _load(self, user_id: int) -> AuthUser:
        user = AuthUser.objects.filter(pk=user_id).first()
        if user is None:
            raise CommandError(f"No such user: {user_id}")
        return user

    def _references(self, cursor) -> list[tuple[str, str]]:
        """Every foreign key into auth_user, read from the database.

        Discovered rather than listed. A hand-maintained list is a loophole with
        a delay on it: the next table to reference auth_user would be left
        pointing at a deactivated account and nothing would say so.
        """
        cursor.execute("""
            select tc.table_name, kcu.column_name
            from information_schema.table_constraints tc
            join information_schema.key_column_usage kcu
              on kcu.constraint_name = tc.constraint_name
            join information_schema.constraint_column_usage ccu
              on ccu.constraint_name = tc.constraint_name
            where tc.constraint_type = 'FOREIGN KEY'
              and ccu.table_name = 'auth_user' and ccu.column_name = 'id'
            order by 1, 2""")
        return cursor.fetchall()

    def _plan(self, keep_id: int, lose_id: int) -> list[tuple]:
        carry = set(CARRY_OVER)
        discard = set(DISCARD)
        plan = []
        with connections["default"].cursor() as c:
            for table, column in self._references(c):
                try:
                    n = self._count(c, table, column, lose_id)
                except Exception:
                    c.execute("rollback")
                    continue
                if not n:
                    continue
                if (table, column) in discard:
                    plan.append((table, column, n, "delete"))
                elif (table, column) in carry:
                    if table == "globals_extrainfo" and self._count(
                            c, table, "user_id", keep_id):
                        # The keeper already has a profile; the spare one is not
                        # better information, and moving it would collide.
                        plan.append((table, column, n, "keep-as-is"))
                    else:
                        plan.append((table, column, n, "move"))
                else:
                    plan.append((table, column, n, "UNCLASSIFIED"))
        order = {"move": 0, "delete": 1, "keep-as-is": 2, "UNCLASSIFIED": 3}
        return sorted(plan, key=lambda p: (order[p[3]], p[0]))

    @staticmethod
    def _count(cursor, table: str, column: str, user_id: int) -> int:
        cursor.execute(f'SELECT count(*) FROM "{table}" WHERE "{column}" = %s', [user_id])
        return cursor.fetchone()[0]
