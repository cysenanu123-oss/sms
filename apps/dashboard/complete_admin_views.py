# apps/dashboard/complete_admin_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Sum, Q
from django.db import transaction

from apps.accounts.models import User
from apps.admissions.models import Student, StudentApplication, Parent
from apps.academics.models import Class, Subject, ClassSubject, TeacherClassAssignment, SchoolSettings
from apps.finance.models import FeeStructure, StudentFee, Payment
from apps.attendance.models import Attendance, AttendanceRecord


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_students_list(request):
    """Get all students with filters"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    class_filter = request.GET.get('class_id')
    status_filter = request.GET.get('status', 'active')
    search = request.GET.get('search', '')
    
    students = Student.objects.all()
    
    if class_filter:
        students = students.filter(current_class_id=class_filter)
    if status_filter:
        students = students.filter(status=status_filter)
    if search:
        students = students.filter(
            Q(student_id__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    students = students.select_related('current_class', 'user').order_by('roll_number')
    
    students_data = []
    for student in students:
        # Get parent info
        parent = Parent.objects.filter(children=student).first()
        
        # Calculate attendance (last 30 days)
        total_attendance = AttendanceRecord.objects.filter(student=student).count()
        present = AttendanceRecord.objects.filter(student=student, status='present').count()
        attendance_rate = (present / total_attendance * 100) if total_attendance > 0 else 0
        
        students_data.append({
            'id': student.id,
            'student_id': student.student_id,
            'name': f"{student.first_name} {student.last_name}",
            'email': student.user.email if student.user else '',
            'class': student.current_class.name if student.current_class else 'Not Assigned',
            'class_id': student.current_class.id if student.current_class else None,
            'roll_number': student.roll_number or 'N/A',
            'parent_name': parent.full_name if parent else 'N/A',
            'parent_contact': parent.phone if parent else 'N/A',
            'attendance_rate': round(attendance_rate, 1),
            'average_grade': 87.3,  # TODO: Calculate from grades
            'status': student.status,
            'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else '',
            'blood_group': student.blood_group or 'Not specified',
            'allergies': student.health_notes or 'None',
            'address': student.residential_address or '',
        })
    
    return Response({
        'success': True,
        'data': students_data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_details(request, student_id):
    """Get detailed student information"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        student = Student.objects.select_related('current_class', 'user').get(id=student_id)
        parent = Parent.objects.filter(children=student).first()
        
        # Get fee info
        fees = StudentFee.objects.filter(student=student)
        total_fees = sum([fee.total_amount for fee in fees])
        paid = sum([fee.amount_paid for fee in fees])
        balance = total_fees - paid
        
        student_data = {
            'id': student.id,
            'student_id': student.student_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'name': f"{student.first_name} {student.last_name}",
            'email': student.user.email if student.user else '',
            'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else '',
            'gender': student.sex,
            'blood_group': student.blood_group or '',
            'address': student.residential_address or '',
            'allergies': student.health_notes or '',
            'class': student.current_class.name if student.current_class else '',
            'roll_number': student.roll_number or '',
            'admission_date': student.admission_date.isoformat(),
            'academic_year': student.academic_year,
            'status': student.status,
            'parent_name': parent.full_name if parent else '',
            'parent_contact': parent.phone if parent else '',
            'attendance_rate': 95.5,  # Calculate actual
            'average_grade': 87.3,  # Calculate actual
            'financial': {
                'total_fees': float(total_fees),
                'amount_paid': float(paid),
                'balance': float(balance)
            }
        }
        
        return Response({
            'success': True,
            'data': student_data
        })
        
    except Student.DoesNotExist:
        return Response({'success': False, 'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
def get_classes_list(request):
    """Get all classes with details"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    classes = Class.objects.filter(is_active=True).order_by('name')
    
    classes_data = []
    for cls in classes:
        # Get class teacher
        class_teacher_assignment = TeacherClassAssignment.objects.filter(
            class_obj=cls,
            is_class_teacher=True,
            is_active=True
        ).select_related('teacher').first()
        
        # Get students count
        students_count = Student.objects.filter(current_class=cls, status='active').count()
        
        # Calculate attendance
        attendance_records = AttendanceRecord.objects.filter(
            attendance__class_obj=cls
        )
        total = attendance_records.count()
        present = attendance_records.filter(status='present').count()
        avg_attendance = (present / total * 100) if total > 0 else 0
        
        classes_data.append({
            'id': cls.id,
            'name': cls.name,
            'academic_year': cls.academic_year,
            'capacity': cls.capacity,
            'enrolled': students_count,
            'available': cls.capacity - students_count,
            'class_teacher': class_teacher_assignment.teacher.get_full_name() if class_teacher_assignment else 'Not Assigned',
            'class_teacher_id': class_teacher_assignment.teacher.id if class_teacher_assignment else None,
            'avg_attendance': round(avg_attendance, 1),
            'is_active': cls.is_active
        })
    
    return Response({
        'success': True,
        'data': classes_data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_class(request):
    """Create a new class"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    name = request.data.get('name')
    capacity = request.data.get('capacity', 50)
    academic_year = request.data.get('academic_year')
    
    if not all([name, academic_year]):
        return Response({'success': False, 'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        cls = Class.objects.create(
            name=name,
            capacity=capacity,
            academic_year=academic_year,
            is_active=True
        )
        
        return Response({
            'success': True,
            'message': 'Class created successfully',
            'data': {
                'id': cls.id,
                'name': cls.name
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_finance_overview(request):
    """Get financial overview"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    # Total fees
    all_fees = StudentFee.objects.all()
    total_expected = sum([fee.total_amount - fee.discount_amount for fee in all_fees])
    total_collected = sum([fee.amount_paid for fee in all_fees])
    pending = total_expected - total_collected
    
    # This month collection
    from datetime import datetime
    this_month = datetime.now().month
    this_year = datetime.now().year
    
    month_payments = Payment.objects.filter(
        payment_date__month=this_month,
        payment_date__year=this_year,
        status='completed'
    )
    monthly_collection = sum([p.amount for p in month_payments])
    
    # Students with pending fees
    pending_students = StudentFee.objects.filter(
        status__in=['pending', 'partial', 'overdue']
    ).count()
    
    # Overdue fees
    overdue_fees = StudentFee.objects.filter(status='overdue')
    overdue_amount = sum([fee.balance for fee in overdue_fees])
    
    collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
    
    return Response({
        'success': True,
        'data': {
            'total_revenue': float(total_collected),
            'pending_fees': float(pending),
            'monthly_collection': float(monthly_collection),
            'overdue_amount': float(overdue_amount),
            'collection_rate': round(collection_rate, 1),
            'students_with_pending': pending_students
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_fee_students(request):
    """Get students with pending fees"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    pending_fees = StudentFee.objects.filter(
        status__in=['pending', 'partial', 'overdue']
    ).select_related('student', 'student__current_class')
    
    students_data = []
    for fee in pending_fees:
        students_data.append({
            'student_id': fee.student.student_id,
            'name': f"{fee.student.first_name} {fee.student.last_name}",
            'class': fee.student.current_class.name if fee.student.current_class else 'N/A',
            'total_amount': float(fee.total_amount),
            'paid': float(fee.amount_paid),
            'balance': float(fee.balance),
            'due_date': fee.due_date.isoformat(),
            'status': fee.status,
            'is_overdue': fee.is_overdue
        })
    
    return Response({
        'success': True,
        'data': students_data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_payment(request):
    """Record a payment"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    student_id = request.data.get('student_id')
    amount = request.data.get('amount')
    payment_method = request.data.get('payment_method', 'cash')
    reference = request.data.get('reference', '')
    
    if not all([student_id, amount]):
        return Response({'success': False, 'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        student = Student.objects.get(student_id=student_id)
        
        # Get pending fee
        pending_fee = StudentFee.objects.filter(
            student=student,
            status__in=['pending', 'partial', 'overdue']
        ).first()
        
        if not pending_fee:
            return Response({'success': False, 'error': 'No pending fees for this student'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create payment
        payment = Payment.objects.create(
            student_fee=pending_fee,
            amount=amount,
            payment_method=payment_method,
            reference_number=reference,
            processed_by=request.user,
            status='completed'
        )
        
        return Response({
            'success': True,
            'message': 'Payment recorded successfully',
            'data': {
                'receipt_number': payment.receipt_number,
                'amount': float(payment.amount),
                'balance': float(pending_fee.balance)
            }
        }, status=status.HTTP_201_CREATED)
        
    except Student.DoesNotExist:
        return Response({'success': False, 'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manage_school_settings(request):
    """Get or update school settings"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        settings = SchoolSettings.objects.first()
        
        if not settings:
            return Response({
                'success': True,
                'data': {
                    'school_name': 'Excellence Academy',
                    'current_academic_year': '2024-2025',
                    'current_term': 'first',
                    'grading_system': 'percentage'
                }
            })
        
        return Response({
            'success': True,
            'data': {
                'school_name': settings.school_name,
                'school_email': settings.contact_email or '',
                'school_phone': settings.contact_phone or '',
                'school_address': settings.address or '',
                'current_academic_year': settings.current_academic_year,
                'current_term': settings.current_term,
                'grading_system': settings.grading_system or 'percentage'
            }
        })
    
    elif request.method == 'POST':
        settings, created = SchoolSettings.objects.get_or_create(id=1)
        
        settings.school_name = request.data.get('school_name', settings.school_name)
        settings.contact_email = request.data.get('school_email', settings.contact_email)
        settings.contact_phone = request.data.get('school_phone', settings.contact_phone)
        settings.address = request.data.get('school_address', settings.address)
        settings.current_academic_year = request.data.get('current_academic_year', settings.current_academic_year)
        settings.current_term = request.data.get('current_term', settings.current_term)
        settings.grading_system = request.data.get('grading_system', 'percentage')
        
        settings.save()
        
        return Response({
            'success': True,
            'message': 'Settings updated successfully'
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teacher_performance_report(request):
    """Get teacher performance overview"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    teachers = User.objects.filter(role='teacher', is_active=True)
    
    teachers_data = []
    for teacher in teachers:
        # Get assigned classes
        assignments = TeacherClassAssignment.objects.filter(
            teacher=teacher,
            is_active=True
        ).count()
        
        # Check attendance marking
        attendances_marked = Attendance.objects.filter(marked_by=teacher).count()
        
        teachers_data.append({
            'id': teacher.id,
            'name': teacher.get_full_name(),
            'email': teacher.email,
            'classes_assigned': assignments,
            'attendances_marked': attendances_marked,
            'performance_score': 4.5  # TODO: Calculate actual score
        })
    
    return Response({
        'success': True,
        'data': teachers_data
    })