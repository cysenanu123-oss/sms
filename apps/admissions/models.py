# apps/admissions/models.py
from django.db import models
from django.utils import timezone
from apps.accounts.models import User
import uuid
import random


class StudentApplication(models.Model):
    """Application form submissions from prospective students"""

    DEPARTMENT_CHOICES = (
        ('baby_sitting', 'Baby Sitting'),
        ('pre_school', 'Pre-School'),
        ('primary', 'Primary'),
        ('jhs', 'Junior High School'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('exam_scheduled', 'Exam Scheduled'),
        ('exam_completed', 'Exam Completed'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    )

    SEX_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
    )

    # Application Info
    application_number = models.CharField(max_length=20, unique=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Learner's Details
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    other_names = models.CharField(max_length=100, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES)
    date_of_birth = models.DateField()
    age = models.IntegerField()
    applying_for_class = models.CharField(max_length=50)
    previous_school = models.CharField(max_length=200, blank=True)
    residential_address = models.TextField()
    nationality = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    languages_spoken = models.CharField(max_length=200)
    religion = models.CharField(max_length=50, blank=True)

    # Health Details
    has_health_challenge = models.BooleanField(default=False)
    health_challenge_details = models.TextField(blank=True)
    has_allergies = models.BooleanField(default=False)
    allergies_details = models.TextField(blank=True)
    medication_details = models.TextField(blank=True)
    insurance_company = models.CharField(max_length=200, blank=True)
    insurance_number = models.CharField(max_length=100, blank=True)
    insurance_card = models.FileField(upload_to='applications/insurance/', blank=True, null=True)

    # Parent Status
    parents_status = models.CharField(max_length=100, blank=True)

    # Parent/Guardian Contact Info
    parent_email = models.EmailField(blank=True)
    parent_phone = models.CharField(max_length=20, blank=True)
    parent_full_name = models.CharField(max_length=200, blank=True)
    parent_relationship = models.CharField(max_length=50, blank=True, choices=(
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('guardian', 'Guardian'),
        ('other', 'Other'),
    ))
    parent_occupation = models.CharField(max_length=200, blank=True)

    # Declaration - FIXED INDENTATION
    declaration_name = models.CharField(max_length=200, blank=True, default='')
    signature = models.FileField(upload_to='applications/signatures/', blank=True, null=True)
    declaration_date = models.DateField(blank=True, null=True)

    # Admin Notes - FIXED INDENTATION
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_applications'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # FIXED: Meta class should be inside StudentApplication
    class Meta:
        ordering = ['-submitted_at']

    # FIXED: save method should be inside StudentApplication
    def save(self, *args, **kwargs):
        if not self.application_number:
            # Generate unique application number: APP-2024-0001
            year = timezone.now().year
            last_app = StudentApplication.objects.filter(
                application_number__startswith=f'APP-{year}-'
            ).order_by('-application_number').first()

            if last_app:
                last_num = int(last_app.application_number.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1

            self.application_number = f'APP-{year}-{new_num:04d}'

        super().save(*args, **kwargs)

    @property
    def learner_name(self):
        return " ".join(filter(None, [self.first_name, self.other_names, self.last_name]))

    def __str__(self):
        return f"{self.application_number} - {self.learner_name}"


class Student(models.Model):
    """Enrolled students in the school"""

    # Link to User account (created after acceptance)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')

    # Unique student ID: STU-2024-0001
    student_id = models.CharField(max_length=20, unique=True, blank=True)

    # Link to original application
    application = models.OneToOneField(StudentApplication, on_delete=models.SET_NULL, null=True, blank=True)

    # Basic Info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    other_names = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    sex = models.CharField(max_length=10, choices=StudentApplication.SEX_CHOICES)
    roll_number = models.CharField(max_length=20, null=True, blank=True)
    blood_group = models.CharField(max_length=5, null=True, blank=True)

    # Current Academic Info
    current_class = models.ForeignKey('academics.Class', on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.CharField(max_length=20)
    roll_number = models.CharField(max_length=10, blank=True)

    # Contact Info
    residential_address = models.TextField()
    nationality = models.CharField(max_length=100)
    region = models.CharField(max_length=100)

    # Health Info
    blood_group = models.CharField(max_length=5, blank=True)
    has_health_challenge = models.BooleanField(default=False)
    health_notes = models.TextField(blank=True)

    # Status
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('graduated', 'Graduated'),
        ('transferred', 'Transferred'),
        ('expelled', 'Expelled'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Dates
    admission_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student_id']

    def save(self, *args, **kwargs):
        if not self.student_id:
            first_initial = self.first_name[0].upper() if self.first_name else ''
            other_initial = self.other_names[0].upper() if self.other_names else ''
            last_initial = self.last_name[0].upper() if self.last_name else ''

            max_attempts = 100
            for attempt in range(max_attempts):
                random_digits = str(random.randint(100, 999))
                year_suffix = str(timezone.now().year)[-2:]

                if other_initial:
                    potential_id = f"{first_initial}{other_initial}{last_initial}{random_digits}{year_suffix}"
                else:
                    potential_id = f"{first_initial}{last_initial}{random_digits}{year_suffix}"

                if not Student.objects.filter(student_id=potential_id).exists():
                    self.student_id = potential_id
                    break

            if not self.student_id:
                year = timezone.now().year
                last_student = Student.objects.filter(
                    student_id__startswith=f'STU-{year}-'
                ).order_by('-student_id').first()

                if last_student:
                    last_num = int(last_student.student_id.split('-')[-1])
                    new_num = last_num + 1
                else:
                    new_num = 1

                self.student_id = f'STU-{year}-{new_num:04d}'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_id} - {self.first_name} {self.last_name}"


class AcademicYear(models.Model):
    """Track academic years and terms"""
    year = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return self.year


class StudentPromotion(models.Model):
    """Track student promotions/repeats"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='promotions')
    from_class = models.ForeignKey('academics.Class', on_delete=models.SET_NULL, null=True, related_name='promoted_from')
    to_class = models.ForeignKey('academics.Class', on_delete=models.SET_NULL, null=True, related_name='promoted_to')
    academic_year = models.CharField(max_length=20)

    PROMOTION_TYPE = (
        ('promoted', 'Promoted'),
        ('repeated', 'Repeated'),
    )
    promotion_type = models.CharField(max_length=20, choices=PROMOTION_TYPE)
    promoted_at = models.DateTimeField(auto_now_add=True)
    promoted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student.student_id} - {self.promotion_type} to {self.to_class}"


class Parent(models.Model):
    """Parent/Guardian accounts linked to students"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')

    full_name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=50, choices=(
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('guardian', 'Guardian'),
        ('other', 'Other'),
    ))

    phone = models.CharField(max_length=20)
    alt_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    residential_address = models.TextField()

    occupation = models.CharField(max_length=200, blank=True)
    employer = models.CharField(max_length=200, blank=True)
    work_phone = models.CharField(max_length=20, blank=True)

    is_emergency_contact = models.BooleanField(default=True)
    children = models.ManyToManyField(Student, related_name='parents')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} - {self.relationship}"