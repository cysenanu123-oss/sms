# apps/dashboard/urls.py
from django.urls import path
from . import views, admin_views

urlpatterns = [
    # Access verification
    path('verify-admin/', views.verify_admin_access, name='verify-admin'),
    path('verify-teacher/', views.verify_teacher_access, name='verify-teacher'),
    path('verify-student/', views.verify_student_access, name='verify-student'),
    path('verify-parent/', views.verify_parent_access, name='verify-parent'),
    
    # Admin dashboard data
    path('admin/overview/', admin_views.admin_overview, name='admin-overview'),
]