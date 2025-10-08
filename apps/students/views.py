# apps/students/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db.models import Avg, Sum
from datetime import timedelta

from apps.admissions.models import Student
from apps.academics.models import ClassSubject, Timetable, TimetableEntry
from apps.grades.models import Assignment, Grade


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_dashboard(request):
    """
    Get student dashboard data including:
    - Student info
    - Courses
    - Assignments
    - Recent test results
    - Timetable
    - Stats
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
            'error': 'No class assigned to student'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get student info
    student_info = {
        'student_id': student.student_id,
        'first_name': student.first_name,
        'last_name': student.last_name,
        'full_name': f"{student.first_name} {student.last_name}",
        'roll_number': student.roll_number or 'Not Assigned',
        'class': current_class.name,
        'class_id': current_class.id,
        'academic_year': student.academic_year,
        'email': request.user.email,
        'phone': request.user.phone or 'Not Provided'
    }
    
    # Get courses
    class_subjects = ClassSubject.objects.filter(
        class_obj=current_class,
    ).select_related('subject', 'teacher')
    
    courses = []
    for cs in class_subjects:
        # Get average grade for this subject
        subject_grades = Grade.objects.filter(
            student=student,
            subject=cs.subject
        )
        
        if subject_grades.exists():
            # Calculate average percentage correctly
            total_score = 0
            total_possible = 0
            for grade in subject_grades:
                total_score += grade.score
                total_possible += grade.total_marks
            
            avg_grade = round((total_score / total_possible * 100), 1) if total_possible > 0 else 0
        else:
            avg_grade = 0
        
        courses.append({
            'id': cs.id,
            'name': cs.subject.name,
            'code': cs.subject.code,
            'teacher': cs.teacher.get_full_name() if cs.teacher else 'TBA',
            'average_grade': avg_grade
        })
    
    # Get pending assignments
    pending_assignments = Assignment.objects.filter(
        class_obj=current_class,
        due_date__gte=timezone.now().date()
    ).select_related('subject').order_by('due_date')
    
    assignments_data = []
    for assignment in pending_assignments:
        # Calculate days until due
        days_until_due = (assignment.due_date - timezone.now().date()).days
        
        if days_until_due == 0:
            due_status = 'Due Today'
            status_color = 'red'
        elif days_until_due == 1:
            due_status = 'Due Tomorrow'
            status_color = 'red'
        elif days_until_due <= 3:
            due_status = f'Due in {days_until_due} days'
            status_color = 'yellow'
        else:
            due_status = f'Due in {days_until_due} days'
            status_color = 'blue'
        
        assignments_data.append({
            'id': assignment.id,
            'title': assignment.title,
            'description': assignment.description,
            'subject': assignment.subject.name if assignment.subject else 'General',
            'due_date': assignment.due_date.isoformat(),
            'due_status': due_status,
            'status_color': status_color,
            'total_marks': assignment.total_marks,
            'submitted': False,  # You can implement submission tracking later
            'submission_date': None,
            'submission_status': None
        })
    
    # Get recent test results
    recent_results = Grade.objects.filter(
        student=student
    ).select_related('subject').order_by('-exam_date')[:5]
    
    results_data = []
    for result in recent_results:
        percentage = (result.score / result.total_marks * 100) if result.total_marks > 0 else 0
        
        results_data.append({
            'id': result.id,
            'subject': result.subject.name if result.subject else 'N/A',
            'test_name': result.exam_name,
            'date': result.exam_date.strftime('%b %d, %Y'),
            'score': f"{result.score}/{result.total_marks}",
            'percentage': round(percentage, 1),
            'grade': result.grade,
            'status': 'Published'
        })
    
    # Get timetable
    timetable_data = get_student_timetable_helper(current_class)
    
    # Calculate stats
    total_courses = len(courses)
    
    # Average grade
    all_grades = Grade.objects.filter(student=student)
    if all_grades.exists():
        total_score = 0
        total_possible = 0
        for grade in all_grades:
            total_score += grade.score
            total_possible += grade.total_marks
        
        avg_percentage = (total_score / total_possible * 100) if total_possible > 0 else 0
        average_grade = f"{round(avg_percentage, 1)}%"
    else:
        average_grade = 'N/A'
    
    # Attendance rate (last 30 days)
    try:
        from apps.attendance.models import AttendanceRecord
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        
        attendance_records = AttendanceRecord.objects.filter(
            student=student,
            attendance__date__gte=thirty_days_ago
        )
        
        total_days = attendance_records.count()
        present_days = attendance_records.filter(status='present').count()
        attendance_rate = round((present_days / total_days * 100), 1) if total_days > 0 else 0
    except:
        attendance_rate = 0
    
    # Pending assignments count
    pending_count = len(assignments_data)
    
    stats = {
        'total_courses': total_courses,
        'average_grade': average_grade,
        'attendance_rate': attendance_rate,
        'pending_assignments': pending_count
    }
    
    return Response({
        'success': True,
        'data': {
            'student_info': student_info,
            'courses': courses,
            'assignments': assignments_data,
            'recent_results': results_data,
            'timetable': timetable_data,
            'stats': stats
        }
    })


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
        student = Student.objects.get(user=request.user)
        class_subject = ClassSubject.objects.get(id=course_id)
        
        # Verify student is in this class
        if student.current_class != class_subject.class_obj:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get all grades for this subject
        grades = Grade.objects.filter(
            student=student,
            subject=class_subject.subject
        ).order_by('-exam_date')
        
        # Calculate grade breakdown
        test_grades = grades.filter(exam_type='quiz')
        assignment_grades = grades.filter(exam_type='assignment')
        midterm_grades = grades.filter(exam_type='midterm')
        
        def calculate_avg(grade_set):
            if not grade_set.exists():
                return 0
            total_score = 0
            total_possible = 0
            for grade in grade_set:
                total_score += grade.score
                total_possible += grade.total_marks
            return round((total_score / total_possible * 100), 1) if total_possible > 0 else 0
        
        test_avg = calculate_avg(test_grades)
        assignment_avg = calculate_avg(assignment_grades)
        midterm_avg = calculate_avg(midterm_grades)
        
        # Calculate overall (weighted average)
        # Tests 40%, Assignments 30%, Midterm 20%, Participation 10%
        overall = (test_avg * 0.4) + (assignment_avg * 0.3) + (midterm_avg * 0.2) + (95 * 0.1)
        
        # Get teacher info
        teacher = class_subject.teacher
        teacher_info = {
            'name': teacher.get_full_name() if teacher else 'TBA',
            'email': teacher.email if teacher else None,
            'phone': teacher.phone if teacher else None
        }
        
        # Get timetable for this subject
        timetable_entries = TimetableEntry.objects.filter(
            timetable__class_obj=class_subject.class_obj,
            subject=class_subject.subject,
            timetable__is_active=True
        ).select_related('time_slot')
        
        schedule = []
        for entry in timetable_entries:
            schedule.append({
                'day': entry.day_of_week.capitalize(),
                'time': f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
                'room': entry.room_number or 'TBA'
            })
        
        course_data = {
            'id': class_subject.id,
            'name': class_subject.subject.name,
            'code': class_subject.subject.code,
            'description': class_subject.subject.description or 'No description available',
            'teacher': teacher_info,
            'credits': 3.0,  # Default credits
            'schedule': schedule,
            'grade_breakdown': {
                'tests': test_avg,
                'assignments': assignment_avg,
                'midterm': midterm_avg,
                'participation': 95,  # Default for now
                'overall': round(overall, 1)
            },
            'recent_grades': [
                {
                    'exam_name': g.exam_name,
                    'date': g.exam_date.isoformat(),
                    'score': g.score,
                    'total': g.total_marks,
                    'percentage': round((g.score / g.total_marks * 100), 1) if g.total_marks > 0 else 0,
                    'grade': g.grade
                }
                for g in grades[:5]
            ]
        }
        
        return Response({
            'success': True,
            'data': course_data
        })
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except ClassSubject.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Course not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_test_results(request):
    """
    Get all test results for the student
    """
    if request.user.role != 'student' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Student access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        student = Student.objects.get(user=request.user)
        
        # Get all grades
        grades = Grade.objects.filter(
            student=student
        ).select_related('subject').order_by('-exam_date')
        
        results_data = []
        for grade in grades:
            percentage = (grade.score / grade.total_marks * 100) if grade.total_marks > 0 else 0
            
            results_data.append({
                'id': grade.id,
                'subject': grade.subject.name if grade.subject else 'N/A',
                'exam_name': grade.exam_name,
                'exam_type': grade.exam_type,
                'date': grade.exam_date.isoformat(),
                'score': grade.score,
                'total_marks': grade.total_marks,
                'percentage': round(percentage, 1),
                'grade': grade.grade,
                'remarks': grade.remarks or ''
            })
        
        return Response({
            'success': True,
            'data': results_data
        })
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student profile not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_assignment(request):
    """
    Submit an assignment file
    """
    if request.user.role != 'student' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Student access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        student = Student.objects.get(user=request.user)
        assignment_id = request.data.get('assignment_id')
        
        if not assignment_id:
            return Response({
                'success': False,
                'error': 'Assignment ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        assignment = Assignment.objects.get(id=assignment_id)
        
        # For now, just return success
        # You can implement file upload and submission tracking later
        return Response({
            'success': True,
            'message': 'Assignment submission functionality coming soon'
        })
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Assignment.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Assignment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error submitting assignment: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_student_timetable_helper(class_obj):
    """
    Helper function to get timetable for a class
    """
    if not class_obj:
        return {'periods': [], 'days': []}
    
    timetable = Timetable.objects.filter(
        class_obj=class_obj,
        is_active=True
    ).first()
    
    if not timetable:
        return {'periods': [], 'days': []}
    
    entries = TimetableEntry.objects.filter(
        timetable=timetable
    ).select_related('subject', 'teacher', 'time_slot').order_by('time_slot__slot_order')
    
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    periods_dict = {}
    
    for entry in entries:
        time_key = entry.time_slot.name
        time_str = f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}"
        
        if time_key not in periods_dict:
            periods_dict[time_key] = {
                'time': time_str,
                'monday': None,
                'tuesday': None,
                'wednesday': None,
                'thursday': None,
                'friday': None
            }
        
        periods_dict[time_key][entry.day_of_week] = {
            'subject': entry.subject.name,
            'teacher': entry.teacher.get_full_name() if entry.teacher else 'TBA',
            'room': entry.room_number or 'TBA',
            'type': 'class'
        }
    
    return {
        'periods': list(periods_dict.values()),
        'days': days
    }