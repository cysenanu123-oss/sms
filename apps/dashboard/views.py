# apps/dashboard/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_admin_access(request):
    """Verify user has admin access"""
    user = request.user
    
    if user.role in ['admin', 'super_admin'] or user.is_superuser:
        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            }
        })
    
    return Response({
        'success': False,
        'error': 'Admin access required'
    }, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_teacher_access(request):
    """Verify user has teacher access"""
    user = request.user
    
    if user.role == 'teacher' or user.is_superuser:
        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            }
        })
    
    return Response({
        'success': False,
        'error': 'Teacher access required'
    }, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_student_access(request):
    """Verify user has student access"""
    user = request.user
    
    if user.role == 'student' or user.is_superuser:
        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            }
        })
    
    return Response({
        'success': False,
        'error': 'Student access required'
    }, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_parent_access(request):
    """Verify user has parent access"""
    user = request.user
    
    if user.role == 'parent' or user.is_superuser:
        return Response({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            }
        })
    
    return Response({
        'success': False,
        'error': 'Parent access required'
    }, status=status.HTTP_403_FORBIDDEN)