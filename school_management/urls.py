
# school_management/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Public pages
    path('', TemplateView.as_view(template_name='landing_page.html'), name='home'),
    path('apply/', TemplateView.as_view(template_name='application_form.html'), name='apply'),
    path('auth/', TemplateView.as_view(template_name='auth.html'), name='auth'),

    # Dashboards
    path('dashboard/admin/', TemplateView.as_view(template_name='admin_dashboard.html'),
         name='admin-dashboard'),
    path('dashboard/parent/', TemplateView.as_view(template_name='parent_dashboard.html'),
         name='parent-dashboard'),
    path('dashboard/teacher/', TemplateView.as_view(
        template_name='teacher_dashboard.html'), name='teacher-dashboard'),
    path('dashboard/student/', TemplateView.as_view(
        template_name='student_dashboard.html'), name='student-dashboard'),

    # API endpoints
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/admissions/', include('apps.admissions.urls')),
    path('api/v1/admin/admissions/', include('apps.admissions.admin_urls')),
    path('api/v1/dashboard/', include('apps.dashboard.urls')),

    # ADD THESE NEW LINES:
    # New admin endpoints
    path('api/v1/admin/', include('apps.dashboard.admin_urls')),

    path('api/v1/students/', include('apps.students.urls')),
    path('api/v1/parents/', include('apps.parents.urls')),
    path('api/v1/teachers/', include('apps.teachers.urls')),
    path('api/v1/academics/', include('apps.academics.urls')),
    path('reset-password/', TemplateView.as_view(template_name='reset_password.html'), name='reset-password'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Excellence Academy Management"
admin.site.site_title = "School Admin"
admin.site.index_title = "Welcome to School Management System"
