# ============================================
# AUTH VIEWS (authentication/views.py)
# ============================================

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie

@api_view(['POST'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def login_view(request):
    """Handle user login via API"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': 'Username and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Authenticate user
    user = authenticate(request, username=username, password=password)
    
    if user is not None:
        # Create session
        login(request, user)
        
        # Debug logging
        print(f"✓ User logged in: {user.username}")
        print(f"✓ User type: {user.user_type}")
        print(f"✓ Is superuser: {user.is_superuser}")
        print(f"✓ Session key: {request.session.session_key}")
        
        # Determine redirect URL based on user type
        user_type = user.user_type.upper() if hasattr(user, 'user_type') else None
        
        if user.is_superuser or user_type == 'ADMIN':
            dashboard_url = '/dashboard/admin/'
        elif user_type == 'TEACHER':
            dashboard_url = '/dashboard/teacher/'
        elif user_type == 'STUDENT':
            dashboard_url = '/dashboard/student/'
        elif user_type == 'PARENT':
            dashboard_url = '/dashboard/parent/'
        else:
            dashboard_url = '/'
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'user_type': user_type,
                'is_superuser': user.is_superuser,
            },
            'redirect_url': dashboard_url
        }, status=status.HTTP_200_OK)
    else:
        return Response(
            {'error': 'Invalid username or password'},
            status=status.HTTP_401_UNAUTHORIZED
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Handle user logout"""
    username = request.user.username
    logout(request)
    print(f"✓ User logged out: {username}")
    
    return Response({
        'success': True,
        'message': 'Logout successful'
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    """Get current authenticated user"""
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'user_type': user.user_type,
        'is_superuser': user.is_superuser,
        'is_authenticated': user.is_authenticated,
    })