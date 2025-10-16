# apps/teachers/urls.py - COMPLETE UPDATED VERSION

from django.urls import path
from apps.teachers import admin_views
from apps.teachers import views

urlpatterns = [
    # Admin endpoints (from admin_views.py)
    path('manage/', admin_views.manage_teachers, name='manage-teachers'),
    path('subjects/', admin_views.get_available_subjects, name='available-subjects'),
    path('classes/', admin_views.get_available_classes, name='available-classes'),
    path('manage/<int:teacher_id>/', admin_views.delete_teacher, name='delete-teacher'),
    
    # Teacher dashboard endpoints (from views.py)
    path('dashboard/', views.get_teacher_dashboard_data, name='teacher-dashboard'),
    path('class/<int:class_id>/students/', views.get_class_students, name='class-students'),
    path('attendance/save/', views.save_attendance, name='save-attendance'),
    path('assignments/', views.get_teacher_assignments, name='teacher-assignments'),
    path('assignment/create/', views.create_assignment, name='create-assignment'),
    path('assignment/<int:assignment_id>/delete/', views.delete_assignment, name='delete-assignment'),
    path('assignment/<int:assignment_id>/status/', views.update_assignment_status, name='update-assignment-status'),
    path('assignment/<int:assignment_id>/submissions/', views.get_assignment_submissions, name='assignment-submissions'),
    
    # ✅ Resource endpoints - NOW INCLUDING DELETE
    path('resources/', views.get_teacher_resources, name='teacher-resources'),
    path('resource/upload/', views.upload_resource, name='upload-resource'),
    path('resource/<int:resource_id>/delete/', views.delete_resource, name='delete-resource'),  # ✅ NEW
    
    path('timetable/', views.get_teacher_timetable, name='teacher-timetable'),
    path('today-classes/', views.get_today_classes, name='teacher-today-classes'),
    path('grades/save/', views.save_grades, name='save-grades'),
    path('subjects/', views.get_teacher_subjects, name='teacher-subjects'),
    
    # Student promotion endpoints
    path('promote-students/', views.promote_students, name='promote-students'),
    path('class/<int:class_id>/promotion-eligible/', views.get_promotion_eligible_students, name='promotion-eligible-students'),
    
    # Reports endpoints
    path('reports/attendance/', views.download_attendance_report, name='download-attendance-report'),
    path('reports/performance/', views.download_performance_report, name='download-performance-report'),
]