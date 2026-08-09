-- Restores the two rows removed by 2026-08-08-remove-invalid-designations.sql.
-- Captured with pg_dump --column-inserts before the delete.

begin;
INSERT INTO public.globals_holdsdesignation (id, held_at, designation_id, user_id, working_id) VALUES (10088, '2026-07-18 12:22:02.003945+05:30', 19, 5755, 5755);
INSERT INTO public.globals_holdsdesignation (id, held_at, designation_id, user_id, working_id) VALUES (10089, '2026-07-18 13:23:25.123743+05:30', 3, 5425, 5425);
commit;
