# apps/students/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.student_dashboard_data, name='student-dashboard'),
    path('courses/<int:course_id>/', views.get_course_details, name='course-details'),
]