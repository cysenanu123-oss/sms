# apps/accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Extra fields
    must_change_password = models.BooleanField(default=False)
    
    ROLE_CHOICES = (
    ('admin', 'Admin'),
    ('teacher', 'Teacher'),
    ('student', 'Student'),
    ('parent', 'Parent'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    email_verified = models.BooleanField(default=False)  # Email verification status
    phone = models.CharField(max_length=20, blank=True, null=True) # Contact number

    def __str__(self):
        return self.username


class InitialLoginToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_tokens")
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"Token for {self.user.username} - {'USED' if self.used else 'ACTIVE'}"
