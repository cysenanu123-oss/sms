# apps/academics/urls.py (CREATE THIS FILE)
from django.urls import path
from . import views

urlpatterns = [
    # Class endpoints
    path('classes/', views.list_classes, name='list-classes'),
    
    # Teacher management (admin)
    path('teachers/', views.teacher_list_create, name='teacher-list-create'),
    path('teachers/<int:teacher_id>/', views.teacher_detail, name='teacher-detail'),
    path('teachers/assign-classes/', views.assign_teacher_to_class, name='assign-teacher-classes'),
    
    # Teacher portal - get own classes
    path('my-classes/', views.teacher_classes, name='teacher-classes'),
    
    # Available data for dropdowns
    path('subjects/', views.get_all_subjects, name='all-subjects'),
]