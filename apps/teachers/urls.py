# apps/teachers/urls.py
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
    path('timetable/', views.get_teacher_timetable, name='teacher-timetable'),
    path('grades/save/', views.save_grades, name='save-grades'),

    path('dashboard/', views.get_teacher_timetable, name='teacher-dashboard'),
    path('today-classes/', views.get_today_classes, name='teacher-today-classes'),

]