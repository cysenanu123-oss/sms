# apps/grades/models.py
from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.admissions.models import Student
from apps.academics.models import Class, Subject


class Grade(models.Model):
    """Individual student grades for exams/tests"""
    EXAM_TYPE_CHOICES = (
        ('quiz', 'Quiz'),
        ('test', 'Class Test'),
        ('midterm', 'Mid-term Exam'),
        ('final', 'Final Exam'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPE_CHOICES)
    exam_name = models.CharField(max_length=200)
    exam_date = models.DateField()
    
    score = models.DecimalField(max_digits=5, decimal_places=2)
    total_marks = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=3)  # A+, A, B+, etc.
    
    academic_year = models.CharField(max_length=20)  # Changed to CharField to support "2024-2025" format
    remarks = models.TextField(blank=True, null=True)  # Added remarks field
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'grades'
        ordering = ['-exam_date', '-created_at']
        unique_together = ['student', 'subject', 'exam_type', 'exam_name', 'exam_date']
    
    def __str__(self):
        return f"{self.student.first_name} - {self.subject.name} - {self.grade}"
    
    @property
    def percentage(self):
        """Calculate percentage"""
        if self.total_marks > 0:
            return round((float(self.score) / float(self.total_marks)) * 100, 2)
        return 0


class Exam(models.Model):
    """Exam/Test definition"""
    EXAM_TYPE_CHOICES = (
        ('quiz', 'Quiz'),
        ('test', 'Class Test'),
        ('midterm', 'Mid-term Exam'),
        ('final', 'Final Exam'),
        ('assignment', 'Assignment'),
    )
    
    name = models.CharField(max_length=200)
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPE_CHOICES)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='exams')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='exams')
    date = models.DateField()
    total_marks = models.IntegerField(default=100)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_exams')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.name} - {self.class_obj.name} - {self.subject.name}"


class ExamResult(models.Model):
    """Individual student exam results"""
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='results')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_results')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    remarks = models.TextField(blank=True)
    
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='entered_results')
    entered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['exam', 'student']
        ordering = ['-exam__date']
    
    def __str__(self):
        return f"{self.student.student_id} - {self.exam.name} - {self.score}"
    
    @property
    def percentage(self):
        if self.exam.total_marks > 0:
            return (self.score / self.exam.total_marks) * 100
        return 0
    
    @property
    def grade(self):
        percentage = self.percentage
        if percentage >= 90:
            return 'A+'
        elif percentage >= 80:
            return 'A'
        elif percentage >= 70:
            return 'B+'
        elif percentage >= 60:
            return 'B'
        elif percentage >= 50:
            return 'C+'
        elif percentage >= 40:
            return 'C'
        elif percentage >= 33:
            return 'D'
        else:
            return 'F'


class Assignment(models.Model):
    """Assignment definition"""
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('draft', 'Draft'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments', null=True, blank=True)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='given_assignments')
    
    assigned_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    total_marks = models.IntegerField(default=100)
    
    instructions = models.TextField(blank=True)
    attachment = models.FileField(upload_to='assignments/attachments/', null=True, blank=True)
    
    # ✅ ADDED: Status field with default='active'
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['class_obj', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.class_obj.name}"
    
    @property
    def is_active(self):
        """Check if assignment is still active and not past due"""
        return self.status == 'active' and self.due_date >= timezone.now().date()
    
    @property
    def is_past_due(self):
        """Check if assignment is past due date"""
        return self.due_date < timezone.now().date()
    
    @property
    def days_until_due(self):
        """Calculate days until due date"""
        if self.is_past_due:
            return 0
        delta = self.due_date - timezone.now().date()
        return delta.days
    
    @property
    def submission_count(self):
        """Get total number of submissions"""
        return self.submissions.count()
    
    def auto_close_if_overdue(self):
        """Automatically close assignment if past due date"""
        if self.is_past_due and self.status == 'active':
            self.status = 'closed'
            self.save(update_fields=['status', 'updated_at'])
            return True
        return False


class AssignmentSubmission(models.Model):
    """Student assignment submissions"""
    STATUS_CHOICES = (
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
        ('returned', 'Returned'),
        ('late', 'Late Submission'),
    )
    
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assignment_submissions')
    
    file = models.FileField(upload_to='assignments/submissions/')
    comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='graded_submissions')
    graded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['assignment', 'student']
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['assignment', 'status']),
            models.Index(fields=['student', 'submitted_at']),
        ]
    
    def __str__(self):
        return f"{self.student.student_id} - {self.assignment.title}"
    
    @property
    def is_late(self):
        """Check if submission was made after due date"""
        if self.submitted_at and self.assignment.due_date:
            return self.submitted_at.date() > self.assignment.due_date
        return False
    
    @property
    def percentage(self):
        """Calculate percentage score"""
        if self.score and self.assignment.total_marks > 0:
            return round((float(self.score) / self.assignment.total_marks) * 100, 2)
        return None
    
    @property
    def grade_letter(self):
        """Calculate letter grade based on percentage"""
        if not self.score:
            return None
        
        percentage = self.percentage
        if percentage >= 90:
            return 'A+'
        elif percentage >= 80:
            return 'A'
        elif percentage >= 70:
            return 'B+'
        elif percentage >= 60:
            return 'B'
        elif percentage >= 50:
            return 'C+'
        elif percentage >= 40:
            return 'C'
        elif percentage >= 33:
            return 'D'
        else:
            return 'F'
    
    def save(self, *args, **kwargs):
        """Override save to auto-mark late submissions"""
        if not self.pk and self.is_late:  # New submission that's late
            self.status = 'late'
        super().save(*args, **kwargs)