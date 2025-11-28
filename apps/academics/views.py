# apps/academics/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings

from apps.accounts.models import User
from apps.academics.models import (
    Class, Subject, ClassSubject, TeacherClassAssignment
)
from apps.academics.serializers import (
    ClassSerializer, SubjectSerializer, CreateTeacherSerializer
)

def is_admin(user):
    """Check if user is admin"""
    return user.role in ['admin', 'super_admin'] or user.is_superuser


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_classes(request):
    """Get list of all classes"""
    classes = Class.objects.filter(is_active=True).order_by('grade_level', 'section')
    serializer = ClassSerializer(classes, many=True)
    
    return Response({
        'success': True,
        'data': {
            'classes': serializer.data
        }
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def teacher_list_create(request):
    """
    GET: List all teachers
    POST: Create new teacher (admin only)
    """
    
    if request.method == 'GET':
        # Get all teacher profiles
        teachers = TeacherProfile.objects.filter(
            is_active=True
        ).select_related('user').order_by('-created_at')
        
        serializer = TeacherProfileSerializer(teachers, many=True)
        
        # Get class assignments for each teacher
        teachers_data = []
        for teacher_data in serializer.data:
            teacher_id = teacher_data['id']
            teacher_profile = TeacherProfile.objects.get(id=teacher_id)
            
            # Get assigned classes
            assignments = TeacherClassAssignment.objects.filter(
                teacher=teacher_profile.user,
                is_active=True
            ).select_related('class_obj')
            
            assigned_classes = []
            class_teacher_for = None
            
            for assignment in assignments:
                assigned_classes.append({
                    'id': assignment.class_obj.id,
                    'name': assignment.class_obj.name,
                    'is_class_teacher': assignment.is_class_teacher
                })
                
                if assignment.is_class_teacher:
                    class_teacher_for = assignment.class_obj.id
            
            teacher_data['assigned_classes'] = assigned_classes
            teacher_data['class_teacher_for'] = class_teacher_for
            teachers_data.append(teacher_data)
        
        return Response({
            'success': True,
            'data': {
                'teachers': teachers_data,
                'total': len(teachers_data)
            }
        })
    
    elif request.method == 'POST':
        # Verify admin access
        if not is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = CreateTeacherSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    result = serializer.save()
                    
                    # Send welcome email with credentials
                    try:
                        send_mail(
                            subject='Welcome to Unique Success Academy - Teacher Account Created',
                            message=f"""
Dear {result['user'].get_full_name()},

Welcome to Unique Success Academy! Your teacher account has been created.

Login Credentials:
Username: {result['username']}
Temporary Password: {result['temporary_password']}

Please log in at: {settings.FRONTEND_URL}/auth/

IMPORTANT: You will be required to change your password upon first login.

If you have any questions, please contact the administration.

Best regards,
Unique Success Academy Administration
                            """,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[result['user'].email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f"Email send error: {e}")
                    
                    # Get the created teacher profile
                    teacher_profile = TeacherProfile.objects.get(user=result['user'])
                    teacher_serializer = TeacherProfileSerializer(teacher_profile)
                    
                    return Response({
                        'success': True,
                        'message': 'Teacher created successfully',
                        'data': {
                            'teacher': teacher_serializer.data,
                            'credentials': {
                                'username': result['username'],
                                'temporary_password': result['temporary_password'],
                                'email': result['user'].email
                            }
                        }
                    }, status=status.HTTP_201_CREATED)
                    
            except Exception as e:
                return Response({
                    'success': False,
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def teacher_detail(request, teacher_id):
    """
    GET: Get teacher details
    PUT: Update teacher (admin only)
    DELETE: Deactivate teacher (admin only)
    """
    
    try:
        teacher_profile = TeacherProfile.objects.select_related('user').get(id=teacher_id)
    except TeacherProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Teacher not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = TeacherProfileSerializer(teacher_profile)
        teacher_data = serializer.data
        
        # Get class assignments
        assignments = TeacherClassAssignment.objects.filter(
            teacher=teacher_profile.user,
            is_active=True
        ).select_related('class_obj')
        
        teacher_data['assigned_classes'] = TeacherClassAssignmentSerializer(
            assignments, many=True
        ).data
        
        return Response({
            'success': True,
            'data': teacher_data
        })
    
    elif request.method == 'PUT':
        # Verify admin access
        if not is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Update teacher profile fields
        update_fields = [
            'department', 'qualification', 'specialization',
            'years_of_experience', 'emergency_contact_name',
            'emergency_contact_phone', 'address', 'notes'
        ]
        
        for field in update_fields:
            if field in request.data:
                setattr(teacher_profile, field, request.data[field])
        
        teacher_profile.save()
        
        # Update user fields if provided
        if 'phone' in request.data:
            teacher_profile.user.phone = request.data['phone']
            teacher_profile.user.save()
        
        serializer = TeacherProfileSerializer(teacher_profile)
        
        return Response({
            'success': True,
            'message': 'Teacher updated successfully',
            'data': serializer.data
        })
    
    elif request.method == 'DELETE':
        # Verify admin access
        if not is_admin(request.user):
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Deactivate instead of delete
        teacher_profile.is_active = False
        teacher_profile.save()
        
        teacher_profile.user.is_active = False
        teacher_profile.user.save()
        
        return Response({
            'success': True,
            'message': 'Teacher deactivated successfully'
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_teacher_to_class(request):
    """Assign teacher to classes (admin only)"""
    
    if not is_admin(request.user):
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    teacher_id = request.data.get('teacher_id')
    class_ids = request.data.get('class_ids', [])
    class_teacher_for = request.data.get('class_teacher_for')  # ID of class to be homeroom teacher
    
    if not teacher_id or not class_ids:
        return Response({
            'success': False,
            'error': 'Teacher ID and at least one class ID are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        teacher_profile = TeacherProfile.objects.get(id=teacher_id)
        teacher_user = teacher_profile.user
    except TeacherProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Teacher not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get current academic year
    from apps.academics.models import SchoolSettings
    try:
        settings_obj = SchoolSettings.objects.first()
        academic_year = settings_obj.current_academic_year if settings_obj else "2024-2025"
    except:
        academic_year = "2024-2025"
    
    # Remove old assignments for this academic year
    TeacherClassAssignment.objects.filter(
        teacher=teacher_user,
        academic_year=academic_year
    ).delete()
    
    # Create new assignments
    created_assignments = []
    for class_id in class_ids:
        try:
            class_obj = Class.objects.get(id=class_id)
            is_class_teacher = (class_id == class_teacher_for)
            
            assignment = TeacherClassAssignment.objects.create(
                teacher=teacher_user,
                class_obj=class_obj,
                academic_year=academic_year,
                is_class_teacher=is_class_teacher
            )
            created_assignments.append(assignment)
            
            # Update class teacher if applicable
            if is_class_teacher:
                class_obj.class_teacher = teacher_user
                class_obj.save()
                
        except Class.DoesNotExist:
            pass
    
    serializer = TeacherClassAssignmentSerializer(created_assignments, many=True)
    
    return Response({
        'success': True,
        'message': 'Teacher assigned to classes successfully',
        'data': {
            'assignments': serializer.data
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def teacher_classes(request):
    """Get classes assigned to the logged-in teacher"""
    
    if request.user.role != 'teacher':
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get current academic year
    from apps.academics.models import SchoolSettings
    try:
        settings_obj = SchoolSettings.objects.first()
        academic_year = settings_obj.current_academic_year if settings_obj else "2024-2025"
    except:
        academic_year = "2024-2025"
    
    # Get teacher's class assignments
    assignments = TeacherClassAssignment.objects.filter(
        teacher=request.user,
        academic_year=academic_year,
        is_active=True
    ).select_related('class_obj')
    
    classes_data = []
    for assignment in assignments:
        from apps.admissions.models import Student
        enrolled_count = Student.objects.filter(
            current_class=assignment.class_obj,
            status='active'
        ).count()
        
        classes_data.append({
            'id': assignment.class_obj.id,
            'name': assignment.class_obj.name,
            'grade_level': assignment.class_obj.grade_level,
            'section': assignment.class_obj.section,
            'capacity': assignment.class_obj.capacity,
            'enrolled': enrolled_count,
            'is_class_teacher': assignment.is_class_teacher,
            'academic_year': assignment.academic_year
        })
    
    return Response({
        'success': True,
        'data': {
            'classes': classes_data,
            'total': len(classes_data)
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_subjects(request):
    """Get all available subjects"""
    
    subjects = Subject.objects.all().order_by('code')
    
    subjects_data = [{
        'id': s.id,
        'name': s.name,
        'code': s.code,
        'description': s.description or ''
    } for s in subjects]
    
    return Response({
        'success': True,
        'data': subjects_data
    })