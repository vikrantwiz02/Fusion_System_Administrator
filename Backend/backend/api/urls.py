from django.urls import path
from . import views
from . import update_global_db

urlpatterns = [
    path("departments/", views.get_all_departments, name="get_all_departments"),
    path("batches/", views.get_all_batches, name="get_all_batches"),
    path("programmes/", views.get_all_programmes, name="get_all_programmes"),
    path(
        "get-user-roles-by-username/",
        views.get_user_role_by_username,
        name="get_user_role_by_username",
    ),
    path("update-user-roles/", views.update_user_roles, name="update_user_roles"),
    path("view-roles/", views.global_designation_list, name="global_designation_list"),
    path(
        "view-designations/",
        views.get_category_designations,
        name="get_category_designations",
    ),
    path("create-role/", views.add_designation, name="add_designation"),
    path("modify-role/", views.update_designation, name="update_designation"),
    path("get-module-access/", views.get_module_access, name="get_module_access"),
    path("modify-roleaccess/", views.modify_moduleaccess, name="modify_moduleaccess"),
    path(
        "users/add-student/",
        views.add_individual_student,
        name="add_individual_student",
    ),
    path("users/add-staff/", views.add_individual_staff, name="add_individual_staff"),
    path(
        "users/add-faculty/",
        views.add_individual_faculty,
        name="add_individual_faculty",
    ),
    path("users/reset_password/", views.reset_password, name="reset-password"),
    path("users/import/", views.bulk_import_users, name="bulk-import-users"),
    path("users/export/", views.bulk_export_users, name="bulk-export-users"),
    path("users/mail-batch/", views.mail_to_whole_batch, name="mail-to-whole-batch"),
    path(
        "update-globals-db/",
        update_global_db.update_globals_db,
        name="update_globals_db",
    ),
    path("download-sample-csv/", views.download_sample_csv, name="download_sample_csv"),
    path("users/", views.UserListView.as_view(), name="user-list"),
    # backup management
    path("backups/", backup_views.list_backups, name="list-backups"),
    path("backups/create/", backup_views.create_backup, name="create-backup"),
    path("backups/<uuid:backup_id>/", backup_views.get_backup, name="get-backup"),
    path(
        "backups/<uuid:backup_id>/delete/",
        backup_views.delete_backup,
        name="delete-backup",
    ),
    path(
        "backups/<uuid:backup_id>/restore/",
        backup_views.restore_backup,
        name="restore-backup",
    ),
    # restore management
    path("restores/", backup_views.list_restores, name="list-restores"),
    path("restores/<uuid:restore_id>/", backup_views.get_restore, name="get-restore"),
    # schedule management
    path("schedules/", backup_views.list_schedules, name="list-schedules"),
    path("schedules/save/", backup_views.save_schedule, name="save-schedule"),
    path(
        "schedules/preview/", backup_views.preview_next_runs, name="preview-next-runs"
    ),
    path(
        "schedules/<uuid:schedule_id>/toggle/",
        backup_views.toggle_schedule,
        name="toggle-schedule",
    ),
    path(
        "schedules/<uuid:schedule_id>/delete/",
        backup_views.delete_schedule,
        name="delete-schedule",
    ),
    # health checks
    path("health-checks/", backup_views.list_health_checks, name="list-health-checks"),
    path("health-checks/run/", backup_views.run_health_check, name="run-health-check"),
    # database info
    path("db-info/", backup_views.db_info, name="db-info"),
    path('departments/', views.get_all_departments ,name='get_all_departments'),
    path('batches/', views.get_all_batches ,name='get_all_batches'),
    path('programmes/', views.get_all_programmes ,name='get_all_programmes'),
    path('get-user-roles-by-username/', views.get_user_role_by_username ,name='get_user_role_by_username'),
    path('update-user-roles/', views.update_user_roles ,name='update_user_roles'),
    path('view-roles/', views.global_designation_list ,name='global_designation_list'),
    path('view-designations/', views.get_category_designations ,name='get_category_designations'),
    path('create-role/', views.add_designation ,name='add_designation'),
    path('modify-role/', views.update_designation ,name='update_designation'),
    path('get-module-access/', views.get_module_access, name='get_module_access'),
    path('modify-roleaccess/', views.modify_moduleaccess ,name='modify_moduleaccess'),
    path('users/add-student/', views.add_individual_student, name='add_individual_student'),
    path('users/add-staff/', views.add_individual_staff, name='add_individual_staff'),
    path('users/add-faculty/', views.add_individual_faculty, name='add_individual_faculty'),
    path('users/reset_password/', views.reset_password, name='reset-password'),
    path('users/import/', views.bulk_import_users, name='bulk-import-users'),
    path('users/export/', views.bulk_export_users, name='bulk-export-users'),
    path('users/mail-batch/', views.mail_to_whole_batch, name='mail-to-whole-batch'),
    path('update-globals-db/', update_global_db.update_globals_db, name='update_globals_db'),
    path('download-sample-csv/', views.download_sample_csv, name='download_sample_csv'),
    path("users/", views.UserListView.as_view(), name='user-list'),
    path('audit-logs/', views.get_audit_logs, name='audit-logs'),
]
