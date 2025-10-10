# apps/dashboard/reports_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Avg, Count, Sum, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import io

from apps.admissions.models import Student, StudentApplication
from apps.academics.models import Class, Subject
from apps.attendance.models import Attendance, AttendanceRecord
from apps.finance.models import StudentFee, Payment, FeeStructure
from apps.accounts.models import User


def is_admin(user):
    """Check if user is admin"""
    return user.role in ['admin', 'super_admin'] or user.is_superuser


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_academic_report(request):
    """
    Download academic performance report as CSV
    Filters: class_id, academic_year, term
    """
    if not is_admin(request.user):
        return Response({'success': False, 'error': 'Admin access required'}, status=403)
    
    class_id = request.GET.get('class_id')
    academic_year = request.GET.get('academic_year', '2024-2025')
    
    if not class_id:
        return Response({'success': False, 'error': 'class_id is required'}, status=400)
    
    try:
        class_obj = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({'success': False, 'error': 'Class not found'}, status=404)
    
    # Get all students in the class
    students = Student.objects.filter(
        current_class=class_obj,
        status='active'
    ).select_related('user')
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'Student ID',
        'Student Name',
        'Class',
        'Gender',
        'Date of Birth',
        'Attendance Rate (%)',
        'Total Days Present',
        'Total Days Absent',
        'Academic Status'
    ])
    
    # Data rows
    for student in students:
        # Calculate attendance
        total_attendance = AttendanceRecord.objects.filter(student=student)
        present_count = total_attendance.filter(status='present').count()
        absent_count = total_attendance.filter(status='absent').count()
        total_days = total_attendance.count()
        
        attendance_rate = (present_count / total_days * 100) if total_days > 0 else 0
        
        writer.writerow([
            student.student_id,
            f"{student.first_name} {student.last_name}",
            class_obj.name,
            student.gender or 'N/A',
            student.date_of_birth.strftime('%Y-%m-%d') if student.date_of_birth else 'N/A',
            f"{attendance_rate:.2f}",
            present_count,
            absent_count,
            student.status.upper()
        ])
    
    # Prepare response
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="academic_report_{class_obj.name}_{academic_year}.csv"'
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_attendance_report(request):
    """
    Download attendance report as CSV
    Filters: class_id, start_date, end_date
    """
    if not is_admin(request.user):
        return Response({'success': False, 'error': 'Admin access required'}, status=403)
    
    class_id = request.GET.get('class_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not class_id:
        return Response({'success': False, 'error': 'class_id is required'}, status=400)
    
    try:
        class_obj = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({'success': False, 'error': 'Class not found'}, status=404)
    
    # Date filtering
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    else:
        start_date = timezone.now().date() - timedelta(days=30)
    
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    else:
        end_date = timezone.now().date()
    
    # Get attendance records
    attendance_sessions = Attendance.objects.filter(
        class_obj=class_obj,
        date__range=[start_date, end_date]
    ).order_by('date', 'period')
    
    # Get all students in class
    students = Student.objects.filter(
        current_class=class_obj,
        status='active'
    ).order_by('student_id')
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers - Dynamic dates
    dates = list(attendance_sessions.values_list('date', flat=True).distinct())
    headers = ['Student ID', 'Student Name'] + [date.strftime('%Y-%m-%d') for date in dates] + ['Total Present', 'Total Absent', 'Attendance %']
    writer.writerow(headers)
    
    # Data rows
    for student in students:
        row = [student.student_id, f"{student.first_name} {student.last_name}"]
        
        present_count = 0
        absent_count = 0
        
        for date in dates:
            attendance = Attendance.objects.filter(
                class_obj=class_obj,
                date=date
            ).first()
            
            if attendance:
                record = AttendanceRecord.objects.filter(
                    attendance=attendance,
                    student=student
                ).first()
                
                if record:
                    status = record.status[0].upper()  # P, A, L, E
                    row.append(status)
                    
                    if record.status == 'present':
                        present_count += 1
                    elif record.status == 'absent':
                        absent_count += 1
                else:
                    row.append('-')
            else:
                row.append('-')
        
        total_days = present_count + absent_count
        attendance_rate = (present_count / total_days * 100) if total_days > 0 else 0
        
        row.extend([present_count, absent_count, f"{attendance_rate:.2f}%"])
        writer.writerow(row)
    
    # Prepare response
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{class_obj.name}_{start_date}_to_{end_date}.csv"'
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_financial_report(request):
    """
    Download financial report as CSV
    Filters: academic_year, term, status (optional)
    """
    if not is_admin(request.user):
        return Response({'success': False, 'error': 'Admin access required'}, status=403)
    
    academic_year = request.GET.get('academic_year', '2024-2025')
    term = request.GET.get('term')  # optional
    status_filter = request.GET.get('status')  # pending, paid, partial, overdue
    
    # Get all student fees
    student_fees = StudentFee.objects.filter(
        fee_structure__academic_year=academic_year
    ).select_related('student', 'fee_structure', 'fee_structure__class_level')
    
    if term:
        student_fees = student_fees.filter(fee_structure__term=term)
    
    if status_filter:
        student_fees = student_fees.filter(status=status_filter)
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'Student ID',
        'Student Name',
        'Class',
        'Academic Year',
        'Term',
        'Total Amount (GHS)',
        'Discount (GHS)',
        'Amount Paid (GHS)',
        'Balance (GHS)',
        'Status',
        'Due Date',
        'Is Overdue'
    ])
    
    # Data rows
    total_expected = 0
    total_collected = 0
    total_pending = 0
    
    for fee in student_fees:
        total_expected += float(fee.total_amount)
        total_collected += float(fee.amount_paid)
        total_pending += float(fee.balance)
        
        writer.writerow([
            fee.student.student_id,
            f"{fee.student.first_name} {fee.student.last_name}",
            fee.fee_structure.class_level.name,
            fee.fee_structure.academic_year,
            fee.fee_structure.get_term_display(),
            f"{fee.total_amount:.2f}",
            f"{fee.discount_amount:.2f}",
            f"{fee.amount_paid:.2f}",
            f"{fee.balance:.2f}",
            fee.status.upper(),
            fee.due_date.strftime('%Y-%m-%d'),
            'YES' if fee.is_overdue else 'NO'
        ])
    
    # Summary row
    writer.writerow([])
    writer.writerow(['SUMMARY', '', '', '', '', '', '', '', '', '', ''])
    writer.writerow(['Total Expected', '', '', '', '', f"{total_expected:.2f}", '', '', '', '', ''])
    writer.writerow(['Total Collected', '', '', '', '', '', '', f"{total_collected:.2f}", '', '', ''])
    writer.writerow(['Total Pending', '', '', '', '', '', '', '', f"{total_pending:.2f}", '', ''])
    collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
    writer.writerow(['Collection Rate', '', '', '', '', '', '', '', f"{collection_rate:.2f}%", '', ''])
    
    # Prepare response
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    filename = f"financial_report_{academic_year}"
    if term:
        filename += f"_{term}"
    filename += ".csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_applications_report(request):
    """
    Download applications report as CSV
    Filters: status, academic_year, department
    """
    if not is_admin(request.user):
        return Response({'success': False, 'error': 'Admin access required'}, status=403)
    
    status_filter = request.GET.get('status')  # pending, accepted, rejected
    academic_year = request.GET.get('academic_year', '2024-2025')
    department = request.GET.get('department')
    
    applications = StudentApplication.objects.all().select_related('applying_for_class')
    
    if status_filter:
        applications = applications.filter(status=status_filter)
    
    if department:
        applications = applications.filter(department=department)
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'Application Number',
        'Student Name',
        'Date of Birth',
        'Gender',
        'Department',
        'Applying For Class',
        'Parent Name',
        'Parent Email',
        'Parent Phone',
        'Status',
        'Application Fee',
        'Payment Status',
        'Submitted Date',
        'Last Updated'
    ])
    
    # Data rows
    for app in applications:
        writer.writerow([
            app.application_number,
            app.learner_name,
            app.date_of_birth.strftime('%Y-%m-%d') if app.date_of_birth else 'N/A',
            app.gender or 'N/A',
            app.get_department_display(),
            app.applying_for_class.name if app.applying_for_class else 'N/A',
            app.parent_name,
            app.parent_email,
            app.parent_phone,
            app.status.upper(),
            f"{app.application_fee:.2f}" if app.application_fee else '0.00',
            app.payment_status.upper() if app.payment_status else 'PENDING',
            app.submitted_at.strftime('%Y-%m-%d %H:%M') if app.submitted_at else 'N/A',
            app.updated_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    # Prepare response
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="applications_report_{academic_year}.csv"'
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_students_list(request):
    """
    Download complete students list as CSV
    Filters: class_id, status
    """
    if not is_admin(request.user):
        return Response({'success': False, 'error': 'Admin access required'}, status=403)
    
    class_id = request.GET.get('class_id')
    status_filter = request.GET.get('status', 'active')
    
    students = Student.objects.filter(status=status_filter).select_related('current_class', 'user')
    
    if class_id:
        students = students.filter(current_class_id=class_id)
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'Student ID',
        'First Name',
        'Last Name',
        'Gender',
        'Date of Birth',
        'Class',
        'Email',
        'Phone',
        'Parent Name',
        'Parent Contact',
        'Address',
        'Admission Date',
        'Status'
    ])
    
    # Data rows
    for student in students:
        writer.writerow([
            student.student_id,
            student.first_name,
            student.last_name,
            student.gender or 'N/A',
            student.date_of_birth.strftime('%Y-%m-%d') if student.date_of_birth else 'N/A',
            student.current_class.name if student.current_class else 'N/A',
            student.user.email if student.user else 'N/A',
            student.phone or 'N/A',
            student.parent_name or 'N/A',
            student.parent_contact or 'N/A',
            student.address or 'N/A',
            student.admission_date.strftime('%Y-%m-%d') if student.admission_date else 'N/A',
            student.status.upper()
        ])
    
    # Prepare response
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="students_list_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    return response