# apps/grades/models.py
from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.admissions.models import Student
from apps.academics.models import Class, Subject


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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date']
    
    def __str__(self):
        return f"{self.title} - {self.class_obj.name}"


class AssignmentSubmission(models.Model):
    """Student assignment submissions"""
    STATUS_CHOICES = (
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
        ('returned', 'Returned'),
    )
    
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assignments')
    
    file = models.FileField(upload_to='assignments/submissions/')
    comments = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='graded_assignments')
    graded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['assignment', 'student']
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.student.student_id} - {self.assignment.title}"