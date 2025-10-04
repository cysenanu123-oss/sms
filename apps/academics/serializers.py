# apps/academics/serializers.py
from rest_framework import serializers
from apps.accounts.models import User
from apps.academics.models import (
    Class, Subject, ClassSubject, TeacherProfile, 
    TeacherClassAssignment
)
from django.contrib.auth.hashers import make_password
import random
import string


class ClassSerializer(serializers.ModelSerializer):
    """Serializer for Class model"""
    
    enrolled_count = serializers.ReadOnlyField()
    class_teacher_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Class
        fields = [
            'id', 'name', 'grade_level', 'section', 'capacity',
            'enrolled_count', 'class_teacher', 'class_teacher_name',
            'academic_year', 'is_active'
        ]
    
    def get_class_teacher_name(self, obj):
        if obj.class_teacher:
            return obj.class_teacher.get_full_name()
        return None


class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for Subject model"""
    
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'description']


class CreateTeacherSerializer(serializers.Serializer):
    """Serializer for creating a new teacher"""
    
    # User fields
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False)
    
    # Class and subject assignments
    subjects = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False
    )
    classes = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        allow_empty=False
    )
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate_subjects(self, value):
        if value:
            existing = Subject.objects.filter(id__in=value).count()
            if existing != len(value):
                raise serializers.ValidationError("One or more subject IDs are invalid.")
        return value
    
    def validate_classes(self, value):
        if value:
            existing = Class.objects.filter(id__in=value).count()
            if existing != len(value):
                raise serializers.ValidationError("One or more class IDs are invalid.")
        return value
    
    def create(self, validated_data):
        """Create user and class assignments"""
        
        # Extract class and subject assignment data
        subjects = validated_data.pop('subjects', [])
        classes = validated_data.pop('classes', [])
        
        # Generate username and temporary password
        username = self.generate_username(
            validated_data['first_name'],
            validated_data['last_name']
        )
        temp_password = self.generate_temp_password()
        
        # Create User
        user = User.objects.create(
            username=username,
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone=validated_data.get('phone', ''),
            password=make_password(temp_password),
            role='teacher',
            is_teacher=True,
            must_change_password=True,
            is_active=True
        )
        
        # Get current academic year
        from apps.academics.models import SchoolSettings
        try:
            settings = SchoolSettings.objects.first()
            academic_year = settings.current_academic_year if settings else "2024-2025"
        except:
            academic_year = "2024-2025"
        
        # Create class assignments
        for class_id in classes:
            try:
                class_obj = Class.objects.get(id=class_id)
                
                TeacherClassAssignment.objects.create(
                    teacher=user,
                    class_obj=class_obj,
                    academic_year=academic_year,
                    is_class_teacher=False
                )
            except Class.DoesNotExist:
                pass
        
        # Assign subjects to classes
        for class_id in classes:
            for subject_id in subjects:
                try:
                    class_obj = Class.objects.get(id=class_id)
                    subject_obj = Subject.objects.get(id=subject_id)
                    
                    ClassSubject.objects.update_or_create(
                        class_obj=class_obj,
                        subject=subject_obj,
                        defaults={'teacher': user}
                    )
                except (Class.DoesNotExist, Subject.DoesNotExist):
                    pass
        
        return {
            'user': user,
            'username': username,
            'temporary_password': temp_password
        }
    
    def generate_username(self, first_name, last_name):
        """Generate unique username"""
        base = f"{first_name.lower()}.{last_name.lower()}"
        username = base
        counter = 1
        
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        
        return username
    
    def generate_temp_password(self):
        """Generate temporary password"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(12))