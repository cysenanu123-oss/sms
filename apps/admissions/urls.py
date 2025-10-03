# apps/admissions/urls.py
from django.urls import path
from . import views
from . import admin_views

urlpatterns = [
    # Public endpoint (no authentication required)
    path('submit/', views.submit_application, name='submit-application'),
    
    # Admin endpoints (authentication required)
    path('applications/', admin_views.get_applications, name='get-applications'),
    path('applications/<str:application_number>/', admin_views.get_application_detail, name='application-detail'),
    path('applications/<str:application_number>/status/', admin_views.update_application_status, name='update-status'),
    path('applications/<str:application_number>/enroll/', admin_views.accept_and_enroll, name='enroll-student'),
]