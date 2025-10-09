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

    from .models import User

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
                    'role': user.role
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


# apps/accounts/views.py - ADD THESE NEW FUNCTIONS



@api_view(['POST'])
def request_password_reset(request):
    """
    Request a password reset email
    """
    email = request.data.get('email')
    
    if not email:
        return Response({
            'success': False,
            'error': 'Email is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email, is_active=True)
        
        # Generate token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Build reset URL
        reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
        
        # Send email
        context = {
            'user_name': user.get_full_name() or user.username,
            'reset_url': reset_url,
            'expiry_hours': 24,
        }
        
        html_message = render_to_string('emails/password_reset.html', context)
        text_message = render_to_string('emails/password_reset.txt', context)
        
        send_mail(
            subject='Reset Your Password - Excellence Academy',
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return Response({
            'success': True,
            'message': 'Password reset email sent. Please check your inbox.'
        })
        
    except User.DoesNotExist:
        # Don't reveal if email exists or not for security
        return Response({
            'success': True,
            'message': 'If that email exists, we sent a password reset link.'
        })
    except Exception as e:
        print(f"Error sending password reset email: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error sending email. Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def reset_password(request):
    """
    Reset password with token
    """
    uidb64 = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')
    
    if not all([uidb64, token, new_password, confirm_password]):
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
            'error': 'Password must be at least 8 characters long'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Decode user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
        
        # Verify token
        if not default_token_generator.check_token(user, token):
            return Response({
                'success': False,
                'error': 'Invalid or expired reset link'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
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
        print(f"Error resetting password: {str(e)}")
        return Response({
            'success': False,
            'error': 'Error resetting password. Please try again.'
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