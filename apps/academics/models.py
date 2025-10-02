# apps/academics/models.py
from django.db import models
from apps.accounts.models import User


class Class(models.Model):
    """School classes/grades"""
    name = models.CharField(max_length=50)  # e.g., "Grade 6-A"
    grade_level = models.CharField(max_length=20)  # e.g., "Grade 6"
    section = models.CharField(max_length=10, blank=True)  # e.g., "A"
    capacity = models.IntegerField(default=50)
    
    # Class Teacher
    class_teacher = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        limit_choices_to={'role': 'teacher'},
        related_name='classes_taught'
    )
    
    # Academic year
    academic_year = models.CharField(max_length=20)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Classes"
        ordering = ['grade_level', 'section']
    
    def __str__(self):
        return f"{self.name} ({self.academic_year})"
    
    @property
    def enrolled_count(self):
        """Get number of enrolled students"""
        return self.student_set.filter(status='active').count()


class Subject(models.Model):
    """School subjects"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name


class ClassSubject(models.Model):
    """Subjects assigned to classes with teachers"""
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'role': 'teacher'}
    )
    
    class Meta:
        unique_together = ('class_obj', 'subject')
    
    def __str__(self):
        return f"{self.class_obj.name} - {self.subject.name}"