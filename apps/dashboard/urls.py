# apps/dashboard/urls.py - UPDATED
from django.urls import path
from . import views, admin_views
from apps.dashboard import complete_admin_views

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
    path('admin/classes/', complete_admin_views.create_class, name='admin-create-class'),
    
    # Finance management endpoints
    path('admin/finance/overview/', complete_admin_views.get_finance_overview, name='admin-finance-overview'),
    path('admin/finance/pending-fees/', complete_admin_views.get_pending_fee_students, name='admin-pending-fees'),
    path('admin/finance/record-payment/', complete_admin_views.record_payment, name='admin-record-payment'),
    
    # Reports endpoints
    path('admin/reports/teacher-performance/', complete_admin_views.get_teacher_performance_report, name='admin-teacher-performance'),
    
    # Settings endpoints
    path('admin/settings/', complete_admin_views.manage_school_settings, name='admin-settings'),
]