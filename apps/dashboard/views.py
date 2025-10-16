# apps/dashboard/views.py - ADD TO EXISTING FILE

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Notification


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



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """Get notifications for current user"""
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:50]
    
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'icon': n.icon,
        'type': n.notification_type,
        'is_read': n.is_read,
        'time': n.time_ago,
        'related_type': n.related_object_type,
        'related_id': n.related_object_id,
    } for n in notifications]
    
    unread_count = notifications.filter(is_read=False).count()
    
    return Response({
        'success': True,
        'data': {
            'notifications': data,
            'unread_count': unread_count
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark notification as read"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        notification.is_read = True
        notification.save()
        
        return Response({
            'success': True,
            'message': 'Notification marked as read'
        })
    except Notification.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Notification not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(is_read=True)
    
    return Response({
        'success': True,
        'message': f'{count} notifications marked as read'
    })


# ============================================
# HELPER FUNCTIONS FOR CREATING NOTIFICATIONS
# ============================================

def create_assignment_notifications(assignment):
    """Create notifications when assignment is posted"""
    from apps.admissions.models import Student
    
    students = Student.objects.filter(
        current_class=assignment.class_obj,
        status='active'
    ).select_related('user')
    
    notifications = []
    for student in students:
        if student.user:
            notification = Notification.objects.create(
                user=student.user,
                title='New Assignment Posted',
                message=f'"{assignment.title}" - Due: {assignment.due_date.strftime("%b %d, %Y")}',
                notification_type='assignment',
                icon='fas fa-tasks text-orange-600',
                related_object_type='assignment',
                related_object_id=assignment.id
            )
            notifications.append(notification)
    
    return len(notifications)


def create_grade_notifications(student, subject_name, exam_name, grade):
    """Create notification when grade is published"""
    if not student.user:
        return
    
    Notification.objects.create(
        user=student.user,
        title='New Grade Published',
        message=f'{subject_name} - {exam_name}: Grade {grade}',
        notification_type='grade',
        icon='fas fa-chart-line text-green-600',
        related_object_type='grade',
        related_object_id=None
    )
    
    # Also notify parent if exists
    try:
        from apps.admissions.models import Parent
        parent_relation = Parent.objects.filter(children=student).first()
        if parent_relation and parent_relation.user:
            Notification.objects.create(
                user=parent_relation.user,
                title=f'Grade Published - {student.first_name}',
                message=f'{subject_name} - {exam_name}: Grade {grade}',
                notification_type='grade',
                icon='fas fa-chart-line text-green-600',
                related_object_type='grade',
                related_object_id=None
            )
    except:
        pass


def create_resource_notifications(resource):
    """Create notifications when teaching resource is uploaded"""
    from apps.admissions.models import Student
    
    students = Student.objects.filter(
        current_class=resource.class_obj,
        status='active'
    ).select_related('user')
    
    subject_name = resource.subject.name if resource.subject else 'General'
    
    notifications = []
    for student in students:
        if student.user:
            notification = Notification.objects.create(
                user=student.user,
                title='New Learning Resource',
                message=f'{subject_name}: {resource.title}',
                notification_type='resource',
                icon='fas fa-book text-blue-600',
                related_object_type='resource',
                related_object_id=resource.id
            )
            notifications.append(notification)
    
    return len(notifications)


def create_attendance_notification(student, date, status):
    """Notify parent about attendance"""
    try:
        from apps.admissions.models import Parent
        parent_relation = Parent.objects.filter(children=student).first()
        
        if parent_relation and parent_relation.user:
            status_text = {
                'absent': 'was absent',
                'late': 'arrived late',
                'present': 'attended class'
            }.get(status, status)
            
            Notification.objects.create(
                user=parent_relation.user,
                title=f'Attendance - {student.first_name}',
                message=f'Your child {status_text} on {date.strftime("%b %d, %Y")}',
                notification_type='attendance',
                icon='fas fa-calendar-check text-purple-600',
                related_object_type='attendance',
                related_object_id=None
            )
    except:
        pass