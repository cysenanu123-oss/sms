# apps/teachers/urls.py
from django.urls import path
from . import views, admin_views

urlpatterns = [
    # Admin endpoints
    path('manage/', admin_views.manage_teachers, name='manage-teachers'),
    path('manage/<int:teacher_id>/', admin_views.manage_teacher_detail, name='teacher-detail'),
    path('subjects/', admin_views.get_available_subjects, name='available-subjects'),
    path('classes/', admin_views.get_available_classes, name='available-classes'),
    
    # Teacher endpoints
    path('my-classes/', admin_views.get_teacher_classes, name='teacher-classes'),
]