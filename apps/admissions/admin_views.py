# apps/admissions/admin_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import StudentApplication, Student
from .serializers import StudentApplicationSerializer
from apps.accounts.models import User
import secrets


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_applications(request):
    """
    Get all applications for admin review
    Admin only endpoint
    """
    # Check if user is admin
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get filter parameters
    status_filter = request.GET.get('status', None)
    
    # Query applications
    applications = StudentApplication.objects.all()
    
    if status_filter:
        applications = applications.filter(status=status_filter)
    
    serializer = StudentApplicationSerializer(applications, many=True)
    
    # Calculate statistics
    stats = {
        'total_received': StudentApplication.objects.count(),
        'pending_review': StudentApplication.objects.filter(status='pending').count(),
        'under_review': StudentApplication.objects.filter(status='under_review').count(),
        'exam_completed': StudentApplication.objects.filter(status='exam_completed').count(),
        'accepted': StudentApplication.objects.filter(status='accepted').count(),
        'rejected': StudentApplication.objects.filter(status='rejected').count(),
    }
    
    return Response({
        'success': True,
        'data': {
            'applications': serializer.data,
            'statistics': stats
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_application_detail(request, application_number):
    """
    Get detailed view of a single application
    Admin only endpoint
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        application = StudentApplication.objects.get(application_number=application_number)
        serializer = StudentApplicationSerializer(application)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    except StudentApplication.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Application not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_application_status(request, application_number):
    """
    Update application status (accept, reject, etc.)
    Admin only endpoint
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        application = StudentApplication.objects.get(application_number=application_number)
        new_status = request.data.get('status')
        admin_notes = request.data.get('admin_notes', '')
        
        if new_status not in dict(StudentApplication.STATUS_CHOICES).keys():
            return Response({
                'success': False,
                'error': 'Invalid status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        application.status = new_status
        application.admin_notes = admin_notes
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.save()
        
        return Response({
            'success': True,
            'message': f'Application status updated to {new_status}',
            'data': StudentApplicationSerializer(application).data
        })
        
    except StudentApplication.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Application not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_and_enroll(request, application_number):
    """
    Accept application and create student account
    This creates:
    1. User account for student
    2. Student profile with unique student ID
    3. Links to original application
    
    Admin only endpoint
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        application = StudentApplication.objects.get(application_number=application_number)
        
        if application.status == 'accepted':
            return Response({
                'success': False,
                'error': 'Application already accepted and student enrolled'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get class assignment from request
        assigned_class_id = request.data.get('class_id')
        if not assigned_class_id:
            return Response({
                'success': False,
                'error': 'Please assign a class for the student'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from apps.academics.models import Class
        try:
            assigned_class = Class.objects.get(id=assigned_class_id)
        except Class.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Invalid class ID'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create username from learner name
        name_parts = application.learner_name.lower().split()
        base_username = ''.join(name_parts[:2])  # First two names
        username = base_username
        counter = 1
        
        # Ensure username is unique
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Generate temporary password
        temp_password = secrets.token_urlsafe(12)
        
        # Create user account
        user = User.objects.create_user(
            username=username,
            email=f"{username}@student.excellenceacademy.edu.gh",  # Temporary email
            password=temp_password,
            first_name=name_parts[0].capitalize(),
            last_name=' '.join(name_parts[1:]).capitalize() if len(name_parts) > 1 else '',
            role='student',
            must_change_password=True
        )
        
        # Create student profile
        student = Student.objects.create(
            user=user,
            application=application,
            first_name=user.first_name,
            last_name=user.last_name,
            date_of_birth=application.date_of_birth,
            sex=application.sex,
            current_class=assigned_class,
            academic_year=assigned_class.academic_year,
            residential_address=application.residential_address,
            nationality=application.nationality,
            region=application.region,
            has_health_challenge=application.has_health_challenge,
            health_notes=application.health_challenge_details or application.allergies_details,
            status='active',
            admission_date=timezone.now().date()
        )
        
        # Update application status
        application.status = 'accepted'
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.save()
        
        # TODO: Send email to parent with login credentials
        # TODO: Send welcome email to student
        
        return Response({
            'success': True,
            'message': 'Student enrolled successfully',
            'data': {
                'student_id': student.student_id,
                'username': username,
                'temporary_password': temp_password,  # Send this to parent via email
                'class': assigned_class.name,
                'admission_date': student.admission_date.isoformat()
            }
        })
        
    except StudentApplication.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Application not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Enrollment failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)