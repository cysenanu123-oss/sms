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


