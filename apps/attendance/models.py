# apps/attendance/models.py
from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.admissions.models import Student
from apps.academics.models import Class, Subject


class Attendance(models.Model):
    """Daily attendance record for a class"""
    TERM_CHOICES = (
        ('first', 'First Term'),
        ('second', 'Second Term'),
        ('third', 'Third Term'),
    )

    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    period = models.IntegerField(default=1)  # Period number (1-6)
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)
    marked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='marked_attendances')
    marked_at = models.DateTimeField(auto_now_add=True)

    # Term tracking
    academic_year = models.CharField(max_length=20, default='2024/2025')  # e.g., "2024/2025"
    term = models.CharField(max_length=20, choices=TERM_CHOICES, default='first')

    class Meta:
        unique_together = ['class_obj', 'date', 'period']
        ordering = ['-date', 'period']

    def __str__(self):
        return f"{self.class_obj.name} - {self.date} Period {self.period} ({self.get_term_display()} {self.academic_year})"


class AttendanceRecord(models.Model):
    """Individual student attendance record"""
    ATTENDANCE_STATUS = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    )
    
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS)
    remarks = models.CharField(max_length=200, blank=True)
    
    class Meta:
        unique_together = ['attendance', 'student']
    
    def __str__(self):
        return f"{self.student.student_id} - {self.status} - {self.attendance.date}"