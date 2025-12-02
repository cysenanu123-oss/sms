# apps/students/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db.models import Avg, Sum
from datetime import timedelta

from apps.admissions.models import Student
from apps.academics.models import ClassSubject, Timetable, TimetableEntry, SchoolSettings
from apps.grades.models import Assignment, Grade, AssignmentSubmission


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

    # Get current term from school settings
    school_settings = SchoolSettings.objects.first()
    if not school_settings:
        return Response({
            'success': False,
            'error': 'School settings not configured. Please contact admin.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    current_term = school_settings.current_term
    current_academic_year = school_settings.current_academic_year

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
        'academic_year': current_academic_year,
        'current_term': school_settings.get_current_term_display(),
        'term_start': school_settings.term_start_date.isoformat() if school_settings.term_start_date else None,
        'term_end': school_settings.term_end_date.isoformat() if school_settings.term_end_date else None,
        'email': request.user.email,
        'phone': request.user.phone or 'Not Provided'
    }
    
    # Get courses
    class_subjects = ClassSubject.objects.filter(
        class_obj=current_class,
    ).select_related('subject', 'teacher')
    
    courses = []
    for cs in class_subjects:
        # Get average grade for this subject (filtered by current term)
        subject_grades = Grade.objects.filter(
            student=student,
            subject=cs.subject,
            academic_year=current_academic_year,
            term=current_term
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
    
    # Get pending assignments (filtered by current term)
    pending_assignments = Assignment.objects.filter(
        class_obj=current_class,
        status='active',
        academic_year=current_academic_year,
        term=current_term
    ).select_related('subject').order_by('due_date')
    
    assignments_data = []
    for assignment in pending_assignments:
        # Check if submitted
        submission = AssignmentSubmission.objects.filter(assignment=assignment, student=student).first()

        if assignment.due_date:
            # Calculate days until due
            days_until_due = (assignment.due_date - timezone.now().date()).days
            
            if assignment.due_date < timezone.now().date():
                due_status = 'Overdue'
                status_color = 'red'
            elif days_until_due == 0:
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
            
            due_date_iso = assignment.due_date.isoformat()
        else:
            due_status = 'No due date'
            status_color = 'gray'
            due_date_iso = None

        assignments_data.append({
            'id': assignment.id,
            'title': assignment.title,
            'description': assignment.description,
            'subject': assignment.subject.name if assignment.subject else 'General',
            'due_date': due_date_iso,
            'due_status': due_status,
            'status_color': status_color,
            'total_marks': assignment.total_marks,
            'submitted': submission is not None,
            'submission_date': submission.submitted_at.isoformat() if submission else None,
            'submission_status': submission.status if submission else None,
            'status': assignment.status,
        })
    
    # Get recent test results (filtered by current term)
    recent_results = Grade.objects.filter(
        student=student,
        academic_year=current_academic_year,
        term=current_term
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

    # Average grade (for current term only)
    all_grades = Grade.objects.filter(
        student=student,
        academic_year=current_academic_year,
        term=current_term
    )
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
    
    # Attendance rate (for current term)
    try:
        from apps.attendance.models import AttendanceRecord

        attendance_records = AttendanceRecord.objects.filter(
            student=student,
            attendance__academic_year=current_academic_year,
            attendance__term=current_term
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
    
    # Get resources
    from apps.academics.models import TeachingResource
    resources = TeachingResource.objects.filter(
        class_obj=current_class,
        is_active=True
    ).select_related('subject', 'teacher').order_by('-created_at')
    
    resources_data = []
    for resource in resources:
        resources_data.append({
            'id': resource.id,
            'title': resource.title,
            'description': resource.description,
            'subject': resource.subject.name if resource.subject else 'General',
            'teacher': resource.teacher.get_full_name() if resource.teacher else 'N/A',
            'resource_type': resource.resource_type,
            'file_url': resource.file.url if resource.file else None,
            'external_link': resource.external_link,
            'created_at': resource.created_at.isoformat()
        })
    
    return Response({
        'success': True,
        'data': {
            'student_info': student_info,
            'courses': courses,
            'assignments': assignments_data,
            'recent_results': results_data,
            'timetable': timetable_data,
            'stats': stats,
            'resources': resources_data
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
    if request.user.role != 'student':
        return Response({'success': False, 'error': 'Student access required'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        student = Student.objects.get(user=request.user)
        assignment_id = request.data.get('assignment_id')
        file = request.FILES.get('file')

        if not assignment_id:
            return Response({'success': False, 'error': 'Assignment ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not file:
            return Response({'success': False, 'error': 'File is required'}, status=status.HTTP_400_BAD_REQUEST)

        assignment = Assignment.objects.get(id=assignment_id)

        # Check if assignment is closed
        if assignment.due_date is None:
            return Response({'success': False, 'error': 'Assignment has no due date.'}, status=status.HTTP_400_BAD_REQUEST)

        if assignment.status == 'closed' or assignment.due_date < timezone.now().date():
            return Response({'success': False, 'error': 'Assignment submission is closed.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create or update submission
        submission, created = AssignmentSubmission.objects.update_or_create(
            student=student,
            assignment=assignment,
            defaults={'file': file}
        )

        return Response({'success': True, 'message': 'Assignment submitted successfully!'})

    except Student.DoesNotExist:
        return Response({'success': False, 'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
    except Assignment.DoesNotExist:
        return Response({'success': False, 'error': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'error': f'Error submitting assignment: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_term_history(request):
    """
    Get list of all terms with data for this student
    """
    if request.user.role != 'student' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Student access required'
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        student = Student.objects.get(user=request.user)

        # Get unique term/year combinations from student's grades
        grade_terms = Grade.objects.filter(
            student=student
        ).values('academic_year', 'term').distinct().order_by('-academic_year', '-term')

        terms_list = []
        for item in grade_terms:
            academic_year = item['academic_year']
            term = item['term']

            # Get term display name
            term_display = dict([
                ('first', 'First Term'),
                ('second', 'Second Term'),
                ('third', 'Third Term')
            ]).get(term, term)

            # Get counts for this term
            grades_count = Grade.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term
            ).count()

            assignments_count = Assignment.objects.filter(
                class_obj=student.current_class,
                academic_year=academic_year,
                term=term
            ).count()

            # Check if this is the current term
            school_settings = SchoolSettings.objects.first()
            is_current = (
                school_settings and
                school_settings.current_term == term and
                school_settings.current_academic_year == academic_year
            )

            terms_list.append({
                'academic_year': academic_year,
                'term': term,
                'term_display': term_display,
                'grades_count': grades_count,
                'assignments_count': assignments_count,
                'is_current': is_current
            })

        return Response({
            'success': True,
            'data': terms_list
        })

    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student profile not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_term_data(request):
    """
    Get student data for a specific term
    Query params: academic_year, term
    """
    if request.user.role != 'student' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Student access required'
        }, status=status.HTTP_403_FORBIDDEN)

    academic_year = request.query_params.get('academic_year')
    term = request.query_params.get('term')

    if not academic_year or not term:
        return Response({
            'success': False,
            'error': 'academic_year and term parameters are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        student = Student.objects.get(user=request.user)

        # Get grades for this term
        grades = Grade.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).select_related('subject').order_by('-exam_date')

        grades_data = []
        for grade in grades:
            percentage = (grade.score / grade.total_marks * 100) if grade.total_marks > 0 else 0

            grades_data.append({
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

        # Get assignments for this term
        assignments = Assignment.objects.filter(
            class_obj=student.current_class,
            academic_year=academic_year,
            term=term
        ).select_related('subject').order_by('-due_date')

        assignments_data = []
        for assignment in assignments:
            # Check if submitted
            submission = AssignmentSubmission.objects.filter(
                assignment=assignment,
                student=student
            ).first()

            assignments_data.append({
                'id': assignment.id,
                'title': assignment.title,
                'subject': assignment.subject.name if assignment.subject else 'General',
                'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
                'total_marks': assignment.total_marks,
                'submitted': submission is not None,
                'score': submission.score if submission else None,
                'status': submission.status if submission else 'Not Submitted'
            })

        # Calculate term average
        if grades:
            total_score = sum(g.score for g in grades)
            total_possible = sum(g.total_marks for g in grades)
            term_average = round((total_score / total_possible * 100), 1) if total_possible > 0 else 0
        else:
            term_average = 0

        # Get term display name
        term_display = dict([
            ('first', 'First Term'),
            ('second', 'Second Term'),
            ('third', 'Third Term')
        ]).get(term, term)

        return Response({
            'success': True,
            'data': {
                'term_info': {
                    'academic_year': academic_year,
                    'term': term,
                    'term_display': term_display
                },
                'grades': grades_data,
                'assignments': assignments_data,
                'statistics': {
                    'term_average': term_average,
                    'total_grades': len(grades_data),
                    'total_assignments': len(assignments_data)
                }
            }
        })

    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student profile not found'
        }, status=status.HTTP_404_NOT_FOUND)


def get_student_timetable_helper(class_obj):
    """
    Helper function to get timetable for a class
    FIXED VERSION - Returns complete subject and teacher information
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
    
    print(f"📊 Found {entries.count()} timetable entries for {class_obj.name}")
    
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
        
        # Get the day in lowercase to match our dictionary keys
        day_lower = entry.day_of_week.lower()
        
        # ✅ FIX: Make sure we're returning complete information
        if entry.subject and entry.teacher:
            periods_dict[time_key][day_lower] = {
                'subject': entry.subject.name,
                'teacher': entry.teacher.get_full_name(),
                'room': entry.room_number or 'TBA',
                'type': 'class'
            }
            print(f"✅ Added: {day_lower.capitalize()} {time_str} - {entry.subject.name} by {entry.teacher.get_full_name()}")
        elif entry.time_slot.is_break:
            periods_dict[time_key][day_lower] = {
                'subject': 'Break',
                'teacher': '',
                'room': '',
                'type': 'break'
            }
        else:
            print(f"⚠️ Incomplete entry: {day_lower.capitalize()} {time_str} - Missing subject or teacher")
    
    print(f"📋 Returning {len(periods_dict)} periods")
    
    return {
        'periods': list(periods_dict.values()),
        'days': days
    }