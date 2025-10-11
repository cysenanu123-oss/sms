# apps/teachers/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction
from apps.accounts.models import User
from apps.academics.models import Class, Subject, ClassSubject, TeacherClassAssignment, Timetable, TimetableEntry
from apps.admissions.models import Student
from apps.attendance.models import Attendance, AttendanceRecord
from apps.grades.models import Assignment
from apps.grades.models import Grade
from apps.admissions.email_utils import send_teacher_credentials_email
import secrets


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



@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manage_teachers(request):
    """Get all teachers or create a new teacher"""
    
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        teachers = User.objects.filter(role='teacher', is_active=True)
        
        teachers_data = []
        for teacher in teachers:
            # Get assigned subjects
            subject_assignments = ClassSubject.objects.filter(teacher=teacher, is_active=True)
            subjects = list(set([cs.subject.name for cs in subject_assignments]))
            
            # Get assigned classes
            class_assignments = TeacherClassAssignment.objects.filter(
                teacher=teacher, 
                is_active=True
            )
            classes_count = class_assignments.count()
            
            # Count total students across all classes
            total_students = sum([
                assignment.class_obj.student_set.filter(status='active').count() 
                for assignment in class_assignments
            ])
            
            teachers_data.append({
                'id': teacher.id,
                'full_name': teacher.get_full_name(),
                'first_name': teacher.first_name,
                'last_name': teacher.last_name,
                'email': teacher.email,
                'phone': teacher.phone or '',
                'subjects': subjects,
                'total_classes': classes_count,
                'total_students': total_students,
                'is_active': teacher.is_active
            })
        
        return Response({
            'success': True,
            'data': teachers_data
        })
    
    elif request.method == 'POST':
        # ✅ FIXED: Create teacher with email sending
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        email = request.data.get('email')
        phone = request.data.get('phone', '')
        subject_ids = request.data.get('subjects', [])
        class_ids = request.data.get('classes', [])
        
        if not all([first_name, last_name, email]):
            return Response({
                'success': False,
                'error': 'First name, last name, and email are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=email).exists():
            return Response({
                'success': False,
                'error': 'A user with this email already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Generate username
                base_username = f"{first_name.lower()}.{last_name.lower()}"
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # ✅ Generate temporary password
                temp_password = secrets.token_urlsafe(12)
                
                # ✅ Create user with the temp password
                teacher_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=temp_password,  # ✅ This will hash it properly
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    role='teacher',
                    is_active=True,
                    must_change_password=True  # ✅ Force password change on first login
                )
                
                # Assign subjects
                subjects_list = []
                for subject_id in subject_ids:
                    try:
                        subject = Subject.objects.get(id=subject_id)
                        subjects_list.append(subject.name)
                    except Subject.DoesNotExist:
                        continue
                
                # Assign classes
                classes_list = []
                for class_id in class_ids:
                    try:
                        class_obj = Class.objects.get(id=class_id)
                        classes_list.append(class_obj.name)
                        
                        # Create class assignment
                        TeacherClassAssignment.objects.create(
                            teacher=teacher_user,
                            class_obj=class_obj,
                            is_class_teacher=False,
                            is_active=True
                        )
                        
                        # Assign subjects to this class
                        for subject_id in subject_ids:
                            try:
                                subject = Subject.objects.get(id=subject_id)
                                ClassSubject.objects.update_or_create(
                                    class_obj=class_obj,
                                    subject=subject,
                                    defaults={
                                        'teacher': teacher_user,
                                        'is_active': True
                                    }
                                )
                            except Subject.DoesNotExist:
                                continue
                                
                    except Class.DoesNotExist:
                        continue
                
                # ✅ SEND EMAIL WITH CREDENTIALS
                try:
                    email_sent = send_teacher_credentials_email(
                        teacher_user=teacher_user,
                        username=username,
                        password=temp_password,
                        subjects=subjects_list,
                        classes=classes_list
                    )
                    
                    if email_sent:
                        print(f"✅ Teacher credentials email sent to {email}")
                    else:
                        print(f"⚠️ Email sending failed for {email}")
                        
                except Exception as email_error:
                    print(f"⚠️ Email error: {str(email_error)}")
                    # Don't fail the whole operation if email fails
                
                return Response({
                    'success': True,
                    'message': 'Teacher created successfully! Credentials have been sent via email.',
                    'data': {
                        'teacher_id': teacher_user.id,
                        'username': username,
                        'temporary_password': temp_password,  # ✅ Show in response too
                        'email': email,
                        'subjects_assigned': len(subjects_list),
                        'classes_assigned': len(classes_list),
                        'email_sent': email_sent
                    }
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'success': False,
                'error': f'Error creating teacher: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_teacher(request, teacher_id):
    """Deactivate a teacher"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        teacher = User.objects.get(id=teacher_id, role='teacher')
        
        # Deactivate instead of delete
        teacher.is_active = False
        teacher.save()
        
        # Deactivate assignments
        TeacherClassAssignment.objects.filter(teacher=teacher).update(is_active=False)
        ClassSubject.objects.filter(teacher=teacher).update(is_active=False)
        
        return Response({
            'success': True,
            'message': 'Teacher deactivated successfully'
        })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Teacher not found'
        }, status=status.HTTP_404_NOT_FOUND)





@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_timetable(request):
    """Get timetable for logged-in teacher"""
    if request.user.role != 'teacher':
        return Response({'success': False, 'error': 'Teacher access only'}, status=403)
    
    try:
        # Get all timetable entries where this teacher is assigned
        entries = TimetableEntry.objects.filter(
            teacher=request.user
        ).select_related('timetable__class_obj', 'subject', 'time_slot').order_by(
            'day_of_week', 'time_slot__start_time'
        )
        
        # Organize by day and time
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        timetable_data = {}
        
        for day in days:
            timetable_data[day] = []
        
        for entry in entries:
            day = entry.day_of_week
            if day in timetable_data:
                timetable_data[day].append({
                    'id': entry.id,
                    'time_slot': entry.time_slot.name,
                    'start_time': entry.time_slot.start_time.strftime('%H:%M'),
                    'end_time': entry.time_slot.end_time.strftime('%H:%M'),
                    'subject': entry.subject.name if entry.subject else 'Break',
                    'class': entry.timetable.class_obj.name,
                    'room': entry.room_number or '-'
                })
        
        # Get today's schedule
        today = datetime.now().strftime('%A')
        today_schedule = timetable_data.get(today, [])
        
        # Get teacher's class assignments for quick stats
        class_assignments = TeacherClassAssignment.objects.filter(
            teacher=request.user,
            is_active=True
        ).select_related('class_obj', 'subject')
        
        assigned_classes = []
        for assignment in class_assignments:
            assigned_classes.append({
                'class_id': assignment.class_obj.id,
                'class_name': assignment.class_obj.name,
                'subject': assignment.subject.name if assignment.subject else 'All Subjects',
                'is_class_teacher': assignment.is_class_teacher
            })
        
        return Response({
            'success': True,
            'data': {
                'weekly_timetable': timetable_data,
                'today_schedule': today_schedule,
                'today': today,
                'assigned_classes': assigned_classes,
                'total_periods_per_week': entries.count()
            }
        })
        
    except Exception as e:
        print(f"Error loading teacher timetable: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Error loading timetable: {str(e)}'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_today_classes(request):
    """Get today's classes for teacher - for quick dashboard view"""
    if request.user.role != 'teacher':
        return Response({'success': False, 'error': 'Teacher access only'}, status=403)
    
    try:
        today = datetime.now().strftime('%A')
        
        entries = TimetableEntry.objects.filter(
            teacher=request.user,
            day_of_week=today
        ).select_related('timetable__class_obj', 'subject', 'time_slot').order_by(
            'time_slot__start_time'
        )
        
        today_classes = []
        for entry in entries:
            today_classes.append({
                'id': entry.id,
                'time': f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
                'class': entry.timetable.class_obj.name,
                'subject': entry.subject.name if entry.subject else 'Break',
                'room': entry.room_number or 'TBA',
                'class_id': entry.timetable.class_obj.id
            })
        
        return Response({
            'success': True,
            'data': today_classes
        })
        
    except Exception as e:
        print(f"Error loading today's classes: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def promote_students(request):
    """
    Allow class teachers to promote their students to the next class
    """
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from_class_id = request.data.get('from_class_id')
        to_class_id = request.data.get('to_class_id')
        academic_year = request.data.get('academic_year')
        student_ids = request.data.get('student_ids', [])
        
        if not all([from_class_id, to_class_id, academic_year, student_ids]):
            return Response({
                'success': False,
                'error': 'All fields are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get classes
        from_class = Class.objects.get(id=from_class_id)
        to_class = Class.objects.get(id=to_class_id)
        
        # ✅ VERIFY: Teacher is the class teacher for from_class
        is_class_teacher = TeacherClassAssignment.objects.filter(
            teacher=user,
            class_obj=from_class,
            is_class_teacher=True,
            is_active=True
        ).exists()
        
        if not is_class_teacher and not user.is_superuser:
            return Response({
                'success': False,
                'error': 'Only the class teacher can promote students from this class'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Promote students
        promoted_count = 0
        errors = []
        
        with transaction.atomic():
            for student_id in student_ids:
                try:
                    student = Student.objects.get(id=student_id)
                    
                    # Verify student is in from_class
                    if student.current_class != from_class:
                        errors.append(f'{student.first_name} {student.last_name} is not in the source class')
                        continue
                    
                    # Create promotion record
                    from apps.admissions.models import StudentPromotion
                    StudentPromotion.objects.create(
                        student=student,
                        from_class=from_class,
                        to_class=to_class,
                        academic_year=academic_year,
                        promotion_type='promoted',
                        promoted_by=user
                    )
                    
                    # ✅ UPDATE STUDENT'S CURRENT CLASS
                    student.current_class = to_class
                    student.academic_year = academic_year
                    student.save()
                    
                    promoted_count += 1
                    
                except Student.DoesNotExist:
                    errors.append(f'Student {student_id} not found')
                except Exception as e:
                    errors.append(f'Error promoting student {student_id}: {str(e)}')
        
        response_data = {
            'success': True,
            'message': f'Successfully promoted {promoted_count} student(s)',
            'promoted_count': promoted_count,
            'from_class': from_class.name,
            'to_class': to_class.name
        }
        
        if errors:
            response_data['errors'] = errors
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Error promoting students: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)