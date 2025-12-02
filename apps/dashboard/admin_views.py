# apps/dashboard/admin_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q, Avg
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from apps.admissions.models import StudentApplication, Student, Parent, StudentPromotion
from apps.academics.models import Class, Subject, SchoolSettings
from apps.accounts.models import User


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_overview(request):
    """
    Get comprehensive admin dashboard overview
    """
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    today = timezone.now().date()
    this_month_start = today.replace(day=1)
    
    # Student Statistics
    total_students = Student.objects.filter(status='active').count()
    new_admissions_this_month = Student.objects.filter(
        admission_date__gte=this_month_start
    ).count()
    
    # Application Statistics
    application_stats = {
        'total_received': StudentApplication.objects.count(),
        'pending_review': StudentApplication.objects.filter(status='pending').count(),
        'under_review': StudentApplication.objects.filter(status='under_review').count(),
        'exam_completed': StudentApplication.objects.filter(status='exam_completed').count(),
        'accepted': StudentApplication.objects.filter(status='accepted').count(),
        'rejected': StudentApplication.objects.filter(status='rejected').count(),
    }
    
    # User Statistics
    user_stats = {
        'teachers': User.objects.filter(role='teacher', is_active=True).count(),
        'students': User.objects.filter(role='student', is_active=True).count(),
        'parents': User.objects.filter(role='parent', is_active=True).count(),
        'admins': User.objects.filter(Q(role='admin') | Q(role='super_admin'), is_active=True).count(),
    }
    
    # Financial Statistics
    financial_stats = {
        'application_fees_collected': 0,
        'collection_rate': 0,
        'pending_fees': 0,
    }
    
    # Class Statistics
    classes = Class.objects.all()
    class_stats = []
    for cls in classes:
        enrolled = Student.objects.filter(current_class=cls, status='active').count()
        class_stats.append({
            'class_name': cls.name,
            'capacity': cls.capacity,
            'enrolled': enrolled,
            'available': cls.capacity - enrolled
        })
    
    # Recent Applications
    recent_applications = StudentApplication.objects.order_by('-submitted_at')[:10]
    recent_apps_data = []
    for app in recent_applications:
        recent_apps_data.append({
            'application_number': app.application_number,
            'name': f"{app.first_name} {app.last_name}",
            'email': app.parent_email,
            'applying_for': app.applying_for_class,
            'status': app.status,
            'submitted_at': app.submitted_at.isoformat()
        })
    
    # Quick Actions
    quick_actions = []
    pending_apps = application_stats['pending_review']
    if pending_apps > 0:
        quick_actions.append({
            'title': 'Review Applications',
            'count': pending_apps,
            'priority': 'high',
            'icon': 'fas fa-file-alt'
        })
    
    exam_completed = application_stats['exam_completed']
    if exam_completed > 0:
        quick_actions.append({
            'title': 'Finalize Admissions',
            'count': exam_completed,
            'priority': 'high',
            'icon': 'fas fa-user-check'
        })
    
    dashboard_data = {
        'students': {
            'total_enrolled': total_students,
            'new_admissions': new_admissions_this_month,
        },
        'applications': application_stats,
        'user_statistics': user_stats,
        'financial': financial_stats,
        'classes': class_stats,
        'recent_applications': recent_apps_data,
        'quick_actions': quick_actions,
    }
    
    return Response({
        'success': True,
        'data': dashboard_data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def promote_students_bulk(request):
    """Promote multiple students to next class"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)

    from_class_id = request.data.get('from_class_id')
    to_class_id = request.data.get('to_class_id')
    student_ids = request.data.get('student_ids', [])
    academic_year = request.data.get('academic_year')

    if not all([from_class_id, to_class_id, student_ids, academic_year]):
        return Response({
            'success': False,
            'error': 'All fields are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from_class = Class.objects.get(id=from_class_id)
        to_class = Class.objects.get(id=to_class_id)

        promoted_count = 0
        errors = []

        with transaction.atomic():
            for student_id in student_ids:
                try:
                    student = Student.objects.get(id=student_id)

                    StudentPromotion.objects.create(
                        student=student,
                        from_class=from_class,
                        to_class=to_class,
                        academic_year=academic_year,
                        promotion_type='promoted',
                        promoted_by=request.user
                    )

                    # ✅ THIS IS THE FIX - ACTUALLY UPDATE THE STUDENT'S CLASS
                    student.current_class = to_class
                    student.academic_year = academic_year
                    student.save()

                    promoted_count += 1

                except Student.DoesNotExist:
                    errors.append(f'Student {student_id} not found')
                except Exception as e:
                    errors.append(str(e))

        response_data = {
            'success': True,
            'message': f'Successfully promoted {promoted_count} student(s)',
            'promoted_count': promoted_count
        }

        if errors:
            response_data['warnings'] = errors

        return Response(response_data)

    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================
# TERM MANAGEMENT ENDPOINTS
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_school_settings(request):
    """Get school settings including current term"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        settings = SchoolSettings.objects.first()
        if not settings:
            return Response({
                'success': False,
                'error': 'School settings not found. Please configure school settings first.'
            }, status=status.HTTP_404_NOT_FOUND)

        data = {
            'school_name': settings.school_name,
            'school_motto': settings.school_motto,
            'school_address': settings.school_address,
            'school_phone': settings.school_phone,
            'school_email': settings.school_email,
            'school_website': settings.school_website,
            'current_academic_year': settings.current_academic_year,
            'academic_year_start': settings.academic_year_start.isoformat() if settings.academic_year_start else None,
            'academic_year_end': settings.academic_year_end.isoformat() if settings.academic_year_end else None,
            'current_term': settings.current_term,
            'current_term_display': settings.get_current_term_display(),
            'term_start_date': settings.term_start_date.isoformat() if settings.term_start_date else None,
            'term_end_date': settings.term_end_date.isoformat() if settings.term_end_date else None,
            'grading_system': settings.grading_system,
            'admission_fee': str(settings.admission_fee),
            'application_fee': str(settings.application_fee),
            'entrance_exam_required': settings.entrance_exam_required,
            'exam_duration_minutes': settings.exam_duration_minutes,
            'exam_pass_percentage': settings.exam_pass_percentage,
        }

        return Response({
            'success': True,
            'data': data
        })

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_school_settings(request):
    """Update school settings including term switching"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        settings = SchoolSettings.objects.first()
        if not settings:
            return Response({
                'success': False,
                'error': 'School settings not found. Please create school settings first.'
            }, status=status.HTTP_404_NOT_FOUND)

        # Update fields if provided
        if 'current_term' in request.data:
            old_term = settings.get_current_term_display()
            settings.current_term = request.data['current_term']
            new_term = settings.get_current_term_display()

        if 'current_academic_year' in request.data:
            settings.current_academic_year = request.data['current_academic_year']

        if 'term_start_date' in request.data:
            settings.term_start_date = request.data['term_start_date']

        if 'term_end_date' in request.data:
            settings.term_end_date = request.data['term_end_date']

        if 'academic_year_start' in request.data:
            settings.academic_year_start = request.data['academic_year_start']

        if 'academic_year_end' in request.data:
            settings.academic_year_end = request.data['academic_year_end']

        # Update other fields
        for field in ['school_name', 'school_motto', 'school_address', 'school_phone',
                     'school_email', 'school_website', 'grading_system', 'admission_fee',
                     'application_fee', 'entrance_exam_required', 'exam_duration_minutes',
                     'exam_pass_percentage']:
            if field in request.data:
                setattr(settings, field, request.data[field])

        settings.updated_by = request.user
        settings.save()

        return Response({
            'success': True,
            'message': 'School settings updated successfully',
            'data': {
                'current_term': settings.get_current_term_display(),
                'current_academic_year': settings.current_academic_year
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_term_statistics(request):
    """Get statistics for different terms"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        from apps.grades.models import Grade, Assignment
        from apps.attendance.models import Attendance

        # Get all unique term/year combinations from existing data
        terms_data = []

        # Get unique term combinations from grades
        grade_terms = Grade.objects.values('academic_year', 'term').distinct()

        for item in grade_terms:
            academic_year = item['academic_year']
            term = item['term']

            # Get statistics for this term
            grades_count = Grade.objects.filter(
                academic_year=academic_year,
                term=term
            ).count()

            assignments_count = Assignment.objects.filter(
                academic_year=academic_year,
                term=term
            ).count()

            attendance_count = Attendance.objects.filter(
                academic_year=academic_year,
                term=term
            ).count()

            # Get term display name
            term_display = dict([
                ('first', 'First Term'),
                ('second', 'Second Term'),
                ('third', 'Third Term')
            ]).get(term, term)

            terms_data.append({
                'academic_year': academic_year,
                'term': term,
                'term_display': term_display,
                'grades_count': grades_count,
                'assignments_count': assignments_count,
                'attendance_records': attendance_count
            })

        # Sort by academic year and term
        terms_data.sort(key=lambda x: (x['academic_year'], x['term']), reverse=True)

        return Response({
            'success': True,
            'data': terms_data
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
