# apps/parents/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.parent_dashboard_data, name='parent-dashboard'),
    path('children/<int:student_id>/', views.get_child_details, name='child-details'),
    path('children/<int:student_id>/results/', views.get_all_child_results, name='child-all-results'),
]