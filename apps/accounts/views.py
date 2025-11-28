# apps/accounts/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny  # Add AllowAny here
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction
from .models import User

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    email_or_username = request.data.get('email_or_username')
    password = request.data.get('password')

    if not email_or_username or not password:
        return Response({
            'success': False,
            'errors': {'general': ['Email/username and password are required']}
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Find user by email or username
        if '@' in email_or_username:
            user = User.objects.get(email=email_or_username)
        else:
            user = User.objects.get(username=email_or_username)

        # Check password
        if not user.check_password(password):
            raise User.DoesNotExist

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'success': True,
            'data': {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': user.role,
                    'must_change_password': user.must_change_password
                },
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token)
                }
            }
        }, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response({
            'success': False,
            'errors': {'general': ['Invalid username or password']}
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({
            'success': True,
            'message': 'Logged out successfully'
        }, status=status.HTTP_200_OK)
    except Exception:
        return Response({
            'success': False,
            'errors': {'general': ['Invalid token']}
        }, status=status.HTTP_400_BAD_REQUEST)





# apps/accounts/views.py - ADD THESE UPDATED FUNCTIONS

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

@api_view(['POST'])
def password_reset_request(request):
    """
    Request password reset - ACCEPTS EMAIL OR USERNAME
    """
    identifier = request.data.get('identifier')  # Can be email or username
    
    if not identifier:
        return Response({
            'success': False,
            'error': 'Email or username is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Try to find user by email or username
        user = None
        
        # Check if it's an email
        if '@' in identifier:
            try:
                user = User.objects.get(email=identifier, is_active=True)
            except User.DoesNotExist:
                pass
        
        # If not found, try username
        if not user:
            try:
                user = User.objects.get(username=identifier, is_active=True)
            except User.DoesNotExist:
                pass
        
        if not user:
            # Don't reveal if user exists or not (security)
            return Response({
                'success': True,
                'message': 'If an account exists with that email/username, a password reset link has been sent.'
            })
        
        # Generate reset token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Create reset URL
        reset_url = f"{settings.FRONTEND_URL or 'http://127.0.0.1:8000'}/reset-password/?uid={uid}&token={token}"
        
        # Send email
        subject = 'Password Reset Request - Unique Success Academy'
        html_message = render_to_string('emails/password_reset.html', {
            'user_name': user.get_full_name() or user.username,
            'reset_url': reset_url,
            'expiry_hours': 24,
        })
        
        try:
            send_mail(
                subject=subject,
                message=f"Click this link to reset your password: {reset_url}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            print(f"✅ Password reset email sent to {user.email}")
            print(f"🔗 Reset URL: {reset_url}")
            
        except Exception as e:
            print(f"❌ Email sending failed: {str(e)}")
            # Continue anyway for development
        
        return Response({
            'success': True,
            'message': 'Password reset link sent to your email address',
            'dev_info': {
                'reset_url': reset_url  # Remove in production
            } if settings.DEBUG else None
        })
        
    except Exception as e:
        print(f"❌ Error in password reset request: {str(e)}")
        return Response({
            'success': False,
            'error': 'An error occurred. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def password_reset_confirm(request):
    """
    Confirm password reset with token
    """
    uid = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')
    
    if not all([uid, token, new_password, confirm_password]):
        return Response({
            'success': False,
            'error': 'All fields are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if new_password != confirm_password:
        return Response({
            'success': False,
            'error': 'Passwords do not match'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if len(new_password) < 8:
        return Response({
            'success': False,
            'error': 'Password must be at least 8 characters'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Decode user ID
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
        
        # Verify token
        if not default_token_generator.check_token(user, token):
            return Response({
                'success': False,
                'error': 'Invalid or expired reset link'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(new_password)
        user.must_change_password = False  # They just changed it
        user.save()
        
        print(f"✅ Password reset successful for user: {user.username}")
        
        return Response({
            'success': True,
            'message': 'Password reset successful! You can now login with your new password.'
        })
        
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response({
            'success': False,
            'error': 'Invalid reset link'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"❌ Error resetting password: {str(e)}")
        return Response({
            'success': False,
            'error': 'An error occurred. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change password for logged-in user
    """
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')
    
    if not all([current_password, new_password, confirm_password]):
        return Response({
            'success': False,
            'error': 'All fields are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if new_password != confirm_password:
        return Response({
            'success': False,
            'error': 'New passwords do not match'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if len(new_password) < 8:
        return Response({
            'success': False,
            'error': 'Password must be at least 8 characters long'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = request.user
    
    # Verify current password
    if not user.check_password(current_password):
        return Response({
            'success': False,
            'error': 'Current password is incorrect'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Set new password
    user.set_password(new_password)
    user.must_change_password = False
    user.save()
    
    return Response({
        'success': True,
        'message': 'Password changed successfully!'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_password_status(request):
    """
    Check if user must change password
    """
    return Response({
        'success': True,
        'must_change_password': request.user.must_change_password
    })