# apps/teachers/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta

from apps.accounts.models import User
from apps.academics.models import Class, Subject, ClassSubject, TeacherClassAssignment, Timetable, TimetableEntry
from apps.admissions.models import Student
from apps.attendance.models import Attendance, AttendanceRecord
from apps.grades.models import Assignment
from apps.grades.models import Grade

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_dashboard_data(request):
    """
    Get complete teacher dashboard data including classes, students, and statistics
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get teacher's assigned classes
        class_assignments = TeacherClassAssignment.objects.filter(
            teacher=user,
            is_active=True
        ).select_related('class_obj')
        
        my_classes = []
        total_students = 0
        
        for assignment in class_assignments:
            class_obj = assignment.class_obj
            
            # Get students in this class
            students_count = Student.objects.filter(
                current_class=class_obj,
                status='active'
            ).count()
            
            total_students += students_count
            
            # Get class subjects taught by this teacher
            class_subjects = ClassSubject.objects.filter(
                class_obj=class_obj,
                teacher=user
            ).select_related('subject')
            
            subjects = [cs.subject.name for cs in class_subjects]
            
            # Calculate average attendance for this class (last 30 days)
            thirty_days_ago = timezone.now().date() - timedelta(days=30)
            attendance_records = AttendanceRecord.objects.filter(
                attendance__class_obj=class_obj,
                attendance__date__gte=thirty_days_ago
            )
            
            total_records = attendance_records.count()
            present_records = attendance_records.filter(status='present').count()
            avg_attendance = (present_records / total_records * 100) if total_records > 0 else 0
            
            my_classes.append({
                'id': class_obj.id,
                'name': class_obj.name,
                'subject': ', '.join(subjects) if subjects else 'N/A',
                'total_students': students_count,
                'capacity': class_obj.capacity,
                'avg_attendance': round(avg_attendance, 1),
                'class_average': 75.0,  # TODO: Calculate from grades
                'is_class_teacher': assignment.is_class_teacher
            })
        
        # Get pending assignments
        pending_assignments = Assignment.objects.filter(
            teacher=user,
            due_date__gte=timezone.now().date()
        ).count()
        
        # Statistics
        stats = {
            'total_classes': len(my_classes),
            'total_students': total_students,
            'pending_assignments': pending_assignments,
            'avg_attendance': round(sum([c['avg_attendance'] for c in my_classes]) / len(my_classes), 1) if my_classes else 0
        }
        
        # Get today's schedule
        today = timezone.now().date()
        day_name = today.strftime('%A').lower()
        
        today_schedule = []
        for assignment in class_assignments:
            timetable = Timetable.objects.filter(
                class_obj=assignment.class_obj,
                is_active=True
            ).first()
            
            if timetable:
                entries = TimetableEntry.objects.filter(
                    timetable=timetable,
                    day_of_week=day_name,
                    teacher=user
                ).select_related('subject', 'time_slot').order_by('time_slot__slot_order')
                
                for entry in entries:
                    today_schedule.append({
                        'id': entry.id,
                        'time': f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
                        'class': assignment.class_obj.name,
                        'subject': entry.subject.name,
                        'class_id': assignment.class_obj.id,
                        'room': entry.room_number or 'TBA'
                    })
        
        # Sort by time
        today_schedule.sort(key=lambda x: x['time'])
        
        return Response({
            'success': True,
            'data': {
                'my_classes': my_classes,
                'stats': stats,
                'today_schedule': today_schedule
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error fetching dashboard data: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_class_students(request, class_id):
    """
    Get all students in a specific class for attendance marking
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_obj = Class.objects.get(id=class_id)
        
        # Verify teacher has access to this class
        has_access = TeacherClassAssignment.objects.filter(
            teacher=user,
            class_obj=class_obj,
            is_active=True
        ).exists()
        
        if not has_access and not user.is_superuser:
            return Response({
                'success': False,
                'error': 'You do not have access to this class'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get all active students in this class
        students = Student.objects.filter(
            current_class=class_obj,
            status='active'
        ).order_by('roll_number', 'first_name')
        
        students_data = []
        for student in students:
            students_data.append({
                'id': student.id,
                'name': f"{student.first_name} {student.last_name}",
                'roll_number': student.roll_number or 'N/A',
                'student_id': student.student_id,
                'attendance': None  # Will be set by frontend
            })
        
        return Response({
            'success': True,
            'data': {
                'class_name': class_obj.name,
                'students': students_data
            }
        })
        
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_attendance(request):
    """
    Save attendance records for a class
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_id = request.data.get('class_id')
        date_str = request.data.get('date')
        period = request.data.get('period', 1)
        attendance_records = request.data.get('attendance_records', [])
        
        if not all([class_id, date_str, attendance_records]):
            return Response({
                'success': False,
                'error': 'Missing required fields'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        class_obj = Class.objects.get(id=class_id)
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Verify teacher has access
        has_access = TeacherClassAssignment.objects.filter(
            teacher=user,
            class_obj=class_obj,
            is_active=True
        ).exists()
        
        if not has_access and not user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Create or get attendance record
        attendance, created = Attendance.objects.get_or_create(
            class_obj=class_obj,
            date=attendance_date,
            period=period,
            defaults={'marked_by': user}
        )
        
        # Save individual student attendance records
        for record in attendance_records:
            student_id = record.get('student_id')
            status_value = record.get('status')
            
            if student_id and status_value:
                student = Student.objects.get(id=student_id)
                AttendanceRecord.objects.update_or_create(
                    attendance=attendance,
                    student=student,
                    defaults={'status': status_value}
                )
        
        return Response({
            'success': True,
            'message': 'Attendance saved successfully'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error saving attendance: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_assignments(request):
    """
    Get all assignments created by the teacher
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    assignments = Assignment.objects.filter(
        teacher=user
    ).select_related('class_obj', 'subject').prefetch_related('submissions')
    
    assignments_data = []
    for assignment in assignments:
        total_students = Student.objects.filter(
            current_class=assignment.class_obj,
            status='active'
        ).count()
        
        submissions_count = assignment.submissions.count()
        
        status_value = 'active' if assignment.due_date >= timezone.now().date() else 'closed'
        
        assignments_data.append({
            'id': assignment.id,
            'title': assignment.title,
            'description': assignment.description,
            'class': assignment.class_obj.name,
            'subject': assignment.subject.name if assignment.subject else 'General',
            'due_date': assignment.due_date.isoformat(),
            'submissions': submissions_count,
            'total_students': total_students,
            'status': status_value
        })
    
    return Response({
        'success': True,
        'data': assignments_data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_timetable(request):
    """
    Get teacher's weekly timetable
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get all timetable entries for this teacher
    entries = TimetableEntry.objects.filter(
        teacher=user
    ).select_related('timetable__class_obj', 'subject', 'time_slot').order_by('time_slot__slot_order')
    
    # Organize by time slots
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
            'class': entry.timetable.class_obj.name,
            'subject': entry.subject.name
        }
    
    timetable_periods = list(periods_dict.values())
    
    return Response({
        'success': True,
        'data': timetable_periods
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_grades(request):
    """
    Save grades for multiple students in a class
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_id = request.data.get('class_id')
        subject_id = request.data.get('subject_id')
        exam_type = request.data.get('exam_type')
        exam_name = request.data.get('exam_name')
        exam_date_str = request.data.get('exam_date')
        total_marks = request.data.get('total_marks')
        grades_data = request.data.get('grades', [])
        
        # Validate required fields
        if not all([class_id, subject_id, exam_type, exam_name, exam_date_str, total_marks]):
            return Response({
                'success': False,
                'error': 'Missing required fields'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not grades_data:
            return Response({
                'success': False,
                'error': 'No grades provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get class and verify access
        class_obj = Class.objects.get(id=class_id)
        has_access = TeacherClassAssignment.objects.filter(
            teacher=user,
            class_obj=class_obj,
            is_active=True
        ).exists()
        
        if not has_access and not user.is_superuser:
            return Response({
                'success': False,
                'error': 'You do not have access to this class'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get subject
        subject = Subject.objects.get(id=subject_id)
        
        # Parse exam date
        exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        
        # Import Grade model (add this at the top of your file)
        from apps.grades.models import Grade
        
        # Save grades for each student
        saved_count = 0
        errors = []
        
        for grade_entry in grades_data:
            try:
                student_id = grade_entry.get('student_id')
                score = grade_entry.get('score')
                grade_letter = grade_entry.get('grade')
                
                if not all([student_id, score is not None, grade_letter]):
                    continue
                
                student = Student.objects.get(id=student_id)
                
                # Verify student is in the class
                if student.current_class != class_obj:
                    errors.append(f"Student {student.first_name} is not in this class")
                    continue
                
                # Create or update grade
                grade, created = Grade.objects.update_or_create(
                    student=student,
                    subject=subject,
                    class_obj=class_obj,
                    exam_type=exam_type,
                    exam_name=exam_name,
                    exam_date=exam_date,
                    defaults={
                        'score': float(score),
                        'total_marks': float(total_marks),
                        'grade': grade_letter,
                        'teacher': user,
                        'academic_year': timezone.now().year  # Adjust as needed
                    }
                )
                saved_count += 1
                
            except Student.DoesNotExist:
                errors.append(f"Student with ID {student_id} not found")
            except Exception as e:
                errors.append(f"Error saving grade for student {student_id}: {str(e)}")
        
        response_data = {
            'success': True,
            'message': f'Successfully saved {saved_count} grade(s)',
            'saved_count': saved_count
        }
        
        if errors:
            response_data['warnings'] = errors
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Subject.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Subject not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except ValueError as e:
        return Response({
            'success': False,
            'error': f'Invalid data format: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error saving grades: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)