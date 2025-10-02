# apps/admissions/public_urls.py (for public application submission)
from django.urls import path
from . import views

urlpatterns = [
    path('submit/', views.submit_application, name='submit-application'),
]


# apps/admissions/urls.py (for admin management - protected)
from django.urls import path
from . import admin_views

urlpatterns = [
    path('applications/', admin_views.get_applications, name='get-applications'),
    path('applications/<str:application_number>/', admin_views.get_application_detail, name='application-detail'),
    path('applications/<str:application_number>/status/', admin_views.update_application_status, name='update-status'),
    path('applications/<str:application_number>/enroll/', admin_views.accept_and_enroll, name='enroll-student'),
]