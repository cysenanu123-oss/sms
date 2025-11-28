# apps/teachers/admin_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from apps.accounts.models import User
from apps.academics.models import Class, ClassSubject, Subject, TeacherClassAssignment
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
        # FIX: Remove the invalid prefetch_related
        teachers = User.objects.filter(role='teacher', is_active=True)

        teachers_data = []
        for teacher in teachers:
            # Get assigned classes through TeacherClassAssignment
            class_assignments = TeacherClassAssignment.objects.filter(
                teacher=teacher,
                is_active=True
            ).select_related('class_obj')

            # Get subjects taught through ClassSubject
            class_subjects = ClassSubject.objects.filter(
                teacher=teacher
            ).select_related('class_obj', 'subject')

            classes_teaching = []
            subjects_set = set()

            for assignment in class_assignments:
                classes_teaching.append({
                    'class_id': assignment.class_obj.id,
                    'class_name': assignment.class_obj.name,
                })

            for cs in class_subjects:
                subjects_set.add(cs.subject.name)

            # Count total students
            unique_class_ids = set(
                [assignment.class_obj.id for assignment in class_assignments])
            total_students = 0
            for class_id in unique_class_ids:
                from apps.admissions.models import Student
                total_students += Student.objects.filter(
                    current_class_id=class_id,
                    status='active'
                ).count()

            teachers_data.append({
                'id': teacher.id,
                'username': teacher.username,
                'email': teacher.email,
                'first_name': teacher.first_name,
                'last_name': teacher.last_name,
                'full_name': teacher.get_full_name(),
                'phone': teacher.phone or 'N/A',
                'total_classes': len(unique_class_ids),
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
        subjects = request.data.get('subjects', [])
        classes = request.data.get('classes', [])

        if not all([first_name, last_name, email]):
            return Response({
                'success': False,
                'error': 'First name, last name, and email are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({
                'success': False,
                'error': 'Email already exists'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Generate username
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
                    must_change_password=True,
                    is_active=True
                )

                # Get academic year
                from apps.academics.models import SchoolSettings
                try:
                    settings_obj = SchoolSettings.objects.first()
                    academic_year = settings_obj.current_academic_year if settings_obj else "2024-2025"
                except:
                    academic_year = "2024-2025"

                # Create class assignments
                for class_id in classes:
                    try:
                        class_obj = Class.objects.get(id=class_id)
                        TeacherClassAssignment.objects.create(
                            teacher=teacher,
                            class_obj=class_obj,
                            academic_year=academic_year,
                            is_class_teacher=False
                        )
                    except Class.DoesNotExist:
                        pass

                # Assign subjects to classes
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
                            pass
                
                # Send email with credentials
                from apps.admissions.email_utils import send_teacher_credentials_email
                subject_names = [Subject.objects.get(id=s_id).name for s_id in subjects]
                class_names = [Class.objects.get(id=c_id).name for c_id in classes]
                send_teacher_credentials_email(teacher, username, temp_password, subject_names, class_names)

                return Response({
                    'success': True,
                    'message': 'Teacher created successfully',
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_subjects(request):
    user = request.user
    
    # Admin sees all subjects
    if user.role == 'admin' or user.is_superuser:
        subjects = Subject.objects.all()
    
    # Teachers only see their assigned subjects
    elif user.role == 'teacher':
        # Get subjects from teacher's class assignments
        assigned_subjects = ClassSubject.objects.filter(
            teacher=user
        ).values_list('subject_id', flat=True).distinct()
        
        subjects = Subject.objects.filter(id__in=assigned_subjects)
    
    else:
        return Response({
            'success': False,
            'error': 'Access denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    data = [{
        'id': s.id,
        'name': s.name,
        'code': s.code
    } for s in subjects]
    
    return Response({
        'success': True,
        'data': data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_classes(request):
    """Get all available classes for assignment"""

    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)

    classes = Class.objects.filter(is_active=True).order_by('name')

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


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_teacher(request, teacher_id):
    """Delete a teacher"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        teacher = User.objects.get(id=teacher_id, role='teacher')
        teacher.is_active = False  # Soft delete
        teacher.save()

        # Unassign teacher from classes and subjects
        TeacherClassAssignment.objects.filter(teacher=teacher).update(is_active=False)
        ClassSubject.objects.filter(teacher=teacher).update(teacher=None)

        return Response({
            'success': True,
            'message': 'Teacher removed successfully'
        })
    except User.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Teacher not found'
        }, status=status.HTTP_404_NOT_FOUND)
