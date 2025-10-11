# ============================================
# FILE 1: apps/finance/models.py (FIXED VERSION)
# ============================================

from django.db import models
from django.utils import timezone
from django.db.models import Sum
from apps.academics.models import Class
from apps.admissions.models import Student
from apps.accounts.models import User


class FeeStructure(models.Model):
    """Fee structure for each class/grade level"""
    class_level = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='fee_structures')
    academic_year = models.CharField(max_length=20)
    
    TERM_CHOICES = (
        ('first', 'First Term'),
        ('second', 'Second Term'),
        ('third', 'Third Term'),
        ('annual', 'Annual'),
    )
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    
    # Fee Components
    tuition_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    admission_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    examination_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    library_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sports_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    laboratory_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    uniform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    transport_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    miscellaneous_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    due_date = models.DateField()
    late_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    late_fee_applicable_after = models.DateField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-academic_year', 'class_level', 'term']
        unique_together = ['class_level', 'academic_year', 'term']
    
    def __str__(self):
        return f"{self.class_level.name} - {self.academic_year} - {self.get_term_display()}"
    
    @property
    def total_fee(self):
        return (
            self.tuition_fee + self.admission_fee + self.examination_fee +
            self.library_fee + self.sports_fee + self.laboratory_fee +
            self.uniform_fee + self.transport_fee + self.miscellaneous_fee
        )


class StudentFee(models.Model):
    """Individual student fee records"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fees')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE)
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_reason = models.CharField(max_length=200, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('overdue', 'Overdue'),
        ('waived', 'Waived'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.student.student_id} - {self.fee_structure}"
    
    @property
    def balance(self):
        """Calculate remaining balance"""
        return self.total_amount - self.discount_amount - self.amount_paid
    
    @property
    def is_overdue(self):
        """Check if payment is overdue"""
        return self.due_date < timezone.now().date() and self.status != 'paid'
    
    def recalculate_from_payments(self):
        """
        🔥 CRITICAL FIX: Always calculate from actual payments
        This prevents the multiplication bug!
        """
        actual_paid = Payment.objects.filter(
            student_fee=self,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Only update if different
        if self.amount_paid != actual_paid:
            print(f"🔧 Auto-fixing {self.student.student_id}: "
                  f"GHS {self.amount_paid} → GHS {actual_paid}")
            self.amount_paid = actual_paid
        
        return actual_paid
    
    def update_status(self):
        """Update payment status based on balance"""
        balance = self.balance
        
        if balance <= 0:
            self.status = 'paid'
            if not self.paid_date:
                self.paid_date = timezone.now().date()
        elif self.amount_paid > 0:
            self.status = 'partial'
        elif self.is_overdue:
            self.status = 'overdue'
        else:
            self.status = 'pending'
    
    def save(self, *args, **kwargs):
        """
        Override save to ALWAYS verify payments before saving
        This ensures consistency!
        """
        # Recalculate from actual payments
        self.recalculate_from_payments()
        
        # Update status
        self.update_status()
        
        # Now save
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Record of fee payments - BULLETPROOF VERSION"""
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('card', 'Card'),
        ('online', 'Online Payment'),
    )
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    
    transaction_id = models.CharField(max_length=100, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    notes = models.TextField(blank=True)
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    payment_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.receipt_number} - GHS {self.amount}"
    
    def save(self, *args, **kwargs):
        """
        🔥 FIXED VERSION: No more multiplication!
        """
        # Generate receipt number if needed
        if not self.receipt_number:
            last_payment = Payment.objects.filter(
                receipt_number__startswith='RCP-'
            ).order_by('-receipt_number').first()
            
            if last_payment:
                last_num = int(last_payment.receipt_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.receipt_number = f'RCP-{timezone.now().year}-{new_num:05d}'
        
        # Save payment FIRST
        super().save(*args, **kwargs)
        
        # Then update student fee (it will recalculate from ALL payments)
        if self.status == 'completed':
            print(f"\n💰 Payment {self.receipt_number}: GHS {self.amount}")
            
            # Just save the student_fee - it will auto-recalculate!
            self.student_fee.save()
            
            print(f"✅ New balance: GHS {self.student_fee.balance}\n")


class FeeReminder(models.Model):
    """Automated fee reminders"""
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='reminders')
    
    reminder_type = models.CharField(max_length=20, choices=(
        ('due_soon', 'Due Soon'),
        ('overdue', 'Overdue'),
        ('final_notice', 'Final Notice'),
    ))
    
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_via = models.CharField(max_length=20, choices=(
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('both', 'Email & SMS'),
    ))
    
    is_sent = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.student_fee.student.student_id} - {self.reminder_type}"


