# apps/dashboard/urls.py 
from django.urls import path
from . import views, admin_views, complete_admin_views, timetable_views

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
    
    # Finance management endpoints
    path('admin/finance/overview/', complete_admin_views.get_finance_overview, name='admin-finance-overview'),
    path('admin/finance/pending-fees/', complete_admin_views.get_pending_fee_students, name='admin-pending-fees'),
    path('admin/finance/record-payment/', complete_admin_views.record_payment, name='admin-record-payment'),
    
    # Reports endpoints
    path('admin/reports/teacher-performance/', complete_admin_views.get_teacher_performance_report, name='admin-teacher-performance'),
    
    # Settings endpoints
    path('admin/settings/', complete_admin_views.manage_school_settings, name='admin-settings'),

    # ========== TIMETABLE MANAGEMENT ENDPOINTS ==========
    # Get time slots
    path('admin/timetable/time-slots/', timetable_views.get_time_slots, name='admin-time-slots'),
    
    # Get class timetable - THIS IS THE MISSING ENDPOINT
    path('admin/timetable/class/<int:class_id>/', timetable_views.get_class_timetable, name='admin-class-timetable'),
    
    # Create timetable
    path('admin/timetable/create/', timetable_views.create_timetable, name='admin-create-timetable'),
    
    # Create/Update timetable entry
    path('admin/timetable/entry/', timetable_views.create_or_update_timetable_entry, name='admin-timetable-entry'),
    
    # Delete timetable entry
    path('admin/timetable/entry/<int:entry_id>/', timetable_views.delete_timetable_entry, name='admin-delete-timetable-entry'),
    
    # Get subjects and teachers for a class
    path('admin/timetable/class/<int:class_id>/resources/', timetable_views.get_subjects_and_teachers, name='admin-timetable-resources'),

    
    # Timetable endpoints
    path('api/v1/admin/timetable/slots/', timetable_views.get_time_slots, name='get_time_slots'),
    path('api/v1/admin/timetable/slots/create/', timetable_views.create_time_slot, name='create_time_slot'),
    path('api/v1/admin/timetable/class/<int:class_id>/', timetable_views.get_class_timetable, name='get_class_timetable'),
    path('api/v1/admin/timetable/create/', timetable_views.create_timetable, name='create_timetable'),
    path('api/v1/admin/timetable/entry/', timetable_views.create_or_update_timetable_entry, name='create_or_update_timetable_entry'),
    
    # FIXED DELETE ENDPOINT - Remove '/delete/' from the URL
    path('api/v1/admin/timetable/entry/<int:entry_id>/', timetable_views.delete_timetable_entry, name='delete_timetable_entry'),
    path('admin/timetable/entry/<int:entry_id>/', timetable_views.delete_timetable_entry, name='delete_timetable_entry'),
    path('api/v1/admin/timetable/class/<int:class_id>/resources/', timetable_views.get_subjects_and_teachers, name='get_subjects_and_teachers'),

   # Notification endpoints 
    path('notifications/', views.get_notifications, name='get-notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark-notification-read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark-all-read'),

]
