from django.contrib import admin
from .models import Class, Subject, ClassSubject

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['name', 'grade_level', 'class_teacher', 'capacity', 'enrolled_count', 'academic_year']
    list_filter = ['grade_level', 'academic_year', 'is_active']
    search_fields = ['name', 'grade_level']

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']

@admin.register(ClassSubject)
class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ['class_obj', 'subject', 'teacher']
    list_filter = ['class_obj', 'subject']