# apps/dashboard/admin_urls.py - FIXED VERSION
from django.urls import path
from . import complete_admin_views, timetable_views
from .reports_views import (
    download_academic_report,
    download_attendance_report,
    download_financial_report
)

urlpatterns = [
    # Student Management
    path('students/', complete_admin_views.get_students_list, name='admin-students'),
    path('students/<int:student_id>/', complete_admin_views.get_student_details, name='admin-student-detail'),

    # Class Management
    path('classes/', complete_admin_views.get_classes_list, name='admin-classes'),
    path('classes/create/', complete_admin_views.create_class, name='admin-create-class'),

    # Finance
    path('finance/overview/', complete_admin_views.get_finance_overview, name='admin-finance-overview'),
    path('finance/pending-fees/', complete_admin_views.get_pending_fee_students, name='admin-pending-fees'),
    path('finance/record-payment/', complete_admin_views.record_payment, name='admin-record-payment'),

    # Reports - Teacher Performance
    path('reports/teacher-performance/', complete_admin_views.get_teacher_performance_report, name='admin-teacher-performance'),
    
    # Reports - Downloads (FIXED - using direct imports)
    path('reports/academic/', download_academic_report, name='download-academic-report'),
    path('reports/attendance/', download_attendance_report, name='download-attendance-report'),
    path('reports/financial/', download_financial_report, name='download-financial-report'),

    # Settings
    path('settings/', complete_admin_views.manage_school_settings, name='admin-settings'),

    # ========== TIMETABLE MANAGEMENT ENDPOINTS ==========
    path('timetable/time-slots/', timetable_views.get_time_slots, name='admin-time-slots'),
    path('timetable/class/<int:class_id>/', timetable_views.get_class_timetable, name='admin-class-timetable'),
    path('timetable/create/', timetable_views.create_timetable, name='admin-create-timetable'),
    path('timetable/entry/', timetable_views.create_or_update_timetable_entry, name='admin-timetable-entry'),
    path('timetable/entry/<int:entry_id>/', timetable_views.delete_timetable_entry, name='admin-delete-timetable-entry'),
    path('timetable/class/<int:class_id>/resources/', timetable_views.get_subjects_and_teachers, name='admin-timetable-resources'),
]