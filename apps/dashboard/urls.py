# apps/dashboard/urls.py - UPDATED
from django.urls import path
from . import views, admin_views
from apps.dashboard import complete_admin_views
try:
    from apps.dashboard import timetable_views
except ImportError:
    timetable_views = None

urlpatterns = [
    # Access verification
    path('verify-admin/', views.verify_admin_access, name='verify-admin'),
    path('verify-teacher/', views.verify_teacher_access, name='verify-teacher'),
    path('verify-student/', views.verify_student_access, name='verify-student'),
    path('verify-parent/', views.verify_parent_access, name='verify-parent'),
    
    # Admin dashboard data
    path('admin/overview/', admin_views.admin_overview, name='admin-overview'),
    
    # Students management endpoints
    path('admin/students/', complete_admin_views.get_students_list, name='admin-students-list'),
    path('admin/students/<int:student_id>/', complete_admin_views.get_student_details, name='admin-student-details'),
    
    # Classes management endpoints
    path('admin/classes/', complete_admin_views.get_classes_list, name='admin-classes-list'),
    path('admin/classes/', complete_admin_views.create_class, name='admin-create-class'),
    
    # Finance management endpoints
    path('admin/finance/overview/', complete_admin_views.get_finance_overview, name='admin-finance-overview'),
    path('admin/finance/pending-fees/', complete_admin_views.get_pending_fee_students, name='admin-pending-fees'),
    path('admin/finance/record-payment/', complete_admin_views.record_payment, name='admin-record-payment'),
    
    # Reports endpoints
    path('admin/reports/teacher-performance/', complete_admin_views.get_teacher_performance_report, name='admin-teacher-performance'),
    
    # Settings endpoints
    path('admin/settings/', complete_admin_views.manage_school_settings, name='admin-settings'),

      # ========== TIMETABLE MANAGEMENT ENDPOINTS (NEW) ==========
    path('admin/timetable/time-slots/', timetable_views.get_time_slots, name='admin-time-slots'),
    path('admin/timetable/time-slots/create/', timetable_views.create_time_slot, name='admin-create-time-slot'),
    path('admin/timetable/class/<int:class_id>/', timetable_views.get_class_timetable, name='admin-class-timetable'),
    path('admin/timetable/create/', timetable_views.create_timetable, name='admin-create-timetable'),
    path('admin/timetable/entry/create/', timetable_views.create_or_update_timetable_entry, name='admin-create-timetable-entry'),
    path('admin/timetable/entry/<int:entry_id>/update/', timetable_views.create_or_update_timetable_entry, name='admin-update-timetable-entry'),
    path('admin/timetable/entry/<int:entry_id>/delete/', timetable_views.delete_timetable_entry, name='admin-delete-timetable-entry'),
    path('admin/timetable/class/<int:class_id>/resources/', timetable_views.get_subjects_and_teachers, name='admin-timetable-resources'),

]