# apps/dashboard/admin_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from apps.admissions.models import StudentApplication, Student, Parent
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
