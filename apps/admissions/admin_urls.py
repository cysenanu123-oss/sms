# apps/admissions/admin_urls.py (NEW FILE)
from django.urls import path
from . import admin_views

urlpatterns = [
    path('applications/', admin_views.get_applications, name='admin-get-applications'),
    path('applications/<str:application_number>/', admin_views.get_application_detail, name='admin-application-detail'),
    path('applications/<str:application_number>/status/', admin_views.update_application_status, name='admin-update-status'),
    path('applications/<str:application_number>/enroll/', admin_views.accept_and_enroll, name='admin-enroll-student'),
    path('applications/<str:application_number>/schedule-exam/', admin_views.schedule_exam, name='admin-schedule-exam'),
]