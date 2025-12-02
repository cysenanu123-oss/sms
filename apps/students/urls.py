# apps/students/urls.py - NEW FILE
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.student_dashboard, name='student-dashboard'),
    path('courses/<int:course_id>/', views.get_course_details, name='course-details'),
    path('test-results/', views.get_test_results, name='test-results'),
    path('assignments/submit/', views.submit_assignment, name='submit-assignment'),

    # Term history endpoints
    path('terms/history/', views.get_student_term_history, name='student-term-history'),
    path('terms/data/', views.get_student_term_data, name='student-term-data'),
]
