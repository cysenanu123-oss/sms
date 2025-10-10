# apps/dashboard/reports_views.py - CREATE THIS FILE
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Avg, Count, Sum
import csv
from datetime import datetime, timedelta
from apps.academics.models import Class
from apps.admissions.models import Student
from apps.attendance.models import Attendance, AttendanceRecord
from apps.grades.models import Grade
from apps.finance.models import StudentFee, Payment


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_academic_report(request):
    """Download academic performance report for a specific class"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=403)
    
    class_id = request.GET.get('class_id')
    report_format = request.GET.get('format', 'csv')
    
    if not class_id:
        return Response({'success': False, 'error': 'Class ID required'}, status=400)
    
    try:
        class_obj = Class.objects.get(id=class_id)
        students = Student.objects.filter(current_class=class_obj, status='active')
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="academic_report_{class_obj.name}_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Student ID', 'Student Name', 'Class', 
            'Average Score', 'Grade', 'Total Exams', 
            'Attendance Rate', 'Rank', 'Status'
        ])
        
        # Get performance data for each student
        student_data = []
        for student in students:
            grades = Grade.objects.filter(student=student, class_obj=class_obj)
            
            avg_score = grades.aggregate(Avg('score'))['score__avg'] or 0
            total_exams = grades.count()
            
            # Calculate attendance rate
            total_attendance = AttendanceRecord.objects.filter(student=student).count()
            present_count = AttendanceRecord.objects.filter(
                student=student, 
                status__in=['present', 'late']
            ).count()
            attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0
            
            # Calculate grade
            if avg_score >= 90:
                grade = 'A+'
            elif avg_score >= 80:
                grade = 'A'
            elif avg_score >= 70:
                grade = 'B+'
            elif avg_score >= 60:
                grade = 'B'
            elif avg_score >= 50:
                grade = 'C'
            else:
                grade = 'F'
            
            student_data.append({
                'student': student,
                'avg_score': avg_score,
                'grade': grade,
                'total_exams': total_exams,
                'attendance_rate': round(attendance_rate, 2)
            })
        
        # Sort by average score for ranking
        student_data.sort(key=lambda x: x['avg_score'], reverse=True)
        
        # Write data
        for rank, data in enumerate(student_data, 1):
            student = data['student']
            writer.writerow([
                student.student_id,
                f"{student.first_name} {student.last_name}",
                class_obj.name,
                round(data['avg_score'], 2),
                data['grade'],
                data['total_exams'],
                f"{data['attendance_rate']}%",
                rank,
                'Excellent' if data['avg_score'] >= 80 else 'Good' if data['avg_score'] >= 60 else 'Needs Improvement'
            ])
        
        return response
        
    except Class.DoesNotExist:
        return Response({'success': False, 'error': 'Class not found'}, status=404)
    except Exception as e:
        print(f"Error generating report: {str(e)}")
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_attendance_report(request):
    """Download attendance report (weekly/monthly)"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=403)
    
    class_id = request.GET.get('class_id')
    period = request.GET.get('period', 'weekly')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not class_id:
        return Response({'success': False, 'error': 'Class ID required'}, status=400)
    
    try:
        class_obj = Class.objects.get(id=class_id)
        
        # Calculate date range if not provided
        if not start_date or not end_date:
            end_date = datetime.now().date()
            if period == 'weekly':
                start_date = end_date - timedelta(days=7)
            else:
                start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        students = Student.objects.filter(current_class=class_obj, status='active')
        
        # Create CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_report_{class_obj.name}_{start_date}_to_{end_date}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Student ID', 'Student Name', 'Total Days', 
            'Present', 'Absent', 'Late', 'Excused', 
            'Attendance Rate', 'Status'
        ])
        
        for student in students:
            # Get attendance records in date range
            records = AttendanceRecord.objects.filter(
                student=student,
                attendance__date__range=[start_date, end_date]
            )
            
            total_days = records.count()
            present = records.filter(status='present').count()
            absent = records.filter(status='absent').count()
            late = records.filter(status='late').count()
            excused = records.filter(status='excused').count()
            
            attendance_rate = ((present + late) / total_days * 100) if total_days > 0 else 0
            
            status = 'Excellent' if attendance_rate >= 95 else 'Good' if attendance_rate >= 85 else 'Poor'
            
            writer.writerow([
                student.student_id,
                f"{student.first_name} {student.last_name}",
                total_days,
                present,
                absent,
                late,
                excused,
                f"{round(attendance_rate, 2)}%",
                status
            ])
        
        return response
        
    except Class.DoesNotExist:
        return Response({'success': False, 'error': 'Class not found'}, status=404)
    except Exception as e:
        print(f"Error generating attendance report: {str(e)}")
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_financial_report(request):
    """Download financial report showing fee payments"""
    if request.user.role not in ['admin', 'super_admin'] and not request.user.is_superuser:
        return Response({'success': False, 'error': 'Admin access required'}, status=403)
    
    class_id = request.GET.get('class_id')
    status_filter = request.GET.get('status', 'all')
    
    try:
        # Filter students
        if class_id:
            class_obj = Class.objects.get(id=class_id)
            students = Student.objects.filter(current_class=class_obj, status='active')
            filename = f'financial_report_{class_obj.name}_{datetime.now().strftime("%Y%m%d")}.csv'
        else:
            students = Student.objects.filter(status='active')
            filename = f'financial_report_all_classes_{datetime.now().strftime("%Y%m%d")}.csv'
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Student ID', 'Student Name', 'Class', 
            'Total Fees', 'Amount Paid', 'Balance', 
            'Payment Status', 'Due Date', 'Last Payment Date',
            'Last Receipt Number', 'Payment Method'
        ])
        
        for student in students:
            # Get current term fees
            student_fees = StudentFee.objects.filter(student=student).order_by('-created_at')
            
            for fee in student_fees:
                # Apply status filter
                if status_filter != 'all' and fee.status != status_filter:
                    continue
                
                # Get last payment
                last_payment = Payment.objects.filter(
                    student_fee=fee, 
                    status='completed'
                ).order_by('-payment_date').first()
                
                writer.writerow([
                    student.student_id,
                    f"{student.first_name} {student.last_name}",
                    student.current_class.name if student.current_class else 'N/A',
                    float(fee.total_amount),
                    float(fee.amount_paid),
                    float(fee.balance),
                    fee.get_status_display(),
                    fee.due_date.strftime('%Y-%m-%d'),
                    last_payment.payment_date.strftime('%Y-%m-%d') if last_payment else 'N/A',
                    last_payment.receipt_number if last_payment else 'N/A',
                    last_payment.get_payment_method_display() if last_payment else 'N/A'
                ])
        
        return response
        
    except Class.DoesNotExist:
        return Response({'success': False, 'error': 'Class not found'}, status=404)
    except Exception as e:
        print(f"Error generating financial report: {str(e)}")
        return Response({'success': False, 'error': str(e)}, status=500)