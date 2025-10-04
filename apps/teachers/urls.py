# apps/teachers/urls.py
from django.urls import path
from . import admin_views

urlpatterns = [
    # Admin endpoints
    path('manage/', admin_views.manage_teachers, name='manage-teachers'),
    path('subjects/', admin_views.get_available_subjects, name='available-subjects'),
    path('classes/', admin_views.get_available_classes, name='available-classes'),
]