# apps/admissions/admin.py
from django.contrib import admin
from .models import StudentApplication, Student, AcademicYear, StudentPromotion, Parent

@admin.register(StudentApplication)
class StudentApplicationAdmin(admin.ModelAdmin):
    list_display = ['application_number', 'first_name', 'last_name', 'department', 'status', 'submitted_at']
    list_filter = ['status', 'department', 'submitted_at']
    search_fields = ['application_number', 'first_name', 'last_name', 'residential_address']
    readonly_fields = ['application_number', 'submitted_at']
    
    fieldsets = (
        ('Application Info', {
            'fields': ('application_number', 'status', 'submitted_at', 'department')
        }),
        ('Student Details', {
            'fields': ('first_name', 'last_name', 'other_names', 'sex', 'date_of_birth', 'age', 
                      'applying_for_class', 'previous_school')
        }),
        ('Contact & Location', {
            'fields': ('residential_address', 'nationality', 'region', 'languages_spoken', 'religion')
        }),
        ('Parent/Guardian Info', {
            'fields': ('parent_full_name', 'parent_email', 'parent_phone', 'parents_status')
        }),
        ('Health Information', {
            'fields': ('has_health_challenge', 'health_challenge_details', 'has_allergies', 
                      'allergies_details', 'medication_details', 'insurance_company', 
                      'insurance_number', 'insurance_card')
        }),
        ('Declaration', {
            'fields': ('declaration_name', 'signature', 'declaration_date')
        }),
        ('Admin Review', {
            'fields': ('admin_notes', 'reviewed_by', 'reviewed_at')
        }),
    )

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'first_name', 'last_name', 'current_class', 'status']
    list_filter = ['status', 'current_class', 'academic_year']
    search_fields = ['student_id', 'first_name', 'last_name']
    readonly_fields = ['student_id', 'created_at', 'updated_at']

@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'relationship', 'phone', 'email', 'is_active']
    list_filter = ['relationship', 'is_active']
    search_fields = ['full_name', 'email', 'phone']

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['year', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current']

@admin.register(StudentPromotion)
class StudentPromotionAdmin(admin.ModelAdmin):
    list_display = ['student', 'from_class', 'to_class', 'promotion_type', 'promoted_at']
    list_filter = ['promotion_type', 'academic_year']