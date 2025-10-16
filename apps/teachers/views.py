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
from apps.grades.models import Assignment, Grade
from apps.admissions.email_utils import send_teacher_credentials_email
import secrets
from django.http import HttpResponse
import csv
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from apps.grades.models import AssignmentSubmission, Exam, ExamResult


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_dashboard_data(request):
    """Get complete teacher dashboard data"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_assignments = TeacherClassAssignment.objects.filter(
            teacher=user,
            is_active=True
        ).select_related('class_obj')
        
        my_classes = []
        total_students = 0
        
        for assignment in class_assignments:
            class_obj = assignment.class_obj
            students_count = Student.objects.filter(
                current_class=class_obj,
                status='active'
            ).count()
            
            total_students += students_count
            
            class_subjects = ClassSubject.objects.filter(
                class_obj=class_obj,
                teacher=user
            ).select_related('subject')
            
            subjects = [cs.subject.name for cs in class_subjects]
            
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
                'class_average': 75.0,
                'is_class_teacher': assignment.is_class_teacher
            })
        
        pending_assignments = Assignment.objects.filter(
            teacher=user,
            due_date__gte=timezone.now().date()
        ).count()
        
        stats = {
            'total_classes': len(my_classes),
            'total_students': total_students,
            'pending_assignments': pending_assignments,
            'avg_attendance': round(sum([c['avg_attendance'] for c in my_classes]) / len(my_classes), 1) if my_classes else 0
        }
        
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
    """Get all students in a specific class"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
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
                'attendance': None
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
    """Save attendance records"""
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
        
        attendance, created = Attendance.objects.get_or_create(
            class_obj=class_obj,
            date=attendance_date,
            period=period,
            defaults={'marked_by': user}
        )
        
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
    """Get all assignments created by teacher"""
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_grades(request):
    """
    ✅ FIXED: Save grades with proper academic_year handling
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
        
        subject = Subject.objects.get(id=subject_id)
        exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        
        # ✅ Get academic year from class or use current year
        academic_year = getattr(class_obj, 'academic_year', f"{timezone.now().year}-{timezone.now().year + 1}")
        
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
                
                if student.current_class != class_obj:
                    errors.append(f"Student {student.first_name} is not in this class")
                    continue
                
                # ✅ FIXED: Create or update grade with proper fields
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
                        'academic_year': academic_year
                    }
                )
                saved_count += 1
                
                print(f"✅ Saved grade for {student.first_name}: {score}/{total_marks} = {grade_letter}")
                
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
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Error saving grades: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manage_teachers(request):
    """Get all teachers or create new teacher"""
    
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        teachers = User.objects.filter(role='teacher', is_active=True)
        
        teachers_data = []
        for teacher in teachers:
            subject_assignments = ClassSubject.objects.filter(teacher=teacher, is_active=True)
            subjects = list(set([cs.subject.name for cs in subject_assignments]))
            
            class_assignments = TeacherClassAssignment.objects.filter(
                teacher=teacher, 
                is_active=True
            )
            classes_count = class_assignments.count()
            
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
                base_username = f"{first_name.lower()}.{last_name.lower()}"
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                temp_password = secrets.token_urlsafe(12)
                
                teacher_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=temp_password,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    role='teacher',
                    is_active=True,
                    must_change_password=True
                )
                
                subjects_list = []
                for subject_id in subject_ids:
                    try:
                        subject = Subject.objects.get(id=subject_id)
                        subjects_list.append(subject.name)
                    except Subject.DoesNotExist:
                        continue
                
                classes_list = []
                for class_id in class_ids:
                    try:
                        class_obj = Class.objects.get(id=class_id)
                        classes_list.append(class_obj.name)
                        
                        TeacherClassAssignment.objects.create(
                            teacher=teacher_user,
                            class_obj=class_obj,
                            is_class_teacher=False,
                            is_active=True
                        )
                        
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
                
                return Response({
                    'success': True,
                    'message': 'Teacher created successfully! Credentials have been sent via email.',
                    'data': {
                        'teacher_id': teacher_user.id,
                        'username': username,
                        'temporary_password': temp_password,
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
        
        teacher.is_active = False
        teacher.save()
        
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
    """Get teacher's weekly timetable"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        entries = TimetableEntry.objects.filter(
            teacher=user
        ).select_related('timetable__class_obj', 'subject', 'time_slot').order_by(
            'time_slot__slot_order'
        )
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        time_slots = {}
        
        for entry in entries:
            time_key = entry.time_slot.name
            time_str = f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}"
            
            if time_key not in time_slots:
                time_slots[time_key] = {
                    'time': time_str,
                    'start_time': entry.time_slot.start_time.strftime('%H:%M'),
                    'end_time': entry.time_slot.end_time.strftime('%H:%M'),
                    'Monday': None,
                    'Tuesday': None,
                    'Wednesday': None,
                    'Thursday': None,
                    'Friday': None
                }
            
            day = entry.day_of_week.capitalize()
            
            if day in days:
                time_slots[time_key][day] = {
                    'class': entry.timetable.class_obj.name,
                    'subject': entry.subject.name if entry.subject else 'Break',
                    'room': entry.room_number or 'TBA',
                    'class_id': entry.timetable.class_obj.id
                }
        
        timetable_periods = list(time_slots.values())
        
        today = timezone.now().strftime('%A')
        today_schedule = []
        
        for period in timetable_periods:
            if period.get(today):
                today_schedule.append({
                    'time': period['time'],
                    'class': period[today]['class'],
                    'subject': period[today]['subject'],
                    'room': period[today]['room'],
                    'class_id': period[today].get('class_id')
                })
        
        return Response({
            'success': True,
            'data': {
                'weekly_timetable': {
                    'Monday': [p for p in timetable_periods if p.get('Monday')],
                    'Tuesday': [p for p in timetable_periods if p.get('Tuesday')],
                    'Wednesday': [p for p in timetable_periods if p.get('Wednesday')],
                    'Thursday': [p for p in timetable_periods if p.get('Thursday')],
                    'Friday': [p for p in timetable_periods if p.get('Friday')]
                },
                'today_schedule': today_schedule,
                'today': today,
                'total_periods_per_week': entries.count()
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Error loading timetable: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def promote_students(request):
    """Promote students to next class"""
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
        
        from_class = Class.objects.get(id=from_class_id)
        to_class = Class.objects.get(id=to_class_id)
        
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
        
        promoted_count = 0
        errors = []
        
        with transaction.atomic():
            for student_id in student_ids:
                try:
                    student = Student.objects.get(id=student_id)
                    
                    if student.current_class != from_class:
                        errors.append(f'{student.first_name} {student.last_name} is not in the source class')
                        continue
                    
                    from apps.admissions.models import StudentPromotion
                    StudentPromotion.objects.create(
                        student=student,
                        from_class=from_class,
                        to_class=to_class,
                        academic_year=academic_year,
                        promotion_type='promoted',
                        promoted_by=user
                    )
                    
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_promotion_eligible_students(request, class_id):
    """Get list of students eligible for promotion"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_obj = Class.objects.get(id=class_id)
        
        is_class_teacher = TeacherClassAssignment.objects.filter(
            teacher=user,
            class_obj=class_obj,
            is_class_teacher=True,
            is_active=True
        ).exists()
        
        if not is_class_teacher and not user.is_superuser:
            return Response({
                'success': False,
                'error': 'Only the class teacher can view promotion-eligible students'
            }, status=status.HTTP_403_FORBIDDEN)
        
        students = Student.objects.filter(
            current_class=class_obj,
            status='active'
        ).order_by('roll_number', 'first_name')
        
        students_data = []
        for student in students:
            grades = Grade.objects.filter(student=student)
            
            if grades.exists():
                total_score = sum(g.score for g in grades)
                total_marks = sum(g.total_marks for g in grades)
                avg_percentage = (total_score / total_marks * 100) if total_marks > 0 else 0
            else:
                avg_percentage = 0
            
            attendance_records = AttendanceRecord.objects.filter(student=student)
            total_days = attendance_records.count()
            present_days = attendance_records.filter(status='present').count()
            attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0
            
            students_data.append({
                'id': student.id,
                'student_id': student.student_id,
                'name': f"{student.first_name} {student.last_name}",
                'roll_number': student.roll_number or 'N/A',
                'average_grade': round(avg_percentage, 1),
                'attendance_rate': round(attendance_rate, 1),
                'eligible': avg_percentage >= 40 and attendance_rate >= 75
            })
        
        return Response({
            'success': True,
            'data': {
                'class_name': class_obj.name,
                'students': students_data,
                'total_students': len(students_data),
                'eligible_count': len([s for s in students_data if s['eligible']])
            }
        })
        
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_subjects(request):
    """Get all subjects taught by teacher"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_subjects = ClassSubject.objects.filter(
            teacher=user,
            is_active=True
        ).select_related('subject').distinct()
        
        subjects_dict = {}
        for cs in class_subjects:
            if cs.subject.id not in subjects_dict:
                subjects_dict[cs.subject.id] = {
                    'id': cs.subject.id,
                    'name': cs.subject.name,
                    'code': cs.subject.code if hasattr(cs.subject, 'code') else '',
                    'description': cs.subject.description if hasattr(cs.subject, 'description') else ''
                }
        
        subjects_list = list(subjects_dict.values())
        
        return Response({
            'success': True,
            'data': subjects_list
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Error fetching subjects: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_assignment(request):
    """Create a new assignment"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        title = request.data.get('title')
        description = request.data.get('description')
        class_id = request.data.get('class_id')
        subject_id = request.data.get('subject_id')
        due_date_str = request.data.get('due_date')
        total_marks = request.data.get('total_marks')
        instructions = request.data.get('instructions', '')
        attachment = request.FILES.get('attachment')
        
        if not all([title, description, class_id, due_date_str, total_marks]):
            return Response({
                'success': False,
                'error': 'Missing required fields'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            class_obj = Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Class not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
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
        
        subject = None
        if subject_id:
            try:
                subject = Subject.objects.get(id=subject_id)
            except Subject.DoesNotExist:
                pass
        
        try:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'success': False,
                'error': 'Invalid date format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        assignment = Assignment.objects.create(
            title=title,
            description=description,
            instructions=instructions,
            class_obj=class_obj,
            subject=subject,
            teacher=user,
            due_date=due_date,
            total_marks=float(total_marks),
            status='active'
        )
        
        if attachment:
            assignment.attachment = attachment
            assignment.save()
        
        total_students = Student.objects.filter(
            current_class=class_obj,
            status='active'
        ).count()
        
        return Response({
            'success': True,
            'message': 'Assignment created successfully',
            'data': {
                'id': assignment.id,
                'title': assignment.title,
                'description': assignment.description,
                'class': class_obj.name,
                'subject': subject.name if subject else 'General',
                'due_date': assignment.due_date.isoformat(),
                'total_marks': assignment.total_marks,
                'total_students': total_students,
                'status': 'active'
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Error creating assignment: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_assignment(request, assignment_id):
    """Delete an assignment"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        assignment = Assignment.objects.get(id=assignment_id)
        
        if assignment.teacher != user and not user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        submissions_count = assignment.submissions.count()
        if submissions_count > 0:
            return Response({
                'success': False,
                'error': f'Cannot delete assignment with {submissions_count} submissions'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        assignment.status = 'deleted'
        assignment.save()
        
        return Response({
            'success': True,
            'message': 'Assignment deleted successfully'
        })
        
    except Assignment.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Assignment not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_assignment_status(request, assignment_id):
    """Update assignment status"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        assignment = Assignment.objects.get(id=assignment_id)
        
        if assignment.teacher != user and not user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        new_status = request.data.get('status')
        if new_status not in ['active', 'closed']:
            return Response({
                'success': False,
                'error': 'Invalid status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        assignment.status = new_status
        assignment.save()
        
        return Response({
            'success': True,
            'message': f'Assignment status updated to {new_status}'
        })
        
    except Assignment.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Assignment not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_assignment_submissions(request, assignment_id):
    """Get all submissions for an assignment"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        assignment = Assignment.objects.select_related(
            'class_obj', 'subject', 'teacher'
        ).get(id=assignment_id)
        
        if assignment.teacher != user and not user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        submissions = assignment.submissions.select_related('student').all()
        all_students = Student.objects.filter(
            current_class=assignment.class_obj,
            status='active'
        )
        
        submissions_data = []
        for student in all_students:
            submission = submissions.filter(student=student).first()
            
            submissions_data.append({
                'student_id': student.id,
                'student_name': f"{student.first_name} {student.last_name}",
                'roll_number': student.roll_number or 'N/A',
                'submitted': submission is not None,
                'submission_date': submission.submitted_at.isoformat() if submission else None,
                'score': submission.score if submission and submission.score else None,
                'status': 'graded' if submission and submission.score else 'submitted' if submission else 'pending'
            })
        
        return Response({
            'success': True,
            'data': {
                'assignment': {
                    'id': assignment.id,
                    'title': assignment.title,
                    'due_date': assignment.due_date.isoformat(),
                    'total_marks': assignment.total_marks
                },
                'submissions': submissions_data,
                'stats': {
                    'total_students': len(all_students),
                    'submitted': len([s for s in submissions_data if s['submitted']]),
                    'pending': len([s for s in submissions_data if not s['submitted']]),
                    'graded': len([s for s in submissions_data if s['status'] == 'graded'])
                }
            }
        })
        
    except Assignment.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Assignment not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_resource(request):
    """Upload teaching resource"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        title = request.data.get('title')
        description = request.data.get('description', '')
        class_id = request.data.get('class_id')
        subject_id = request.data.get('subject_id')
        resource_type = request.data.get('resource_type')
        
        if not all([title, class_id, resource_type]):
            return Response({
                'success': False,
                'error': 'Missing required fields'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        class_obj = Class.objects.get(id=class_id)
        subject_obj = Subject.objects.get(id=subject_id) if subject_id else None
        
        file_upload = None
        external_link = None
        
        if resource_type in ['pdf', 'video']:
            file_upload = request.FILES.get('file')
            if not file_upload:
                return Response({
                    'success': False,
                    'error': 'File is required for this resource type'
                }, status=status.HTTP_400_BAD_REQUEST)
        elif resource_type == 'link':
            external_link = request.data.get('link')
            if not external_link:
                return Response({
                    'success': False,
                    'error': 'Link is required for this resource type'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        from apps.academics.models import TeachingResource
        
        resource = TeachingResource.objects.create(
            title=title,
            description=description,
            class_obj=class_obj,
            subject=subject_obj,
            teacher=user,
            resource_type=resource_type,
            file=file_upload,
            external_link=external_link
        )
        
        return Response({
            'success': True,
            'message': 'Resource uploaded successfully',
            'data': {
                'id': resource.id,
                'title': resource.title,
                'resource_type': resource.resource_type
            }
        }, status=status.HTTP_201_CREATED)
        
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error uploading resource: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_resources(request):
    """Get all resources uploaded by teacher"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from apps.academics.models import TeachingResource
        
        resources = TeachingResource.objects.filter(
            teacher=user
        ).select_related('class_obj', 'subject').order_by('-created_at')
        
        resources_data = []
        for resource in resources:
            resources_data.append({
                'id': resource.id,
                'title': resource.title,
                'description': resource.description,
                'class': resource.class_obj.name,
                'subject': resource.subject.name if resource.subject else 'General',
                'resource_type': resource.resource_type,
                'file_url': resource.file.url if resource.file else None,
                'external_link': resource.external_link,
                'created_at': resource.created_at.isoformat()
            })
        
        return Response({
            'success': True,
            'data': resources_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error fetching resources: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ NEW: Delete resource endpoint
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_resource(request, resource_id):
    """Delete a teaching resource"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from apps.academics.models import TeachingResource
        
        resource = TeachingResource.objects.get(id=resource_id)
        
        if resource.teacher != user and not user.is_superuser:
            return Response({
                'success': False,
                'error': 'You can only delete your own resources'
            }, status=status.HTTP_403_FORBIDDEN)
        
        resource.delete()
        
        return Response({
            'success': True,
            'message': 'Resource deleted successfully'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error deleting resource: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_attendance_report(request):
    """Download attendance report"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_id = request.GET.get('class_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        format_type = request.GET.get('format', 'csv')
        
        if not all([class_id, start_date, end_date]):
            return Response({
                'success': False,
                'error': 'Missing required parameters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        class_obj = Class.objects.get(id=class_id)
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        students = Student.objects.filter(
            current_class=class_obj,
            status='active'
        ).order_by('roll_number')
        
        attendances = Attendance.objects.filter(
            class_obj=class_obj,
            date__gte=start,
            date__lte=end
        ).order_by('date')
        
        if format_type == 'csv':
            return generate_csv_attendance_report(class_obj, students, attendances, start, end)
        else:
            return generate_pdf_attendance_report(class_obj, students, attendances, start, end)
            
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error generating report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def generate_csv_attendance_report(class_obj, students, attendances, start_date, end_date):
    """Generate CSV attendance report"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{class_obj.name}_{start_date}_{end_date}.csv"'
    
    writer = csv.writer(response)
    
    writer.writerow(['Attendance Report'])
    writer.writerow([f'Class: {class_obj.name}'])
    writer.writerow([f'Period: {start_date} to {end_date}'])
    writer.writerow([])
    
    dates = attendances.values_list('date', flat=True).distinct().order_by('date')
    
    headers = ['Roll No', 'Student Name'] + [date.strftime('%Y-%m-%d') for date in dates] + ['Present', 'Absent', 'Late', 'Attendance %']
    writer.writerow(headers)
    
    for student in students:
        row = [student.roll_number or 'N/A', f"{student.first_name} {student.last_name}"]
        
        present_count = 0
        absent_count = 0
        late_count = 0
        
        for date in dates:
            attendance = attendances.filter(date=date).first()
            if attendance:
                record = AttendanceRecord.objects.filter(
                    attendance=attendance,
                    student=student
                ).first()
                
                if record:
                    row.append(record.status.upper()[0])
                    if record.status == 'present':
                        present_count += 1
                    elif record.status == 'absent':
                        absent_count += 1
                    elif record.status == 'late':
                        late_count += 1
                else:
                    row.append('-')
            else:
                row.append('-')
        
        total_days = len(dates)
        attendance_percentage = (present_count / total_days * 100) if total_days > 0 else 0
        
        row.extend([present_count, absent_count, late_count, f"{attendance_percentage:.1f}%"])
        writer.writerow(row)
    
    return response


def generate_pdf_attendance_report(class_obj, students, attendances, start_date, end_date):
    """Generate PDF attendance report"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph(f"<b>Attendance Report - {class_obj.name}</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    period = Paragraph(f"Period: {start_date} to {end_date}", styles['Normal'])
    elements.append(period)
    elements.append(Spacer(1, 20))
    
    total_students = students.count()
    dates = attendances.values_list('date', flat=True).distinct()
    total_days = len(dates)
    
    summary_data = [
        ['Total Students', str(total_students)],
        ['Total Days', str(total_days)],
        ['Report Generated', timezone.now().strftime('%Y-%m-%d %H:%M')]
    ]
    
    summary_table = Table(summary_data, colWidths=[150, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    table_data = [['Roll No', 'Student Name', 'Present', 'Absent', 'Late', 'Attendance %']]
    
    for student in students:
        present = AttendanceRecord.objects.filter(
            attendance__in=attendances,
            student=student,
            status='present'
        ).count()
        
        absent = AttendanceRecord.objects.filter(
            attendance__in=attendances,
            student=student,
            status='absent'
        ).count()
        
        late = AttendanceRecord.objects.filter(
            attendance__in=attendances,
            student=student,
            status='late'
        ).count()
        
        percentage = (present / total_days * 100) if total_days > 0 else 0
        
        table_data.append([
            student.roll_number or 'N/A',
            f"{student.first_name} {student.last_name}",
            str(present),
            str(absent),
            str(late),
            f"{percentage:.1f}%"
        ])
    
    attendance_table = Table(table_data, colWidths=[60, 150, 50, 50, 50, 80])
    attendance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(attendance_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{class_obj.name}_{start_date}_{end_date}.pdf"'
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_performance_report(request):
    """Download performance report"""
    user = request.user
    
    if user.role != 'teacher' and not user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        class_id = request.GET.get('class_id')
        report_type = request.GET.get('report_type', 'midterm')
        format_type = request.GET.get('format', 'pdf')
        
        if not class_id:
            return Response({
                'success': False,
                'error': 'Class ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        class_obj = Class.objects.get(id=class_id)
        students = Student.objects.filter(
            current_class=class_obj,
            status='active'
        ).order_by('roll_number')
        
        exams = Exam.objects.filter(
            class_obj=class_obj,
            exam_type=report_type
        )
        
        if format_type == 'csv':
            return generate_csv_performance_report(class_obj, students, exams, report_type)
        else:
            return generate_pdf_performance_report(class_obj, students, exams, report_type)
            
    except Class.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Class not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error generating report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def generate_csv_performance_report(class_obj, students, exams, report_type):
    """Generate CSV performance report"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="performance_report_{class_obj.name}_{report_type}.csv"'
    
    writer = csv.writer(response)
    
    writer.writerow(['Performance Report'])
    writer.writerow([f'Class: {class_obj.name}'])
    writer.writerow([f'Report Type: {report_type.title()}'])
    writer.writerow([])
    
    subjects = exams.values_list('subject__name', flat=True).distinct()
    
    headers = ['Roll No', 'Student Name'] + list(subjects) + ['Average', 'Grade', 'Rank']
    writer.writerow(headers)
    
    student_data = []
    
    for student in students:
        row = [student.roll_number or 'N/A', f"{student.first_name} {student.last_name}"]
        
        subject_scores = []
        for subject in subjects:
            exam = exams.filter(subject__name=subject).first()
            if exam:
                result = ExamResult.objects.filter(exam=exam, student=student).first()
                if result:
                    percentage = result.percentage
                    row.append(f"{percentage:.1f}%")
                    subject_scores.append(percentage)
                else:
                    row.append('-')
            else:
                row.append('-')
        
        average = sum(subject_scores) / len(subject_scores) if subject_scores else 0
        
        if average >= 90:
            grade = 'A+'
        elif average >= 80:
            grade = 'A'
        elif average >= 70:
            grade = 'B+'
        elif average >= 60:
            grade = 'B'
        elif average >= 50:
            grade = 'C+'
        elif average >= 40:
            grade = 'C'
        elif average >= 33:
            grade = 'D'
        else:
            grade = 'F'
        
        row.extend([f"{average:.1f}%", grade, ''])
        student_data.append((average, row))
    
    student_data.sort(key=lambda x: x[0], reverse=True)
    
    for rank, (avg, row) in enumerate(student_data, 1):
        row[-1] = rank
        writer.writerow(row)
    
    return response


def generate_pdf_performance_report(class_obj, students, exams, report_type):
    """Generate PDF performance report"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph(f"<b>Performance Report - {class_obj.name}</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    report_info = Paragraph(f"Report Type: {report_type.title()}", styles['Normal'])
    elements.append(report_info)
    elements.append(Spacer(1, 20))
    
    subjects = exams.values_list('subject__name', flat=True).distinct()
    
    table_data = [['Roll No', 'Student Name'] + list(subjects) + ['Avg', 'Grade']]
    
    for student in students:
        row = [student.roll_number or 'N/A', f"{student.first_name} {student.last_name}"[:20]]
        
        subject_scores = []
        for subject in subjects:
            exam = exams.filter(subject__name=subject).first()
            if exam:
                result = ExamResult.objects.filter(exam=exam, student=student).first()
                if result:
                    percentage = result.percentage
                    row.append(f"{percentage:.0f}%")
                    subject_scores.append(percentage)
                else:
                    row.append('-')
            else:
                row.append('-')
        
        average = sum(subject_scores) / len(subject_scores) if subject_scores else 0
        
        if average >= 90:
            grade = 'A+'
        elif average >= 80:
            grade = 'A'
        elif average >= 70:
            grade = 'B+'
        elif average >= 60:
            grade = 'B'
        elif average >= 50:
            grade = 'C+'
        elif average >= 40:
            grade = 'C'
        elif average >= 33:
            grade = 'D'
        else:
            grade = 'F'
        
        row.extend([f"{average:.0f}%", grade])
        table_data.append(row)
    
    performance_table = Table(table_data)
    performance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
    ]))
    
    elements.append(performance_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="performance_report_{class_obj.name}_{report_type}.pdf"'
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_today_classes(request):
    """Get today's classes for teacher"""
    if request.user.role != 'teacher' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Teacher access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        today = timezone.now().strftime('%A')
        
        entries = TimetableEntry.objects.filter(
            teacher=request.user,
            day_of_week=today.lower()
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
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)