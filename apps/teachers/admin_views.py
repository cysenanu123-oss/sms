# apps/teachers/admin_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from apps.accounts.models import User
from apps.academics.models import Class, ClassSubject, Subject
import secrets


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manage_teachers(request):
    """
    GET: List all teachers
    POST: Add new teacher
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        teachers = User.objects.filter(role='teacher', is_active=True).prefetch_related('taught_subjects')
        
        teachers_data = []
        for teacher in teachers:
            # Get assigned classes
            assigned_classes = ClassSubject.objects.filter(teacher=teacher).select_related('class_obj', 'subject')
            
            classes_teaching = []
            subjects_set = set()
            
            for cs in assigned_classes:
                classes_teaching.append({
                    'class_id': cs.class_obj.id,
                    'class_name': cs.class_obj.name,
                    'subject': cs.subject.name
                })
                subjects_set.add(cs.subject.name)
            
            # Count unique students across all classes
            unique_classes = set([cs['class_id'] for cs in classes_teaching])
            total_students = sum([
                Class.objects.get(id=class_id).students.filter(status='active').count() 
                for class_id in unique_classes
            ])
            
            teachers_data.append({
                'id': teacher.id,
                'username': teacher.username,
                'email': teacher.email,
                'first_name': teacher.first_name,
                'last_name': teacher.last_name,
                'full_name': teacher.get_full_name(),
                'phone': teacher.phone or 'N/A',
                'total_classes': len(unique_classes),
                'total_students': total_students,
                'subjects': list(subjects_set),
                'classes': classes_teaching,
                'date_joined': teacher.date_joined.isoformat(),
            })
        
        return Response({
            'success': True,
            'data': teachers_data
        })
    
    elif request.method == 'POST':
        # Add new teacher
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        email = request.data.get('email')
        phone = request.data.get('phone', '')
        subjects = request.data.get('subjects', [])  # List of subject IDs
        classes = request.data.get('classes', [])  # List of class IDs
        
        # Validation
        if not all([first_name, last_name, email]):
            return Response({
                'success': False,
                'error': 'First name, last name, and email are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return Response({
                'success': False,
                'error': 'Email already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate username from name
        base_username = f"{first_name.lower()}.{last_name.lower()}"
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Generate temporary password
        temp_password = secrets.token_urlsafe(12)
        
        try:
            with transaction.atomic():
                # Create teacher user account
                teacher = User.objects.create_user(
                    username=username,
                    email=email,
                    password=temp_password,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    role='teacher',
                    must_change_password=True
                )
                
                # Assign to classes and subjects
                for class_id in classes:
                    for subject_id in subjects:
                        try:
                            class_obj = Class.objects.get(id=class_id)
                            subject_obj = Subject.objects.get(id=subject_id)
                            
                            # Create or update ClassSubject assignment
                            ClassSubject.objects.update_or_create(
                                class_obj=class_obj,
                                subject=subject_obj,
                                defaults={'teacher': teacher}
                            )
                        except (Class.DoesNotExist, Subject.DoesNotExist):
                            continue
                
                # TODO: Send email with credentials
                
                return Response({
                    'success': True,
                    'message': 'Teacher added successfully',
                    'data': {
                        'id': teacher.id,
                        'username': username,
                        'temporary_password': temp_password,
                        'email': email,
                        'full_name': teacher.get_full_name(),
                    }
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Error creating teacher: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_teacher_detail(request, teacher_id):
    """
    PUT: Update teacher details and assignments
    DELETE: Remove teacher
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        teacher = User.objects.get(id=teacher_id, role='teacher')
    except User.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Teacher not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'PUT':
        # Update teacher info
        teacher.first_name = request.data.get('first_name', teacher.first_name)
        teacher.last_name = request.data.get('last_name', teacher.last_name)
        teacher.email = request.data.get('email', teacher.email)
        teacher.phone = request.data.get('phone', teacher.phone)
        teacher.save()
        
        # Update class and subject assignments
        subjects = request.data.get('subjects', [])
        classes = request.data.get('classes', [])
        
        if subjects and classes:
            # Remove old assignments
            ClassSubject.objects.filter(teacher=teacher).update(teacher=None)
            
            # Add new assignments
            for class_id in classes:
                for subject_id in subjects:
                    try:
                        class_obj = Class.objects.get(id=class_id)
                        subject_obj = Subject.objects.get(id=subject_id)
                        
                        ClassSubject.objects.update_or_create(
                            class_obj=class_obj,
                            subject=subject_obj,
                            defaults={'teacher': teacher}
                        )
                    except (Class.DoesNotExist, Subject.DoesNotExist):
                        continue
        
        return Response({
            'success': True,
            'message': 'Teacher updated successfully'
        })
    
    elif request.method == 'DELETE':
        # Soft delete - deactivate teacher
        teacher.is_active = False
        teacher.save()
        
        # Remove from class assignments
        ClassSubject.objects.filter(teacher=teacher).update(teacher=None)
        
        return Response({
            'success': True,
            'message': 'Teacher removed successfully'
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_classes(request):
    """
    Get classes assigned to logged-in teacher
    """
    if request.user.role != 'teacher' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get all class-subject assignments for this teacher
    assignments = ClassSubject.objects.filter(
        teacher=request.user
    ).select_related('class_obj', 'subject')
    
    # Group by class
    classes_dict = {}
    for assignment in assignments:
        class_id = assignment.class_obj.id
        if class_id not in classes_dict:
            classes_dict[class_id] = {
                'id': class_id,
                'name': assignment.class_obj.name,
                'capacity': assignment.class_obj.capacity,
                'academic_year': assignment.class_obj.academic_year,
                'total_students': assignment.class_obj.students.filter(status='active').count(),
                'subjects': []
            }
        
        classes_dict[class_id]['subjects'].append({
            'id': assignment.subject.id,
            'name': assignment.subject.name,
            'code': assignment.subject.code
        })
    
    return Response({
        'success': True,
        'data': list(classes_dict.values())
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_subjects(request):
    """
    Get all available subjects for assignment
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    subjects = Subject.objects.all()
    
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_classes(request):
    """
    Get all available classes for assignment
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    classes = Class.objects.all()
    
    classes_data = [{
        'id': c.id,
        'name': c.name,
        'capacity': c.capacity,
        'academic_year': c.academic_year
    } for c in classes]
    
    return Response({
        'success': True,
        'data': classes_data
    })