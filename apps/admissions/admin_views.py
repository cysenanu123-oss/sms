# apps/admissions/admin_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction
from .models import StudentApplication, Student, Parent
from .serializers import StudentApplicationSerializer
from apps.accounts.models import User
import secrets
from .email_utils import send_student_credentials_email, send_parent_credentials_email


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_applications(request):
    """Get all applications for admin review"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    status_filter = request.GET.get('status', None)
    applications = StudentApplication.objects.all()
    
    if status_filter:
        applications = applications.filter(status=status_filter)
    
    serializer = StudentApplicationSerializer(applications, many=True)
    
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
    """Get detailed view of a single application"""
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
    """Update application status"""
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
    """Accept application and create student + parent accounts"""
    
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    try:
        application = StudentApplication.objects.get(application_number=application_number)
        
        if application.status == 'accepted':
            return Response({'success': False, 'error': 'Already enrolled'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        assigned_class_id = request.data.get('class_id')
        if not assigned_class_id:
            return Response({'success': False, 'error': 'Class required'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        from apps.academics.models import Class
        assigned_class = Class.objects.get(id=assigned_class_id)
        
        with transaction.atomic():
            # Create student username
            base_username = f"{application.first_name.lower()}_{application.last_name.lower()}"
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Generate passwords
            student_temp_password = secrets.token_urlsafe(12)
            parent_temp_password = secrets.token_urlsafe(12)
            
            # Create STUDENT account
            student_user = User.objects.create_user(
                username=username,
                email=f"{username}@student.excellenceacademy.edu.gh",
                password=student_temp_password,
                first_name=application.first_name.capitalize(),
                last_name=application.last_name.capitalize(),
                role='student',
                must_change_password=True
            )
            
            # Create student profile
            student = Student.objects.create(
                user=student_user,
                application=application,
                first_name=student_user.first_name,
                last_name=student_user.last_name,
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
            
            # Create PARENT account if email provided
            parent = None
            parent_username = None
            if application.parent_email:
                parent_username = f"parent_{username}"
                
                parent_user = User.objects.create_user(
                    username=parent_username,
                    email=application.parent_email,
                    password=parent_temp_password,
                    first_name=application.parent_full_name.split()[0] if application.parent_full_name else 'Parent',
                    last_name=' '.join(application.parent_full_name.split()[1:]) if application.parent_full_name else '',
                    role='parent',
                    phone=application.parent_phone,
                    must_change_password=True
                )
                
                # Create parent profile
                parent = Parent.objects.create(
                    user=parent_user,
                    full_name=application.parent_full_name or 'Parent/Guardian',
                    relationship='guardian',
                    phone=application.parent_phone or '',
                    email=application.parent_email,
                    residential_address=application.residential_address,
                )
                
                # Link parent to student
                parent.children.add(student)
            
            # Update application
            application.status = 'accepted'
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save()
            
            # Send emails
            if application.parent_email:
                send_student_credentials_email(
                    student, username, student_temp_password, application.parent_email
                )
                if parent:
                    send_parent_credentials_email(
                        parent, parent_username, parent_temp_password, 
                        f"{student.first_name} {student.last_name}"
                    )
            
            return Response({
                'success': True,
                'message': 'Student enrolled successfully',
                'data': {
                    'student_id': student.student_id,
                    'student_username': username,
                    'student_password': student_temp_password,
                    'parent_username': parent_username,
                    'parent_password': parent_temp_password if parent else None,
                    'class': assigned_class.name,
                    'admission_date': student.admission_date.isoformat()
                }
            })
        
    except StudentApplication.DoesNotExist:
        return Response({'success': False, 'error': 'Application not found'}, 
                       status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Enrollment failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_and_enroll(request, application_number):
    """Accept application and create student + parent accounts - FIXED VERSION"""
    
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    try:
        application = StudentApplication.objects.get(application_number=application_number)
        
        if application.status == 'accepted':
            return Response({'success': False, 'error': 'Already enrolled'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        assigned_class_id = request.data.get('class_id')
        if not assigned_class_id:
            return Response({'success': False, 'error': 'Class required'}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        from apps.academics.models import Class
        assigned_class = Class.objects.get(id=assigned_class_id)
        
        with transaction.atomic():
            # Create student username
            base_username = f"{application.first_name.lower()}_{application.last_name.lower()}"
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Generate passwords
            student_temp_password = secrets.token_urlsafe(12)
            parent_temp_password = secrets.token_urlsafe(12)
            
            # Create STUDENT account
            student_user = User.objects.create_user(
                username=username,
                email=f"{username}@student.excellenceacademy.edu.gh",
                password=student_temp_password,
                first_name=application.first_name.capitalize(),
                last_name=application.last_name.capitalize(),
                role='student',
                must_change_password=True
            )
            
            # Create student profile with ALL data from application
            student = Student.objects.create(
                user=student_user,
                application=application,
                first_name=application.first_name,
                last_name=application.last_name,
                other_names=application.other_names or '',  # Include other_names
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
            
            # Create PARENT account with COMPLETE information
            parent = None
            parent_username = None
            if application.parent_email and application.parent_full_name:
                parent_username = f"parent_{username}"
                
                # Split parent name properly
                parent_name_parts = application.parent_full_name.strip().split()
                parent_first = parent_name_parts[0] if parent_name_parts else 'Parent'
                parent_last = ' '.join(parent_name_parts[1:]) if len(parent_name_parts) > 1 else ''
                
                parent_user = User.objects.create_user(
                    username=parent_username,
                    email=application.parent_email,
                    password=parent_temp_password,
                    first_name=parent_first,
                    last_name=parent_last,
                    role='parent',
                    phone=application.parent_phone or '',  # Save phone to User model
                    must_change_password=True
                )
                
                # Create parent profile with COMPLETE data
                parent = Parent.objects.create(
                    user=parent_user,
                    full_name=application.parent_full_name,  # Save COMPLETE name
                    relationship=application.parent_relationship or 'guardian',
                    phone=application.parent_phone or '',  # Save phone
                    email=application.parent_email,  # Save email
                    residential_address=application.residential_address,
                    occupation=application.parent_occupation or '',
                    is_emergency_contact=True,
                    is_active=True
                )
                
                # Link parent to student
                parent.children.add(student)
            
            # Update application
            application.status = 'accepted'
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save()
            
            # Send emails
            if application.parent_email:
                send_student_credentials_email(
                    student, username, student_temp_password, application.parent_email
                )
                if parent:
                    send_parent_credentials_email(
                        parent, parent_username, parent_temp_password, 
                        f"{student.first_name} {student.last_name}"
                    )
            
            return Response({
                'success': True,
                'message': 'Student enrolled successfully',
                'data': {
                    'student_id': student.student_id,
                    'student_username': username,
                    'student_password': student_temp_password,
                    'parent_username': parent_username,
                    'parent_password': parent_temp_password if parent else None,
                    'parent_full_name': application.parent_full_name,
                    'parent_phone': application.parent_phone,
                    'parent_email': application.parent_email,
                    'class': assigned_class.name,
                    'admission_date': student.admission_date.isoformat()
                }
            })
        
    except StudentApplication.DoesNotExist:
        return Response({'success': False, 'error': 'Application not found'}, 
                       status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Enrollment failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)