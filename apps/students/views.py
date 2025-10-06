# apps/students/views.py - NEW FILE FOR STUDENT DASHBOARD APIs
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Avg, Count, Q
from apps.admissions.models import Student
from apps.academics.models import ClassSubject, Timetable, TimetableEntry
from apps.attendance.models import AttendanceRecord
from apps.grades.models import Grade


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_dashboard(request):
    """Get student dashboard data with real information"""
    
    if request.user.role != 'student' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Student access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get student profile
        student = Student.objects.select_related(
            'current_class', 'user'
        ).get(user=request.user)
        
        # Get parent information
        parent = student.parents.first()
        
        # Student Info
        student_info = {
            'student_id': student.student_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'other_names': student.other_names or '',
            'full_name': f"{student.first_name} {student.other_names} {student.last_name}".strip(),
            'email': student.user.email,
            'phone': student.user.phone or 'Not provided',
            'class': student.current_class.name if student.current_class else 'Not Assigned',
            'academic_year': student.academic_year,
            'roll_number': student.roll_number or 'Not assigned',
            'admission_date': student.admission_date.isoformat() if student.admission_date else None,
            'blood_group': student.blood_group or 'Not specified',
            'parent_name': parent.full_name if parent else 'Not available',
            'parent_phone': parent.phone if parent else 'Not available',
            'parent_email': parent.email if parent else 'Not available',
        }
        
        # Get courses/subjects for this student's class
        courses = []
        if student.current_class:
            class_subjects = ClassSubject.objects.filter(
                class_obj=student.current_class,
                is_active=True
            ).select_related('subject', 'teacher')
            
            for cs in class_subjects:
                # Get grades for this subject
                grades = Grade.objects.filter(
                    student=student,
                    subject=cs.subject
                ).values_list('score', flat=True)
                
                average_grade = sum(grades) / len(grades) if grades else None
                
                courses.append({
                    'id': cs.id,
                    'name': cs.subject.name,
                    'code': cs.subject.code,
                    'teacher': cs.teacher.get_full_name() if cs.teacher else 'TBA',
                    'teacher_email': cs.teacher.email if cs.teacher else '',
                    'credits': 3.0,  # Can add this to Subject model later
                    'average_grade': round(average_grade, 1) if average_grade else 'N/A'
                })
        
        # Calculate attendance rate
        total_attendance = AttendanceRecord.objects.filter(student=student).count()
        present = AttendanceRecord.objects.filter(
            student=student, 
            status='present'
        ).count()
        attendance_rate = round((present / total_attendance * 100), 1) if total_attendance > 0 else 0
        
        # Calculate average grade across all subjects
        all_grades = Grade.objects.filter(student=student).values_list('score', flat=True)
        average_grade = round(sum(all_grades) / len(all_grades), 1) if all_grades else 'N/A'
        
        # Get pending assignments
        # You'll need to create an Assignment model, but for now:
        pending_assignments = 0  # TODO: Implement Assignment model
        
        # Statistics
        stats = {
            'total_courses': len(courses),
            'average_grade': average_grade,
            'attendance_rate': attendance_rate,
            'pending_assignments': pending_assignments
        }
        
        # Get timetable
        timetable = get_student_timetable(student)
        
        return Response({
            'success': True,
            'data': {
                'student_info': student_info,
                'courses': courses,
                'stats': stats,
                'timetable': timetable
            }
        })
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Error loading dashboard: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_student_timetable(student):
    """Get timetable for student's class"""
    if not student.current_class:
        return {'days': [], 'periods': []}
    
    try:
        # Get active timetable for the class
        timetable = Timetable.objects.filter(
            class_obj=student.current_class,
            is_active=True
        ).first()
        
        if not timetable:
            return {'days': [], 'periods': []}
        
        # Get all entries
        entries = TimetableEntry.objects.filter(
            timetable=timetable
        ).select_related('subject', 'teacher', 'time_slot').order_by(
            'time_slot__start_time', 'day_of_week'
        )
        
        # Build timetable structure
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        time_slots = timetable.time_slots.all().order_by('start_time')
        
        periods = []
        for slot in time_slots:
            period_data = {
                'time': f"{slot.start_time.strftime('%I:%M %p')} - {slot.end_time.strftime('%I:%M %p')}",
                'slot_id': slot.id
            }
            
            for day in days:
                entry = entries.filter(
                    time_slot=slot,
                    day_of_week=day
                ).first()
                
                if entry:
                    period_data[day] = {
                        'type': 'class',
                        'subject': entry.subject.name,
                        'teacher': entry.teacher.get_full_name() if entry.teacher else 'TBA',
                        'room': entry.room_number or 'TBA'
                    }
                elif slot.is_break:
                    period_data[day] = {
                        'type': 'break',
                        'subject': 'Break'
                    }
                else:
                    period_data[day] = None
            
            periods.append(period_data)
        
        return {
            'days': days,
            'periods': periods
        }
        
    except Exception as e:
        print(f"Error loading timetable: {e}")
        return {'days': [], 'periods': []}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_course_details(request, course_id):
    """Get detailed information about a specific course"""
    
    if request.user.role != 'student' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Student access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        student = Student.objects.get(user=request.user)
        
        class_subject = ClassSubject.objects.select_related(
            'subject', 'teacher'
        ).get(id=course_id, class_obj=student.current_class)
        
        # Get all grades for this subject
        grades = Grade.objects.filter(
            student=student,
            subject=class_subject.subject
        ).order_by('-date_recorded')
        
        grade_breakdown = []
        for grade in grades:
            grade_breakdown.append({
                'assessment_type': grade.assessment_type,
                'score': grade.score,
                'max_score': grade.max_score,
                'date': grade.date_recorded.isoformat(),
                'remarks': grade.remarks or ''
            })
        
        # Calculate overall grade
        total_score = sum([g.score for g in grades])
        total_possible = sum([g.max_score for g in grades])
        overall_percentage = round((total_score / total_possible * 100), 1) if total_possible > 0 else 0
        
        course_data = {
            'name': class_subject.subject.name,
            'code': class_subject.subject.code,
            'teacher': class_subject.teacher.get_full_name() if class_subject.teacher else 'TBA',
            'teacher_email': class_subject.teacher.email if class_subject.teacher else '',
            'description': class_subject.subject.description or 'No description available',
            'credits': 3.0,
            'grade_breakdown': grade_breakdown,
            'overall_grade': overall_percentage,
            'letter_grade': calculate_letter_grade(overall_percentage)
        }
        
        return Response({
            'success': True,
            'data': course_data
        })
        
    except ClassSubject.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Course not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def calculate_letter_grade(percentage):
    """Convert percentage to letter grade"""
    if percentage >= 90:
        return 'A'
    elif percentage >= 80:
        return 'B+'
    elif percentage >= 70:
        return 'B'
    elif percentage >= 60:
        return 'C'
    elif percentage >= 50:
        return 'D'
    else:
        return 'F'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_test_results(request):
    """Get recent test results for student"""
    
    if request.user.role != 'student' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Student access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        student = Student.objects.get(user=request.user)
        
        # Get recent grades
        recent_grades = Grade.objects.filter(
            student=student
        ).select_related('subject').order_by('-date_recorded')[:10]
        
        results = []
        for grade in recent_grades:
            percentage = (grade.score / grade.max_score * 100) if grade.max_score > 0 else 0
            
            results.append({
                'subject': grade.subject.name,
                'test_name': grade.assessment_type,
                'date': grade.date_recorded.isoformat(),
                'score': f"{grade.score}/{grade.max_score}",
                'percentage': round(percentage, 1),
                'grade': calculate_letter_grade(percentage),
                'status': 'published' if grade.is_published else 'pending'
            })
        
        return Response({
            'success': True,
            'data': results
        })
        
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student profile not found'
        }, status=status.HTTP_404_NOT_FOUND)