# apps/parents/views.py - UPDATED WITH FINANCE INTEGRATION
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from apps.admissions.models import Parent, Student
from apps.grades.models import Grade
from apps.finance.models import StudentFee, Payment
from django.db.models import Avg, Count, Q, Sum
from datetime import datetime, timedelta
from django.utils import timezone
from apps.academics.models import TeacherClassAssignment, ClassSubject, Timetable, TimetableEntry


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_dashboard_data(request):
    """Get parent dashboard with all linked children data INCLUDING FEES"""
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
        
        # Calculate grades
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
        
        # ====== CALCULATE PENDING FEES ======
        student_fees = StudentFee.objects.filter(
            student=child,
            status__in=['pending', 'partial', 'overdue']
        )
        pending_fees = sum([fee.balance for fee in student_fees])
        
        # Class rank
        class_rank = 0
        total_students = 0
        if child.current_class:
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
            'pending_fees': float(pending_fees),  # NOW SHOWING REAL DATA
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
    Get detailed information about a specific child including FEES
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
        
        # Remove duplicates from teachers list
        unique_teachers = []
        seen_ids = set()
        for teacher in teachers_list:
            if teacher['id'] not in seen_ids:
                unique_teachers.append(teacher)
                seen_ids.add(teacher['id'])
        teachers_list = unique_teachers
        
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
                'percentage': round((result.score / result.total_marks * 100), 1) if result.total_marks > 0 else 0,
                'grade': result.grade
            })
        
        # Get timetable
        timetable_data = get_timetable_for_class(current_class)
        
        # Get attendance calendar (last 30 days)
        from apps.attendance.models import AttendanceRecord
        
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
                'status': record.status
            })
        
        # ====== GET DETAILED FEE INFORMATION ======
        student_fees = StudentFee.objects.filter(
            student=child
        ).select_related('fee_structure').order_by('-due_date')
        
        fees_data = []
        total_fees = 0
        total_paid = 0
        total_balance = 0
        
        for fee in student_fees:
            fee_info = {
                'id': fee.id,
                'term': fee.fee_structure.get_term_display(),
                'academic_year': fee.fee_structure.academic_year,
                'total_amount': float(fee.total_amount),
                'discount': float(fee.discount_amount),
                'amount_paid': float(fee.amount_paid),
                'balance': float(fee.balance),
                'status': fee.status,
                'due_date': fee.due_date.isoformat(),
                'is_overdue': fee.is_overdue,
                'breakdown': {
                    'tuition': float(fee.fee_structure.tuition_fee),
                    'admission': float(fee.fee_structure.admission_fee),
                    'examination': float(fee.fee_structure.examination_fee),
                    'library': float(fee.fee_structure.library_fee),
                    'sports': float(fee.fee_structure.sports_fee),
                    'laboratory': float(fee.fee_structure.laboratory_fee),
                    'uniform': float(fee.fee_structure.uniform_fee),
                    'transport': float(fee.fee_structure.transport_fee),
                    'miscellaneous': float(fee.fee_structure.miscellaneous_fee),
                }
            }
            fees_data.append(fee_info)
            
            total_fees += fee.total_amount
            total_paid += fee.amount_paid
            total_balance += fee.balance
        
        # Get payment history
        payments = Payment.objects.filter(
            student_fee__student=child,
            status='completed'
        ).select_related('student_fee').order_by('-payment_date')[:10]
        
        payment_history = []
        for payment in payments:
            payment_history.append({
                'id': payment.id,
                'receipt_number': payment.receipt_number,
                'amount': float(payment.amount),
                'payment_method': payment.get_payment_method_display(),
                'payment_date': payment.payment_date.strftime('%b %d, %Y'),
                'term': payment.student_fee.fee_structure.get_term_display(),
                'reference': payment.reference_number or payment.transaction_id,
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
            'teachers': teachers_list,
            # ====== FINANCE DATA ======
            'fees': fees_data,
            'fee_summary': {
                'total_fees': float(total_fees),
                'total_paid': float(total_paid),
                'total_balance': float(total_balance),
            },
            'payment_history': payment_history,
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


def get_timetable_for_class(class_obj):
    """Helper function to get timetable for a class"""
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
        
        day_lower = entry.day_of_week.lower()
        
        if entry.subject and entry.teacher:
            periods_dict[time_key][day_lower] = {
                'subject': entry.subject.name,
                'teacher': entry.teacher.get_full_name(),
                'room': entry.room_number or 'TBA',
                'type': 'class'
            }
        elif entry.time_slot.is_break:
            periods_dict[time_key][day_lower] = {
                'subject': 'Break',
                'teacher': '',
                'room': '',
                'type': 'break'
            }
    
    return {
        'periods': list(periods_dict.values()),
        'days': days
    }