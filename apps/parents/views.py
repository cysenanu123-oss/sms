# apps/parents/views.py - FIXED VERSION
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from apps.admissions.models import Parent, Student
from apps.grades.models import Grade
from django.db.models import Avg, Count, Q
from datetime import datetime, timedelta
from django.utils import timezone


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_dashboard_data(request):
    """Get parent dashboard with all linked children data"""
    if request.user.role != 'parent' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Parent access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        parent = Parent.objects.get(user=request.user)
    except Parent.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Parent profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get all children
    children = parent.children.all()
    
    children_data = []
    for child in children:
        # Calculate attendance
        from apps.attendance.models import AttendanceRecord
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        attendance_records = AttendanceRecord.objects.filter(
            student=child,
            attendance__date__gte=thirty_days_ago
        )
        
        total_days = attendance_records.count()
        present_days = attendance_records.filter(status='present').count()
        attendance_rate = (present_days / total_days * 100) if total_days > 0 else 0
        
        # Calculate grades - FIXED
        grades = Grade.objects.filter(student=child)
        if grades.exists():
            avg_percentage = 0
            total_score = 0
            total_marks = 0
            
            for grade in grades:
                total_score += grade.score
                total_marks += grade.total_marks
            
            avg_percentage = (total_score / total_marks * 100) if total_marks > 0 else 0
            
            # Determine letter grade
            if avg_percentage >= 90:
                overall_grade = 'A+'
            elif avg_percentage >= 80:
                overall_grade = 'A'
            elif avg_percentage >= 70:
                overall_grade = 'B+'
            elif avg_percentage >= 60:
                overall_grade = 'B'
            elif avg_percentage >= 50:
                overall_grade = 'C+'
            elif avg_percentage >= 40:
                overall_grade = 'C'
            elif avg_percentage >= 33:
                overall_grade = 'D'
            else:
                overall_grade = 'F'
        else:
            avg_percentage = 0
            overall_grade = 'N/A'
        
        # Pending fees
        pending_fees = 0
        
        # Class rank
        class_rank = 0
        total_students = 0
        if child.current_class:
            from django.db.models import Sum
            class_students = Student.objects.filter(
                current_class=child.current_class,
                status='active'
            )
            
            # Calculate average for each student
            student_averages = []
            for student in class_students:
                student_grades = Grade.objects.filter(student=student)
                if student_grades.exists():
                    total_s = sum(g.score for g in student_grades)
                    total_m = sum(g.total_marks for g in student_grades)
                    avg = (total_s / total_m * 100) if total_m > 0 else 0
                    student_averages.append({'id': student.id, 'avg': avg})
            
            # Sort and find rank
            student_averages.sort(key=lambda x: x['avg'], reverse=True)
            total_students = len(student_averages)
            
            for idx, sa in enumerate(student_averages, 1):
                if sa['id'] == child.id:
                    class_rank = idx
                    break
        
        child_data = {
            'id': child.id,
            'student_id': child.student_id,
            'name': f"{child.first_name} {child.last_name}",
            'class': child.current_class.name if child.current_class else 'Not Assigned',
            'class_id': child.current_class.id if child.current_class else None,
            'academic_year': child.academic_year,
            'status': child.status,
            'admission_date': child.admission_date.isoformat() if child.admission_date else None,
            'attendance_rate': round(attendance_rate, 1),
            'overall_grade': overall_grade,
            'average_percentage': round(avg_percentage, 1),
            'pending_fees': pending_fees,
            'class_rank': class_rank,
            'total_students': total_students,
        }
        children_data.append(child_data)
    
    parent_info = {
        'full_name': parent.full_name,
        'email': parent.email,
        'phone': parent.phone,
        'relationship': parent.relationship,
        'total_children': len(children_data),
    }
    
    return Response({
        'success': True,
        'data': {
            'parent_info': parent_info,
            'children': children_data,
        }
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_child_details(request, student_id):
    """
    Get detailed information about a specific child including:
    - Roll number
    - Class teacher
    - Blood group
    - Recent test results
    - Courses/subjects
    - Timetable
    """
    if request.user.role != 'parent' and not request.user.is_superuser:
        return Response({
            'success': False,
            'error': 'Parent access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        parent = Parent.objects.get(user=request.user)
        child = Student.objects.get(id=student_id)
        
        # Verify this child belongs to this parent
        if child not in parent.children.all():
            return Response({
                'success': False,
                'error': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        current_class = child.current_class
        
        # Get class teacher
        class_teacher = "Not Assigned"
        if current_class:
            class_teacher_assignment = TeacherClassAssignment.objects.filter(
                class_obj=current_class,
                is_class_teacher=True,
                is_active=True
            ).select_related('teacher').first()
            
            if class_teacher_assignment:
                teacher = class_teacher_assignment.teacher
                class_teacher = f"{teacher.first_name} {teacher.last_name}"
        
        # Get courses/subjects
        class_subjects = ClassSubject.objects.filter(
            class_obj=current_class
        ).select_related('subject', 'teacher')
        
        courses = []
        teachers_list = []
        
        for cs in class_subjects:
            course_data = {
                'id': cs.id,
                'subject': cs.subject.name,
                'code': cs.subject.code,
                'teacher': cs.teacher.get_full_name() if cs.teacher else 'TBA',
            }
            courses.append(course_data)
            
            # Add to teachers list (for contact)
            if cs.teacher:
                teachers_list.append({
                    'id': cs.teacher.id,
                    'name': cs.teacher.get_full_name(),
                    'subject': cs.subject.name,
                    'email': cs.teacher.email
                })
        
        # Get recent test results
        recent_results = Grade.objects.filter(
            student=child
        ).select_related('subject').order_by('-exam_date')[:10]
        
        results_data = []
        for result in recent_results:
            results_data.append({
                'id': result.id,
                'subject': result.subject.name if result.subject else 'N/A',
                'test_name': result.exam_name,
                'date': result.exam_date.strftime('%b %d, %Y'),
                'score': result.score,
                'total': result.total_marks,
                'percentage': round((result.score / result.total_marks * 100), 1),
                'grade': result.grade
            })
        
        # Get timetable
        from apps.students.views import get_student_timetable_helper
        timetable_data = get_student_timetable_helper(current_class)
        
        # Get attendance calendar (last 30 days)
        from apps.attendance.models import AttendanceRecord
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        attendance_records = AttendanceRecord.objects.filter(
            student=child,
            attendance__date__gte=thirty_days_ago
        ).select_related('attendance').order_by('attendance__date')
        
        attendance_calendar = []
        for record in attendance_records:
            attendance_calendar.append({
                'date': record.attendance.date.isoformat(),
                'day': record.attendance.date.day,
                'status': record.status  # present, absent, late
            })
        
        child_data = {
            'student_id': child.student_id,
            'name': f"{child.first_name} {child.last_name}",
            'class': current_class.name if current_class else 'Not Assigned',
            'roll_number': child.roll_number or 'Not Assigned',
            'class_teacher': class_teacher,
            'blood_group': child.blood_group or 'Not Specified',
            'courses': courses,
            'recent_results': results_data,
            'timetable': timetable_data,
            'attendance_calendar': attendance_calendar,
            'teachers': teachers_list
        }
        
        return Response({
            'success': True,
            'data': child_data
        })
        
    except Parent.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Parent profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Student.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Student not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)