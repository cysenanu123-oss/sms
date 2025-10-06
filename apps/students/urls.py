# apps/students/urls.py - NEW FILE
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.student_dashboard, name='student-dashboard'),
    path('courses/<int:course_id>/', views.get_course_details, name='course-details'),
    path('test-results/', views.get_test_results, name='test-results'),
]




