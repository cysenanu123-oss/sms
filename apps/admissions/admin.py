from django.contrib import admin
from .models import StudentApplication, Student, AcademicYear, StudentPromotion

@admin.register(StudentApplication)
class StudentApplicationAdmin(admin.ModelAdmin):
    list_display = ['application_number', 'learner_name', 'department', 'status', 'submitted_at']
    list_filter = ['status', 'department', 'submitted_at']
    search_fields = ['application_number', 'learner_name', 'residential_address']
    readonly_fields = ['application_number', 'submitted_at']

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'first_name', 'last_name', 'current_class', 'status']
    list_filter = ['status', 'current_class', 'academic_year']
    search_fields = ['student_id', 'first_name', 'last_name']
    readonly_fields = ['student_id', 'created_at', 'updated_at']

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['year', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current']

@admin.register(StudentPromotion)
class StudentPromotionAdmin(admin.ModelAdmin):
    list_display = ['student', 'from_class', 'to_class', 'promotion_type', 'promoted_at']
    list_filter = ['promotion_type', 'academic_year']