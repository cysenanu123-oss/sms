# apps/finance/admin.py
from django.contrib import admin
from .models import FeeStructure, StudentFee, Payment, FeeReminder


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ['class_level', 'academic_year', 'term', 'total_fee', 'due_date', 'is_active']
    list_filter = ['academic_year', 'term', 'is_active', 'class_level']
    search_fields = ['class_level__name', 'academic_year']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('class_level', 'academic_year', 'term', 'due_date')
        }),
        ('Fee Components', {
            'fields': (
                'tuition_fee', 'admission_fee', 'examination_fee',
                'library_fee', 'sports_fee', 'laboratory_fee',
                'uniform_fee', 'transport_fee', 'miscellaneous_fee'
            )
        }),
        ('Late Fee', {
            'fields': ('late_fee_amount', 'late_fee_applicable_after')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']


@admin.register(StudentFee)
class StudentFeeAdmin(admin.ModelAdmin):
    list_display = ['student', 'fee_structure', 'total_amount', 'amount_paid', 'balance', 'status', 'due_date']
    list_filter = ['status', 'fee_structure__academic_year', 'fee_structure__term']
    search_fields = ['student__student_id', 'student__first_name', 'student__last_name']
    readonly_fields = ['balance', 'created_at', 'updated_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'student_fee', 'amount', 'payment_method', 'status', 'payment_date']
    list_filter = ['status', 'payment_method', 'payment_date']
    search_fields = ['receipt_number', 'transaction_id', 'student_fee__student__student_id']
    readonly_fields = ['receipt_number', 'created_at']


@admin.register(FeeReminder)
class FeeReminderAdmin(admin.ModelAdmin):
    list_display = ['student_fee', 'reminder_type', 'sent_via', 'is_sent', 'sent_at']
    list_filter = ['reminder_type', 'sent_via', 'is_sent']