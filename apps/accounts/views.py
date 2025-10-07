from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken


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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password (forced on first login or voluntary)
    """
    user = request.user
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')
    
    # Validation
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
    
    # Check current password
    if not user.check_password(current_password):
        return Response({
            'success': False,
            'error': 'Current password is incorrect'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Password strength check
    if len(new_password) < 8:
        return Response({
            'success': False,
            'error': 'Password must be at least 8 characters long'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Change password
    user.set_password(new_password)
    user.must_change_password = False  # ✅ Clear the flag
    user.save()
    
    return Response({
        'success': True,
        'message': 'Password changed successfully! Please login with your new password.'
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