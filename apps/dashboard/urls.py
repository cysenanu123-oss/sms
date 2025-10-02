from django.urls import path
from . import views

urlpatterns = [
    path('verify-admin/', views.verify_admin_access, name='verify-admin'),
    path('verify-teacher/', views.verify_teacher_access, name='verify-teacher'),
    path('verify-student/', views.verify_student_access, name='verify-student'),
    path('verify-parent/', views.verify_parent_access, name='verify-parent'),
]