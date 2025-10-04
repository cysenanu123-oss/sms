# apps/students/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Avg
from django.utils import timezone
from apps.admissions.models import Student
from apps.academics.models import Timetable, TimetableEntry, ClassSubject, Subject


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_dashboard_data(request):
    """
    Get complete student dashboard data
    """
    if request.user.role != 'student' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Student access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    current_class = student.current_class
    
    if not current_class:
        return Response({
            'success': False,
            'error': 'No class assigned yet'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get courses for this class
    class_subjects = ClassSubject.objects.filter(class_obj=current_class).select_related('subject', 'teacher')
    courses = []
    for cs in class_subjects:
        courses.append({
            'id': cs.subject.id,
            'name': cs.subject.name,
            'code': cs.subject.code,
            'description': cs.subject.description or '',
            'teacher': cs.teacher.get_full_name() if cs.teacher else 'To Be Assigned',
            'teacher_id': cs.teacher.id if cs.teacher else None,
            'teacher_email': cs.teacher.email if cs.teacher else '',
        })
    
    # Get timetable organized by day and period
    timetable_data = get_student_timetable_helper(current_class)
    
    # Student basic info
    student_info = {
        'student_id': student.student_id,
        'first_name': student.first_name,
        'last_name': student.last_name,
        'full_name': f"{student.first_name} {student.last_name}",
        'email': request.user.email,
        'class': current_class.name,
        'class_id': current_class.id,
        'roll_number': student.roll_number or 'Not Assigned',
        'academic_year': student.academic_year,
        'admission_date': student.admission_date.isoformat(),
        'blood_group': student.blood_group or 'Not Specified',
    }
    
    # Statistics (using placeholder values for now)
    stats = {
        'total_courses': len(courses),
        'attendance_rate': 95.5,
        'average_grade': 'A',
        'pending_assignments': 3,
    }
    
    return Response({
        'success': True,
        'data': {
            'student_info': student_info,
            'courses': courses,
            'timetable': timetable_data,
            'stats': stats,
        }
    })


def get_student_timetable_helper(class_obj):
    """
    Helper function to get organized timetable data
    """
    try:
        timetable = Timetable.objects.get(class_obj=class_obj, is_active=True)
        entries = TimetableEntry.objects.filter(timetable=timetable).select_related(
            'subject', 'teacher', 'time_slot'
        ).order_by('time_slot__slot_order')
        
        # Organize by time slots and days
        periods = {}
        days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        
        for entry in entries:
            time_key = entry.time_slot.name
            if time_key not in periods:
                periods[time_key] = {
                    'time': f"{entry.time_slot.start_time.strftime('%I:%M %p')} - {entry.time_slot.end_time.strftime('%I:%M %p')}",
                    'monday': None,
                    'tuesday': None,
                    'wednesday': None,
                    'thursday': None,
                    'friday': None,
                }
            
            periods[time_key][entry.day_of_week] = {
                'subject': entry.subject.name,
                'teacher': entry.teacher.get_full_name() if entry.teacher else 'TBA',
                'room': entry.room_number or '',
                'type': entry.time_slot.slot_type,
            }
        
        return {
            'periods': list(periods.values()),
            'days': days_order,
        }
        
    except Timetable.DoesNotExist:
        return {
            'periods': [],
            'days': [],
            'message': 'Timetable not available yet'
        }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_course_details(request, course_id):
    """
    Get detailed information about a specific course
    """
    if request.user.role != 'student' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Student access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        subject = Subject.objects.get(id=course_id)
        student = Student.objects.get(user=request.user)
        
        # Get class-subject relationship
        try:
            class_subject = ClassSubject.objects.get(
                class_obj=student.current_class,
                subject=subject
            )
            
            course_data = {
                'id': subject.id,
                'name': subject.name,
                'code': subject.code,
                'description': subject.description,
                'teacher': class_subject.teacher.get_full_name() if class_subject.teacher else 'TBA',
                'teacher_email': class_subject.teacher.email if class_subject.teacher else '',
            }
            
            return Response({
                'success': True,
                'data': course_data
            })
            
        except ClassSubject.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Course not found in your class'
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Subject.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Course not found'
        }, status=status.HTTP_404_NOT_FOUND)