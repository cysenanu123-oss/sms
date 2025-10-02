# apps/accounts/serializers.py
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import User, InitialLoginToken

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom token serializer with additional user info"""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add custom claims
        data['user'] = {
            'id': str(self.user.id),
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': self.user.role,
            'must_change_password': self.user.must_change_password,
            'email_verified': self.user.email_verified
        }
        
        # Update last login
        self.user.last_login = timezone.now()
        self.user.save(update_fields=['last_login'])
        
        return data

class LoginSerializer(serializers.Serializer):
    """Login serializer with email or username support"""
    
    email_or_username = serializers.CharField()
    password = serializers.CharField(style={'input_type': 'password'})
    
    def validate(self, attrs):
        email_or_username = attrs.get('email_or_username')
        password = attrs.get('password')
        
        if email_or_username and password:
            # Try to find user by email or username
            user = None
            if '@' in email_or_username:
                try:
                    user = User.objects.get(email=email_or_username)
                except User.DoesNotExist:
                    pass
            else:
                try:
                    user = User.objects.get(username=email_or_username)
                except User.DoesNotExist:
                    pass
            
            if user:
                # Authenticate user
                user = authenticate(username=user.username, password=password)
                
                if user:
                    if not user.is_active:
                        raise serializers.ValidationError('User account is disabled.')
                    
                    attrs['user'] = user
                else:
                    raise serializers.ValidationError('Invalid password.')
            else:
                raise serializers.ValidationError('User not found.')
        else:
            raise serializers.ValidationError('Must include email/username and password.')
        
        return attrs

class InitialLoginSerializer(serializers.Serializer):
    """Serializer for first-time login with token"""
    
    token = serializers.CharField()
    new_password = serializers.CharField(style={'input_type': 'password'})
    confirm_password = serializers.CharField(style={'input_type': 'password'})
    
    def validate(self, attrs):
        token = attrs.get('token')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        # Validate token
        try:
            login_token = InitialLoginToken.objects.get(token=token, is_used=False)
            if login_token.is_expired():
                raise serializers.ValidationError('Token has expired.')
            attrs['login_token'] = login_token
        except InitialLoginToken.DoesNotExist:
            raise serializers.ValidationError('Invalid or expired token.')
        
        # Validate password match
        if new_password != confirm_password:
            raise serializers.ValidationError('Passwords do not match.')
        
        # Validate password strength
        try:
            validate_password(new_password, user=login_token.user)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})
        
        return attrs

class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    
    current_password = serializers.CharField(style={'input_type': 'password'})
    new_password = serializers.CharField(style={'input_type': 'password'})
    confirm_password = serializers.CharField(style={'input_type': 'password'})
    
    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value
    
    def validate(self, attrs):
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError('New passwords do not match.')
        
        # Validate password strength
        user = self.context['request'].user
        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})
        
        return attrs

class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting password reset"""
    
    email = serializers.EmailField()
    
    def validate_email(self, value):
        try:
            user = User.objects.get(email=value, is_active=True)
            self.user = user
        except User.DoesNotExist:
            # Don't reveal if email exists for security
            pass
        return value

class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset"""
    
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(style={'input_type': 'password'})
    confirm_password = serializers.CharField(style={'input_type': 'password'})
    
    def validate(self, attrs):
        uid = attrs.get('uid')
        token = attrs.get('token')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        # Decode user ID
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError('Invalid reset link.')
        
        # Validate token
        if not default_token_generator.check_token(user, token):
            raise serializers.ValidationError('Invalid or expired reset link.')
        
        # Validate password match
        if new_password != confirm_password:
            raise serializers.ValidationError('Passwords do not match.')
        
        # Validate password strength
        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})
        
        attrs['user'] = user
        return attrs

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information"""
    
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'full_name', 'role', 'phone', 'is_active', 'email_verified',
            'date_joined', 'last_login'
        ]
        read_only_fields = [
            'id', 'username', 'role', 'is_active', 'email_verified',
            'date_joined', 'last_login'
        ]

