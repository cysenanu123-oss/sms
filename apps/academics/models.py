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

# apps/academics/models.py - ADD TO END OF FILE

class SchoolSettings(models.Model):
    """Global school settings - Only ONE record should exist"""
    
    # School Information
    school_name = models.CharField(max_length=200, default="Excellence Academy")
    school_motto = models.CharField(max_length=200, blank=True)
    school_address = models.TextField()
    school_phone = models.CharField(max_length=20)
    school_email = models.EmailField()
    school_website = models.URLField(blank=True)
    
    # Academic Year Settings
    current_academic_year = models.CharField(max_length=20)
    academic_year_start = models.DateField()
    academic_year_end = models.DateField()
    
    # Current Term
    TERM_CHOICES = (
        ('first', 'First Term'),
        ('second', 'Second Term'),
        ('third', 'Third Term'),
    )
    current_term = models.CharField(max_length=20, choices=TERM_CHOICES)
    term_start_date = models.DateField()
    term_end_date = models.DateField()
    
    # Grading System
    GRADING_SYSTEM_CHOICES = (
        ('percentage', 'Percentage (0-100)'),
        ('letter', 'Letter Grade (A-F)'),
        ('gpa', 'GPA (0-4.0)'),
    )
    grading_system = models.CharField(max_length=20, choices=GRADING_SYSTEM_CHOICES, default='percentage')
    
    # Fee Settings
    admission_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    application_fee = models.DecimalField(max_digits=10, decimal_places=2, default=50)
    
    # Entrance Exam Settings
    entrance_exam_required = models.BooleanField(default=True)
    exam_duration_minutes = models.IntegerField(default=120)
    exam_pass_percentage = models.IntegerField(default=50)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "School Settings"
        verbose_name_plural = "School Settings"
    
    def __str__(self):
        return f"{self.school_name} Settings"


class ExamSchedule(models.Model):
    """Entrance exam schedules set by admin"""
    
    academic_year = models.CharField(max_length=20)
    department = models.CharField(max_length=20, choices=(
        ('baby_sitting', 'Baby Sitting'),
        ('pre_school', 'Pre-School'),
        ('primary', 'Primary'),
        ('jhs', 'Junior High School'),
    ))
    
    exam_date = models.DateField()
    exam_time = models.TimeField()
    exam_location = models.CharField(max_length=200)
    
    max_students = models.IntegerField(default=50)
    registered_students = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    special_instructions = models.TextField(blank=True)
    
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['exam_date', 'exam_time']
    
    def __str__(self):
        return f"{self.get_department_display()} Exam - {self.exam_date}"


class TimeSlot(models.Model):
    """Time periods for classes"""
    
    name = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_order = models.IntegerField()
    
    SLOT_TYPE_CHOICES = (
        ('class', 'Class Period'),
        ('break', 'Break'),
        ('lunch', 'Lunch'),
    )
    slot_type = models.CharField(max_length=20, choices=SLOT_TYPE_CHOICES, default='class')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['slot_order']
    
    def __str__(self):
        return f"{self.name} ({self.start_time.strftime('%I:%M %p')}-{self.end_time.strftime('%I:%M %p')})"


class Timetable(models.Model):
    """Class timetables"""
    
    class_obj = models.OneToOneField(Class, on_delete=models.CASCADE, related_name='timetable')
    academic_year = models.CharField(max_length=20)
    term = models.CharField(max_length=20)
    
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Timetable - {self.class_obj.name} ({self.academic_year})"


class TimetableEntry(models.Model):
    """Individual timetable entries"""
    
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='entries')
    
    DAY_CHOICES = (
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
    )
    day_of_week = models.CharField(max_length=20, choices=DAY_CHOICES)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, 
                                limit_choices_to={'role': 'teacher'})
    room_number = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['day_of_week', 'time_slot__slot_order']
        unique_together = ['timetable', 'day_of_week', 'time_slot']
    
    def __str__(self):
        return f"{self.timetable.class_obj.name} - {self.day_of_week} {self.time_slot.name}"