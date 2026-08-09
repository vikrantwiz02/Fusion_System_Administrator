-- Remove two designations their holder's basic role may not hold.
--
--   23BCS265  (user_type student) held  Dean Academic
--   ntripathi (user_type staff)   held  Assistant Professor
--
-- Both were inserted on 2026-07-18 an hour apart and are the only two rows
-- added to globals_holdsdesignation in the month before this script. Neither is
-- a wrong user_type that should be corrected instead: 23BCS265 is a B.Tech
-- student of the 2023 batch, and ntripathi has no globals_faculty row and
-- already holds acadadmin in the Academics section.
--
-- Dean Academic carried 54 permissions in IAM, including curriculum.course.manage
-- and curriculum.instructor.assign.
--
-- Matched by username and designation name rather than by id, so it is safe to
-- run against a database whose sequence differs. Idempotent: running it twice
-- deletes nothing the second time.
--
-- To reverse, see ops/sql/2026-08-08-remove-invalid-designations.undo.sql.

begin;

delete from globals_holdsdesignation h
using auth_user u, globals_extrainfo e, globals_designation d
where h.user_id = u.id
  and e.user_id = u.id
  and d.id = h.designation_id
  and (   (u.username = '23BCS265'  and e.user_type = 'student' and d.name = 'Dean Academic')
       or (u.username = 'ntripathi' and e.user_type = 'staff'   and d.name = 'Assistant Professor'));

commit;
